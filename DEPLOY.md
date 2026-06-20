# DEPLOY.md — EC2 + S3 access cheatsheet (HAYSTACK Ultimate Toolkit)

Quick reference for accessing the cloud deployment. For project background &
architecture see [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) and
[docs/HANDOVER.md](docs/HANDOVER.md); for the running change log see
[history.md](history.md).

> ⚠️ Secrets (the `.pem`, `.env`, AWS keys) are **never** committed. Paths below
> point at where they live locally / on the box.

---

## Key facts

| Item | Value |
| --- | --- |
| EC2 instance ID | `i-0aa879e43b48ba029` |
| Region | `us-east-2` (Ohio) |
| Elastic IP | `18.227.41.213` |
| OS / login user | Ubuntu 24.04 / `ubuntu` |
| SSH key (local) | `/home/raghaventra/Downloads/Ultimate_Toolkit.pem` |
| Public domain | **`https://toolkit.haystack-robotics.com`** *(LIVE — HTTPS via Let's Encrypt)* |
| App dir (on box) | `/home/ubuntu/apps/ultimate-dashboard` |
| App service | `ultimate-dashboard` (uvicorn on `127.0.0.1:8000`) |
| Reverse proxy | Caddy, config `/etc/caddy/Caddyfile`, auto-HTTPS on `:443` |
| S3 bucket | `haystack-ultimate-toolkit` (us-east-2) |
| Instance IAM role | `ultimate-toolkit-ec2-role` (gives the box keyless S3 access) |

---

## 1. Access the EC2 instance

```bash
chmod 400 /home/raghaventra/Downloads/Ultimate_Toolkit.pem   # first time only
ssh -i /home/raghaventra/Downloads/Ultimate_Toolkit.pem ubuntu@18.227.41.213
```

Preview the app before DNS is live (tunnel localhost:8000 to your laptop):
```bash
ssh -i /home/raghaventra/Downloads/Ultimate_Toolkit.pem -L 8000:localhost:8000 ubuntu@18.227.41.213
# then open http://localhost:8000
```

### Manage the app (on the box)
```bash
sudo systemctl status  ultimate-dashboard
sudo systemctl restart ultimate-dashboard
sudo journalctl -u ultimate-dashboard -f          # live app logs
sudo journalctl -u caddy -f                        # live Caddy/TLS logs
curl -s http://127.0.0.1:8000/healthz              # -> {"status":"ok"}
```

### Redeploy app code (from the dev machine)
```bash
cd "/home/raghaventra/python/Ultimate Dashboard"
tar --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='.env' \
    --exclude='*.db' --exclude='.claude' -czf /tmp/ud.tar.gz .
scp -i /home/raghaventra/Downloads/Ultimate_Toolkit.pem /tmp/ud.tar.gz ubuntu@18.227.41.213:/tmp/
ssh -i /home/raghaventra/Downloads/Ultimate_Toolkit.pem ubuntu@18.227.41.213 '
  APP=/home/ubuntu/apps/ultimate-dashboard
  tar -xzf /tmp/ud.tar.gz -C "$APP"
  "$APP"/.venv/bin/pip install -q -r "$APP"/requirements.txt
  sudo systemctl restart ultimate-dashboard'
```
`.env` and `*.db` are excluded → accounts/data/secrets preserved across deploys.

---

## 2. Access the S3 bucket

**From the EC2 instance: no keys needed** — the instance role authenticates
automatically. Run these over SSH (or let the app use boto3 with no credentials):

```bash
aws sts get-caller-identity                                   # confirms the role
aws s3 ls   s3://haystack-ultimate-toolkit/
aws s3 cp   ./file.txt s3://haystack-ultimate-toolkit/path/   # upload
aws s3 cp   s3://haystack-ultimate-toolkit/path/file.txt ./   # download
aws s3 sync ./dir s3://haystack-ultimate-toolkit/dir/         # sync a folder (models/datasets)
aws s3 rm   s3://haystack-ultimate-toolkit/path/file.txt      # delete
```

**Storage convention** — keep EC2 lean, push the rest to S3:
- On EC2 (must be local to run): the app + what it actively serves.
- In S3 (cold/shared): DB backups (`backups/`), ML models & datasets (`models/`),
  deploy bundles, large generated artifacts.

**From a laptop** (optional): the instance role does NOT apply. Install AWS CLI and
`aws configure` with an IAM user's access key that has the `ultimate-toolkit-s3`
policy. Prefer using the instance for S3 ops to avoid long-lived keys.

---

## 2b. Database & backups

The app DB is **SQLite** on the box (`/home/ubuntu/apps/ultimate-dashboard/
ultimate_dashboard.db`), in **WAL mode** for concurrent access. Tables: `users`,
`dashboards`, `otps`, `activity_logs` (the audit/history trail). The live DB must
stay on local disk (SQLite can't run off S3) — only **backups** go to S3.

- **Automated:** a cron (ubuntu user, `crontab -l`) runs `scripts/backup_db.py`
  **daily at 02:30 UTC** → consistent `VACUUM INTO` snapshot →
  `s3://haystack-ultimate-toolkit/backups/ultimate_dashboard-<UTC>.db` (keeps 30).
- **Back up now:** `cd ~/apps/ultimate-dashboard && .venv/bin/python -m scripts.backup_db`
- **List backups:** `aws s3 ls s3://haystack-ultimate-toolkit/backups/`
- **Restore** a snapshot:
  ```bash
  sudo systemctl stop ultimate-dashboard
  cd ~/apps/ultimate-dashboard
  aws s3 cp s3://haystack-ultimate-toolkit/backups/<file>.db ./ultimate_dashboard.db
  sudo systemctl start ultimate-dashboard
  ```
- **Read the activity log** (not shown in the UI):
  `.venv/bin/python -c "from app.database import SessionLocal; from app.models import ActivityLog; d=SessionLocal(); [print(a.timestamp,a.username,a.action,a.detail or '') for a in d.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(100)]"`

---

## 3. Multi-dashboard model (one EC2, many ports behind Caddy)

- Each dashboard binds to **`127.0.0.1:<port>`** (localhost only) and is exposed by
  Caddy at a URL path — so only ports **22/80/443** are open publicly.
- Port assignments + deploy steps: `/opt/dashboards/PORT-REGISTRY.md` (on the box).
- Onboard a teammate: `sudo add-teammate.sh <user> "<their-ssh-public-key>"`.
- systemd template for a new dashboard: `/opt/dashboards/dashboard.service.template`.
- After adding a tool: add its route in `/etc/caddy/Caddyfile`,
  `sudo systemctl reload caddy`, then add the tile in the Toolkit **Admin** page.
- **Streamlit apps** (and any app that emits root-absolute asset/websocket URLs):
  start it with `--server.baseUrlPath /<category>/<name>` and bind
  `--server.address 127.0.0.1`, and use Caddy **`handle`** (preserves the prefix),
  **not** `handle_path` (which strips it). Stripping breaks Streamlit's `/static`
  and `/_stcore/stream` websocket. Working example: Document Automation on `:5555`
  → `/productivity/document-automation` (see the Caddyfile).
- **Live tools:** Document Automation (`software-doc-generator.service`, Streamlit
  `:5555`) → `/productivity/document-automation`.

---

## 4. Pending / housekeeping

- [x] **DNS:** `A  toolkit.haystack-robotics.com → 18.227.41.213` is live; Caddy
      issued the Let's Encrypt cert (valid through ~Sep 2026, auto-renews).
      Note: web domain is `haystack-robotics.com` (hyphen); registration email
      allowlist is `haystackrobotics.com` (no hyphen) — intentional, different things.
- [ ] **Rotate the Gmail app password** in `.env` (`SENDER_PASSWORD`) — the current
      one was shared in plaintext during setup — then `sudo systemctl restart ultimate-dashboard`.
- Security group currently allows inbound 22, 80, 443 (correct).
