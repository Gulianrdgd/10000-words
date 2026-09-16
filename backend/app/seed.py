import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Card, DEFAULT_USER_ID, Word

WORDS_JSON_PATH = Path(__file__).parent / "data" / "words.json"


def seed_words_and_cards(db: Session) -> None:
    if db.query(Word).count() > 0:
        return

    with open(WORDS_JSON_PATH, encoding="utf-8") as f:
        words = json.load(f)

    for w in words:
        db.add(
            Word(
                id=w["id"],
                lemma=w["lemma"],
                pos=w["pos"],
                frequency_rank=w["frequency_rank"],
                translation_en=w["translation_en"],
                cefr_estimate=w["cefr_estimate"],
                sentences_json=json.dumps(w["sentences"], ensure_ascii=False),
            )
        )
    db.flush()

    for w in words:
        db.add(Card(user_id=DEFAULT_USER_ID, word_id=w["id"], track="recognition"))
        db.add(Card(user_id=DEFAULT_USER_ID, word_id=w["id"], track="production"))

    db.commit()
