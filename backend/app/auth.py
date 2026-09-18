"""Username/password accounts with opaque bearer tokens.

Passwords are hashed with stdlib scrypt; tokens are random and only their
sha256 is stored. Every data table already carried a user_id column from the
single-user era, so auth just decides which user_id a request acts as.
"""
import hashlib
import hmac
import logging
import os
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AuthToken,
    Card,
    DEFAULT_USER_ID,
    Review,
    User,
    UserStreak,
    WeeklyGoal,
    WordMastery,
)
from app.seed import ensure_cards

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_current_user_id(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> str:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized
    row = db.get(AuthToken, _token_hash(authorization.removeprefix("Bearer ")))
    if row is None:
        raise unauthorized
    return row.user_id


class Credentials(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=6, max_length=200)


class AuthResponse(BaseModel):
    token: str
    username: str


class MeResponse(BaseModel):
    username: str


def _issue_token(db: Session, user: User) -> AuthResponse:
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token_hash=_token_hash(token), user_id=user.id))
    db.commit()
    return AuthResponse(token=token, username=user.username)


def _max_users() -> int | None:
    """MAX_USERS caps how many accounts can ever exist — the app is internet-
    facing behind a proxy, and every account can spend the Azure quota. Unset
    (the default) leaves registration open; 0 closes it entirely."""
    raw = os.environ.get("MAX_USERS", "").strip()
    if not raw:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        log.warning("MAX_USERS=%r is not a number; leaving registration open", raw)
        return None


MAX_USERS = _max_users()


def _claim_single_user_data(db: Session, user_id: str) -> bool:
    """The app used to be single-user, storing everything under "default".
    The first account registered on such a database inherits that history."""
    if db.query(Card.id).filter(Card.user_id == DEFAULT_USER_ID).first() is None:
        return False
    for model in (Card, Review, WeeklyGoal, WordMastery, UserStreak):
        db.query(model).filter(model.user_id == DEFAULT_USER_ID).update({model.user_id: user_id})
    return True


@router.post("/register", response_model=AuthResponse)
def register(body: Credentials, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="That username is taken")

    existing_users = db.query(User).count()
    if MAX_USERS is not None and existing_users >= MAX_USERS:
        raise HTTPException(status_code=403, detail="Registration is closed.")

    is_first_user = existing_users == 0
    user = User(id=uuid.uuid4().hex, username=username, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    if is_first_user:
        _claim_single_user_data(db, user.id)
    db.commit()
    ensure_cards(db, user.id)
    return _issue_token(db, user)


@router.post("/login", response_model=AuthResponse)
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip().lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong username or password")
    return _issue_token(db, user)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if authorization and authorization.startswith("Bearer "):
        db.query(AuthToken).filter(
            AuthToken.token_hash == _token_hash(authorization.removeprefix("Bearer "))
        ).delete()
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return MeResponse(username=db.get(User, user_id).username)
