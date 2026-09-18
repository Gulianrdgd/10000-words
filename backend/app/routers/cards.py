import json
import math
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import streaks
from app.auth import get_current_user_id
from app.database import get_db
from app.fsrs_engine import _as_utc, apply_review, levenshtein, rating_for_answer, rating_for_spoken
from app.gender import display_form, gender_correct, production_answer, split_article
from app.models import Card, Review, UserStreak, Word, WordMastery
from app.schemas import DueCard, DueCardsResponse, ReviewRequest, ReviewResponse, Sentence
from app.session_composer import build_cloze, build_mcq_options, interleave_by_pos, pick_mode, pick_sentence
from app.weekly import current_week_target

router = APIRouter(prefix="/cards", tags=["cards"])

# Azure accuracy below this fails the card, however right the transcription is.
PRONUNCIATION_PASS = 70

# A word counts as mastered once FSRS says both its cards would still be
# recalled with 90% probability this many days from now.
MASTERY_STABILITY_DAYS = 21.0


@router.get("/due", response_model=DueCardsResponse)
def get_due_cards(
    limit: int = 30,
    extra_new: int = Query(default=0, ge=0, le=50),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """`extra_new` unlocks that many words beyond today's pace, when the user
    explicitly asks to keep learning. The daily limit is a default, not a cap."""
    now = datetime.now(timezone.utc)
    today = date.today()

    target_words = current_week_target(db, user_id)
    daily_new_word_limit = max(1, math.ceil(target_words / 7))

    new_words_today = (
        db.query(func.count(func.distinct(Card.word_id)))
        .filter(
            Card.user_id == user_id,
            Card.track == "recognition",
            Card.introduced.is_(True),
            func.date(Card.introduced_at) == today.isoformat(),
        )
        .scalar()
        or 0
    )
    remaining_new = max(0, daily_new_word_limit - new_words_today) + extra_new

    due_cards = (
        db.query(Card)
        .filter(Card.user_id == user_id, Card.introduced.is_(True), Card.due_date <= now)
        .all()
    )

    if remaining_new > 0:
        new_candidates = (
            db.query(Card)
            .join(Word, Card.word_id == Word.id)
            .filter(Card.user_id == user_id, Card.track == "recognition", Card.introduced.is_(False))
            .order_by(Word.frequency_rank.asc())
            .limit(remaining_new)
            .all()
        )
        for c in new_candidates:
            c.introduced = True
            c.introduced_at = now
            c.due_date = now
        db.flush()
        due_cards.extend(new_candidates)
        new_words_today += len(new_candidates)

    all_words = db.query(Word).all()
    words_by_id = {w.id: w for w in all_words}

    pairs = [(c, words_by_id[c.word_id]) for c in due_cards]
    ordered = interleave_by_pos(pairs)[:limit]

    result: list[DueCard] = []
    for card, word in ordered:
        sentence_dict = pick_sentence(word, card)
        mode = pick_mode(card, has_sentences=sentence_dict is not None)
        sentence = Sentence(**sentence_dict) if sentence_dict else None
        options = None
        cloze_sentence = None
        expected_answer = None

        if mode in (1, 6):
            # mode 6 is the same choice of translations, prompted by audio
            options = build_mcq_options(word, all_words)
            card.pending_answer = None
        elif mode == 3:
            cloze_sentence, expected_answer = build_cloze(sentence_dict["fr"], word.lemma)
            card.pending_answer = expected_answer
        else:
            card.pending_answer = None
            if mode in (2, 5):
                expected_answer = production_answer(word.lemma, word.gender) if word.pos == "noun" else word.lemma

        result.append(
            DueCard(
                card_id=card.id,
                word_id=word.id,
                lemma=word.lemma,
                pos=word.pos,
                translation_en=word.translation_en,
                cefr_estimate=word.cefr_estimate,
                gender=word.gender,
                display_lemma=display_form(word.lemma, word.gender),
                emoji=word.emoji,
                track=card.track,
                mode=mode,
                is_new=card.reps == 0,
                mastery_level=card.mastery_level,
                sentence=sentence,
                options=options,
                cloze_sentence=cloze_sentence,
                expected_answer=expected_answer,
            )
        )

    db.commit()

    return DueCardsResponse(
        cards=result,
        daily_new_word_limit=daily_new_word_limit,
        new_words_introduced_today=new_words_today,
    )


def _grade_typed(word: Word, typed: str) -> tuple[bool, bool, bool | None, str]:
    """Grades modes 2 and 5. Returns (correct, near_miss, gender_correct, expected_answer).
    A noun answer needs its article: the right word with the wrong gender is wrong."""
    if word.pos != "noun":
        dist = levenshtein(typed, word.lemma)
        return dist <= 1, dist == 1, None, word.lemma

    article, bare = split_article(typed)
    dist = levenshtein(bare, word.lemma)
    gender_ok = gender_correct(article, word.gender)
    correct = dist <= 1 and gender_ok is not False
    return correct, correct and dist == 1, gender_ok, production_answer(word.lemma, word.gender)


def _mastered(db: Session, user_id: str, word_id: str) -> bool:
    """Mastery is FSRS's own memory estimate, not a tally of right answers.

    `stability` is the number of days until recall probability decays to 90%,
    so this asks "would I still know this in three weeks?" — which counts four
    correct answers seconds apart very differently from four spread over
    months. Both tracks must clear it: recognizing a word isn't producing it.
    """
    both_cards = db.query(Card).filter(Card.user_id == user_id, Card.word_id == word_id).all()
    if len(both_cards) != 2:
        return False
    return all(
        c.reps > 0 and (c.stability or 0.0) >= MASTERY_STABILITY_DAYS for c in both_cards
    )


def _replayed_response(db: Session, user_id: str, card: Card, review: Review) -> ReviewResponse:
    """The review was already applied (a retry, or an offline replay that got
    through before the connection dropped): report it without re-applying."""
    due, reviewed = _as_utc(card.due_date), _as_utc(review.timestamp)
    streak = db.get(UserStreak, user_id)
    return ReviewResponse(
        card_id=card.id,
        word_id=card.word_id,
        track=card.track,
        rating=review.rating,
        correct=review.correct,
        near_miss=review.near_miss,
        gender_correct=review.gender_correct,
        interval_days=max(1, (due - reviewed).days) if due and reviewed else 1,
        mastery_level=card.mastery_level,
        word_mastered=_mastered(db, user_id, card.word_id),
        streak=streak.current_streak if streak else 0,
    )


@router.post("/{card_id}/review", response_model=ReviewResponse)
def submit_review(
    card_id: int,
    body: ReviewRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    card = db.query(Card).filter(Card.id == card_id, Card.user_id == user_id).first()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    word = db.query(Word).filter(Word.id == card.word_id).first()

    if body.client_review_id:
        previous = db.query(Review).filter(Review.client_id == body.client_review_id).first()
        if previous is not None:
            return _replayed_response(db, user_id, card, previous)

    # Offline-queued reviews carry their real answer time; keep it within
    # (last review, now] so FSRS never sees time running backwards.
    now = datetime.now(timezone.utc)
    reviewed_at = min(_as_utc(body.reviewed_at) or now, now)
    last_review = _as_utc(card.last_review)
    if last_review and reviewed_at < last_review:
        reviewed_at = last_review

    near_miss = False
    gender_ok: bool | None = None
    expected_answer: str | None = None
    if body.mode in (2, 5):
        correct, near_miss, gender_ok, expected_answer = _grade_typed(word, body.typed_answer or "")
    elif body.mode == 3:
        expected_answer = body.expected_answer or card.pending_answer or word.lemma
        dist = levenshtein(body.typed_answer or "", expected_answer)
        correct = dist <= 1
        near_miss = dist == 1
    elif body.mode == 4 and body.pronunciation_score is not None:
        # spoken mode 4: reading the example sentence aloud, graded purely on
        # how it sounded — there's no single right answer to match text against
        expected_answer = body.expected_answer
        correct = body.pronunciation_score >= PRONUNCIATION_PASS
    else:
        # modes 1 and 6 (choice, graded client-side against the revealed
        # options) and typed mode 4 (free production, honest self-report)
        correct = bool(body.self_reported_correct if body.mode == 4 else body.correct)

    # A spoken answer has to be both the right word and intelligibly pronounced:
    # Azure will happily transcribe a mangled attempt into the correct spelling.
    if body.pronunciation_score is not None and body.mode in (2, 3, 4, 5):
        if body.mode != 4:  # mode 4 was already graded on the score alone
            correct = correct and body.pronunciation_score >= PRONUNCIATION_PASS
        rating = rating_for_spoken(correct, body.pronunciation_score)
    else:
        rating = rating_for_answer(correct, body.latency_ms, near_miss)
    was_first_review = card.reps == 0

    updated, interval_days = apply_review(card, rating, reviewed_at)
    card.fsrs_state = int(updated.state)
    card.fsrs_step = updated.step
    card.stability = updated.stability
    card.difficulty = updated.difficulty
    card.due_date = updated.due
    card.last_review = updated.last_review
    card.reps += 1
    card.pending_answer = None
    card.sentence_cursor += 1

    if rating == 1:  # Again
        card.lapses += 1
        card.mastery_level = max(0, card.mastery_level - 1)
    elif rating >= 3:  # Good or Easy
        card.mastery_level = min(5, card.mastery_level + 1)
    # Hard: mastery unchanged

    if card.track == "recognition" and was_first_review:
        production_card = (
            db.query(Card)
            .filter(Card.user_id == user_id, Card.word_id == card.word_id, Card.track == "production")
            .first()
        )
        if production_card and not production_card.introduced:
            production_card.introduced = True
            production_card.introduced_at = reviewed_at
            production_card.due_date = reviewed_at

    db.add(
        Review(
            user_id=user_id,
            card_id=card.id,
            word_id=card.word_id,
            track=card.track,
            mode=body.mode,
            correct=correct,
            near_miss=near_miss,
            gender_correct=gender_ok,
            client_id=body.client_review_id,
            latency_ms=body.latency_ms,
            rating=int(rating),
            timestamp=reviewed_at,
            pronunciation_score=body.pronunciation_score,
            phonemes_json=(
                json.dumps([p.model_dump() for p in body.phonemes]) if body.phonemes else None
            ),
        )
    )

    word_mastered = _mastered(db, user_id, card.word_id)
    if word_mastered:
        existing = (
            db.query(WordMastery)
            .filter(WordMastery.user_id == user_id, WordMastery.word_id == card.word_id)
            .first()
        )
        if existing is None:
            db.add(WordMastery(user_id=user_id, word_id=card.word_id, mastered_at=reviewed_at))

    streak = streaks.record_activity(db, user_id, reviewed_at.astimezone().date())

    db.commit()

    return ReviewResponse(
        card_id=card.id,
        word_id=card.word_id,
        track=card.track,
        rating=int(rating),
        correct=correct,
        near_miss=near_miss,
        gender_correct=gender_ok,
        expected_answer=expected_answer,
        interval_days=interval_days,
        mastery_level=card.mastery_level,
        word_mastered=word_mastered,
        streak=streak.current_streak,
    )
