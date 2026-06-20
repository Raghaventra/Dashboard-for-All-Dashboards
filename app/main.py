"""HAYSTACK Ultimate Toolkit - application entry point.

A centralized hub that links out to the team's internal dashboards, with its
own lightweight login (email + OTP verification), an activity log for basic
auditability, and an admin area to manage dashboards and users.

The hub does NOT provide security for the underlying dashboards; each of those
keeps its own authentication and access control.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.auth import AuthRedirect, get_current_user
from app.config import settings
from app.database import SessionLocal, init_db
from app.maintenance import purge_old_data
from app.routers import account_routes, admin_routes, auth_routes, dashboard_routes, media_routes
from app.seed import seed_dashboards
from app.templating import page_context, templates

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ultimate_dashboard")

app = FastAPI(title="HAYSTACK Ultimate Toolkit", docs_url=None, redoc_url=None)

# Signed-cookie sessions. https_only should be True behind HTTPS in production.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=settings.SESSION_HTTPS_ONLY,
    max_age=60 * 60 * 12,  # 12 hours
)

# Static assets (css / js / icons).
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Routers.
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(account_routes.router)
app.include_router(admin_routes.router)
app.include_router(media_routes.router)


@app.exception_handler(AuthRedirect)
async def auth_redirect_handler(request: Request, exc: AuthRedirect):
    """Turn auth failures (from require_login / require_admin) into redirects."""
    return RedirectResponse(exc.location, status_code=exc.status_code)


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


def _safe_theme(request: Request) -> str:
    """Best-effort lookup of the logged-in user's theme for the error page."""
    try:
        db = SessionLocal()
        try:
            user = get_current_user(request, db)
            return user.theme_preference if user and user.theme_preference else "light"
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - never let the error page itself crash
        return "light"


def _render_error(request: Request, status_code: int, message: str):
    if _wants_json(request):
        return JSONResponse({"ok": False, "error": message}, status_code=status_code)
    ctx = page_context(request, theme_pref=_safe_theme(request),
                       status_code=status_code, message=message)
    return templates.TemplateResponse("error.html", ctx, status_code=status_code)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render a friendly page for 404s and other HTTP errors."""
    messages = {
        404: "We couldn't find that page.",
        403: "You don't have access to that.",
        405: "That action isn't allowed here.",
    }
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else \
        messages.get(exc.status_code, "Something went wrong.")
    return _render_error(request, exc.status_code, message)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort handler so an unexpected error never crashes the server."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _render_error(request, 500, "An unexpected error occurred. Please try again.")


@app.on_event("startup")
def on_startup():
    init_db()
    seed_dashboards()
    purge_old_data()  # drop activity logs / OTPs older than ~6 months


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
