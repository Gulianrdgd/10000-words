from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import DEFAULT_USER_ID, UserStreak


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def record_activity(db: Session, user_id: str = DEFAULT_USER_ID) -> UserStreak:
    """Call once per review. Advances the streak, silently spending a freeze
    day (up to 2/week) to protect it across a single missed day, per the
    'soft streak' design — no guilt messaging, just quiet protection."""
    streak = db.get(UserStreak, user_id)
    if streak is None:
        streak = UserStreak(
            user_id=user_id,
            current_streak=0,
            longest_streak=0,
            freezes_available=2,
            freeze_week_start=_week_start(date.today()),
            last_active_date=None,
        )
        db.add(streak)

    today = date.today()
    week_start = _week_start(today)
    if streak.freeze_week_start != week_start:
        streak.freezes_available = 2
        streak.freeze_week_start = week_start

    if streak.last_active_date == today:
        pass  # already counted today
    elif streak.last_active_date is None:
        streak.current_streak = 1
    else:
        gap = (today - streak.last_active_date).days
        if gap == 1:
            streak.current_streak += 1
        else:
            missed = gap - 1
            if streak.freezes_available >= missed:
                streak.freezes_available -= missed
                streak.current_streak += 1
            else:
                streak.current_streak = 1
        streak.last_active_date = today

    if streak.last_active_date is None:
        streak.last_active_date = today

    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    db.flush()
    return streak
