# Java Quality Gate POC

Maven + PIT mutation testing + JUnit.

## Run locally

```bash
cd solutions/software-quality-collapse/poc/java-quality-gate
mvn -q -DskipTests=false test
mvn -q org.pitest:pitest-maven:mutationCoverage
```

## GitHub Actions example

```yaml
name: Java Quality Gate POC
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'
      - run: mvn -q -DskipTests=false test
        working-directory: solutions/software-quality-collapse/poc/java-quality-gate
      - run: mvn -q org.pitest:pitest-maven:mutationCoverage
        working-directory: solutions/software-quality-collapse/poc/java-quality-gate
```
