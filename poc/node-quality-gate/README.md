# Quality Gate++ Node Example

🎯 **ELI5**: Automated quality checks that stop bad code before it reaches production. Like having a robot inspector test your code, try to break it, and measure how fast your website loads!

This example demonstrates the Quality Gate++ approach with:
- **Unit Tests** (Jest) - Does your code work?
- **Mutation Testing** (Stryker) - Are your tests strong enough to catch bugs?
- **Performance Budgets** (Lighthouse CI) - Is your website fast?
- **Dependency Health** - Are your libraries safe and up-to-date?

## 🚀 Quick Start

```bash
npm install
npm run quality:ci
```

That's it! This runs all quality checks and fails if any threshold isn't met.

## 📊 What Gets Checked

| Check | Tool | Threshold | Why It Matters |
|-------|------|-----------|----------------|
| Unit Tests | Jest | Must pass | Catches basic bugs |
| Mutation Score | Stryker | ≥70% | Ensures tests are strong |
| Performance | Lighthouse | ≥0.90 | Keeps site fast |
| Dependencies | OSV + npm | Warns on issues | Security & freshness |

## 🔧 Run Individual Checks

```bash
npm test              # Run unit tests
npm run mutate        # Run mutation testing
npm run lhci:ci       # Run Lighthouse CI
npm run dep:health    # Check dependency health
```

## ⚙️ Customize Thresholds

**Mutation testing** (`stryker.conf.json`):
```json
{
  "thresholds": { 
    "high": 80, 
    "low": 60, 
    "break": 70    // ← Fail if below this
  }
}
```

**Performance** (`lighthouserc.json`):
```json
{
  "ci": {
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.90 }]  // ← Fail if below
      }
    }
  }
}
```

**Dependency health** (environment variables):
```bash
export DEP_AGE_WARN_DAYS=730           # Warn if package older than 2 years
export DEP_FAIL_ON_VULNS=true          # Fail if vulnerabilities found
export DEP_FAIL_ON_AGE=false           # Don't fail on age (just warn)
export DEP_MAX_VULN_WARN=0             # Fail if ANY vulnerabilities
```

## 🤖 Use in CI (GitHub Actions)

### Option 1: Run Scripts Directly

```yaml
name: Quality Gate
on: [pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm install
      - run: npm run quality:ci
```

## 📂 Project Structure

```
.
├── src/
│   ├── add.js           # Example code
│   └── add.test.js      # Jest tests
├── web/
│   └── index.html       # Static site for Lighthouse
├── scripts/
│   └── dep_health.js    # Dependency health checker
├── stryker.conf.json    # Mutation testing config
├── lighthouserc.json    # Performance budget config
├── jest.config.cjs      # Test runner config
└── package.json         # Scripts and dependencies
```

## 🎓 Learn More

- **Mutation Testing**: Changes your code on purpose to see if tests catch it
- **Performance Budgets**: Sets speed limits for your website
- **Dependency Health**: Checks for security issues and outdated libraries

## 🤝 Contributing

This is a reference implementation. Feel free to:
- Adjust thresholds for your needs
- Add more test examples
- Customize the static site
- Share improvements!

## 📝 License
MIT - Use freely in your projects!
