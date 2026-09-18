from datetime import date, datetime

from pydantic import BaseModel


class Sentence(BaseModel):
    fr: str
    en: str


class DueCard(BaseModel):
    card_id: int
    word_id: str
    lemma: str
    pos: str
    translation_en: str
    cefr_estimate: str
    gender: str | None = None  # see app/gender.py
    display_lemma: str  # lemma with its article for nouns: "la maison"
    emoji: str | None = None
    track: str  # recognition | production
    mode: int  # 1-5
    is_new: bool
    mastery_level: int
    sentence: Sentence | None = None
    options: list[str] | None = None  # MCQ distractors + correct, shuffled (mode 1)
    cloze_sentence: str | None = None  # mode 3, word blanked out
    # what modes 2/3/5 grade the typed answer against. Sent to the client so it
    # can grade offline and echo it back (mode 3's blank differs per fetch).
    expected_answer: str | None = None


class DueCardsResponse(BaseModel):
    cards: list[DueCard]
    daily_new_word_limit: int
    new_words_introduced_today: int


class SpokenPhoneme(BaseModel):
    p: str  # the phoneme
    a: int  # accuracy 0-100


class ReviewRequest(BaseModel):
    mode: int
    correct: bool = False  # authoritative for mode 1; ignored for modes 2/3/5 (server-graded) and 4 (self-report)
    latency_ms: int = 0
    typed_answer: str | None = None  # for fuzzy-matched modes (2, 3, 5)
    self_reported_correct: bool | None = None  # for mode 4 (free production)
    expected_answer: str | None = None  # mode 3: the blank the client was actually shown
    pronunciation_score: int | None = None  # 0-100 when the answer was spoken, not typed
    phonemes: list["SpokenPhoneme"] | None = None  # per-sound accuracy from the same attempt
    client_review_id: str | None = None  # idempotency key for retries / offline replay
    reviewed_at: datetime | None = None  # when answered, if queued offline


class ReviewResponse(BaseModel):
    card_id: int
    word_id: str
    track: str
    rating: int
    correct: bool
    near_miss: bool
    gender_correct: bool | None = None
    expected_answer: str | None = None
    interval_days: int
    mastery_level: int
    word_mastered: bool
    streak: int


class GoalRequest(BaseModel):
    target_words: int


class GoalResponse(BaseModel):
    week_start: date
    target_words: int
    achieved_words: int
    days_remaining: int


class WeekReviewResponse(BaseModel):
    week_start: date
    mastered_words: list[str]
    shaky_words: list[str]
    growth_stat: str
    target_words: int
    achieved_words: int


class GrowthPoint(BaseModel):
    date: date
    cumulative_mastered: int


class GrowthResponse(BaseModel):
    points: list[GrowthPoint]
    total_words_in_deck: int
    coverage_percent: float
    current_streak: int
    longest_streak: int


class ActivityDay(BaseModel):
    date: date
    reviews: int
    correct: int


class ActivityResponse(BaseModel):
    days: list[ActivityDay]


class SpeechToken(BaseModel):
    token: str
    region: str


class SpokenWordStat(BaseModel):
    word_id: str
    lemma: str
    display_lemma: str
    translation_en: str
    average_score: float
    last_score: int
    attempts: int


class PhonemeStat(BaseModel):
    phoneme: str
    average_accuracy: float
    samples: int


class PronunciationStats(BaseModel):
    attempts: int
    average_score: float | None
    worst_words: list[SpokenWordStat]
    weak_phonemes: list[PhonemeStat]
