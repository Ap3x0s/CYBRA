# CYBRA verification: what is confirmed and what is not

> Russian version: [docs/ru/VALIDATION-CYBRA.md](ru/VALIDATION-CYBRA.md).

This document records what has actually been verified on this machine and what has
remained unverified. It exists so that the report to the lead does not present wishes as facts.

## Verified

| What | How | Result |
|---|---|---|
| Backend API | `pytest tests/test_api.py` | authorization, CSRF, dataset versioning, a full run |
| Reporting core | `pytest tests/test_core.py` | consolidation, escaping, paired metrics |
| Scan layer | `pytest tests/test_scan.py` | artifact contract, cancellation, capabilities |
| Metrics | `pytest tests/test_metrics_new.py` | 95 tests for `resilience_gap`, `utility_under_attack`, `agent_false_block_rate` |
| The whole suite | `pytest tests/ -q` | **95 tests, all pass** |
| Lint | `ruff check backend scan` | no findings |
| SPA build | `npm run build` | Vite, no errors |
| Application launch | uvicorn + curl | health 200, SPA is served, API 401 without a session |
| Authorization | curl + browser | login, CSRF token, roles |
| Heavy tools | `python -m cybra setup --tools …` | garak, PyRIT, AgentDojo, Promptfoo are installed in `.tools/` |
| Real runs | UI + `run.py` | 19 runs in the DB, including a run on 8 benchmarks |
| Metrics on real data | `/metrics/series` | 11 metrics, including the three new ones |
| Report | `/runs/{id}/report?fmt=md` and `pdf` | Markdown and HTML, printing without breaking tables apart |
| Dataset versioning | browser, e2e | editing a case → a new version with a parent |
| All UI screens | Playwright + screenshots | 9 screens, no errors in the console |
| Dockerfile | static check | COPY sources, USER, HEALTHCHECK |
| CI | GitHub Actions | tests and linter on push and PR |

## Not verified

**Docker image build.** Docker Desktop on the development machine does not bring up
the engine: `com.docker.service` is in the Stopped state, `docker ps` returns 500 via
the API. The Dockerfile has been checked statically and is included in CI, where the build and the smoke test
will run on a clean runner.

**Official leaderboard scores.** HarmBench and JailbreakBench use the official data,
but not their own stock classifiers and attack optimizers.
BIPIA uses the stock builders, but not the stock evaluators. Therefore the values
obtained are the result of our judge, not the official benchmark metric.

**Judge quality.** The judge's agreement with human labeling has not been
measured. ASR is the verdict of a judge model, not measured truth. All FAILs and
a random sample of PASSes should be reviewed manually.

**exe build.** A PyInstaller configuration has not been created. The decision:
the browser format is the current deliverable, the exe is a later block of work
— not a rejection. See [DEPLOYMENT.md](DEPLOYMENT.md#what-is-not-built).

## How to reproduce the verification

```bash
python -m venv .venv
.venv/bin/pip install -e backend pytest httpx ruff

# the whole suite
.venv/bin/pytest tests/ -q
.venv/bin/ruff check backend scan

# UI
cd frontend && npm install && npm run build && cd ..

# server + demo data
python -m cybra --engine mock &
python scripts/seed_demo.py admin@cybra.local "$CYBRA_PASSWORD"

# screenshots (Chrome required)
pip install playwright
python scripts/shot_docs.py admin@cybra.local "$CYBRA_PASSWORD"
```

The password is passed via the `CYBRA_PASSWORD` environment variable: there is no
value in the scripts, and it is no longer in the repository either.

## Methodology limitations

The report does not cover ACL, tenant isolation, authorization bypass, RAG indexing,
the browser, or external side effects. `COMPLETE` refers to the selected profile, not
to all attacks of the tool. For details — `docs/METHODOLOGY.md`.
