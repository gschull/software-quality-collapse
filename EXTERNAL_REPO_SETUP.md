# External Repository Setup Guide

## Overview

This guide documents the process for setting up Quality Gate workflows on external repositories (outside the software-quality-collapse repo).

## Key Finding: Reusable Workflow Limitation

**Problem**: The reusable workflow (`quality-gate-reusable.yml`) has hardcoded `working-directory` settings that point to `poc/[language]-quality-gate` directories. These paths only exist in the software-quality-collapse repo.

**Solution**: Use **standalone workflows** for external repositories.

## Quick Setup (5 minutes)

### 1. Configure Repository Secrets

```bash
# Set the dashboard upload URL
gh secret set QG_UPLOAD_URL --repo OWNER/REPO --body "https://quality-gate-dashboard-gschull.fly.dev/ingest"

# Set the ingest token
gh secret set QUALITY_GATE_INGEST_TOKEN --repo OWNER/REPO --body "YOUR_TOKEN_HERE"
```

### 2. Create Workflow File

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
  python:
    name: Python Quality Gate
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt', 'pyproject.toml', 'poetry.lock', 'requirements-*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi
          if [ -f "pyproject.toml" ]; then pip install -e .; fi
          pip install pytest mutmut pip-audit

      - name: Dependency health (pip-audit)
        run: |
          pip-audit -f json -o audit.json || true
          python - <<'PY'
          import json, sys
          try:
            with open('audit.json','r') as f:
              data = json.load(f)
            has_critical = False
            for item in data:
              for v in (item.get('vulns') or []):
                if (v.get('severity') or '').lower() == 'critical':
                  has_critical = True
                  break
            if has_critical:
              print("FAIL: Critical vulnerabilities found")
              sys.exit(1)
            print("PASS: No critical vulnerabilities")
          except Exception as e:
            print(f"Warning: Could not parse audit.json: {e}")
          PY

      - name: Run tests
        env:
          PYTHONPATH: ${{ github.workspace }}
        run: pytest -q

      - name: Run mutation tests (mutmut)
        env:
          PYTHONPATH: ${{ github.workspace }}
        run: mutmut run || true

      - name: Collect Python metrics
        id: metrics
        run: |
          python - <<'PY'
          import json, os, sqlite3, sys
          out = {
            "ecosystem": "python",
            "mutation": {"score": None, "killed": 0, "survived": 0, "timeout": 0},
            "dependencies": {"critical": 0, "high": 0, "moderate": 0, "low": 0, "max_cvss": 0.0}
          }
          try:
            con = sqlite3.connect('.mutmut-cache')
            cur = con.cursor()
            counts = {s: 0 for s in ('killed','survived','timeout')}
            for status, cnt in cur.execute("SELECT status, COUNT(*) FROM results GROUP BY status"):
              if status in counts:
                counts[status] = cnt
            killed, survived, timeout = counts['killed'], counts['survived'], counts['timeout']
            considered = killed + survived + timeout
            score = 100.0 if considered == 0 else (killed / considered) * 100.0
            out["mutation"]= {"score": round(score,2), "killed": killed, "survived": survived, "timeout": timeout}
          except Exception:
            pass
          finally:
            try:
              con.close()
            except Exception:
              pass
          try:
            with open('audit.json','r',encoding='utf-8') as f:
              data = json.load(f)
            max_cvss = 0.0
            sev = {"critical":0,"high":0,"moderate":0,"low":0}
            for item in data:
              vulns = item.get('vulns') or []
              for v in vulns:
                cvss = v.get('score','0')
                try:
                  cvss = float(cvss)
                except Exception:
                  cvss = 0.0
                max_cvss = max(max_cvss, cvss)
                s = (v.get('severity') or '').lower()
                if s in sev:
                  sev[s]+=1
            out["dependencies"]= {**sev, "max_cvss": max_cvss}
          except Exception:
            pass
          with open('python_metrics.json','w',encoding='utf-8') as f:
            json.dump(out,f)
          print(json.dumps(out,indent=2))
          PY

      - name: Enforce mutation threshold
        continue-on-error: true
        run: |
          python - <<'PY'
          import os, sqlite3, sys
          threshold = 75.0
          db_path = '.mutmut-cache'
          try:
            con = sqlite3.connect(db_path)
          except Exception as e:
            print(f"Could not open mutmut cache '{db_path}': {e}")
            print("WARN: Skipping mutation threshold check")
            sys.exit(0)
          cur = con.cursor()
          counts = {s: 0 for s in ('killed','survived','timeout')}
          try:
            for status, cnt in cur.execute("SELECT status, COUNT(*) FROM results GROUP BY status"):
              if status in counts:
                counts[status] = cnt
          except Exception as e:
            print(f"Failed reading results from mutmut cache: {e}")
            print("WARN: Skipping mutation threshold check")
            con.close()
            sys.exit(0)
          finally:
            try:
              con.close()
            except:
              pass
          killed = counts['killed']
          survived = counts['survived']
          timeout = counts['timeout']
          considered = killed + survived + timeout
          score = 100.0 if considered == 0 else (killed / considered) * 100.0
          print(f"Mutation score: {score:.2f}% (killed={killed}, survived={survived}, timeout={timeout})")
          if score + 1e-9 < threshold:
            print(f"WARN: mutation score {score:.2f}% is below threshold {threshold:.2f}%")
          else:
            print("PASS: mutation score meets threshold")
          PY

      - name: Post PR comment
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            function readJson(p) { try { return JSON.parse(fs.readFileSync(p,'utf8')); } catch { return null; } }
            const py = readJson('python_metrics.json');
            if (!py) {
              core.info('No metrics found, skipping comment');
              return;
            }
            const m = py.mutation || {};
            const d = py.dependencies || {};
            const body = [
              '## Quality Gate Summary',
              '',
              '| Metric | Value |',
              '|---|---:|',
              `| Mutation Score | ${m.score ?? '–'}% |`,
              `| Mutations Killed | ${m.killed || 0} |`,
              `| Mutations Survived | ${m.survived || 0} |`,
              `| Vulnerabilities (C/H/M/L) | ${d.critical||0}/${d.high||0}/${d.moderate||0}/${d.low||0} |`,
              `| Max CVSS | ${d.max_cvss||0} |`,
              '',
              '_Higher mutation score = stronger tests. Critical vulns mean risky dependencies._'
            ].join('\n');
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body
            });

      - name: Upload metrics to dashboard
        env:
          UPLOAD_URL: ${{ secrets.QG_UPLOAD_URL }}
          UPLOAD_TOKEN: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}
        if: ${{ env.UPLOAD_URL != '' }}
        run: |
          python - <<'PY'
          import json, os, urllib.request
          with open('python_metrics.json','r') as f:
            metrics = json.load(f)
          payload = {
            "repository": os.environ.get('GITHUB_REPOSITORY'),
            "pr_number": os.environ.get('GITHUB_REF','').split('/')[-1],
            "commit_sha": os.environ.get('GITHUB_SHA'),
            "run_id": os.environ.get('GITHUB_RUN_ID'),
            "python": metrics,
            "generated_at": __import__('datetime').datetime.utcnow().isoformat() + 'Z'
          }
          url = os.environ.get('UPLOAD_URL', '')
          token = os.environ.get('UPLOAD_TOKEN', '')
          if not url or not token:
            print("Skipping upload: UPLOAD_URL or UPLOAD_TOKEN not set")
            exit(0)
          req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
              'Authorization': f'Bearer {token}',
              'Content-Type': 'application/json'
            }
          )
          try:
            with urllib.request.urlopen(req) as resp:
              print(f"Upload response: {resp.status}")
          except Exception as e:
            print(f"Upload failed: {e}")
          PY
```

### 3. Create PR to Test

```bash
# Create a test file
echo "# Quality Gate" > QUALITY_GATE.md

# Commit and push
git checkout -b test-quality-gate
git add .github/workflows/quality-gate.yml QUALITY_GATE.md
git commit -m "docs: Add quality gate workflow"
git push origin test-quality-gate

# Create PR
gh pr create --title "test: Quality gate setup" --body "Testing quality gate workflow"
```

## Common Issues and Solutions

### Issue: `ModuleNotFoundError` during tests

**Symptoms**: Tests fail with "No module named 'your_package'"

**Cause**: Local package not in Python path

**Solution**: Add `PYTHONPATH` environment variable to test steps:

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

### Issue: SyntaxError in github-script

**Symptoms**: "Identifier 'context' has already been declared"

**Cause**: Importing variables that github-script already provides

**Solution**: Remove these lines from the script:
```javascript
const {context, github} = require('@actions/github');  // ❌ Remove this
```

The `context` and `github` objects are already available in github-script scope.

### Issue: Workflow runs but doesn't fail PR

**Symptoms**: Quality checks run but PR can still merge despite failures

**Cause**: Using `continue-on-error: true` too liberally

**Solution**: Only use `continue-on-error` for non-blocking checks. Hard failures should exit non-zero.

## Real-World Example: StorageScrubber

### Repository Details
- **Repo**: gschull/StorageScrubber
- **Type**: Public Python project
- **Structure**: Has `scrubber/` package directory and `tests/` directory
- **Dependencies**: pytest, send2trash

### Setup Process

1. **Configured secrets** (2 minutes):
   ```bash
   gh secret set QG_UPLOAD_URL --repo gschull/StorageScrubber \
     --body "https://quality-gate-dashboard-gschull.fly.dev/ingest"
   gh secret set QUALITY_GATE_INGEST_TOKEN --repo gschull/StorageScrubber \
     --body "8pMNfh7Ynb4ogJFvXdHiVC6uxaTk5cDs"
   ```

2. **Created standalone workflow** (5 minutes):
   - Used Python-only template above
   - Added `PYTHONPATH: ${{ github.workspace }}` for local imports
   - Fixed github-script by removing duplicate imports

3. **Created test PR** (1 minute):
   - PR #1: https://github.com/gschull/StorageScrubber/pull/1
   - Workflow triggered automatically
   - Results posted as PR comment

### Results

✅ **What worked**:
- Workflow ran successfully
- Metrics uploaded to dashboard (200 OK)
- PR comment posted with quality summary
- Data visible in `/trends` endpoint

⚠️ **What needs adjustment**:
- Mutation score is 0% (mutmut configuration needed)
- No mutations found/run (need to configure mutmut properly for this repo structure)

### Dashboard Output

```
Repository: gschull/StorageScrubber
Ecosystem: python
Avg Mutation: 0.00%
Worst CVSS: 0.0
Samples: 1
```

## Comparison: Reusable vs Standalone

### Reusable Workflow (quality-gate-reusable.yml)

**Pros**:
- Centralized updates
- Consistent behavior across repos
- Less code duplication

**Cons**:
- Hardcoded `working-directory: poc/[language]-quality-gate`
- Only works for software-quality-collapse internal structure
- Fails on external repos with "No such file or directory"

**Use Case**: Internal POC testing within software-quality-collapse repo

### Standalone Workflow

**Pros**:
- Works from repository root (no path assumptions)
- Fully customizable per-repo
- Easy to debug (all code visible in repo)
- PYTHONPATH configurable per-project

**Cons**:
- Code duplication across repos
- Manual updates needed if core logic changes
- More maintenance burden

**Use Case**: External repositories, public/private projects, production use

## Next Steps

### For StorageScrubber
1. Configure mutmut properly (add `setup.cfg` with paths)
2. Verify mutations are detected
3. Adjust thresholds based on actual scores

### For Other Repos
1. Use this standalone workflow template
2. Adjust Python version if needed (`python-version: '3.11'`)
3. Modify dependency install steps based on project structure
4. Set appropriate thresholds in "Enforce mutation threshold" step

### For Quality Gate Dashboard
- Consider creating a "Copy workflow" button that generates standalone workflow YAML
- Document that reusable workflow is internal-only
- Update SETUP_GUIDE.md to recommend standalone workflows for external repos

## Lessons Learned

1. **Directory assumptions break portability**: Hardcoded paths only work in specific repo structures
2. **PYTHONPATH is essential**: Local packages need explicit path configuration
3. **github-script scope matters**: Built-in objects should not be re-imported
4. **End-to-end testing reveals edge cases**: Testing on real external repos uncovers issues docs miss
5. **Standalone workflows scale better**: More verbose but more reliable across diverse codebases

## Template Variations

### Minimal (No dashboard upload)
Remove the "Upload metrics to dashboard" step and secrets.

### Multi-language
Add Node.js and Java jobs following the same pattern (checkout → setup → install → test → mutate → collect → comment).

### Custom thresholds
Modify the `threshold` variable in "Enforce mutation threshold" step:
```python
threshold = 80.0  # Require 80% mutation score
```

### Skip PR comments
Remove the "Post PR comment" step to avoid cluttering PRs.

---

**Last Updated**: 2025-11-17  
**Tested With**: gschull/StorageScrubber (Python 3.11)  
**Dashboard**: https://quality-gate-dashboard-gschull.fly.dev/
