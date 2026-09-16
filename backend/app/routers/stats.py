from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import Review, UserStreak, Word, WordMastery
from app.schemas import ActivityDay, ActivityResponse, GrowthPoint, GrowthResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/growth", response_model=GrowthResponse)
def growth(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):

    rows = (
        db.query(
            func.date(WordMastery.mastered_at).label("day"),
            func.count().label("count"),
        )
        .filter(WordMastery.user_id == user_id)
        .group_by("day")
        .order_by("day")
        .all()
    )

    points: list[GrowthPoint] = []
    cumulative = 0
    for row in rows:
        cumulative += row.count
        day = row.day if isinstance(row.day, date) else date.fromisoformat(row.day)
        points.append(GrowthPoint(date=day, cumulative_mastered=cumulative))

    total_words = db.query(Word).count()
    coverage = round(100 * cumulative / total_words, 1) if total_words else 0.0

    streak = db.get(UserStreak, user_id)
    current_streak = streak.current_streak if streak else 0
    longest_streak = streak.longest_streak if streak else 0

    return GrowthResponse(
        points=points,
        total_words_in_deck=total_words,
        coverage_percent=coverage,
        current_streak=current_streak,
        longest_streak=longest_streak,
    )


@router.get("/activity", response_model=ActivityResponse)
def activity(days: int = 140, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Reviews per local calendar day, for the activity calendar. Only days with reviews are returned."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = func.date(Review.timestamp, "localtime").label("day")
    rows = (
        db.query(day, func.count().label("reviews"), func.sum(case((Review.correct, 1), else_=0)).label("correct"))
        .filter(Review.user_id == user_id, Review.timestamp >= since)
        .group_by(day)
        .order_by(day)
        .all()
    )
    return ActivityResponse(
        days=[ActivityDay(date=date.fromisoformat(r.day), reviews=r.reviews, correct=r.correct or 0) for r in rows]
    )
