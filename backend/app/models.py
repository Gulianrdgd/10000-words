from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

DEFAULT_USER_ID = "default"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Word(Base):
    __tablename__ = "words"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "w0001"
    lemma: Mapped[str] = mapped_column(String, index=True)
    pos: Mapped[str] = mapped_column(String, index=True)
    frequency_rank: Mapped[int] = mapped_column(Integer, index=True)
    translation_en: Mapped[str] = mapped_column(String)
    cefr_estimate: Mapped[str] = mapped_column(String)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)  # see app/gender.py
    emoji: Mapped[str | None] = mapped_column(String, nullable=True)  # picture for concrete words
    sentences_json: Mapped[str] = mapped_column(String)  # JSON-encoded list

    cards: Mapped[list["Card"]] = relationship(back_populates="word")


class Card(Base):
    """One FSRS-scheduled card per (user, word, track)."""

    __tablename__ = "cards"
    __table_args__ = (UniqueConstraint("user_id", "word_id", "track"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, default=DEFAULT_USER_ID)
    word_id: Mapped[str] = mapped_column(ForeignKey("words.id"), index=True)
    track: Mapped[str] = mapped_column(String)  # "recognition" | "production"

    # FSRS state
    fsrs_state: Mapped[int] = mapped_column(Integer, default=1)  # State enum value
    fsrs_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    mastery_level: Mapped[int] = mapped_column(Integer, default=0)  # 0-5

    introduced: Mapped[bool] = mapped_column(Boolean, default=False)
    introduced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # rotates which of the word's example sentences is shown next
    sentence_cursor: Mapped[int] = mapped_column(Integer, default=0)

    # the exact token blanked out in the most recently served cloze sentence
    # (mode 3), so the follow-up review can grade the typed answer against it
    pending_answer: Mapped[str | None] = mapped_column(String, nullable=True)

    word: Mapped["Word"] = relationship(back_populates="cards")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, default=DEFAULT_USER_ID)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    word_id: Mapped[str] = mapped_column(ForeignKey("words.id"), index=True)
    track: Mapped[str] = mapped_column(String)
    mode: Mapped[int] = mapped_column(Integer)  # 1-6
    correct: Mapped[bool] = mapped_column(Boolean)
    near_miss: Mapped[bool] = mapped_column(Boolean, default=False)
    # None when the answer didn't test noun gender (non-nouns, MCQ, cloze, self-report)
    gender_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # set by the client so a review retried after a dropped connection (or
    # replayed from the offline queue) is only applied once
    client_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer)  # FSRS Rating 1-4
    # Azure pronunciation assessment, only for spoken answers (None when typed).
    # phonemes_json is [{"p": "ʁ", "a": 43}, ...] — kept per review so weak
    # sounds can be aggregated across the whole history.
    pronunciation_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phonemes_json: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, default=DEFAULT_USER_ID)
    week_start: Mapped[date] = mapped_column(Date, index=True)  # Monday
    target_words: Mapped[int] = mapped_column(Integer, default=20)


class WordMastery(Base):
    """Records the first time a word crosses the mastery threshold on both tracks."""

    __tablename__ = "word_mastery"
    __table_args__ = (UniqueConstraint("user_id", "word_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, default=DEFAULT_USER_ID)
    word_id: Mapped[str] = mapped_column(ForeignKey("words.id"), index=True)
    mastered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id: Mapped[str] = mapped_column(String, primary_key=True, default=DEFAULT_USER_ID)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    freezes_available: Mapped[int] = mapped_column(Integer, default=2)
    freeze_week_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token_hash: Mapped[str] = mapped_column(String, primary_key=True)  # sha256 of the bearer token
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String, unique=True)
    p256dh: Mapped[str] = mapped_column(String)
    auth: Mapped[str] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String, default="UTC")  # IANA name, e.g. "Europe/Amsterdam"
    reminder_hour: Mapped[int] = mapped_column(Integer, default=18)  # local hour of day
    last_sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # local date
