# Tamor Maintenance Runbook

Last updated: 2026-01-25

## Quick Reference

```bash
# Health checks
make health-hw          # Hardware health (disk, temps, memory)
make audit              # Dependency vulnerabilities
make doctor             # App health (db, api, ui)

# Manual backups
./scripts/backup_tamor_db.sh

# View logs
tail -50 logs/health_check.log
tail -50 logs/db_backup.log
```

---

## Automated Tasks (Cron)

These run automatically. Verify they're still active with `crontab -l`.

| Schedule | Task | Log |
|----------|------|-----|
| Daily 3am | Database + uploads backup | `logs/db_backup.log` |
| Daily 8am | Health check (if configured) | `logs/health_check.log` |

---

## Weekly Checks

Run these manually once a week (suggest: Monday morning).

### 1. Dependency Vulnerabilities

```bash
make audit
```

If vulnerabilities found:
1. Check severity (DoS vs RCE)
2. Update `requirements.txt` or `package.json`
3. Test locally before deploying
4. Commit and push changes

### 2. System Updates

```bash
# Check pending updates
apt list --upgradable

# Apply updates (requires sudo)
sudo apt update && sudo apt upgrade
```

### 3. Disk Space

```bash
df -h /
```

Warning threshold: 80%. Critical: 90%.

### 4. Review Logs

```bash
# Backup logs - verify daily backups running
tail -20 logs/db_backup.log

# Health logs - check for warnings
grep -E "WARNING|CRITICAL" logs/health_check.log | tail -20

# Application errors
journalctl -u tamor --since "1 week ago" | grep -i error | tail -20
```

---

## Monthly Checks

### 1. Full Health Audit

```bash
# Run all checks
make health-hw
make audit
make doctor

# Check SMART disk health (requires sudo)
sudo smartctl -a /dev/nvme0n1 | grep -E "Percentage Used|Power On Hours|Unsafe Shutdowns"
```

### 2. Backup Verification

```bash
# List recent backups
ls -lh memory/backups/ | tail -10

# Verify backup integrity (pick a recent one)
sqlite3 memory/backups/tamor_YYYYMMDD_HHMMSS.db "PRAGMA integrity_check;"

# Verify uploads backup
tar -tzf memory/backups/uploads_YYYYMMDD_HHMMSS.tar.gz | head -10
```

### 3. Security Review

```bash
# Check firewall status
sudo ufw status

# Check for failed login attempts
sudo grep "Failed password" /var/log/auth.log | tail -20

# Check listening ports (look for unexpected services)
ss -tlnp | grep LISTEN
```

### 4. Database Maintenance

```bash
# Check database size
ls -lh api/memory/tamor.db

# Optimize database (optional, run during low usage)
sqlite3 api/memory/tamor.db "VACUUM;"
sqlite3 api/memory/tamor.db "ANALYZE;"
```

---

## Quarterly Checks

### 1. Backup Restore Test

Critical: Verify you can actually restore from backup.

```bash
# Copy a recent backup to temp location
cp memory/backups/tamor_YYYYMMDD_HHMMSS.db /tmp/test_restore.db

# Verify it opens and has data
sqlite3 /tmp/test_restore.db "SELECT COUNT(*) FROM messages;"
sqlite3 /tmp/test_restore.db "SELECT COUNT(*) FROM memories;"

# Clean up
rm /tmp/test_restore.db
```

### 2. Full Dependency Update

```bash
# Check for outdated Python packages
pip list --outdated

# Check for outdated npm packages
cd ui && npm outdated

# Update and test thoroughly before deploying
```

### 3. Review Access

```bash
# Check users with shell access
grep -E "bash|sh$" /etc/passwd | grep -v nologin

# Check SSH authorized keys
cat ~/.ssh/authorized_keys

# Check sudo access
sudo cat /etc/sudoers.d/*
```

### 4. SSL Certificate Check

If using HTTPS (via Caddy or other):

```bash
# Check certificate expiry
echo | openssl s_client -servername your-domain.com -connect localhost:443 2>/dev/null | openssl x509 -noout -dates
```

---

## Emergency Procedures

### Service Not Responding

```bash
# Check if services are running
systemctl status tamor
ps aux | grep gunicorn
ps aux | grep node

# Restart services
sudo systemctl restart tamor

# Check logs for errors
journalctl -u tamor --since "1 hour ago"
```

### Disk Full

```bash
# Find large files
sudo du -h / | sort -rh | head -20

# Clear old backups (keep at least 7 days)
find memory/backups/ -name "*.db" -mtime +7 -delete

# Clear old logs
find logs/ -name "*.log" -size +100M -exec truncate -s 0 {} \;

# Clear apt cache
sudo apt clean
```

### Database Corruption

```bash
# Check integrity
sqlite3 api/memory/tamor.db "PRAGMA integrity_check;"

# If corrupted, restore from backup:
# 1. Stop the service
sudo systemctl stop tamor

# 2. Backup the corrupted file (for analysis)
mv api/memory/tamor.db api/memory/tamor.db.corrupted

# 3. Restore from most recent backup
cp memory/backups/tamor_YYYYMMDD_HHMMSS.db api/memory/tamor.db

# 4. Restart service
sudo systemctl start tamor
```

### Security Incident

1. **Isolate**: Disconnect from network if actively compromised
2. **Preserve**: Don't delete logs - copy them for analysis
3. **Assess**: Check auth.log, journalctl, and application logs
4. **Rotate**: Change all API keys (OpenAI, TMDB, etc.)
5. **Restore**: If needed, restore from known-good backup

---

## Configuration Reference

### Key Paths

| Item | Path |
|------|------|
| Database | `api/memory/tamor.db` |
| Backups | `memory/backups/` |
| Uploads | `api/uploads/` |
| Logs | `logs/` |
| Config | `api/.env` |
| Scripts | `scripts/` |

### Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Disk usage | 80% | 90% |
| Temperature | 75°C | 85°C |
| Backup age | 2 days | 7 days |

### Ports

| Port | Service | Binding |
|------|---------|---------|
| 5055 | Tamor API (gunicorn) | localhost |
| 5173 | Tamor UI (Vite) | localhost |
| 8080 | Reverse proxy | all interfaces |
| 22 | SSH | all interfaces |

---

## Secrets Rotation Schedule

Rotate these periodically (suggest: every 6 months or after any suspected breach).

| Secret | Location | How to Rotate |
|--------|----------|---------------|
| OpenAI API key | `api/.env` | Generate new key at platform.openai.com |
| TMDB API key | `api/.env` | Generate at themoviedb.org |
| Flask SECRET_KEY | `api/.env` | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |

After rotation:
1. Update `api/.env`
2. Restart the service: `sudo systemctl restart tamor`
3. Verify functionality

---

## Useful Commands Cheatsheet

```bash
# Service management
sudo systemctl start|stop|restart|status tamor

# Database queries
sqlite3 api/memory/tamor.db "SELECT COUNT(*) FROM messages;"
sqlite3 api/memory/tamor.db ".tables"
sqlite3 api/memory/tamor.db ".schema messages"

# Log tailing
tail -f logs/db_backup.log
journalctl -u tamor -f

# Disk usage
du -sh api/memory/ api/uploads/ memory/backups/
ncdu /home/tamor/tamor-core  # interactive (install: apt install ncdu)

# Network
ss -tlnp                      # listening ports
curl -s localhost:5055/api/status | jq

# Git
git log --oneline -10         # recent commits
git status                    # pending changes
```
