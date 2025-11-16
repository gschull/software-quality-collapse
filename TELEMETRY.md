# Telemetry & Privacy

## What We Collect (When You Opt In)

Quality Gate++ includes **optional, anonymous telemetry** to help us improve the product. It's **disabled by default**.

### Data Sent

When `telemetry_enabled: 'true'` is set:

```json
{
  "version": "v0.3.1",
  "timestamp": "2025-11-16T12:34:56.789Z",
  "ecosystems": ["node", "python"],
  "mutation_scores": [85.3, 92.1],
  "has_vulns": true
}
```

**What this tells us:**
- Which language ecosystems are used (helps prioritize adapter development)
- Average mutation score trends (helps set default thresholds)
- Whether teams find vulnerabilities (validates dependency health value)

### What We DON'T Collect

❌ **Never sent:**
- Repository names or URLs
- Commit SHAs or PR numbers
- Source code or file paths
- Developer names or emails
- Company/organization identifiers
- IP addresses (not logged)
- Any personally identifiable information (PII)

## How to Enable

Add `telemetry_enabled: 'true'` to your workflow:

```yaml
jobs:
  quality-gate:
    uses: gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.3.1
    with:
      telemetry_enabled: 'true'  # ← Opt-in
      # ...other inputs
```

**Default:** `'false'` (telemetry disabled unless you explicitly enable it)

## Why We Ask

**The honest reason:** Understanding how Quality Gate++ is used helps us:
1. Prioritize which language adapters to build next (Go? Rust? C#?)
2. Set smarter default thresholds (e.g., "90% mutation score is too high for most teams")
3. Validate feature value (e.g., "Are people actually finding CVEs?")
4. Write better docs (e.g., "Node users struggle with X")

**Our promise:**
- Data is aggregated (no individual repo tracking)
- No tracking cookies or analytics on self-hosted dashboard
- You can self-host and never ping our servers
- We'll publish anonymized insights publicly (e.g., "Average mutation score across 1,000 repos: 78%")

## Data Storage & Retention

- **Endpoint:** `telemetry.quality-gate.dev` (HTTPS only)
- **Storage:** PostgreSQL, encrypted at rest (AWS RDS)
- **Retention:** 90 days (deleted automatically)
- **Access:** Only project maintainers (audited)
- **Logs:** Request counts only, no payloads logged

## Compliance

- **GDPR:** No personal data collected → no consent required (per Article 4.1)
- **CCPA:** Anonymous telemetry exemption (Cal. Civ. Code § 1798.140(o)(1))
- **SOC 2:** Telemetry endpoint included in scope (audit in progress)

## Opt-Out Anytime

**Option 1:** Remove `telemetry_enabled` or set to `'false'` in workflow  
**Option 2:** Self-host entirely (no external network calls)  
**Option 3:** Block DNS: `telemetry.quality-gate.dev` (silent fail, no errors)

## Transparency Report

We'll publish quarterly:
- Total pings received
- Top 5 ecosystems by usage
- Average mutation scores by language
- Percentage of repos with high-severity CVEs

**First report:** March 2026 (public GitHub issue)

## Questions?

Email: privacy@quality-gate.dev  
Data deletion request: Same email (we'll purge your workspace's telemetry in 48h)

---

**TL;DR:** Telemetry is opt-in, anonymous, and helps us build better tools. We never sell data or track individuals. You can self-host without ever talking to our servers.
