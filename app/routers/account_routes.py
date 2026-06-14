"""Account settings: change username / password, both gated by email OTP.

Flow on the Account page:
  1. User clicks "Send verification code" -> OTP emailed to their address.
  2. User submits the change (new username, or new password) together with the
     code. The change only applies if the code is valid.
Password changes additionally require the current password.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import get_current_user, require_login
from app.database import get_db
from app.models import User
from app.otp_service import consume_otp, issue_otp
from app.security import hash_password, verify_password
from app.templating import page_context, templates

router = APIRouter(prefix="/account")


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _render(request, user, status=200, **extra):
    return templates.TemplateResponse(
        "account.html", page_context(request, user=user, **extra), status_code=status
    )


@router.get("")
def account_home(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    log_activity(db, "view_account", user=user, ip_address=_ip(request))
    return _render(request, user)


@router.post("/theme")
def set_theme(
    request: Request,
    theme: str = Form(...),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist the user's theme choice so it's remembered at next login.

    Uses get_current_user (not require_login) so an anonymous toggle is a no-op
    rather than a redirect.
    """
    theme = (theme or "").strip().lower()
    if theme not in {"light", "dark"}:
        return JSONResponse({"ok": False, "error": "invalid theme"}, status_code=400)
    if user is None:
        return JSONResponse({"ok": True, "saved": False})  # anonymous: localStorage only
    user.theme_preference = theme
    db.commit()
    return JSONResponse({"ok": True, "saved": True, "theme": theme})


@router.post("/request-code")
def request_code(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    issue_otp(db, user.email)
    log_activity(db, "account_otp_request", user=user, ip_address=_ip(request))
    return _render(request, user, code_sent=True,
                   info=f"A verification code was sent to {user.email}.")


@router.post("/username")
def change_username(
    request: Request,
    new_username: str = Form(...),
    code: str = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    new_username = new_username.strip()

    if len(new_username) < 3:
        return _render(request, user, error="Username must be at least 3 characters.", status=400)
    if new_username == user.username:
        return _render(request, user, error="That is already your username.", status=400)

    taken = db.query(User).filter(User.username == new_username, User.id != user.id).first()
    if taken:
        return _render(request, user, error="That username is already taken.", status=400)

    ok, otp_error = consume_otp(db, user.email, code)
    if not ok:
        return _render(request, user, error=otp_error, status=400)

    old = user.username
    user.username = new_username
    db.commit()
    log_activity(db, "change_username", user=user, detail=f"{old} -> {new_username}", ip_address=_ip(request))
    return _render(request, user, info="Username updated.")


@router.post("/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    code: str = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if not verify_password(current_password, user.password_hash or ""):
        return _render(request, user, error="Current password is incorrect.", status=400)
    if len(new_password) < 8:
        return _render(request, user, error="New password must be at least 8 characters.", status=400)
    if new_password != confirm_password:
        return _render(request, user, error="New passwords do not match.", status=400)

    ok, otp_error = consume_otp(db, user.email, code)
    if not ok:
        return _render(request, user, error=otp_error, status=400)

    user.password_hash = hash_password(new_password)
    db.commit()
    log_activity(db, "change_password", user=user, ip_address=_ip(request))
    return _render(request, user, info="Password updated.")
