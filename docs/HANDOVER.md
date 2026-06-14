# Ultimate Dashboard — Handover & Architecture Guide

This document is written for a developer **taking over the project**. It
explains what the app is, how it's built, how every piece fits together, how to
run/deploy it, and where to extend it. Read this top-to-bottom once and you
should be able to own the codebase.

Last updated: 2026-06-14.

---

## 1. What this is (and isn't)

**Ultimate Dashboard** is a centralized **Dashboard Hub**: a single web app that
links out to the software & validation teams' internal dashboards (document
automation, robot Wi-Fi identification, bug tracking, robot password management,
and any others added later).

Users log into the hub once, see all tools as cards, and **double-click a card
to open that tool in a new browser tab**. The hub only *provides access and
records usage* — it never embeds the other tools and is not a proxy.

**Explicitly out of scope:** the hub does **not** provide authentication,
authorization, or any security for the underlying dashboards. Each linked tool
keeps its own login and access control. The hub's own login governs only who can
use the hub.

### Core features
- Hub home with dashboards as cards, grouped by category.
- **Double-click (or focus+Enter) opens the tool in a new tab**; the launch is
  logged.
- **Light / dark theme** toggle. Dark mode is pure black/white/grey. The choice
  is **remembered per user** (stored on the account) and re-applied at next
  login on any device. New users default to light.
- **Hub login system** (separate from the linked tools):
  - Self-registration limited to allowed email domains (e.g. `haystackrobotics.com`).
  - **One account per email** (enforced by a unique constraint).
  - Email verification by **one-time code (OTP)** over SMTP.
  - User then sets a username + password.
- **Submit & approval workflow:** any user can submit a new dashboard (name,
  link, icon). It lands on the **Testing** page as `pending` until an **admin
  approves** it onto the main hub (or rejects it).
- **Account page:** change username or password; both require an emailed OTP
  (password change also requires the current password).
- **Admin area:** approve/reject submissions, add/edit/delete dashboards,
  promote/revoke admins, enable/disable users, and view recent activity.
- **Activity log** (SQLite/DB) of all user movement — logins, logouts, page
  views, submissions, approvals, launches, account changes, admin actions —
  keyed by username.
- **6-month data retention:** on startup, activity logs and OTPs older than
  ~182 days are purged automatically.
- **Crash-resistant:** unhandled errors and 404s render a friendly page instead
  of crashing; DB sessions roll back on error; startup tasks never abort boot.

---

## 2. Tech stack

| Concern | Choice |
| --- | --- |
| Web framework | **FastAPI** (Starlette under the hood) |
| Templating | **Jinja2** (server-rendered HTML) |
| Frontend | Vanilla **HTML / CSS / JS** (no build step) |
| ORM / DB | **SQLAlchemy 1.3** + **SQLite** (dev). Swappable to PostgreSQL/MySQL via `DATABASE_URL` |
| Sessions | Signed cookie via Starlette `SessionMiddleware` |
| Passwords | **bcrypt** (direct) |
| OTP hashing | SHA-256 (short-lived single-use codes) |
| Email | `smtplib` (STARTTLS) |
| Server | **uvicorn** |

Tested on Python 3.8. No frontend toolchain — assets are static files.

---

## 3. Directory layout

```
Ultimate Dashboard/
├── app/
│   ├── main.py            # FastAPI app: middleware, routers, exception handlers, startup
│   ├── config.py          # Settings loaded from .env (no hardcoded secrets/paths)
│   ├── database.py        # Engine, session, pooling, lightweight migrations
│   ├── models.py          # ORM models: User, OTP, Dashboard, ActivityLog
│   ├── security.py        # Password + OTP hashing/verification
│   ├── emailer.py         # SMTP OTP sending (fails soft)
│   ├── otp_service.py     # Issue + consume OTPs (shared by auth & account)
│   ├── auth.py            # Sessions + current-user / require_login / require_admin deps
│   ├── activity.py        # log_activity() helper
│   ├── maintenance.py     # purge_old_data() — 6-month retention
│   ├── seed.py            # Seed dashboards from dashboards.json on startup
│   ├── templating.py      # Shared Jinja2 instance + page_context()
│   └── routers/
│       ├── auth_routes.py       # register / verify / set-credentials / login / logout
│       ├── dashboard_routes.py  # hub home, testing page, submit, launch logging
│       ├── account_routes.py    # account page, theme persistence, change username/password
│       └── admin_routes.py      # approvals, dashboard CRUD, user/role management
├── templates/
│   ├── base.html          # Layout, header (logo), theme bootstrap, nav
│   ├── hub.html           # Main grid of approved dashboards
│   ├── testing.html       # Pending dashboards (double-click to try)
│   ├── submit_dashboard.html
│   ├── account.html
│   ├── admin.html
│   ├── login.html / register.html / verify.html / set_credentials.html
│   ├── error.html         # Friendly 404/500 page
│   └── partials/
│       └── logo_inline.html  # Inlined SVG logo (black fills -> currentColor)
├── static/
│   ├── css/styles.css     # Theme variables (light/dark) + all styling
│   ├── js/theme.js        # Theme toggle + per-user persistence
│   ├── js/hub.js          # Double-click launch + toast + launch logging
│   └── img/logo.svg       # Favicon / original logo
├── dashboards.json        # Seed list of dashboards
├── Logo Stacked-cropped.svg  # Source logo (processed into static/img + partial)
├── run.py                 # Convenience launcher (reads HOST/PORT/RELOAD)
├── requirements.txt
├── .env.example           # Config template (copy to .env per deployment)
├── .env                   # Real config for this machine (gitignored)
├── .gitignore
├── README.md              # Quick start
└── docs/HANDOVER.md       # This file
```

---

## 4. Data model (`app/models.py`)

### User
| Column | Notes |
| --- | --- |
| `id` | PK |
| `email` | **unique**, lowercased — this is the account identity (one per email) |
| `username` | unique, set after verification |
| `password_hash` | bcrypt |
| `is_verified` | email confirmed via OTP |
| `is_admin` | admin rights |
| `is_active` | disabled users can't log in |
| `theme_preference` | `"light"` / `"dark"`, default light |
| `created_at`, `last_login_at` | |

### OTP
Email verification codes. Stored **hashed** (`code_hash`), with `expires_at` and
`consumed`. Issuing a new code invalidates prior unconsumed ones for that email.

### Dashboard
A linked tool tile. Key fields: `name`, `url`, `icon`, `category`, `sort_order`,
`is_active`, and the approval workflow fields:
- `status`: `pending` | `approved` | `rejected` (constants in `models.py`).
- `submitted_by`: username of submitter (`system` for seeded, admin's name for admin-added).

Only `approved` + `is_active` tiles appear on the main hub. `pending` tiles
appear on the Testing page.

### ActivityLog
Audit trail: `timestamp`, `username`, `email`, `action`, `detail`, `ip_address`.
Written via `app/activity.py::log_activity()`. Action strings include
`login`, `logout`, `register_request`, `verify_email`, `account_created`,
`view_hub`, `view_testing`, `view_account`, `submit_dashboard`,
`admin_approve_dashboard`, `admin_reject_dashboard`, `launch_dashboard`,
`change_username`, `change_password`, `admin_*`, etc.

---

## 5. Key flows

### Registration → login
```
/register (email)  → issue OTP, email it      → redirect /verify
/verify (email,code) → consume OTP, mark verified → /set-credentials
/set-credentials (username,password) → create creds, log in → /
/login (username,password) → session cookie → /
/logout → clear session → /login
```
OTP logic lives in `app/otp_service.py` (`issue_otp`, `consume_otp`) and is
shared by registration and account changes.

### Submit → approve
```
User: /dashboards/submit → Dashboard(status=pending) → Testing page
Admin: /admin → Pending approvals → Approve (status=approved) → appears on hub
                                  → Reject  (status=rejected)
```

### Launch (double-click)
`static/js/hub.js` handles `dblclick` on a card: it opens the URL with
`window.open(url, "_blank")` **synchronously** (so popup blockers don't
interfere), shows a toast, and fires `POST /launch/{id}` to log the launch
(best-effort; logging failure never blocks the launch).

### Theme persistence
- `templates/base.html` sets `data-theme` before paint. Source of truth for a
  logged-in user is `user.theme_preference` (rendered server-side); anonymous
  visitors fall back to `localStorage` (default light).
- `static/js/theme.js` toggles the theme, writes `localStorage`, and — when
  logged in (`window.__LOGGED_IN__`) — `POST /account/theme` to persist it to
  the account.

### Logo recoloring (black → white in dark mode)
The source SVG uses `fill:#000000` for its line work and a few colored accent
fills. A build step (run once, see §9) rewrote **only the black fills** to
`fill:currentColor` and saved the result as `templates/partials/logo_inline.html`.
The header inlines that SVG; CSS sets `.brand-logo-wrap { color: #000 }` in light
mode and `#fff` in dark mode, so `currentColor` flips black↔white while the
colored accents stay untouched. Light mode shows the logo exactly as designed.

---

## 6. Configuration (`.env`)

All config comes from environment variables / `.env` (loaded in `app/config.py`).
**Nothing is hardcoded**, so the same code runs anywhere by editing `.env`.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs session cookies. Use a long random per-deployment value. |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated domains allowed to register. |
| `ADMIN_EMAILS` | Comma-separated emails that auto-become admins on registration. |
| `DATABASE_URL` | SQLAlchemy URL. SQLite by default; point at Postgres/MySQL in prod. |
| `OTP_TTL_MINUTES` | OTP validity window. |
| `DEBUG` | If `true`, OTPs are also printed to the server console (for local testing without SMTP). Keep `false` in prod. |
| `SMTP_SERVER` / `SMTP_PORT` / `SENDER_EMAIL` / `SENDER_PASSWORD` | Outgoing OTP email. |

Optional launcher vars (read by `run.py`): `HOST`, `PORT`, `RELOAD`.

---

## 7. Running locally

```bash
pip install -r requirements.txt
cp .env.example .env      # then edit values
python run.py             # http://localhost:8000
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Make yourself admin:** add your email to `ADMIN_EMAILS` *before* registering.

**Add dashboards:** edit `dashboards.json` (seeded on startup; existing tiles by
name are never overwritten) or use the Admin page.

---

## 8. Deployment to another server

The app is portable by design. On the target server:

1. Copy the project **excluding** `.env` and the `*.db` file.
2. `pip install -r requirements.txt`.
3. Create a fresh `.env` from `.env.example`:
   - new random `SECRET_KEY`,
   - correct `ALLOWED_EMAIL_DOMAINS` / `ADMIN_EMAILS`,
   - SMTP credentials,
   - for production, set `DATABASE_URL` to a real database (see §10).
4. Run behind a process manager (systemd) and reverse proxy (nginx) with HTTPS.
5. **Over HTTPS, set `https_only=True`** on the `SessionMiddleware` in
   `app/main.py`.

### Protecting the files on the server
The app code can't protect its own files from other OS users — do this at the OS
level:
- Run under a dedicated, unprivileged user (e.g. `ultdash`).
- `chown -R ultdash:ultdash` the project.
- `chmod 750` the project dir, `chmod 600 .env` (secrets readable only by the
  service user).
- Don't run it as root.

---

## 9. How the logo was processed (reproduce if the logo changes)

`templates/partials/logo_inline.html` and `static/img/logo.svg` are generated
from `Logo Stacked-cropped.svg`. To regenerate after a logo change:

```python
import re, shutil
raw = open("Logo Stacked-cropped.svg", encoding="utf-8").read()
shutil.copyfile("Logo Stacked-cropped.svg", "static/img/logo.svg")   # favicon (original)
inline = raw.replace("fill:#000000", "fill:currentColor")            # black -> theme color
inline = inline.replace(' style="max-height: 500px"', "")
inline = re.sub(r"<svg ", '<svg class="brand-logo" ', inline, count=1)
open("templates/partials/logo_inline.html", "w", encoding="utf-8").write(inline)
```
If the new logo encodes black differently (e.g. `fill="#000"` attribute instead
of `style="fill:#000000"`), adjust the replacement accordingly. Keep the colored
accents as real colors so they don't flip with the theme.

---

## 10. Database management & scaling

- **Dev:** SQLite file (`DATABASE_URL=sqlite:///./ultimate_dashboard.db`).
- **Production:** set `DATABASE_URL` to PostgreSQL/MySQL. The engine already
  enables `pool_pre_ping`, `pool_recycle`, and a connection pool for networked
  DBs (`app/database.py`). No code change needed to switch.
- **Schema changes:** `app/database.py` has a *lightweight migration* that adds
  missing columns **on SQLite only** (`_EXPECTED_COLUMNS`). For production
  databases, adopt **Alembic** for real migrations — add it to `requirements.txt`,
  `alembic init`, point it at `DATABASE_URL`, and generate revisions per schema
  change. The lightweight path is a stopgap for the embedded SQLite case.
- **Retention:** `app/maintenance.py::purge_old_data()` deletes activity logs and
  OTPs older than `RETENTION_DAYS` (182). Runs on startup. For a long-running
  server, also schedule it (cron / APScheduler) so it runs without restarts.
- **Sessions** roll back automatically on error (`get_db`), so a failed request
  never leaves a half-written transaction.

---

## 11. Extending the app (recipes)

- **Add a new page:** create a template, add a route in the relevant router (or a
  new router and `include_router` it in `main.py`), guard it with
  `Depends(require_login)` or `Depends(require_admin)`, and log a `view_*` action.
- **Add a logged action:** call `log_activity(db, "action_name", user=user,
  detail=..., ip_address=...)`.
- **Add a user/dashboard field:** add the column to `models.py`, then add it to
  `_EXPECTED_COLUMNS` in `database.py` (SQLite) and/or create an Alembic revision.
- **Add an activity-log viewer page:** query `ActivityLog` with filters/pagination
  and render a table (the admin page already shows the latest 50 as a starting
  point).
- **Per-dashboard visibility/permissions:** add an allow-list or role to
  `Dashboard` and filter in `dashboard_routes.hub`.

---

## 12. Security notes & limitations

- The hub's login is **for the hub only**; linked tools enforce their own
  security. Do not rely on the hub for their access control.
- OTP delivery depends on SMTP being reachable; failures are logged and (in
  `DEBUG`) printed. There's basic resend support; consider rate-limiting OTP
  requests before exposing publicly.
- Set `https_only=True` for cookies under HTTPS and serve only over TLS.
- `SECRET_KEY` and SMTP credentials are secrets — keep `.env` out of version
  control (it's gitignored) and locked down on the server.
- There is no CSRF token on form posts yet; behind a trusted internal network
  this is lower-risk, but add CSRF protection if exposing externally.

---

## 13. Quick reference — routes

| Method & path | Auth | Purpose |
| --- | --- | --- |
| `GET /` | login | Hub home (approved dashboards) |
| `GET /testing` | login | Pending dashboards |
| `GET/POST /dashboards/submit` | login | Submit a dashboard |
| `POST /launch/{id}` | login | Log a launch (browser opens the tab) |
| `GET /account` | login | Account settings |
| `POST /account/theme` | optional | Persist theme preference |
| `POST /account/request-code` | login | Email an OTP for account changes |
| `POST /account/username` | login | Change username (OTP) |
| `POST /account/password` | login | Change password (current pw + OTP) |
| `GET /register`,`POST /register` | public | Start registration |
| `GET /verify`,`POST /verify`,`POST /resend-otp` | public | Email verification |
| `GET/POST /set-credentials` | public (verified) | Set username/password |
| `GET /login`,`POST /login`,`POST /logout` | public/login | Session |
| `GET /admin` | admin | Admin dashboard |
| `POST /admin/dashboards/...` | admin | Create/update/delete/approve/reject |
| `POST /admin/users/{id}/set-admin`,`/set-active` | admin | Manage users |
| `GET /healthz` | public | Health check |
