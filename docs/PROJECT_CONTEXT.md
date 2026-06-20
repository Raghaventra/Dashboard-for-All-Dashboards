# Project Context & Running Log — HAYSTACK Ultimate Toolkit

**Read this first if you're picking up the project in a new chat/session.** It
explains what this is, every significant decision and *why*, the current live
state. Keep it updated after **every** change.

> Companion docs: [HANDOVER.md](HANDOVER.md) (architecture deep-dive) ·
> [../DEPLOY.md](../DEPLOY.md) (cloud ops cheatsheet) ·
> [../history.md](../history.md) (the running change log — **update it every session**).

---

## 1. What this is

A centralized **Dashboard Hub** ("HAYSTACK Ultimate Toolkit") for the software &
validation teams. One page links out to all the internal tools (document
automation, robot Wi-Fi/IP, bug tracking, robot password mgmt, RViz automation,
Agent Haystack, …). Users **double-click a tile to open the tool in the same
tab**; the hub only provides access + records usage. It does **not** secure the
underlying tools — each keeps its own auth.

For global access the target architecture puts the Toolkit and its tools on one
**EC2 instance (one Elastic IP, many ports)** behind a **Caddy** reverse proxy,
so tools open under clean paths like
`toolkit.haystack-robotics.com/productivity/document-automation` instead of raw
`IP:port` URLs. See [../DEPLOY.md](../DEPLOY.md) and the root `Caddyfile`.

## 2. Current live state (production = AWS)

Production is now **AWS EC2 + S3**. The office-server deploy (`10.150.0.218`) was
**decommissioned** on 2026-06-20. Full cloud cheatsheet: [DEPLOY.md](../DEPLOY.md).

| | |
| --- | --- |
| **URL** | **https://toolkit.haystack-robotics.com** (real Let's Encrypt TLS via Caddy) |
| Host | EC2 `i-0aa879e43b48ba029`, Elastic IP `18.227.41.213`, us-east-2, Ubuntu 24.04 |
| SSH | `ssh -i /home/raghaventra/Downloads/Ultimate_Toolkit.pem ubuntu@18.227.41.213` |
| Runs as | systemd `ultimate-dashboard`, uvicorn on `127.0.0.1:8000` behind **Caddy** (:443) |
| App dir | `/home/ubuntu/apps/ultimate-dashboard` |
| DB | SQLite `ultimate_dashboard.db` in the app dir |
| Image storage | **S3 bucket `haystack-ultimate-toolkit`** (us-east-2), keyless via instance role `ultimate-toolkit-ec2-role` |
| Deploy | tar → scp (with the `.pem`) → extract → `pip install -r` → restart (see DEPLOY.md) |

## 3. Tech stack

FastAPI + Jinja2 (server-rendered) + vanilla JS/CSS · SQLAlchemy + SQLite ·
bcrypt · uvicorn. No frontend build step. Dev machine runs older libs
(SQLAlchemy 1.3, Starlette 0.44); the **server runs newer** (SQLAlchemy 2.0,
Starlette 1.3, bcrypt 5) — code is written to run on both.

## 4. Key decisions & why

- **Hub has its own login** (company-email registration → emailed OTP → set
  username/password). Restricted to `@haystackrobotics.com`. *Why:* need to know
  who launched what, and gate access, without touching the underlying tools.
- **Admins via allowlist** (`ADMIN_EMAILS` in `.env`) — auto-granted on
  registration. *Why:* only a few should manage tiles/users.
- **Light/dark theme, remembered per user.** Dark mode is pure black/white/grey
  (user requirement). `localStorage` is the instant source of truth (no
  flicker/flash on navigation); the server copy syncs across devices. *Why:* an
  earlier bug where the theme reverted on navigation — fixed by localStorage-first
  + `color-scheme` to kill the inter-page white flash.
- **Served on port 8000, no nginx.** Originally nginx on 443, but the server's
  `ufw` firewall blocks 80/443 while **already allowing 8000** (other tools use
  high ports). To avoid any firewall change (which could break sibling services
  or SSH), uvicorn serves TLS itself on 8000. *Why:* "users just type the link,
  no laptop changes, don't touch the firewall."
- **Self-signed TLS.** No public domain for an internal IP → self-signed cert →
  one-time browser warning. Encryption still protects passwords/OTPs on the LAN.
- **Connected sidebar shell.** Brand + sidebar form one solid column (a SOLID
  `--panel` colour, *not* frosted glass). *Why:* a glass header tinted lighter
  when content scrolled behind it while the sidebar stayed dark, breaking the
  seam between them — solid fixes it permanently.
- **Activity log NOT shown in the web UI.** Logging still writes to the DB, but
  the admin page no longer displays it. *Why:* user wants it visible only to
  someone with local/server access. See §6 for how to read it.
- **Tile logos** can be an emoji, an image path (`/static/img/x.png`, shown
  cover), or the special value `brand` (renders the inline brand SVG with
  `currentColor` so it's black in light / white in dark, no background box).

## 5. Current dashboards (seeded from `dashboards.json`)

Links are now **relative proxied paths** (served behind Caddy on EC2 — see §1);
Bug Tracking keeps its own public domain and RViz is still a placeholder.

| Name | Category | Link | Upstream | Icon |
| --- | --- | --- | --- | --- |
| Document Automation | Productivity | `/productivity/document-automation` | localhost:5555 | 📄 |
| Robot Wi-Fi Identification | Robotics | `/robotics/wifi-identification` | localhost:9999 | 📶 |
| Agent Haystack | Robotics | `/robotics/agent-haystack` | localhost:8765 (now 54.144.1.169:8765) | `brand` (cube logo) |
| Robot Password Management | Robotics | `/robotics/password-management` | localhost:8104 *(placeholder)* | 🔐 |
| Bug Tracking | Engineering | https://bugtracker.haystackrobots.com/ | — *(already public)* | 🐞 |
| Ultimate RviZ Automation | Engineering | `#` *(under construction)* | — | splash.png |

`dashboards.json` seeds new tiles by name on startup; it never overwrites
existing rows, so edit live ones via the Admin page or a DB update + restart.

## 6. Admins & viewing the activity log

**Admins (`ADMIN_EMAILS`):** dinakaran, arunkumar.b, syed.abu, ponmeganathan.s,
arunkumar.g, raghaventra, sugin.r — all `@haystackrobotics.com`.

**Read the activity log** (server access only, since it's no longer in the UI):
```bash
ssh haystack@10.150.0.218
cd /home/haystack/apps/ultimate-dashboard
.venv/bin/python -c "
from app.database import SessionLocal
from app.models import ActivityLog
db=SessionLocal()
for a in db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(100):
    print(a.timestamp, a.username, a.action, a.detail or '')
db.close()"
```

## 7. How to make changes & deploy (the workflow)

1. Edit the working copy on the dev machine: `/home/raghaventra/python/Ultimate Dashboard`.
2. Test locally (`python3 run.py`, or the TestClient/Playwright checks).
3. Bundle changed files and push (server has **no gzip CLI** → extract with Python):
   ```bash
   tar -czf /tmp/ud.tar.gz <changed files...>
   scp /tmp/ud.tar.gz haystack@10.150.0.218:/tmp/ud.tar.gz
   ssh haystack@10.150.0.218 '
     APP=/home/haystack/apps/ultimate-dashboard
     python3 -c "import tarfile; tarfile.open(\"/tmp/ud.tar.gz\").extractall(\"$APP\")"
     sudo systemctl restart ultimate-dashboard'
   ```
4. `.env`, the SQLite DB, and `certs/` are excluded → preserved across deploys.
5. CSS/JS/template-only changes need no restart (static), but restarting is safe.
   Changing `dashboards.json` needs a restart to re-seed new tiles.
6. **Update this document** (§8 changelog) with what changed and why.

(SSH password is `server@123`; `sudo` uses the same. The dev machine reaches the
server with `sshpass`.)

## 8. Change history

The full dated change log — what was done, errors found, and how they were
fixed — lives in **[../history.md](../history.md)**. Update it every session
(it's an admin order, stated at the top of that file).

---

*Maintainers: keep §2 (live state), §5 (dashboards), and §6 (admins) current, and
log every change in [../history.md](../history.md).*
