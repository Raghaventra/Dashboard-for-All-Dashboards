"""Password / OTP hashing and verification (uses bcrypt directly)."""
import hashlib
import hmac
import secrets

import bcrypt


def hash_password(password: str) -> str:
    """Return a bcrypt hash (utf-8 str) for a plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_otp(num_digits: int = 6) -> str:
    """Cryptographically-random numeric OTP, zero-padded."""
    upper = 10 ** num_digits
    return str(secrets.randbelow(upper)).zfill(num_digits)


def hash_otp(code: str) -> str:
    """Hash an OTP for storage. SHA-256 is fine for short-lived single-use codes."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_otp(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), code_hash or "")
