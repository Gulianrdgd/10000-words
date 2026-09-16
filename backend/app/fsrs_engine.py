"""Wraps py-fsrs so the rest of the app only deals with plain values."""
from datetime import datetime, timezone

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

scheduler = Scheduler()

# Below this latency (ms) a correct answer is graded "Easy" instead of "Good".
FAST_ANSWER_MS = 3000


def rating_for_answer(correct: bool, latency_ms: int, near_miss: bool = False) -> Rating:
    if not correct:
        return Rating.Again
    if near_miss:
        return Rating.Hard
    if latency_ms <= FAST_ANSWER_MS:
        return Rating.Easy
    return Rating.Good


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on round-trip, so datetimes read back from the DB
    come back naive even though everything is stored/computed in UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def card_from_row(row) -> FsrsCard:
    return FsrsCard(
        card_id=row.id,
        state=State(row.fsrs_state),
        step=row.fsrs_step,
        stability=row.stability,
        difficulty=row.difficulty,
        due=_as_utc(row.due_date) or datetime.now(timezone.utc),
        last_review=_as_utc(row.last_review),
    )


def apply_review(row, rating: Rating, now: datetime | None = None) -> tuple[FsrsCard, int]:
    """Runs the FSRS update for a Card row and returns (updated fsrs card, next interval in days).
    `now` is when the review happened (earlier than the real now for offline-queued reviews)."""
    fsrs_card = card_from_row(row)
    now = now or datetime.now(timezone.utc)
    updated, _log = scheduler.review_card(fsrs_card, rating, review_datetime=now)
    interval_days = max(1, (updated.due - now).days)
    return updated, interval_days


def levenshtein(a: str, b: str) -> int:
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]
