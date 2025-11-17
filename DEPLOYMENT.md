# Deployment Guide

## Overview

This project has two deployed components:
1. **Landing Page** - Static marketing site (GitHub Pages)
2. **Dashboard** - FastAPI metrics collection and visualization (Fly.io)

---

## Live URLs

- **Landing Page**: https://gschull.github.io/software-quality-collapse/
- **Dashboard**: https://quality-gate-dashboard-gschull.fly.dev/

---

## Landing Page (GitHub Pages)

### Deployment
- **Platform**: GitHub Pages
- **Workflow**: `.github/workflows/deploy-landing.yml`
- **Source**: `landing/` directory
- **Trigger**: Push to `main` affecting `landing/**` or manual dispatch

### Setup Steps
1. Pages must be enabled in repo settings (automated via workflow with `PAGES_ADMIN_TOKEN`)
2. Workflow uses `actions/configure-pages@v5` with `enablement: true`
3. Publishes static HTML/CSS/JS from `landing/`

### Post-Deployment Tasks
- [ ] Replace Formspree placeholder in `landing/index.html` with real form endpoint
- [ ] Configure custom domain (optional): Settings → Pages → Custom domain
- [ ] Update social share metadata (OG tags) with production URL

---

## Dashboard (Fly.io)

### Deployment
- **Platform**: Fly.io
- **App Name**: `quality-gate-dashboard-gschull`
- **Workflow**: `.github/workflows/deploy-dashboard.yml`
- **Region**: `ord` (Chicago)
- **Config**: `dashboard/fly.toml`

### Architecture
- **Runtime**: FastAPI + Uvicorn (Python 3.11)
- **Database**: SQLite (`/app/metrics.db` - ephemeral, data lost on restart)
- **Machines**: 2 (auto-stop when idle, auto-start on request)
- **IPs**: Shared IPv4 (`66.241.125.90`) + dedicated IPv6

### Endpoints
- `/` - Dashboard UI (HTML)
- `/trends` - Trend charts
- `/api/series` - Time-series metrics (JSON)
- `/api/pricing` - Pricing tiers (JSON)
- `/api/roi` - ROI calculator (JSON)
- `/billing` - Billing portal (MVP)
- `/ingest` - POST endpoint for CI uploads (requires `INGEST_TOKEN`)
- `/webhook/stripe` - Stripe webhook stub

### Environment Variables
```toml
[env]
  INGEST_TOKEN = "change-me"         # ⚠️ Update via secrets!
  DATABASE_URL = "/app/metrics.db"   # SQLite path
```

---

## Ingest Token Configuration

### Purpose
The `INGEST_TOKEN` secures the `/ingest` endpoint so only authorized CI workflows can POST metrics.

### Setup Steps

#### 1. Generate a Secure Token
```powershell
# Generate a random 32-character token
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
```

#### 2. Set as Fly.io Secret
```powershell
$env:Path += ";$env:USERPROFILE\.fly\bin"
flyctl secrets set INGEST_TOKEN=<YOUR_TOKEN_HERE> --app quality-gate-dashboard-gschull
```

This removes the default `"change-me"` value and stores the token securely.

#### 3. Add to GitHub Repository Secrets
For repos using the quality gate wrapper:

```powershell
# Add upload URL (dashboard ingest endpoint)
gh secret set QG_UPLOAD_URL --body "https://quality-gate-dashboard-gschull.fly.dev/ingest" --repo <owner>/<repo>

# Add ingest token (must match Fly secret)
gh secret set QUALITY_GATE_INGEST_TOKEN --body "<YOUR_TOKEN_HERE>" --repo <owner>/<repo>
```

#### 4. Enable Uploads in Wrapper
Update `.github/workflows/quality-gate.yml`:
```yaml
jobs:
  quality-check:
    uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.3.1
    with:
      upload_results: true   # 👈 Enable uploads
      telemetry_enabled: true
    secrets:
      upload_token: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}
```

---

## End-to-End Test

### Verify Dashboard is Live
```powershell
Invoke-WebRequest -Uri "https://quality-gate-dashboard-gschull.fly.dev/" -UseBasicParsing
```

### Test Ingest Endpoint (Manual)
```powershell
$headers = @{ "Authorization" = "Bearer <YOUR_TOKEN>" }
$body = @{
  repo = "test/repo"
  pr_number = 1
  commit_sha = "abc123"
  mutation_score = 85.5
  dependency_health = "OK"
} | ConvertTo-Json

Invoke-WebRequest -Uri "https://quality-gate-dashboard-gschull.fly.dev/ingest" `
  -Method POST -Headers $headers -Body $body -ContentType "application/json"
```

### Trigger a Real PR Run
1. Open a PR in a repo using the quality gate
2. Wait for workflow to complete
3. Check dashboard `/trends` for new data points
4. Verify PR comment includes upload confirmation

---

## Maintenance

### View Logs
```powershell
$env:Path += ";$env:USERPROFILE\.fly\bin"
flyctl logs --app quality-gate-dashboard-gschull
```

### Check Status
```powershell
flyctl status --app quality-gate-dashboard-gschull
```

### Redeploy
```powershell
cd C:\dev\PAINKILLER\solutions\software-quality-collapse\dashboard
flyctl deploy --app quality-gate-dashboard-gschull
```

### Scale Machines
```powershell
# Force 1 machine always running (disable auto-stop)
flyctl scale count 1 --app quality-gate-dashboard-gschull

# Re-enable auto-stop (cost-efficient)
# Edit fly.toml: auto_stop_machines = true, min_machines_running = 0
```

---

## Database Persistence (Optional)

**Current Setup**: SQLite stored in `/app` (ephemeral - data lost on machine restart).

**For Production**: Create a Fly volume for persistent storage.

### Steps
```powershell
# Create volume (10GB)
flyctl volumes create metrics_data --region ord --size 10 --app quality-gate-dashboard-gschull

# Update fly.toml
# Add [mounts] section:
# source = "metrics_data"
# destination = "/data"

# Update DATABASE_URL in fly.toml:
# DATABASE_URL = "/data/metrics.db"

# Redeploy
flyctl deploy --app quality-gate-dashboard-gschull
```

---

## Cost Estimates

### GitHub Pages
- **Free** for public repos

### Fly.io (Free Tier)
- **Machines**: 2× shared-cpu-1x (free allowance: 3 shared machines)
- **Storage**: Ephemeral (no volume charges)
- **Bandwidth**: Generous free tier
- **Cost**: $0/month (within free tier)

---

## Troubleshooting

### Dashboard not responding
1. Check machine status: `flyctl status --app quality-gate-dashboard-gschull`
2. If machines stopped, trigger auto-start by accessing any endpoint
3. View logs: `flyctl logs --app quality-gate-dashboard-gschull`

### Ingest uploads failing
1. Verify `INGEST_TOKEN` matches in Fly secrets and repo secrets
2. Check logs for authentication errors
3. Confirm `upload_url` in workflow matches dashboard URL

### Pages deploy fails
1. Ensure `PAGES_ADMIN_TOKEN` is set (if Pages not manually enabled)
2. Check workflow run logs for specific errors
3. Verify `landing/` directory exists and contains `index.html`

---

## Security Notes

- **INGEST_TOKEN**: Rotate regularly; treat as sensitive credential
- **DATABASE_URL**: Currently in `[env]` (logged); move to secrets for production
- **PAGES_ADMIN_TOKEN**: Revoke after initial Pages enablement (optional)

---

## Next Steps

- [ ] Generate and configure secure `INGEST_TOKEN`
- [ ] Add `QG_UPLOAD_URL` and `QUALITY_GATE_INGEST_TOKEN` to consuming repos
- [ ] Enable uploads in quality gate wrapper workflows
- [ ] Run end-to-end test (PR → upload → dashboard)
- [ ] (Optional) Set up Fly volume for persistent database
- [ ] (Optional) Configure custom domain for landing page
- [ ] (Optional) Integrate Stripe for billing webhooks

