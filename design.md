# Design: Quality Gate++ (MVP)
Date: 2025-11-16

## 🎯 ELI5 (Explain Like I'm 5)

**The Problem**: Imagine you're building with LEGO and sometimes broken pieces sneak into the final creation because nobody checked carefully enough.

**Our Solution**: We built an automatic quality inspector robot that checks three things before your code goes live:
1. **Tests are strong** (Mutation testing) - The robot tries to break your code on purpose. If your tests don't catch the breaks, you need better tests!
2. **Website is fast** (Performance) - The robot times how quickly your website loads. Too slow = no pass!
3. **Building blocks are safe** (Dependencies) - The robot checks if any of your libraries are old or have security problems.

If anything fails, the robot stops the code from being merged until you fix it. This keeps bugs out of production!

---

## Goal
Reduce escaped defects and regressions by enforcing meaningful, automated quality checks in CI for every PR.

## Scope (MVP)
- Languages: JavaScript/TypeScript (Node) POC
- Checks:
  1) Mutation testing score threshold (Stryker + Jest)
  2) Web performance budget (Lighthouse CI on static site)
  3) Basic dependency health score (CVE count + last release age; Phase 2)
- CI: GitHub Actions (composite steps or workflow template)

## Non-Goals (MVP)
- Organization-wide policy management
- Cross-language adapters beyond Node
- Full SLO enforcement from production metrics

## Architecture
- GitHub Actions workflow invokes three stages:
  - Tests: run unit tests + mutation tests; fail if mutation score < threshold
  - Perf: run Lighthouse CI against staticDistDir; fail if performance score < threshold
  - (Optional) Dep health: compute simple risk score and log warnings (non-blocking initially)

## Inputs
- repo with JS tests (Jest)
- static web build dir (e.g., `web/`) with an `index.html`
- thresholds via env or config:
  - `MUTATION_MIN=70` (break)
  - `LH_MIN_PERF=0.90`

## Outputs
- PR status checks (pass/fail)
- Console + HTML reports (Stryker)
- LHCI assertions summary (JSON)

## Configuration
- `stryker.conf.json` with thresholds and mutate globs
- `lighthouserc.json` with `collect.staticDistDir` and `assert.assertions`

## CI Integration (Template)
- Uses Node 20, runs `npm install`, then `npm run quality:ci`
- Fails PR if thresholds not met

## Thresholds (Defaults)
- Mutation break: 70 (high: 80, low: 60)
- Lighthouse performance: 0.90 (tune per repo)

## Performance Considerations
- Run mutation on changed files only in future (Phase 2)
- Cache `~/.npm` and `node_modules` in CI
- Nightly full mutation run, PR partial run

## Telemetry (Later)
- Export scores to artifact or API for trend dashboards

## Risks & Mitigations
- Longer CI time → cache + partial runs
- Flaky perf → 3-run median for LHCI; run on static build
- False positives → allow override label with justification

## Milestones
1. POC (Node): Jest + Stryker + LHCI; fail on thresholds
2. Dep health (OSV + age) as warning; later gating
3. Language adapters (Python mutmut, Java PIT, etc.)
4. Reusable composite action or npm package for easy install

## Acceptance Criteria (MVP)
- PR fails when mutation score < 70 or LH perf < 0.90
- Clear output with guidance to improve
- Documented setup with quick start and example workflow
