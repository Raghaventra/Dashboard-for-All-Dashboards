"""Session handling and current-user dependencies.

Sessions are stored in a signed cookie via Starlette's SessionMiddleware
(configured in main.py). We only keep the user id in the session.
"""
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

SESSION_USER_KEY = "user_id"


class AuthRedirect(Exception):
    """Raised to signal that the caller should be redirected (to login / forbidden)."""

    def __init__(self, location: str, status_code: int = 303):
        self.location = location
        self.status_code = status_code


def login_user(request: Request, user: User) -> None:
    request.session[SESSION_USER_KEY] = user.id


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Return the logged-in user or None. Never raises."""
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        request.session.pop(SESSION_USER_KEY, None)
        return None
    return user


def require_login(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Dependency: ensure a logged-in user, else redirect to /login."""
    if user is None:
        raise AuthRedirect("/login")
    return user


def require_admin(user: User = Depends(require_login)) -> User:
    """Dependency: ensure the logged-in user is an admin."""
    if not user.is_admin:
        raise AuthRedirect("/", status_code=303)
    return user
