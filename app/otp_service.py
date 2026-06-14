"""Issue and verify email OTPs. Shared by registration and account changes."""
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.emailer import send_otp_email
from app.models import OTP
from app.security import generate_otp, hash_otp, verify_otp


def issue_otp(db: Session, email: str) -> None:
    """Generate, store (hashed) and email a fresh OTP, invalidating older ones."""
    db.query(OTP).filter(OTP.email == email, OTP.consumed == False).update(  # noqa: E712
        {"consumed": True}
    )
    code = generate_otp()
    otp = OTP(
        email=email,
        code_hash=hash_otp(code),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_TTL_MINUTES),
    )
    db.add(otp)
    db.commit()
    send_otp_email(email, code)


def consume_otp(db: Session, email: str, code: str) -> Tuple[bool, Optional[str]]:
    """Validate a code for an email and mark it used. Returns (ok, error_message)."""
    code = (code or "").strip()
    otp = (
        db.query(OTP)
        .filter(OTP.email == email, OTP.consumed == False)  # noqa: E712
        .order_by(OTP.created_at.desc())
        .first()
    )
    if otp is None:
        return False, "No active code. Please request a new one."
    if otp.expires_at < datetime.utcnow():
        return False, "This code has expired. Please request a new one."
    if not verify_otp(code, otp.code_hash):
        return False, "Incorrect code. Please try again."

    otp.consumed = True
    db.commit()
    return True, None
