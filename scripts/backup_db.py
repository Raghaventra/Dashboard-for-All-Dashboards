"""Back up the SQLite database to S3.

Takes a *consistent* snapshot with `VACUUM INTO` (safe even while the app is
running and even under WAL), uploads it to
``s3://<bucket>/backups/ultimate_dashboard-<UTC timestamp>.db``, and prunes old
backups so only the most recent KEEP_BACKUPS remain.

Run from the app dir:  .venv/bin/python -m scripts.backup_db
Scheduled via cron (see DEPLOY.md §2b).
"""
import datetime
import os
import sqlite3
import tempfile

import boto3

from app.config import settings

KEEP_BACKUPS = 30  # keep the latest N snapshots in S3


def _db_path() -> str:
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        raise SystemExit("backup_db only supports SQLite.")
    path = url.split("sqlite:///")[-1]
    if path.startswith("./"):
        path = path[2:]
    return path if os.path.isabs(path) else str(settings.BASE_DIR / path)


def main() -> None:
    if not settings.S3_BUCKET:
        raise SystemExit("S3_BUCKET is not set — nothing to back up to.")

    db_file = _db_path()
    if not os.path.exists(db_file):
        raise SystemExit(f"Database not found: {db_file}")

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    key = f"backups/ultimate_dashboard-{ts}.db"

    # Consistent single-file snapshot (includes WAL contents).
    tmp = tempfile.mktemp(suffix=".db")
    src = sqlite3.connect(db_file)
    try:
        src.execute("VACUUM INTO ?", (tmp,))
    finally:
        src.close()

    s3 = boto3.client("s3", region_name=settings.S3_REGION)
    s3.upload_file(tmp, settings.S3_BUCKET, key,
                   ExtraArgs={"ContentType": "application/x-sqlite3"})
    os.remove(tmp)
    print(f"[backup] uploaded s3://{settings.S3_BUCKET}/{key}")

    # Prune: keep only the most recent KEEP_BACKUPS.
    resp = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="backups/")
    objs = sorted(resp.get("Contents", []), key=lambda o: o["Key"])
    old = objs[:-KEEP_BACKUPS] if len(objs) > KEEP_BACKUPS else []
    for o in old:
        s3.delete_object(Bucket=settings.S3_BUCKET, Key=o["Key"])
    if old:
        print(f"[backup] pruned {len(old)} old backup(s)")


if __name__ == "__main__":
    main()
