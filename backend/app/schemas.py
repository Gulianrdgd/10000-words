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
    track: str  # recognition | production
    mode: int  # 1-4
    is_new: bool
    mastery_level: int
    sentence: Sentence | None = None
    options: list[str] | None = None  # MCQ distractors + correct, shuffled (mode 1)
    cloze_sentence: str | None = None  # mode 3, word blanked out


class DueCardsResponse(BaseModel):
    cards: list[DueCard]
    daily_new_word_limit: int
    new_words_introduced_today: int


class ReviewRequest(BaseModel):
    mode: int
    correct: bool = False  # authoritative for mode 1; ignored for modes 2/3 (server-graded) and 4 (self-report)
    latency_ms: int = 0
    typed_answer: str | None = None  # for fuzzy-matched modes (2, 3)
    self_reported_correct: bool | None = None  # for mode 4 (free production)


class ReviewResponse(BaseModel):
    card_id: int
    word_id: str
    track: str
    rating: int
    correct: bool
    near_miss: bool
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
