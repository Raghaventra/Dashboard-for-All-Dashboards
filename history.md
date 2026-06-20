# Project History — HAYSTACK Ultimate Toolkit

> ## ⛔ ADMIN ORDER — READ FIRST (mandatory for every chat / contributor)
> **You MUST update this file at the end of every working session.** This is a
> direct order from the admin, not optional. For each change you make, add a
> dated entry at the **top** of the log below recording:
> 1. **What you did** (the change/feature),
> 2. **What errors/bugs you hit** (be honest — include the ones you caused), and
> 3. **How you fixed them**.
>
> Keep entries short and factual. Newest entry on top. If you found no errors,
> say "no errors". This is the single source of truth for project history.

---

## Log (newest first)

### 2026-06-20 — Package cleanup + history.md
- **Did:** Renamed lingering "Ultimate Dashboard" → "Ultimate Toolkit" in docs
  (the app/UI was already "HAYSTACK Ultimate Toolkit"). Removed redundant/stale
  files: `docs/DEPLOYMENT.md` (old office-server doc — that server was
  decommissioned), root `splash.png` (duplicate of `static/img/splash.png`),
  `push.txt` (scratch git notes). Created this `history.md`.
- **Errors:** None. Left operational names (`ultimate-dashboard` service,
  `ultimate_dashboard.db`, app dir, logger) unchanged on purpose — renaming them
  would break the live EC2 deploy and the `DATABASE_URL`.

### 2026-06-20 — Disk full → grew EBS volume
- **Did:** Reclaimed ~730 MB of junk (AWS-CLI installer leftovers in `/tmp`, apt
  & pip caches). Grew the EBS root volume **8 GiB → 25 GiB** (admin did the
  console Modify; I ran `growpart` + `resize2fs`). Now 24 GB FS, 18 GB free.
- **Error found:** EC2 root disk was **100% full** (42 MB free) — a real risk to
  DB writes/logs. **Fix:** cache cleanup + volume grow (online, no downtime).
- **Note:** instance role is S3-only (can't modify volumes), so the resize had to
  be initiated by an admin in the AWS console.

### 2026-06-20 — DB hardening + S3 backups
- **Did:** Enabled SQLite **WAL** mode (+ `busy_timeout=5000`,
  `synchronous=NORMAL`) for safe concurrent reads/writes. Added
  `scripts/backup_db.py` — consistent `VACUUM INTO` snapshot → S3
  `backups/` (keeps 30), daily cron 02:30 UTC.
- **Errors:** (1) cron install aborted under `set -e` when the crontab was empty
  → fixed with `|| true` + filtered rebuild. (2) `datetime.utcnow()` deprecation
  warning → switched to timezone-aware UTC.

### 2026-06-20 — Fixes + full responsiveness
- **Did:** "Click any tool" copy (dropped "double-click"); Creator-name field on
  Submit; creators set per dashboard; "Preview" placeholder in upload box; mobile/
  tablet responsive layout (compact header + horizontal scroll nav, 1-col grid).
- **Errors found & fixed:**
  - **Faded tile after browser Back** — the `.launching` (dimmed) class survived
    the bfcache restore. Fixed by clearing it on `pageshow`.
  - **Admin "Active" un-tick didn't save** — checkbox default was `Form("on")`,
    and browsers omit unchecked boxes, so it could never turn off. Fixed by
    defaulting to `"off"`.

### 2026-06-20 — Single-click, creators, image uploads (S3)
- **Did:** Single-click to open tiles; "Created by: <name>" on cards; **image
  uploads with square-only cropping** (Cropper.js, ≤5 MB; Pillow re-crops to a
  512×512 JPEG server-side). New `app/storage.py` → S3 on EC2 (keyless via
  instance role) / local `uploads/` in dev, served via `/media/{key}` (private
  bucket). Profile pictures + dashboard image logos. Decommissioned the office
  server.
- **Errors:** Forced-square handled server-side so a bypassed client can't upload
  non-square/oversized. No other issues.

### ~2026-06-18–20 — Migrated to AWS (EC2 + Caddy + S3) & went live
- **Did:** Moved production off the office server to **EC2** `i-0aa879e43b48ba029`
  (us-east-2, Elastic IP `18.227.41.213`) behind **Caddy** (auto Let's Encrypt).
  Tiles open in the **same tab** under clean proxied paths
  (`/productivity/document-automation`, …). DNS
  `toolkit.haystack-robotics.com` live.
- **Error found:** domain mismatch — web domain is `haystack-robotics.com`
  (hyphen) but the email allowlist is `haystackrobotics.com` (no hyphen). These
  are intentionally different; corrected the Caddy site name accordingly.
- **Still to do:** rotate the Gmail app password (was shared in plaintext during
  setup).

### 2026-06-15 — Initial build, deploy, polish
- **Did:** Built the hub — email+OTP auth, admin area, submit/approve workflow,
  light/dark theme (remembered per user), activity log, 6-month auto-purge.
  Renamed to **HAYSTACK Ultimate Toolkit** with the two-line brand lockup. Added
  the RViz Automation and Agent Haystack tiles. First deployed to the office
  server `10.150.0.218`; set 7 admins.
- **Errors found & fixed:**
  - **Theme reverted / white-flashed on navigation** — server-pref was preferred
    over localStorage and a Jinja auto-escape turned the bootstrap JS quotes into
    `&#34;` (broke the script). Fixed: localStorage-first + `color-scheme`, and
    quote the value literally in the template.
  - **Hub vs Testing header mismatch** — the glass header tinted lighter as
    content scrolled behind it while the sidebar stayed dark. Fixed by making the
    shell a **solid** panel.
  - **Site unreachable externally** — office-server `ufw` blocked 80/443. Fixed by
    serving HTTPS directly on the already-open port 8000 (no firewall change).
  - **Dark-mode delete button illegible** (white-on-grey) — added a proper red
    `#ff453a` override in dark mode.
  - **Newer server libs** (SQLAlchemy 2.0 / Starlette 1.3) changed the
    `TemplateResponse` signature → added a compatibility shim in
    `app/templating.py`.
