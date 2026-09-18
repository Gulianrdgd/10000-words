import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import Review, UserStreak, Word, WordMastery
from app.gender import display_form
from app.schemas import (
    ActivityDay,
    ActivityResponse,
    GrowthPoint,
    GrowthResponse,
    PhonemeStat,
    PronunciationStats,
    SpokenWordStat,
)

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


@router.get("/pronunciation", response_model=PronunciationStats)
def pronunciation(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Where speaking is going wrong: the words scored lowest on average, and
    the individual sounds that come out weak across every word."""
    spoken = Review.pronunciation_score.isnot(None)

    totals = (
        db.query(func.count().label("attempts"), func.avg(Review.pronunciation_score).label("average"))
        .filter(Review.user_id == user_id, spoken)
        .one()
    )

    rows = (
        db.query(
            Review.word_id,
            func.avg(Review.pronunciation_score).label("average"),
            func.count().label("attempts"),
            func.max(Review.timestamp).label("last_at"),
        )
        .filter(Review.user_id == user_id, spoken)
        .group_by(Review.word_id)
        .order_by("average")
        .limit(20)
        .all()
    )

    words = {w.id: w for w in db.query(Word).filter(Word.id.in_([r.word_id for r in rows])).all()} if rows else {}
    worst: list[SpokenWordStat] = []
    for row in rows:
        word = words.get(row.word_id)
        if word is None:
            continue
        last = (
            db.query(Review.pronunciation_score)
            .filter(Review.user_id == user_id, Review.word_id == row.word_id, spoken)
            .order_by(Review.timestamp.desc())
            .limit(1)
            .scalar()
        )
        worst.append(
            SpokenWordStat(
                word_id=word.id,
                lemma=word.lemma,
                display_lemma=display_form(word.lemma, word.gender),
                translation_en=word.translation_en,
                average_score=round(row.average, 1),
                last_score=last or 0,
                attempts=row.attempts,
            )
        )

    # Phonemes are stored per review as JSON, so they're aggregated here rather
    # than in SQL. Recent history only: old attempts shouldn't haunt the list.
    sums: dict[str, list[int]] = {}
    recent = (
        db.query(Review.phonemes_json)
        .filter(Review.user_id == user_id, Review.phonemes_json.isnot(None))
        .order_by(Review.timestamp.desc())
        .limit(500)
        .all()
    )
    for (payload,) in recent:
        for entry in json.loads(payload):
            sums.setdefault(entry["p"], []).append(entry["a"])

    weak = [
        PhonemeStat(phoneme=p, average_accuracy=round(sum(v) / len(v), 1), samples=len(v))
        for p, v in sums.items()
        if len(v) >= 3  # one bad attempt isn't a weak spot
    ]
    weak.sort(key=lambda s: s.average_accuracy)

    return PronunciationStats(
        attempts=totals.attempts or 0,
        average_score=round(totals.average, 1) if totals.average is not None else None,
        worst_words=worst,
        weak_phonemes=weak[:12],
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
