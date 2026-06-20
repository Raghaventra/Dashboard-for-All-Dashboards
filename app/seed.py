"""Seed the dashboards table from dashboards.json on first run.

Existing dashboards (matched by name) are left untouched so admin edits made
through the UI are never overwritten. New entries in the file are added.
"""
import json

from app.config import settings
from app.database import SessionLocal
from app.models import STATUS_APPROVED, Dashboard


def seed_dashboards() -> None:
    seed_file = settings.DASHBOARDS_SEED_FILE
    if not seed_file.exists():
        return

    try:
        items = json.loads(seed_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[seed] Could not read {seed_file}: {exc}")
        return

    db = SessionLocal()
    try:
        existing_names = {d.name for d in db.query(Dashboard.name).all()}
        added = 0
        for item in items:
            name = (item.get("name") or "").strip()
            url = (item.get("url") or "").strip()
            if not name or not url or name in existing_names:
                continue
            db.add(
                Dashboard(
                    name=name,
                    url=url,
                    description=item.get("description"),
                    icon=item.get("icon"),
                    category=item.get("category"),
                    sort_order=int(item.get("sort_order", 0) or 0),
                    is_active=True,
                    status=STATUS_APPROVED,  # seeded dashboards go straight to the main page
                    submitted_by=item.get("submitted_by") or "system",
                )
            )
            existing_names.add(name)
            added += 1
        if added:
            db.commit()
            print(f"[seed] Added {added} dashboard(s) from {seed_file.name}")
    finally:
        db.close()
