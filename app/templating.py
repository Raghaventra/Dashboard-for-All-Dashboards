"""Shared Jinja2 templates instance, with common context helpers."""
from typing import Optional

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import User

templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


def page_context(request, user: Optional[User] = None, **extra) -> dict:
    """Base context every page needs (request + current user + theme + extras)."""
    # Logged-in users get their remembered theme; otherwise default to light.
    theme_pref = (user.theme_preference if user and user.theme_preference else "light")
    ctx = {
        "request": request,
        "current_user": user,
        "theme_pref": theme_pref,
        "logged_in": user is not None,
    }
    ctx.update(extra)
    return ctx
