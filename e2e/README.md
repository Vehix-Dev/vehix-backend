E2E Test Runner

Overview

This folder contains a lightweight end-to-end test runner to exercise the API and Channels flows as a Rider and as a Roadie. It logs API responses and websocket messages to a JSON results file and produces an HTML report.

Prerequisites

- Start your Django app and Channels layer (Redis + Daphne)
- Activate the project's virtualenv

Install test deps:

```powershell
cd config
pip install -r requirements.txt
```

How to run

1. Start Django + Channels (runserver or Daphne with Channels configured).
2. In a separate terminal, run:

```powershell
cd config
python e2e/runner.py
```

3. When complete open `config/e2e/report.html` in a browser to view results.

Notes

- Update `TEST_CONFIG` in `runner.py` with real user credentials (existing rider and roadie) and the server base URL.
- This tool is minimal and intended for local dev verification, not CI-grade tests.
