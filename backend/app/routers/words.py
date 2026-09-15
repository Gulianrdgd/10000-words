from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, DEFAULT_USER_ID, Word

router = APIRouter(prefix="/words", tags=["words"])


class WordProgress(BaseModel):
    id: str
    lemma: str
    pos: str
    translation_en: str
    frequency_rank: int
    cefr_estimate: str
    recognition_mastery: int
    production_mastery: int
    mastered: bool


@router.get("", response_model=list[WordProgress])
def list_words(db: Session = Depends(get_db)):
    user_id = DEFAULT_USER_ID
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
