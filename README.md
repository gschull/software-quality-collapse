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

## Why it matters
- Stronger tests catch real bugs (not just higher coverage numbers)
- Performance budgets prevent slowdowns from sneaking into PRs
- Dependency health reduces supply chain risk

## Contributing
- Start with the Node POC, then adapt thresholds and scripts for your project
- PRs welcome for additional languages and checks (Go, Rust, .NET)

## License
MIT