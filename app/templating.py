"""Shared Jinja2 templates instance, with common context helpers.

A compatibility shim lets the whole codebase keep calling the legacy
``templates.TemplateResponse(name, context)`` signature while remaining correct
on newer Starlette (>=0.29), which expects ``TemplateResponse(request, name,
context)``. This keeps the app running unchanged across very different Starlette
versions (e.g. 0.44 locally and 1.3 on the deployment server).
"""
from typing import Optional

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.config import settings
from app.models import User


class _CompatTemplates(Jinja2Templates):
    def TemplateResponse(self, *args, **kwargs):
        # Already new-style: first positional arg is the Request.
        if args and isinstance(args[0], Request):
            return super().TemplateResponse(*args, **kwargs)

        # Legacy style: (name, context, **rest). Normalize to request-first,
        # which every supported Starlette version accepts.
        name = kwargs.pop("name", None)
        if name is None and args:
            name, args = args[0], args[1:]
        context = kwargs.pop("context", None)
        if context is None and args:
            context, args = args[0], args[1:]
        context = context or {}
        request = context.get("request")
        return super().TemplateResponse(request, name, context, *args, **kwargs)


templates = _CompatTemplates(directory=str(settings.TEMPLATES_DIR))


def page_context(request, user: Optional[User] = None, **extra) -> dict:
    """Base context every page needs (request + current user + theme + extras)."""
    # Logged-in users get their remembered theme; otherwise default to light.
    theme_pref = (user.theme_preference if user and user.theme_preference else "light")
    ctx = {
        "request": request,
        "current_user": user,
        "theme_pref": theme_pref,
        "logged_in": user is not None,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
    }
    ctx.update(extra)
    return ctx
