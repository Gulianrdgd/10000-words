from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import DEFAULT_USER_ID, WeeklyGoal

DEFAULT_TARGET_WORDS = 20


def week_start(d: date | None = None) -> date:
    d = d or date.today()
    return d - timedelta(days=d.weekday())  # Monday


def current_week_target(db: Session, user_id: str = DEFAULT_USER_ID) -> int:
    goal = (
        db.query(WeeklyGoal)
        .filter(WeeklyGoal.user_id == user_id, WeeklyGoal.week_start == week_start())
        .first()
    )
    return goal.target_words if goal else DEFAULT_TARGET_WORDS
