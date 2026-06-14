"""Database models for the Ultimate Dashboard hub."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class User(Base):
    """A registered Ultimate Dashboard user.

    Authentication here is for the hub itself only. The underlying dashboards
    keep their own separate security.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(64), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)

    is_verified = Column(Boolean, default=False, nullable=False)  # email confirmed via OTP
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Remembered UI theme ("light" or "dark"); defaults to light for new users.
    theme_preference = Column(String(10), default="light", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)


class OTP(Base):
    """A one-time passcode emailed to a user to verify their address."""

    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)  # OTP is stored hashed, never plain
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Approval states for a dashboard tile.
STATUS_PENDING = "pending"    # submitted by a user, awaiting admin approval (Testing page)
STATUS_APPROVED = "approved"  # live on the main hub page
STATUS_REJECTED = "rejected"  # admin declined it


class Dashboard(Base):
    """An internal dashboard the hub links out to.

    Anyone can *submit* one (it lands in "pending" / the Testing page). An admin
    must approve it before it appears on the main hub page.
    """

    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    url = Column(String(1000), nullable=False)
    description = Column(String(500), nullable=True)
    icon = Column(String(120), nullable=True)        # emoji or icon identifier
    category = Column(String(80), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    status = Column(String(20), default=STATUS_PENDING, nullable=False, index=True)
    submitted_by = Column(String(64), nullable=True)  # username of submitter

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActivityLog(Base):
    """An audit record of something a user did in the hub.

    Examples: login, logout, register, verify_email, launch_dashboard,
    admin actions (create/update/delete dashboard, promote user).
    """

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    username = Column(String(64), nullable=True, index=True)  # who (by username) or None
    email = Column(String(255), nullable=True)
    action = Column(String(64), nullable=False, index=True)   # e.g. "launch_dashboard"
    detail = Column(Text, nullable=True)                      # human-readable context
    ip_address = Column(String(64), nullable=True)
