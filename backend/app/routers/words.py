import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.fsrs_engine import _as_utc
from app.gender import display_form
from app.models import Card, Review, Word, WordMastery
from app.schemas import Sentence

router = APIRouter(prefix="/words", tags=["words"])


class WordProgress(BaseModel):
    id: str
    lemma: str
    display_lemma: str
    gender: str | None
    emoji: str | None
    pos: str
    translation_en: str
    frequency_rank: int
    cefr_estimate: str
    recognition_mastery: int
    production_mastery: int
    mastered: bool


class TrackState(BaseModel):
    track: str
    introduced: bool
    mastery_level: int
    reps: int
    lapses: int
    due_date: datetime | None
    last_review: datetime | None
    # FSRS days-until-90%-recall; mastery is judged on this, not mastery_level
    stability_days: float | None


class ReviewEntry(BaseModel):
    timestamp: datetime
    track: str
    mode: int
    correct: bool
    near_miss: bool
    gender_correct: bool | None


class WordDetail(BaseModel):
    id: str
    lemma: str
    display_lemma: str
    gender: str | None
    emoji: str | None
    pos: str
    translation_en: str
    frequency_rank: int
    cefr_estimate: str
    sentences: list[Sentence]
    tracks: list[TrackState]
    reviews: list[ReviewEntry]  # newest first
    mastered_at: datetime | None


@router.get("", response_model=list[WordProgress])
def list_words(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    words = db.query(Word).order_by(Word.frequency_rank.asc()).all()
    cards = db.query(Card).filter(Card.user_id == user_id).all()

    by_word: dict[str, dict[str, int]] = {}
    for c in cards:
        by_word.setdefault(c.word_id, {})[c.track] = c.mastery_level

    result = []
    for w in words:
        levels = by_word.get(w.id, {})
        rec = levels.get("recognition", 0)
        prod = levels.get("production", 0)
        result.append(
            WordProgress(
                id=w.id,
                lemma=w.lemma,
                display_lemma=display_form(w.lemma, w.gender),
                gender=w.gender,
                emoji=w.emoji,
                pos=w.pos,
                translation_en=w.translation_en,
                frequency_rank=w.frequency_rank,
                cefr_estimate=w.cefr_estimate,
                recognition_mastery=rec,
                production_mastery=prod,
                mastered=rec >= 4 and prod >= 4,
            )
        )
    return result


@router.get("/{word_id}", response_model=WordDetail)
def word_detail(word_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Word not found")

    cards = db.query(Card).filter(Card.user_id == user_id, Card.word_id == word_id).order_by(Card.track.asc()).all()
    reviews = (
        db.query(Review)
        .filter(Review.user_id == user_id, Review.word_id == word_id)
        .order_by(Review.timestamp.desc())
        .limit(100)
        .all()
    )
    mastery = db.query(WordMastery).filter(WordMastery.user_id == user_id, WordMastery.word_id == word_id).first()

    return WordDetail(
        id=word.id,
        lemma=word.lemma,
        display_lemma=display_form(word.lemma, word.gender),
        gender=word.gender,
        emoji=word.emoji,
        pos=word.pos,
        translation_en=word.translation_en,
        frequency_rank=word.frequency_rank,
        cefr_estimate=word.cefr_estimate,
        sentences=[Sentence(**s) for s in json.loads(word.sentences_json)],
        tracks=[
            TrackState(
                track=c.track,
                introduced=c.introduced,
                mastery_level=c.mastery_level,
                reps=c.reps,
                lapses=c.lapses,
                due_date=_as_utc(c.due_date),
                last_review=_as_utc(c.last_review),
                stability_days=round(c.stability, 1) if c.stability else None,
            )
            for c in cards
        ],
        reviews=[
            ReviewEntry(
                timestamp=_as_utc(r.timestamp),
                track=r.track,
                mode=r.mode,
                correct=r.correct,
                near_miss=r.near_miss,
                gender_correct=r.gender_correct,
            )
            for r in reviews
        ],
        mastered_at=_as_utc(mastery.mastered_at) if mastery else None,
    )
