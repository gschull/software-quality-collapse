# Python Quality Gate POC

POC for mutation testing and unit tests with pytest + mutmut.

## Run locally

```powershell
cd solutions\software-quality-collapse\poc\python-quality-gate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pytest -q
mutmut run --use-coverage
mutmut html
```

## GitHub Actions example

```yaml
name: Python Quality Gate POC
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -e .
        working-directory: solutions/software-quality-collapse/poc/python-quality-gate
      - name: Run tests
        run: pytest -q
        working-directory: solutions/software-quality-collapse/poc/python-quality-gate
      - name: Mutation tests
        run: mutmut run --use-coverage
        working-directory: solutions/software-quality-collapse/poc/python-quality-gate
```
