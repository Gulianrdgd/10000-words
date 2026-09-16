"""Web Push review reminders.

A device subscribes with its IANA timezone and a reminder hour. A background
loop checks every few minutes and sends at most one reminder per device per
local day, only when that user has cards due and hasn't reviewed yet today.

VAPID keys are generated on first start into app/data/vapid_private.pem.
Set PUSH_CONTACT (a mailto: or https: URL) for push services that require it.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException
from py_vapid import Vapid01, b64urlencode
from pydantic import BaseModel, Field
from pywebpush import WebPushException, webpush
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import SessionLocal, get_db
from app.fsrs_engine import _as_utc
from app.models import Card, PushSubscription, Review

log = logging.getLogger(__name__)

router = APIRouter(prefix="/push", tags=["push"])

VAPID_KEY_PATH = Path(__file__).parent / "data" / "vapid_private.pem"
PUSH_CONTACT = os.environ.get("PUSH_CONTACT", "mailto:admin@localhost")
CHECK_INTERVAL_SECONDS = 300

_vapid: Vapid01 | None = None


def vapid() -> Vapid01:
    global _vapid
    if _vapid is None:
        if VAPID_KEY_PATH.exists():
            _vapid = Vapid01.from_file(str(VAPID_KEY_PATH))
        else:
            _vapid = Vapid01()
            _vapid.generate_keys()
            _vapid.save_key(str(VAPID_KEY_PATH))
    return _vapid


def public_key() -> str:
    raw = vapid().public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64urlencode(raw)


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys
    timezone: str = "UTC"
    reminder_hour: int = Field(default=18, ge=0, le=23)


class UnsubscribeRequest(BaseModel):
    endpoint: str


class PushStatus(BaseModel):
    subscribed: bool
    reminder_hour: int | None = None


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _send(sub: PushSubscription, payload: dict) -> bool:
    """Returns False when the push service says the subscription is gone."""
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=json.dumps(payload),
            vapid_private_key=vapid(),
            vapid_claims={"sub": PUSH_CONTACT},
            ttl=12 * 3600,
        )
        return True
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return False
        log.warning("push to %s failed: %s", sub.endpoint[:60], e)
        return True


def _due_count(db: Session, user_id: str) -> int:
    return (
        db.query(func.count(Card.id))
        .filter(Card.user_id == user_id, Card.introduced.is_(True), Card.due_date <= datetime.now(timezone.utc))
        .scalar()
        or 0
    )


def send_due_reminders() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for sub in db.query(PushSubscription).all():
            local_now = now.astimezone(_zone(sub.timezone))
            if local_now.hour < sub.reminder_hour or sub.last_sent_date == local_now.date():
                continue
            sub.last_sent_date = local_now.date()

            last_review = db.query(func.max(Review.timestamp)).filter(Review.user_id == sub.user_id).scalar()
            reviewed_today = (
                last_review is not None
                and _as_utc(last_review).astimezone(_zone(sub.timezone)).date() == local_now.date()
            )
            due = _due_count(db, sub.user_id)
            if reviewed_today or due == 0:
                continue
            payload = {
                "title": "Time for your French review",
                "body": f"{due} card{'s' if due != 1 else ''} due today.",
                "url": "/",
            }
            if not _send(sub, payload):
                db.delete(sub)
        db.commit()
    finally:
        db.close()


async def reminder_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(send_due_reminders)
        except Exception:
            log.exception("sending push reminders failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@router.get("/public-key")
def get_public_key():
    return {"public_key": public_key()}


@router.get("/status", response_model=PushStatus)
def status(endpoint: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint)
        .first()
    )
    return PushStatus(subscribed=sub is not None, reminder_hour=sub.reminder_hour if sub else None)


@router.post("/subscribe", response_model=PushStatus)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint)
        db.add(sub)
    sub.user_id = user_id
    sub.p256dh = body.keys.p256dh
    sub.auth = body.keys.auth
    sub.timezone = body.timezone
    sub.reminder_hour = body.reminder_hour
    sub.last_sent_date = None
    db.commit()
    return PushStatus(subscribed=True, reminder_hour=sub.reminder_hour)


@router.post("/unsubscribe", response_model=PushStatus)
def unsubscribe(body: UnsubscribeRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.query(PushSubscription).filter(
        PushSubscription.user_id == user_id, PushSubscription.endpoint == body.endpoint
    ).delete()
    db.commit()
    return PushStatus(subscribed=False)


@router.post("/test")
def send_test(body: UnsubscribeRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id, PushSubscription.endpoint == body.endpoint)
        .first()
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="This device isn't subscribed")
    due = _due_count(db, user_id)
    ok = _send(sub, {"title": "Reminders are on", "body": f"You have {due} card{'s' if due != 1 else ''} due.", "url": "/"})
    if not ok:
        db.delete(sub)
        db.commit()
        raise HTTPException(status_code=410, detail="The subscription expired; turn reminders on again")
    return {"ok": True}
