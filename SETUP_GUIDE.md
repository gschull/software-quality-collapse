# Quality Gate Setup - Quick Reference

## 🚀 5-Minute Setup (Public Repos)

### 1. Add Secrets
```bash
gh secret set QG_UPLOAD_URL \
  --body "https://quality-gate-dashboard-gschull.fly.dev/ingest" \
  --repo <owner>/<repo>

gh secret set QUALITY_GATE_INGEST_TOKEN \
  --body "<YOUR_TOKEN>" \
  --repo <owner>/<repo>
```

### 2. Create Workflow
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
      py_mutation_min: 75.0
      py_dep_health_fail: critical
      upload_results: true
      telemetry_enabled: true
    secrets:
      upload_token: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}
```

### 3. Open a PR
The workflow runs automatically!

---

## 🔒 Private Repository Setup

Private repos **cannot** call public reusable workflows. Use a standalone workflow instead.

### Option 1: Python-Only Standalone (Recommended for most)

See complete example: [gschull/smb-python/.github/workflows/quality-gate.yml](https://github.com/gschull/smb-python/blob/add-quality-gate/.github/workflows/quality-gate.yml)

**Key differences from reusable workflow**:
- Trigger: `on.pull_request` instead of `on.workflow_call`
- No `inputs` or external `secrets` (hardcode your settings)
- Include only the jobs you need (remove Java/Node if Python-only)
- Set `PYTHONPATH: ${{ github.workspace }}` for import compatibility

### Option 2: Copy Full Workflow

1. Copy [quality-gate-reusable.yml](https://github.com/gschull/software-quality-collapse/blob/main/.github/workflows/quality-gate-reusable.yml)
2. Rename to `quality-gate.yml` in your `.github/workflows/`
3. Replace `workflow_call` with `pull_request` trigger
4. Remove `inputs` and `secrets` blocks
5. Hardcode your thresholds and settings

---

## 📁 Project Structure Fixes

### Standard Structure (Best - Works Out of Box)
```
repo/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       └── module.py
├── tests/
│   └── test_module.py
└── requirements.txt
```

### Flat Structure (Needs Config)
```
repo/
├── my_module.py
├── tests/
│   └── test_my_module.py
└── requirements.txt
```

**Fix**: Add `setup.cfg`:
```ini
[mutmut]
paths_to_mutate=my_module.py
runner=python -m pytest -x -q --tb=no
tests_dir=tests/

[tool:pytest]
testpaths = tests
pythonpath = .
```

**And** update workflow:
```yaml
- name: Run tests
  env:
    PYTHONPATH: ${{ github.workspace }}
  run: pytest -q

- name: Run mutation tests (mutmut)
  env:
    PYTHONPATH: ${{ github.workspace }}
  run: mutmut run || true
```

---

## 🐛 Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| **Workflow doesn't run on PR** | Workflow file must be in `main` branch, not just PR branch |
| **401 Unauthorized on upload** | Check `QUALITY_GATE_INGEST_TOKEN` secret matches Fly.io secret |
| **Import errors in tests** | Add `PYTHONPATH: ${{ github.workspace }}` env var |
| **mutmut can't find code** | Create `setup.cfg` with `[mutmut]` section |
| **"no such table: results"** | mutmut failed to run; check for errors in "Run mutation tests" step |
| **Tests timeout** | Add `timeout-minutes: 30` to job, or reduce `paths_to_mutate` scope |
| **Private repo workflow fails** | Copy workflow locally (can't use public reusable workflow) |

---

## 🎯 Threshold Recommendations

### Mutation Score
- **Start**: `50.0` (achievable for most projects)
- **Good**: `75.0` (solid test coverage)
- **Excellent**: `90.0` (production-critical code)

### Dependency Health (Python)
- **Strict**: `py_dep_health_fail: true` (fail on any vulnerability)
- **Balanced**: `py_dep_health_fail: critical` (fail only on critical)
- **Lenient**: Remove `--strict` flag, log only

### Gradual Improvement Strategy
```yaml
# Week 1: Establish baseline
py_mutation_min: 10.0

# Week 2-4: Incremental improvements
py_mutation_min: 25.0

# Month 2: Good coverage
py_mutation_min: 50.0

# Month 3+: Excellent coverage
py_mutation_min: 75.0
```

---

## 📊 Reading Results

### In PR Comment
After workflow completes, check PR for automated comment:

```
## Quality Gate Summary

| Metric | Value |
|---|---:|
| Mutation Score | 78.5% |
| Mutations Killed | 157 |
| Mutations Survived | 43 |
| Vulnerabilities (C/H/M/L) | 0/1/3/5 |
| Max CVSS | 6.2 |
```

### In Dashboard
Visit: https://quality-gate-dashboard-gschull.fly.dev/trends

Charts show mutation score and dependency health trends over time.

### Via API
```bash
curl https://quality-gate-dashboard-gschull.fly.dev/api/series | jq
```

---

## 🔧 Advanced Configuration

### Multi-Language Project
```yaml
jobs:
  quality-check:
    uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.3.1
    with:
      # Python
      py_mutation_min: 80.0
      py_dep_health_fail: critical
      
      # Java
      java_mutation_min: 85.0
      java_cvss_threshold: 7.0
      
      # Node
      node_dep_fail_level: moderate
      
      # Upload
      upload_results: true
      telemetry_enabled: true
    secrets:
      upload_token: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}
```

### Custom Test Command (Python)
In `setup.cfg`:
```ini
[mutmut]
paths_to_mutate=src/
runner=pytest -v --cov --tb=short
tests_dir=tests/
```

### Skip Mutation Testing (Dependency Scanning Only)
Make mutation threshold non-blocking:
```yaml
- name: Enforce mutation threshold
  continue-on-error: true
  run: |
    # ... mutation check script
```

Or remove the entire mutation testing step.

---

## 📚 Full Documentation

For detailed troubleshooting, architecture details, and deployment info, see:
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Complete deployment and configuration guide
- [Dashboard](https://quality-gate-dashboard-gschull.fly.dev/) - Live metrics
- [Landing Page](https://gschull.github.io/software-quality-collapse/) - Project overview

---

## 🆘 Getting Help

### Check Workflow Logs
```bash
gh run list --repo <owner>/<repo> --workflow quality-gate.yml --limit 5
gh run view <run-id> --repo <owner>/<repo> --log
```

### Test Upload Manually
```bash
curl -X POST https://quality-gate-dashboard-gschull.fly.dev/ingest \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"repository":"test/repo","python":{"mutation":{"score":85.0}}}'
```

### Verify Dashboard is Running
```bash
curl https://quality-gate-dashboard-gschull.fly.dev/
```

---

## ✅ Checklist

Before opening first PR:
- [ ] Secrets configured (`QG_UPLOAD_URL`, `QUALITY_GATE_INGEST_TOKEN`)
- [ ] Workflow file in `.github/workflows/quality-gate.yml`
- [ ] Workflow file committed to default branch (main/master)
- [ ] Tests run successfully locally (`pytest` or equivalent)
- [ ] (Python flat structure) `setup.cfg` with `[mutmut]` section created
- [ ] (Private repo) Workflow copied locally, not using `uses:`

After first PR:
- [ ] Workflow runs without errors
- [ ] PR comment appears with quality metrics
- [ ] Dashboard shows new data point at `/trends`
- [ ] Adjust thresholds as needed based on baseline

---

**Last Updated**: 2025-11-17
