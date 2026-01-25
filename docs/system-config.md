# Tamor System Configuration

Last updated: 2026-01-25

## Hardware

| Component | Details |
|-----------|---------|
| System | ASUS Mini PC PN51-S1 |
| CPU | AMD Ryzen (k10temp sensor) |
| RAM | 62GB |
| Storage | WD Green SN350 1TB NVMe |
| OS | Ubuntu 22.04.5 LTS |
| Kernel | 6.8.0-90-generic |

## Architecture

```
Internet
    │
    ▼
Cloudflare Tunnel (cloudflared)
    │
    ▼ localhost:8080
Caddy (reverse proxy)
    │
    ├─ /api/*  ──────► gunicorn :5055 (Flask backend)
    ├─ /stremio/* ───► gunicorn :5055
    └─ /* ───────────► static files (ui/dist)
```

## Services

| Service | Port | Binding | Description |
|---------|------|---------|-------------|
| cloudflared | - | outbound | Cloudflare tunnel |
| caddy | 8080 | 0.0.0.0 | Reverse proxy + static files |
| tamor (gunicorn) | 5055 | 127.0.0.1 | Flask API backend |
| tamor-task-executor | - | - | Background task worker |

### Service Files

**tamor.service** (`/etc/systemd/system/tamor.service`)
```ini
[Unit]
Description=Tamor AI Backend Service
After=network.target

[Service]
Type=simple
User=tamor
WorkingDirectory=/home/tamor/tamor-core/api
Environment="PATH=/home/tamor/tamor-core/api/venv/bin"
EnvironmentFile=/home/tamor/tamor-core/api/.env
ExecStart=/home/tamor/tamor-core/api/venv/bin/gunicorn server:app -b 127.0.0.1:5055 -w 2 --timeout 120
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**tamor-task-executor.service** (`/etc/systemd/system/tamor-task-executor.service`)
```ini
[Unit]
Description=Tamor Task Executor
After=network.target tamor.service

[Service]
Type=simple
User=tamor
WorkingDirectory=/home/tamor/tamor-core
Environment=PYTHONPATH=/home/tamor/tamor-core/api
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/home/tamor/tamor-core/api/.env
ExecStart=/home/tamor/tamor-core/api/venv/bin/python -m api.workers.task_executor
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Caddy Configuration

Location: `/etc/caddy/Caddyfile`

```caddyfile
:8080 {
  # Security headers
  header {
    X-Content-Type-Options "nosniff"
    X-Frame-Options "SAMEORIGIN"
    Referrer-Policy "strict-origin-when-cross-origin"
    Permissions-Policy "geolocation=(), microphone=(), camera=()"
    -Server
  }

  # API (keep /api prefix intact)
  handle /api/* {
    reverse_proxy 127.0.0.1:5055
  }

  handle /stremio/* {
    reverse_proxy 127.0.0.1:5055
  }

  # UI (built SPA)
  handle {
    root * /home/tamor/tamor-core/ui/dist
    encode gzip zstd
    try_files {path} /index.html
    file_server
  }
}
```

## Cloudflare Tunnel

Location: `/etc/cloudflared/config.yml`

```yaml
tunnel: 4f8d8976-fe72-480d-8829-4651a7e2e166
credentials-file: /home/tamor/.cloudflared/4f8d8976-fe72-480d-8829-4651a7e2e166.json

ingress:
  - hostname: tamor.ashestoaltar.com
    service: http://localhost:8080

  - hostname: api.ashestoaltar.com
    service: http://localhost:5055

  - service: http_status:404
```

## Firewall (ufw)

```
Status: active
Default: deny (incoming), allow (outgoing), deny (routed)
```

No explicit rules needed - Cloudflare tunnel connects outbound.

## Cron Jobs

View with: `crontab -l`

| Schedule | Task | Log |
|----------|------|-----|
| `0 3 * * *` | Database + uploads backup | `logs/db_backup.log` |

## Key Paths

| Item | Path |
|------|------|
| Project root | `/home/tamor/tamor-core` |
| API code | `/home/tamor/tamor-core/api` |
| UI code | `/home/tamor/tamor-core/ui` |
| UI build | `/home/tamor/tamor-core/ui/dist` |
| Database | `/home/tamor/tamor-core/api/memory/tamor.db` |
| Backups | `/home/tamor/tamor-core/memory/backups` |
| Uploads | `/home/tamor/tamor-core/api/uploads` |
| Logs | `/home/tamor/tamor-core/logs` |
| Environment | `/home/tamor/tamor-core/api/.env` |
| Python venv | `/home/tamor/tamor-core/api/venv` |

## Monitoring Tools

| Tool | Status | Package |
|------|--------|---------|
| smartmontools | Installed | `smartmontools` |
| lm-sensors | Installed | `lm-sensors` |
| safety (Python audit) | Installed | `pip install safety` |

## Maintenance Scripts

| Script | Purpose |
|--------|---------|
| `scripts/backup_tamor_db.sh` | Database + uploads backup with 30-day retention |
| `scripts/health_check.sh` | Hardware health (disk, temps, memory, SMART) |
| `scripts/health_cron.sh` | Cron wrapper for health checks |

## Makefile Targets

```bash
make doctor      # App health (db, api, ui)
make audit       # Dependency vulnerabilities (Python + npm)
make health-hw   # Hardware health check
```

---

## Changelog

### 2026-01-25 - Maintenance & Security Audit

**Dependencies**
- Updated werkzeug 3.1.3 → 3.1.5 (CVE-2025-66221)
- Updated urllib3 2.5.0 → 2.6.3 (CVE-2025-66471, CVE-2025-66418)
- Updated filelock 3.20.0 → 3.20.3 (CVE-2025-68146)
- Migrated PyPDF2 3.0.1 → pypdf 6.6.1 (CVE-2023-36464 + 4 DoS fixes)
- Added `make audit` targets for vulnerability scanning

**Backups**
- Added 30-day retention policy
- Added uploads directory to backups

**Monitoring**
- Installed smartmontools and lm-sensors
- Created `scripts/health_check.sh` for hardware monitoring
- Added `make health-hw` target

**Services**
- Fixed tamor-task-executor (was crash-looping 160k+ times)
  - Issue: Wrong WorkingDirectory and missing PYTHONPATH
  - Fix: WorkingDirectory=/home/tamor/tamor-core, PYTHONPATH=/home/tamor/tamor-core/api
- Disabled tamor-ui-dev service (Vite dev server not needed, Caddy serves ui/dist)

**Security**
- Added Caddy security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- Verified firewall configuration (ufw: deny incoming by default)

**Documentation**
- Created `docs/maintenance-runbook.md`
- Created `docs/system-config.md` (this file)

**Updated**
- cloudflared 2025.11.1 → 2026.1.1
