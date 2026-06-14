"""Helper for writing audit/activity-log records."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ActivityLog, User


def log_activity(
    db: Session,
    action: str,
    *,
    user: Optional[User] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> ActivityLog:
    """Record an activity event. Commits its own row.

    Pass either a ``user`` object or explicit ``username``/``email`` (useful for
    events that happen before a user fully exists, e.g. registration attempts).
    """
    if user is not None:
        username = username or user.username
        email = email or user.email

    entry = ActivityLog(
        action=action,
        username=username,
        email=email,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    return entry
