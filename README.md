# Ultimate Dashboard

A centralized **Dashboard Hub** — a single entry point that links out to the
software & validation teams' internal web dashboards (document automation,
robot Wi-Fi identification, bug tracking, robot password management, …).

Instead of remembering many URLs and switching between separate interfaces,
users open one hub and **double-click a tool to launch it in a new browser tab**.
Every launch and login is recorded in an activity log for basic auditability.

> The hub does **not** provide security for the underlying dashboards. Each of
> those keeps its own authentication and access control. The login here only
> governs who can use the hub itself.

## Features

- **Hub home** — dashboards shown as cards grouped by category; **double-click**
  (or focus + Enter) opens the tool in a **new tab**, never inside the hub.
- **Light / dark theme** toggle, **remembered per user account** (re-applied at
  next login on any device; new users default to light). Dark mode is pure
  black / white / grey, and the header logo's black lines turn white in dark mode.
- **Submit & approve workflow** — any user can submit a dashboard (name, link,
  icon). It lands in the **Testing** page until an **admin approves** it onto
  the main Hub (or rejects it).
- **Account page** — change username or password; both require an **email OTP**
  (and password change also requires the current password).
- **6-month data retention** — on startup, activity logs and OTPs older than
  ~6 months are automatically purged.
- **Account system** for the hub:
  - Self-registration restricted to allowed email domains (e.g. `haystackrobotics.com`).
  - Email verification via a **one-time code (OTP)** sent over SMTP.
  - User then sets a **username + password** for login.
- **Admin area** (for selected users):
  - Add / edit / delete dashboards.
  - Promote/revoke admins, enable/disable users.
  - View recent activity.
- **Activity log** stored in SQLite (login, logout, register, verify,
  dashboard launches, admin actions) keyed by username.
- **Fully env-configurable** — no hardcoded paths or secrets, so the same code
  deploys to any server by editing `.env`.

## Tech stack

FastAPI + Jinja2 templates + vanilla JS/CSS, SQLAlchemy + SQLite, bcrypt.

> **Taking over the project?** Read [docs/HANDOVER.md](docs/HANDOVER.md) — a full
> architecture, data-model, flow, deployment, and extension guide.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
#    then edit .env — set SECRET_KEY, ALLOWED_EMAIL_DOMAINS, ADMIN_EMAILS,
#    and the SMTP_* / SENDER_* email settings.

# 3. Run
python run.py
#    or: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>.

## Configuration (.env)

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs session cookies. Use a long random string per deployment. |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated domains allowed to register. |
| `ADMIN_EMAILS` | Comma-separated emails that become admins automatically on registration. |
| `DATABASE_URL` | SQLAlchemy URL. Defaults to a local SQLite file. |
| `OTP_TTL_MINUTES` | How long an emailed code stays valid. |
| `DEBUG` | If `true`, OTP codes are also printed to the server console (handy when SMTP is unreachable). |
| `SMTP_SERVER` / `SMTP_PORT` / `SENDER_EMAIL` / `SENDER_PASSWORD` | Outgoing email for OTPs. |

## First admin

Add your email to `ADMIN_EMAILS` in `.env` **before** registering, e.g.:

```
ADMIN_EMAILS=varun.ram@haystackrobotics.com
```

That account becomes an admin on registration and can then promote others from
the Admin page.

## Managing the dashboard list

- **Seed file**: `dashboards.json` is loaded on startup. New entries (matched by
  name) are added; existing ones are left alone so UI edits aren't overwritten.
- **Admin UI**: add / edit / delete dashboards at `/admin`.

## Deploying to another server

1. Copy the project (excluding `.env` and the `*.db` file).
2. `pip install -r requirements.txt`.
3. Create a fresh `.env` from `.env.example` with that server's values
   (new `SECRET_KEY`, correct domains/admins, SMTP creds).
4. Run behind a process manager / reverse proxy. Set `https_only=True` for the
   session cookie in `app/main.py` when served over HTTPS.

## Project layout

```
app/
  main.py            # FastAPI app, middleware, startup
  config.py          # env-driven settings
  database.py        # SQLAlchemy engine/session
  models.py          # User, OTP, Dashboard, ActivityLog
  security.py        # password & OTP hashing
  emailer.py         # SMTP OTP sending
  auth.py            # sessions + current-user dependencies
  activity.py        # activity-log helper
  seed.py            # seed dashboards from dashboards.json
  templating.py      # shared Jinja2 instance
  routers/
    auth_routes.py       # register/verify/set-credentials/login/logout
    dashboard_routes.py  # hub home + launch logging
    admin_routes.py      # dashboards + users + activity
templates/           # Jinja2 HTML
static/              # css + js
dashboards.json      # seed list of dashboards
.env.example         # configuration template
run.py               # convenience launcher
```
