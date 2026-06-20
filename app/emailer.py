"""Send OTP emails over SMTP.

If SMTP is unreachable (e.g. while developing on a machine without internet)
the failure is logged and, in DEBUG mode, the OTP is printed to the console so
testing can continue. The caller can inspect the returned bool.
"""
import smtplib
from email.message import EmailMessage

from app.config import settings


def send_otp_email(recipient: str, code: str) -> bool:
    """Send the OTP code to ``recipient``. Returns True if SMTP accepted it."""
    subject = "Your HAYSTACK Ultimate Toolkit verification code"
    body = (
        f"Hello,\n\n"
        f"Your HAYSTACK Ultimate Toolkit verification code is: {code}\n\n"
        f"It expires in {settings.OTP_TTL_MINUTES} minutes. "
        f"If you did not request this, you can ignore this email.\n\n"
        f"— HAYSTACK Ultimate Toolkit"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SENDER_EMAIL
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(settings.SENDER_EMAIL, settings.SENDER_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - we never want email errors to crash a request
        print(f"[emailer] Failed to send OTP to {recipient}: {exc}")
        if settings.DEBUG:
            print(f"[emailer][DEBUG] OTP for {recipient} is: {code}")
        return False
