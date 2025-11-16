# Early Adopter Outreach Script

## Objective
Find and email 50 CTOs/Engineering leaders whose orgs are already using Quality Gate++ to offer free hosted dashboard beta access in exchange for feedback.

---

## Step 1: Scrape GitHub for Users

### Using GitHub Code Search API

```bash
# Requires GitHub CLI (gh) authenticated with token

# Find all public repos using our reusable workflow
gh api \
  -H "Accept: application/vnd.github+json" \
  -X GET /search/code \
  -f q='gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml language:YAML' \
  --paginate | jq -r '.items[].repository.full_name' | sort -u > repos.txt

# Extract org names (for multi-repo orgs)
cat repos.txt | cut -d/ -f1 | sort -u > orgs.txt

# Get org details (to find contact info)
while read org; do
  gh api /orgs/$org 2>/dev/null | jq -r '{name: .name, email: .email, blog: .blog}' >> org_details.json
  sleep 1  # Rate limit: 5000/hour for authenticated, be polite
done < orgs.txt
```

### Alternative: GitHub Search Web UI

1. Go to https://github.com/search
2. Search: `gschull/software-quality-collapse path:.github/workflows language:YAML`
3. Filter: "Code" results
4. Manually extract org names from top 50 results
5. Look up org profiles for contact emails

---

## Step 2: Find Decision-Maker Emails

### LinkedIn Approach

For each org in `orgs.txt`:
1. Search LinkedIn: `"[Org Name]" (CTO OR "Head of Engineering" OR "VP Engineering")`
2. Note names
3. Use email finder tools:
   - **Hunter.io** (free: 50 searches/month)
   - **RocketReach** (free: 5 lookups/month)
   - **Email pattern guess**: `firstname.lastname@company.com`, `firstname@company.com`, `f.lastname@company.com`

### GitHub Profile Scraping

```bash
# Get maintainers from repos
while read repo; do
  gh api /repos/$repo/contributors --paginate | jq -r '.[0:3] | .[] | .login' >> maintainers.txt
done < repos.txt

# Get emails from profiles (if public)
while read user; do
  gh api /users/$user | jq -r '{user: .login, email: .email, blog: .blog, twitter: .twitter_username}'
done < maintainers.txt > contacts.json
```

---

## Step 3: Email Template

### Subject Line Options (A/B test these)

**Version A (Direct):**
```
Quality Gate++ hosted dashboard - free 90-day beta for early adopters
```

**Version B (Curiosity):**
```
Noticed you're using Quality Gate++ - quick question
```

**Version C (Value):**
```
[Org Name]: Free quality trends dashboard (already using our workflow)
```

### Email Body

```markdown
Hi [First Name],

I noticed [Org Name] is using Quality Gate++ (our GitHub Actions workflow for mutation testing + perf budgets + dep health). That's awesome!

Quick context: I'm [Your Name], creator of Quality Gate++. We're launching a hosted dashboard to track quality trends over time (mutation scores, CVSS, perf budgets), and I'd love to offer [Org Name] free beta access.

**What you'd get:**
- No Docker/Fly.io setup: just point your workflow at our ingest endpoint
- 90-day trend history with Chart.js visualizations
- Slack/Discord webhooks for daily quality digests
- Free for 90 days (normally $10/dev/month)

**What I'm asking:**
- 15-minute feedback call after 2 weeks of usage
- Share what's working / what's missing
- Optional testimonial if you like it (no pressure)

Interested? I can set up your account today. Just reply with your preferred email for the dashboard login.

If not, no worries! Thanks for using Quality Gate++ either way. Let me know if you have any questions or feature requests.

Cheers,
[Your Name]
[Your Title]
Quality Gate++

P.S. We just published a case study analyzing 10,000 PRs. Might interest you: [link to blog post]
```

### Follow-Up Email (if no reply in 5 days)

```markdown
Hi [First Name],

Following up on my email from [Day]. Totally understand if you're busy or not interested.

Just wanted to offer one more time: if [Org Name] wants free hosted dashboard access (no strings attached, just testing it with early users), I can set it up in ~5 minutes.

Otherwise, feel free to ignore. Thanks for using Quality Gate++!

Best,
[Your Name]
```

---

## Step 4: Tracking Spreadsheet

Create Google Sheet or CSV with columns:

| Org Name | Repo | Contact Name | Email | Status | Notes | Follow-Up Date |
|----------|------|--------------|-------|--------|-------|----------------|
| Acme Corp | acme/api | Jane Doe | jane@acme.io | Sent (11/16) | CTO, found on LinkedIn | 11/21 |
| Beta Labs | beta/web | John Smith | john@beta.com | Replied (11/17) | Interested, set up call | - |
| Gamma Inc | gamma/backend | - | - | No contact found | Skip, try later | - |

**Status codes:**
- `Sent (date)` - Email sent, awaiting reply
- `Replied (date)` - Got response, action needed
- `Call scheduled (date)` - Feedback call on calendar
- `Setup complete` - Using hosted dashboard
- `Not interested` - Declined politely
- `Bounced` - Invalid email
- `No contact found` - Skip for now

---

## Step 5: Automation (Optional)

### Using Mailchimp/SendGrid Merge Tags

Create CSV:
```csv
email,first_name,org_name,repo
jane@acme.io,Jane,Acme Corp,acme/api
john@beta.com,John,Beta Labs,beta/web
```

Upload to Mailchimp, create campaign with merge tags:
```
Hi *|FNAME|*,

I noticed *|ORG_NAME|* is using Quality Gate++ (repo: *|REPO|*)...
```

**Caution:** Personalized cold emails work better than bulk sends. SendGrid free tier: 100 emails/day.

---

## Step 6: Call Script (15-Minute Feedback Interview)

**Intro (2 minutes):**
- Thank them for time
- Quick recap: "You've been using Quality Gate++ for [duration]. I want to hear what's working and what's not."

**Discovery (5 minutes):**
1. How did you discover Quality Gate++?
2. What problem were you trying to solve?
3. Which ecosystems are you using? (Node/Python/Java)
4. What are your current mutation score thresholds?
5. Any bugs caught by mutation testing that coverage missed?

**Dashboard feedback (5 minutes):**
1. How often do you check the dashboard?
2. Which metrics matter most? (mutation, CVSS, perf)
3. What's missing? (e.g., email alerts, team leaderboards, historical diffs)
4. Would you pay $10/dev/month after beta ends?

**Wrap-up (3 minutes):**
1. Any other features you'd like to see?
2. Would you recommend Quality Gate++ to other teams?
3. Comfortable giving a testimonial? (quote + logo on website)
4. Ask: "Know 2-3 other CTOs who might be interested?" (referrals)

**Post-call:**
- Send thank-you email with summary
- Add notes to CRM/spreadsheet
- If they say yes to testimonial, draft quote and get approval

---

## Step 7: Referral Loop

**At end of call, ask:**
> "Who else do you know who's frustrated with code coverage or performance regressions? I'm looking for 5-10 more beta testers."

**Incentive options:**
- "Refer 3 teams, get 6 months free" (after beta ends)
- "Refer 1 team, get your company logo on our homepage"
- "Top referrer gets free Enterprise tier for a year"

**Referral tracking:**
- Give each user a unique code: `ACME-CORP-BETA`
- New signups enter code → credit original user
- Monthly leaderboard: "Top 5 referrers this month"

---

## Example Sent Emails (Real Templates)

### Version 1: Short & Direct

```
Subject: Quick question about Quality Gate++

Hi Jane,

Saw Acme Corp is using Quality Gate++ for mutation testing. Nice!

We're launching a hosted dashboard (quality trends, Slack alerts, no Docker setup). Want free beta access?

Takes 5 min to set up. Just reply if interested.

Thanks,
[Your Name]
```

### Version 2: Value-First

```
Subject: [Acme Corp] Free quality trends dashboard

Hi Jane,

I'm the creator of Quality Gate++ (the workflow you're using at acme/api).

I wanted to offer Acme Corp free access to our new hosted dashboard:
- Track mutation scores & CVSS trends over time
- Slack daily digests ("3 PRs merged, avg mutation 82%")
- No Docker/Fly.io setup

Normally $10/dev/month, but free for 90 days for early adopters.

Interested? I can set up your account today.

Either way, thanks for using Quality Gate++!

[Your Name]
Quality Gate++ | quality-gate.dev
```

---

## Metrics to Track

| Metric | Target (30 days) |
|--------|------------------|
| Emails sent | 50 |
| Reply rate | 20% (10 replies) |
| Signups | 10% (5 beta users) |
| Calls scheduled | 5% (2-3 calls) |
| Conversion to paid (after beta) | 40% (2 paid customers) |

**Success = 2 paying customers** from 50 outreach emails (4% cold email → customer rate is excellent for B2B SaaS).

---

## Legal/Compliance

**GDPR/CAN-SPAM compliance:**
- ✅ Include physical address in footer (or use company name + link to contact page)
- ✅ Add unsubscribe option: "Reply UNSUBSCRIBE to opt out"
- ✅ Don't harvest emails from LinkedIn connections (against TOS)
- ✅ Use legitimate interest basis (they're already users, this is product update)

**Email footer template:**
```
---
[Your Company Name]
[Address or quality-gate.dev/contact]

Reply STOP to unsubscribe from beta invites.
```

---

## Tools Checklist

- [ ] GitHub CLI (`gh`) authenticated
- [ ] Hunter.io account (email finder)
- [ ] LinkedIn Premium (optional, better search)
- [ ] Google Sheet for tracking
- [ ] Calendly link for scheduling calls
- [ ] SendGrid/Gmail for sending (avoid spam folder)
- [ ] Loom for video demos (if needed)

---

## Next Steps

1. **Week 1:** Scrape 50 orgs, find 30 emails
2. **Week 2:** Send 10 emails/day (avoid spam triggers)
3. **Week 3:** Follow up with non-responders
4. **Week 4:** Schedule calls, gather feedback, iterate dashboard

**Expected outcome:** 2-5 beta users, 1-2 testimonials, 10+ feature ideas, 1-2 customers post-beta.
