"""Data retention: delete records older than a cutoff (default 6 months).

Runs on startup. Applies to the activity log and spent OTPs — never to users
or dashboards.
"""
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import ActivityLog, OTP

RETENTION_DAYS = 182  # ~6 months


def purge_old_data(days: int = RETENTION_DAYS) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    db = SessionLocal()
    try:
        logs_deleted = (
            db.query(ActivityLog)
            .filter(ActivityLog.timestamp < cutoff)
            .delete(synchronize_session=False)
        )
        otps_deleted = (
            db.query(OTP)
            .filter(OTP.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        if logs_deleted or otps_deleted:
            print(f"[maintenance] Purged {logs_deleted} activity log(s) and "
                  f"{otps_deleted} OTP(s) older than {days} days.")
        return {"logs_deleted": logs_deleted, "otps_deleted": otps_deleted}
    finally:
        db.close()
