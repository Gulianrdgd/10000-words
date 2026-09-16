import json
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Card, Word

WORDS_JSON_PATH = Path(__file__).parent / "data" / "words.json"

TRACKS = ("recognition", "production")


def upgrade_schema(engine: Engine) -> None:
    """create_all() only creates missing tables, so databases created by an
    older version of the app also need their missing columns added."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'))
                if column.unique:
                    conn.execute(
                        text(
                            f"CREATE UNIQUE INDEX IF NOT EXISTS uq_{table.name}_{column.name} "
                            f"ON {table.name} ({column.name})"
                        )
                    )


def sync_words(db: Session) -> None:
    """Inserts new words from words.json and refreshes data fields (gender,
    sentences, translations) on existing ones. Word IDs are stable, so a
    user's cards and review history stay attached."""
    with open(WORDS_JSON_PATH, encoding="utf-8") as f:
        words = json.load(f)

    existing = {w.id: w for w in db.query(Word).all()}
    for w in words:
        fields = dict(
            lemma=w["lemma"],
            pos=w["pos"],
            frequency_rank=w["frequency_rank"],
            translation_en=w["translation_en"],
            cefr_estimate=w["cefr_estimate"],
            gender=w.get("gender"),
            emoji=w.get("emoji"),
            sentences_json=json.dumps(w["sentences"], ensure_ascii=False),
        )
        row = existing.get(w["id"])
        if row is None:
            db.add(Word(id=w["id"], **fields))
        else:
            for key, value in fields.items():
                if getattr(row, key) != value:
                    setattr(row, key, value)
    db.commit()


def ensure_cards(db: Session, user_id: str) -> None:
    """Creates any missing recognition/production cards for this user."""
    have = {(word_id, track) for word_id, track in db.query(Card.word_id, Card.track).filter(Card.user_id == user_id)}
    missing = [
        {"user_id": user_id, "word_id": word_id, "track": track}
        for (word_id,) in db.query(Word.id)
        for track in TRACKS
        if (word_id, track) not in have
    ]
    if missing:
        db.bulk_insert_mappings(Card, missing)
    db.commit()


def ensure_cards_for_all_users(db: Session) -> None:
    for (user_id,) in db.query(Card.user_id).distinct().all():
        ensure_cards(db, user_id)
