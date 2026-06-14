"""Registration, email/OTP verification, credential setup, login and logout.

Flow:
  1. /register   -> enter company email, receive OTP by email
  2. /verify     -> enter OTP to confirm the email
  3. /set-credentials -> choose username + password (account becomes usable)
  4. /login      -> username + password -> session cookie
  5. /logout
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import get_current_user, login_user, logout_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.otp_service import consume_otp, issue_otp
from app.security import hash_password, verify_password
from app.templating import page_context, templates

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# --------------------------------------------------------------------------- #
# Registration -> OTP
# --------------------------------------------------------------------------- #
@router.get("/register")
def register_form(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("register.html", page_context(request))


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    if not settings.email_domain_allowed(email):
        allowed = ", ".join(settings.ALLOWED_EMAIL_DOMAINS)
        return templates.TemplateResponse(
            "register.html",
            page_context(request, error=f"Only {allowed} email addresses are allowed.", email=email),
            status_code=400,
        )

    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.username and existing.password_hash:
        return templates.TemplateResponse(
            "register.html",
            page_context(
                request,
                error="An account with this email already exists. Please log in.",
                email=email,
            ),
            status_code=400,
        )

    if not existing:
        db.add(User(email=email, is_verified=False, is_admin=settings.is_seed_admin(email)))
        try:
            db.commit()
        except IntegrityError:
            # Two registrations raced for the same email; unique constraint held.
            db.rollback()

    issue_otp(db, email)
    log_activity(db, "register_request", email=email, ip_address=_client_ip(request))

    return RedirectResponse(f"/verify?email={email}", status_code=303)


# --------------------------------------------------------------------------- #
# OTP verification
# --------------------------------------------------------------------------- #
@router.get("/verify")
def verify_form(request: Request, email: str = ""):
    return templates.TemplateResponse(
        "verify.html", page_context(request, email=email.strip().lower())
    )


@router.post("/verify")
def verify_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    ok, error = consume_otp(db, email, code)
    if not ok:
        return templates.TemplateResponse(
            "verify.html", page_context(request, email=email, error=error), status_code=400
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, is_admin=settings.is_seed_admin(email))
        db.add(user)
    user.is_verified = True
    db.commit()

    log_activity(db, "verify_email", user=user, ip_address=_client_ip(request))

    # If they already have credentials, just send them to login; otherwise set them.
    if user.username and user.password_hash:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse(f"/set-credentials?email={email}", status_code=303)


@router.post("/resend-otp")
def resend_otp(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if settings.email_domain_allowed(email):
        issue_otp(db, email)
        log_activity(db, "otp_resend", email=email, ip_address=_client_ip(request))
    return RedirectResponse(f"/verify?email={email}", status_code=303)


# --------------------------------------------------------------------------- #
# Set username + password
# --------------------------------------------------------------------------- #
@router.get("/set-credentials")
def set_credentials_form(request: Request, email: str = "", db: Session = Depends(get_db)):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_verified:
        return RedirectResponse("/register", status_code=303)
    return templates.TemplateResponse(
        "set_credentials.html", page_context(request, email=email)
    )


@router.post("/set-credentials")
def set_credentials_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    username = username.strip()

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_verified:
        return RedirectResponse("/register", status_code=303)

    def fail(msg):
        return templates.TemplateResponse(
            "set_credentials.html",
            page_context(request, email=email, username=username, error=msg),
            status_code=400,
        )

    if len(username) < 3:
        return fail("Username must be at least 3 characters.")
    if len(password) < 8:
        return fail("Password must be at least 8 characters.")
    if password != confirm_password:
        return fail("Passwords do not match.")

    taken = (
        db.query(User)
        .filter(User.username == username, User.id != user.id)
        .first()
    )
    if taken:
        return fail("That username is already taken.")

    user.username = username
    user.password_hash = hash_password(password)
    db.commit()

    login_user(request, user)
    log_activity(db, "account_created", user=user, ip_address=_client_ip(request))
    return RedirectResponse("/", status_code=303)


# --------------------------------------------------------------------------- #
# Login / logout
# --------------------------------------------------------------------------- #
@router.get("/login")
def login_form(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", page_context(request))


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()
    user = db.query(User).filter(User.username == username).first()

    if user is None or not verify_password(password, user.password_hash or ""):
        log_activity(db, "login_failed", username=username, ip_address=_client_ip(request))
        return templates.TemplateResponse(
            "login.html",
            page_context(request, error="Invalid username or password.", username=username),
            status_code=401,
        )

    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            page_context(request, error="This account is disabled.", username=username),
            status_code=403,
        )

    user.last_login_at = datetime.utcnow()
    db.commit()
    login_user(request, user)
    log_activity(db, "login", user=user, ip_address=_client_ip(request))
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user:
        log_activity(db, "logout", user=user, ip_address=_client_ip(request))
    logout_user(request)
    return RedirectResponse("/login", status_code=303)
