from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import Card, WeeklyGoal, Word, WordMastery
from app.schemas import GoalRequest, GoalResponse, WeekReviewResponse
from app.weekly import DEFAULT_TARGET_WORDS, week_start

router = APIRouter(prefix="/goals", tags=["goals"])


def _achieved_words(db: Session, user_id: str, ws: date) -> int:
    we = ws + timedelta(days=7)
    return (
        db.query(WordMastery)
        .filter(
            WordMastery.user_id == user_id,
            WordMastery.mastered_at >= datetime.combine(ws, datetime.min.time(), tzinfo=timezone.utc),
            WordMastery.mastered_at < datetime.combine(we, datetime.min.time(), tzinfo=timezone.utc),
        )
        .count()
    )


@router.get("/current", response_model=GoalResponse)
def get_current_goal(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    ws = week_start()
    goal = db.query(WeeklyGoal).filter(WeeklyGoal.user_id == user_id, WeeklyGoal.week_start == ws).first()
    target = goal.target_words if goal else DEFAULT_TARGET_WORDS
    return GoalResponse(
        week_start=ws,
        target_words=target,
        achieved_words=_achieved_words(db, user_id, ws),
        days_remaining=6 - date.today().weekday(),
    )


@router.post("", response_model=GoalResponse)
def set_goal(body: GoalRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    ws = week_start()
    goal = db.query(WeeklyGoal).filter(WeeklyGoal.user_id == user_id, WeeklyGoal.week_start == ws).first()
    if goal is None:
        goal = WeeklyGoal(user_id=user_id, week_start=ws, target_words=body.target_words)
        db.add(goal)
    else:
        goal.target_words = body.target_words
    db.commit()
    return GoalResponse(
        week_start=ws,
        target_words=goal.target_words,
        achieved_words=_achieved_words(db, user_id, ws),
        days_remaining=6 - date.today().weekday(),
    )


@router.get("/{week}/review", response_model=WeekReviewResponse)
def week_review(week: date, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    ws = week_start(week)
    we = ws + timedelta(days=7)
    ws_dt = datetime.combine(ws, datetime.min.time(), tzinfo=timezone.utc)
    we_dt = datetime.combine(we, datetime.min.time(), tzinfo=timezone.utc)

    mastered = (
        db.query(Word.lemma)
        .join(WordMastery, WordMastery.word_id == Word.id)
        .filter(WordMastery.user_id == user_id, WordMastery.mastered_at >= ws_dt, WordMastery.mastered_at < we_dt)
        .all()
    )
    mastered_words = [m.lemma for m in mastered]

    fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
    shaky_word_ids = (
        db.query(Card.word_id)
        .filter(
            Card.user_id == user_id,
            Card.mastery_level.between(1, 2),
            Card.lapses > 0,
            Card.last_review >= fourteen_days_ago,
        )
        .distinct()
        .all()
    )
    shaky_words = []
    if shaky_word_ids:
        ids = [w[0] for w in shaky_word_ids]
        shaky_words = [w.lemma for w in db.query(Word).filter(Word.id.in_(ids)).all()]

    total_words = db.query(Word).count()
    total_mastered = db.query(WordMastery).filter(WordMastery.user_id == user_id).count()
    coverage_pct = round(100 * total_mastered / total_words, 1) if total_words else 0.0
    growth_stat = f"You can now recognize ~{coverage_pct}% of this app's core vocabulary ({total_mastered}/{total_words} words mastered)."

    goal = db.query(WeeklyGoal).filter(WeeklyGoal.user_id == user_id, WeeklyGoal.week_start == ws).first()
    target = goal.target_words if goal else DEFAULT_TARGET_WORDS

    return WeekReviewResponse(
        week_start=ws,
        mastered_words=mastered_words,
        shaky_words=shaky_words,
        growth_stat=growth_stat,
        target_words=target,
        achieved_words=len(mastered_words),
    )
