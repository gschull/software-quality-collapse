# Software Quality Collapse – Quality Gate++

[![Quality Gate](https://github.com/gschull/software-quality-collapse/actions/workflows/quality-gate.yml/badge.svg?branch=main)](https://github.com/gschull/software-quality-collapse/actions/workflows/quality-gate.yml)

🎯 ELI5: This repo is like a robot inspector that checks your code before it goes live. It tries to break your tests (mutation testing), measures website speed (performance budgets), and checks your libraries for safety (dependency health).

## What's here
- `design.md`: MVP design for the Quality Gate++ solution
- `research.md`: Problem analysis and solution landscape
- `poc/`: Proofs of concept for Node, Python, and Java
  - `node-quality-gate/`: Jest + Stryker + Lighthouse + dep health
  - `python-quality-gate/`: pytest + mutmut
  - `java-quality-gate/`: Maven + PIT

## Quick start (Node POC)
```bash
cd poc/node-quality-gate
npm install
npm run quality:ci
```

## Use as a GitHub Action
See the composite action in the parent project, or copy the sample workflow in `.github/workflows/quality-gate.yml` if you extracted this into its own repo.

## Tweak Gates Quickly
- Python mutation threshold: set `PY_MUTATION_MIN` in the workflow (default 90)
- Java mutation threshold: set `JAVA_MUTATION_MIN` in the workflow (default 90)
- Java dep health sensitivity: set `JAVA_DEP_HEALTH_FAIL_CVSS` (default 0.1 = fail on any known vuln)

## Reusable Workflow (with inputs)
You can call the reusable workflow and override thresholds without editing jobs. For an initial rollout (more forgiving), try 80% and CVSS 5.0:

```yaml
name: Quality Gate
on: pull_request
jobs:
  quality-gate:
    uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.1.0
    with:
      py_mutation_min: '80'         # Python mutmut minimum % (initial rollout)
      py_dep_health_fail: 'true'    # pip-audit --strict
      java_mutation_min: '80'       # Java PIT minimum % (initial rollout)
      java_cvss_threshold: '5.0'    # Fail on CVSS >= 5.0 (medium+)
```

## Why it matters
- Stronger tests catch real bugs (not just higher coverage numbers)
- Performance budgets prevent slowdowns from sneaking into PRs
- Dependency health reduces supply chain risk

## What you’ll see on PRs
- Auto-summary comment with mutation scores and dependency risk (Python/Java)
- Strict but adjustable gates (start at 80% / CVSS 5.0 and raise)

## Optional: Send Results to a Dashboard
ELI5: Think of it like sending a scoreboard update. No code leaves your repo, just the scores.

- Run the mini dashboard locally or in Docker:
  ```bash
  docker build -t quality-gate-dashboard -f dashboard/Dockerfile .
  docker run -p 8000:8000 -e INGEST_TOKEN=your-secret quality-gate-dashboard
  # Visit http://localhost:8000
  ```

- Enable uploads in your workflow call by adding inputs and a secret token:
  ```yaml
  jobs:
    quality-gate:
      uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.1.0
      with:
        py_mutation_min: '80'
        py_dep_health_fail: 'true'
        java_mutation_min: '80'
        java_cvss_threshold: '5.0'
        upload_results: 'true'
        upload_url: 'https://your-host/ingest'
      secrets:
        upload_token: ${{ secrets.QUALITY_GATE_INGEST_TOKEN }}
  ```

Data sent: repo, PR number, commit SHA, mutation scores (Python/Java), vulnerability counts, max CVSS.

## Org-wide Rollout Script
Use the helper script to open PRs across many repos (requires GitHub CLI):

```powershell
cd scripts
./rollout-quality-gate.ps1 -Org "YOUR_ORG" -Limit 20 -BranchName "chore/add-quality-gate"
```

## Contributing
- Start with the Node POC, then adapt thresholds and scripts for your project
- PRs welcome for additional languages and checks (Go, Rust, .NET)

## License
MIT