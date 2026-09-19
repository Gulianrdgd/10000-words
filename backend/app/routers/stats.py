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

# How far back the pronunciation figures look, so improving actually shows.
RECENT_SPOKEN_REVIEWS = 500


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
    # One bounded pass over recent history: every figure below comes from the
    # same window, so the page can't show an average from all time next to a
    # phoneme list from the last 500. Old scores shouldn't outweigh how you
    # speak now, and the whole thing stays one query.
    recent = (
        db.query(Review.word_id, Review.pronunciation_score, Review.phonemes_json, Review.timestamp)
        .filter(Review.user_id == user_id, Review.pronunciation_score.isnot(None))
        .order_by(Review.timestamp.desc())
        .limit(RECENT_SPOKEN_REVIEWS)
        .all()
    )

    by_word: dict[str, list[int]] = {}
    latest: dict[str, int] = {}
    sums: dict[str, list[int]] = {}
    for word_id, score, phonemes_json, _ts in recent:
        by_word.setdefault(word_id, []).append(score)
        latest.setdefault(word_id, score)  # rows arrive newest first
        if phonemes_json:
            for entry in json.loads(phonemes_json):
                sums.setdefault(entry["p"], []).append(entry["a"])

    ranked = sorted(by_word.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[:20]
    words = (
        {w.id: w for w in db.query(Word).filter(Word.id.in_([w for w, _ in ranked])).all()}
        if ranked
        else {}
    )
    worst = [
        SpokenWordStat(
            word_id=word.id,
            lemma=word.lemma,
            display_lemma=display_form(word.lemma, word.gender),
            translation_en=word.translation_en,
            average_score=round(sum(scores) / len(scores), 1),
            last_score=latest[word_id],
            attempts=len(scores),
        )
        for word_id, scores in ranked
        if (word := words.get(word_id)) is not None
    ]

    attempts = len(recent)
    average = round(sum(s for _, s, _, _ in recent) / attempts, 1) if attempts else None

    weak = [
        PhonemeStat(phoneme=p, average_accuracy=round(sum(v) / len(v), 1), samples=len(v))
        for p, v in sums.items()
        if len(v) >= 3  # one bad attempt isn't a weak spot
    ]
    weak.sort(key=lambda s: s.average_accuracy)

    return PronunciationStats(
        attempts=attempts,
        average_score=average,
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
