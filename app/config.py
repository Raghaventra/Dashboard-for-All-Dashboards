"""Central configuration, loaded from environment variables / .env file.

Everything the app needs to run is read here so the same code can be deployed
to any server just by changing the .env file. No paths or secrets are hardcoded.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder that contains this "app" package.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the project root (no-op if the file is absent; real env vars win).
load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


class Settings:
    # --- Security / sessions ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-key-change-me")

    # --- Registration policy ---
    ALLOWED_EMAIL_DOMAINS: list[str] = _get_list("ALLOWED_EMAIL_DOMAINS") or ["haystackrobotics.com"]
    ADMIN_EMAILS: list[str] = _get_list("ADMIN_EMAILS")

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ultimate_dashboard.db")

    # --- OTP ---
    OTP_TTL_MINUTES: int = int(os.getenv("OTP_TTL_MINUTES", "10"))

    # --- Email (SMTP) ---
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")
    SENDER_PASSWORD: str = os.getenv("SENDER_PASSWORD", "")

    # --- Misc ---
    DEBUG: bool = _get_bool("DEBUG", False)

    # Filesystem locations (derived, not configured).
    BASE_DIR: Path = BASE_DIR
    DASHBOARDS_SEED_FILE: Path = BASE_DIR / "dashboards.json"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"

    def email_domain_allowed(self, email: str) -> bool:
        email = email.strip().lower()
        return any(email.endswith("@" + domain) for domain in self.ALLOWED_EMAIL_DOMAINS)

    def is_seed_admin(self, email: str) -> bool:
        return email.strip().lower() in self.ADMIN_EMAILS


settings = Settings()
