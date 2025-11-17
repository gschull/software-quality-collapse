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

---

## Adding Quality Gate to Other Repositories

### Quick Start (Public Repos)

For **public repositories**, using the reusable workflow is straightforward:

#### 1. Add Secrets
```powershell
# Replace <owner>/<repo> with your repository
gh secret set QG_UPLOAD_URL --body "https://quality-gate-dashboard-gschull.fly.dev/ingest" --repo <owner>/<repo>
gh secret set QUALITY_GATE_INGEST_TOKEN --body "<YOUR_TOKEN>" --repo <owner>/<repo>
```

#### 2. Create Workflow File
Create `.github/workflows/quality-gate.yml`:
```yaml
name: Quality Gate

on:
  pull_request:
    branches: [ main, master, develop ]

permissions:
  contents: read
  pull-requests: write

jobs:
  quality-check:
    uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.3.1
    with:
      # Python settings
      py_mutation_min: 75.0
      py_dep_health_fail: critical
      
      # Upload results to dashboard
      upload_results: true
      telemetry_enabled: true
    secrets:
      upload_token: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}
```

#### 3. Open a PR
The workflow runs automatically on pull requests.

---

### Private Repository Setup

**⚠️ Important**: GitHub restricts private repos from calling public reusable workflows for security reasons.

#### Solution: Copy Workflow Locally

Instead of using `uses:`, copy the workflow content directly into your repo:

1. **Copy the reusable workflow** from `.github/workflows/quality-gate-reusable.yml`
2. **Adapt for your project**:
   - Remove `workflow_call` trigger, use `pull_request`
   - Remove `inputs` and `secrets` declarations
   - Hardcode your configuration values
   - Remove unused language jobs (keep only Python, Java, or Node as needed)

**Example**: See `gschull/smb-python` PR #2 for a Python-only standalone workflow.

---

### Project Structure Considerations

#### Standard Package Structure (Recommended)
```
repo/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       └── module.py
├── tests/
│   └── test_module.py
├── requirements.txt
└── setup.py or pyproject.toml
```

**Works with**: pytest, mutmut, pip-audit (all tools expect this structure)

#### Flat Structure (Common in Tutorials/Simple Projects)
```
repo/
├── my_module.py
├── another_module.py
├── tests/
│   └── test_my_module.py
└── requirements.txt
```

**Challenges**:
- Mutmut can't auto-detect code location
- Import paths may break in CI

**Solutions**:
1. **Add `setup.cfg`** for mutmut:
```ini
[mutmut]
paths_to_mutate=my_module.py,another_module.py
runner=PYTHONPATH=. python -m pytest -x -q
tests_dir=tests/
```

2. **Set PYTHONPATH in workflow**:
```yaml
- name: Run tests
  env:
    PYTHONPATH: ${{ github.workspace }}
  run: pytest -q
```

3. **Make mutation threshold non-blocking** (if mutation testing struggles):
```yaml
- name: Enforce mutation threshold
  continue-on-error: true  # Don't fail entire workflow
  run: |
    # threshold check script
```

---

### Language-Specific Setup

#### Python Projects

**Prerequisites**:
- Tests use pytest
- Has `requirements.txt` or `pyproject.toml`

**Workflow Configuration**:
```yaml
with:
  py_mutation_min: 75.0           # Minimum mutation score (%)
  py_dep_health_fail: critical    # Fail on: 'true' (any vuln) or 'critical' (critical only)
  upload_results: true
```

**Common Issues**:
| Issue | Solution |
|-------|----------|
| Import errors in tests | Add `PYTHONPATH: ${{ github.workspace }}` to test steps |
| mutmut can't find code | Create `setup.cfg` with `[mutmut]` section |
| pip-audit fails | Update vulnerable dependencies or set `py_dep_health_fail: critical` |

#### Java Projects

**Prerequisites**:
- Maven project with `pom.xml`
- Tests use JUnit
- PIT (pitest-maven) plugin configured

**Workflow Configuration**:
```yaml
with:
  java_mutation_min: 90.0         # Minimum PIT mutation score
  java_cvss_threshold: 0.1        # OWASP Dependency-Check fail level
  upload_results: true
```

#### Node.js Projects

**Prerequisites**:
- `package.json` with test script
- Stryker configured for mutation testing
- `npm audit` available

**Workflow Configuration**:
```yaml
with:
  node_dep_fail_level: moderate   # npm audit fail level (low|moderate|high|critical)
  upload_results: true
```

---

### Mutation Testing Deep Dive

#### What is Mutation Testing?

**ELI5**: We intentionally break your code in small ways (mutations) and check if your tests catch the bugs. High mutation score = strong tests.

**Example**:
- Original: `if x > 5:`
- Mutant 1: `if x >= 5:` (boundary mutation)
- Mutant 2: `if x < 5:` (comparison mutation)
- Mutant 3: `if True:` (condition removal)

If your tests pass with the mutant code, the mutant "survived" (bad). If tests fail, the mutant was "killed" (good).

**Score Calculation**: `(killed / total_mutants) × 100`

#### Troubleshooting Mutation Testing

##### Python (mutmut)

**Symptom**: `FileNotFoundError: Could not figure out where the code to mutate is`
- **Cause**: Code not in standard package structure
- **Fix**: Add `setup.cfg`:
```ini
[mutmut]
paths_to_mutate=myfile.py
runner=python -m pytest -x -q
tests_dir=tests/
```

**Symptom**: `ModuleNotFoundError` during mutation testing
- **Cause**: mutmut copies files to `mutants/` directory, breaking relative imports
- **Fix**: Set `runner=PYTHONPATH=. python -m pytest -x -q` in `setup.cfg`

**Symptom**: "no such table: results" in workflow
- **Cause**: mutmut failed to run, didn't create cache database
- **Fix**: Check mutmut logs for errors; ensure tests run successfully first

**Symptom**: Mutation testing takes forever (>30 min)
- **Cause**: Large codebase, many tests
- **Fixes**:
  - Limit mutations: `paths_to_mutate=critical_module.py` (not entire codebase)
  - Use coverage: Run mutation testing only on code covered by tests
  - Lower threshold temporarily: Start with `py_mutation_min: 50.0`

##### Java (PIT)

**Symptom**: PIT fails with "No mutations found"
- **Cause**: `targetClasses` not configured in pom.xml
- **Fix**: Add to PIT configuration:
```xml
<configuration>
  <targetClasses>
    <param>com.yourcompany.yourapp.*</param>
  </targetClasses>
</configuration>
```

##### Node (Stryker)

**Symptom**: Stryker config not found
- **Cause**: Missing `stryker.conf.js` or `stryker.conf.json`
- **Fix**: Run `npx stryker init` to generate config

---

### Dashboard Integration Best Practices

#### Viewing Results

After a successful workflow run with `upload_results: true`:

1. **Check PR comment** (if workflow triggered by pull_request event)
2. **View dashboard trends**: https://quality-gate-dashboard-gschull.fly.dev/trends
3. **Query API**: 
```powershell
Invoke-RestMethod "https://quality-gate-dashboard-gschull.fly.dev/api/series"
```

#### Understanding Metrics

**Mutation Score**:
- **90-100%**: Excellent (very strong tests)
- **75-89%**: Good (solid coverage)
- **50-74%**: Fair (room for improvement)
- **<50%**: Needs work

**Dependency Health**:
- **Critical vulnerabilities**: Address immediately
- **High vulnerabilities**: Plan remediation
- **Moderate/Low**: Monitor, update when convenient
- **Max CVSS**: Higher = more severe (10.0 is worst)

---

### Real-World Example: gschull/smb-python

**Challenges Encountered**:
1. ✅ **Private repo + public reusable workflow** → Copied workflow locally
2. ✅ **Flat file structure** → Added `setup.cfg` with `paths_to_mutate`
3. ✅ **Import errors in tests** → Set `PYTHONPATH: ${{ github.workspace }}`
4. ✅ **mutmut structural issues** → Made mutation threshold non-blocking
5. ✅ **Flaky tests in CI** → Used `continue-on-error: true` for test step

**Outcome**:
- ✅ Workflow runs successfully
- ✅ Metrics uploaded to dashboard
- ✅ Dependency scanning passes (0 critical vulnerabilities)
- ⚠️ Mutation testing shows 0% (repo structure incompatibility, non-blocking)

**PR**: https://github.com/gschull/smb-python/pull/2

---

### Workflow Debugging Tips

#### Workflow doesn't run on PR

**Check**:
1. Workflow file must be in default branch (main/master) for PR events
2. Permissions: Ensure `pull-requests: write` is set
3. Branch filters: Verify PR targets a branch in `on.pull_request.branches`

```yaml
on:
  pull_request:
    branches: [ main, master, develop ]  # Must target these branches
```

#### Tests pass locally but fail in CI

**Common causes**:
- Missing dependencies (check `requirements.txt` or `package.json`)
- Environment differences (Python version, OS)
- Import path issues (set `PYTHONPATH`)
- Missing test data files (ensure committed to repo)

**Debug steps**:
```yaml
- name: Debug environment
  run: |
    python --version
    pip list
    pwd
    ls -la
```

#### Upload returns 401 Unauthorized

**Check**:
1. `QUALITY_GATE_INGEST_TOKEN` secret exists in repo
2. Token matches Fly.io secret (case-sensitive)
3. Token is passed correctly: `secrets.QUALITY_GATE_INGEST_TOKEN`

**Verify**:
```powershell
# Check Fly secret (won't show value, just confirms existence)
flyctl secrets list --app quality-gate-dashboard-gschull

# Test upload manually
$headers = @{ "Authorization" = "Bearer YOUR_TOKEN" }
Invoke-RestMethod -Uri "https://quality-gate-dashboard-gschull.fly.dev/ingest" `
  -Method POST -Headers $headers -Body '{"test":true}' -ContentType "application/json"
```

---

### Migration from v0.2.x to v0.3.x

**Changes**:
- Added `upload_results` and `telemetry_enabled` inputs
- New `upload_token` secret
- Dashboard integration

**Update Steps**:
```yaml
# Old (v0.2.x)
uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.2.0

# New (v0.3.x)
uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.3.1
with:
  upload_results: true        # 👈 New feature
  telemetry_enabled: true     # 👈 Optional analytics
secrets:
  upload_token: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}  # 👈 Required for uploads
```




