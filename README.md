# CYBRA

**Cybersecurity benchmarks for testing the security of your LLM/AI models.**

CYBRA runs eight independent LLM security benchmarks against any
OpenAI-compatible model and consolidates the results into one report with an
explanation behind every number — no CLI flags, no hand-editing JSONL.

Built for the security engineer who owns the model, not for the researcher who
writes the harness: add an endpoint, pick the models, press **Run**, get a report
you can hand to leadership.

> Also available in [Russian](README.ru.md).

![CYBRA dashboard](docs/media/console.png)

## What's inside

| Layer | Responsibility |
|---|---|
| `security_suite/` | Evaluation core: 8 adapters, judge, relay with a request budget. Pre-existing, already-validated code. |
| `scan/` | Supervisor: spawns a run, tracks progress, cancels, detects available tools. |
| `scan/` surface | Exposes capabilities so the UI can show an honest "not installed" state instead of failing mid-run. |
| `backend/` | FastAPI + SQLite: auth, CRUD, live progress, dataset versioning, 11 metrics. |
| `frontend/` | React SPA: dark console and a light printable report. |

**Benchmarks:** garak, Promptfoo, PyRIT, HarmBench, JailbreakBench, BIPIA,
AgentDojo, Security Regression.

**Metrics:** 11 — see [Metrics](#metrics) below.

## Screens

| | |
|---|---|
| ![Sign in](docs/media/login.png) | ![Runs](docs/media/runs.png) |
| **Sign in** — dark card, brand mark | **Runs** — filters and verdict statuses |
| ![Run detail](docs/media/run-detail.png) | ![Report](docs/media/report.png) |
| **Run detail** — steps, categories, verdicts | **Report** — printable summary |
| ![Metrics](docs/media/metrics.png) | ![Models](docs/media/models.png) |
| **Metrics** — 11 indicators with definitions | **Models** — endpoints and models |
| ![Datasets](docs/media/datasets.png) | ![New run](docs/media/new-run.png) |
| **Datasets** — cases and versions | **New run** — pick benchmarks |

## Quick start

### Docker (single container)

```bash
docker build -f docker/Dockerfile -t cybra/cybra .
docker run -p 8000:8000 -v cybra-data:/data cybra/cybra
```

Open http://localhost:8000. On first start the admin login and password are
printed to the log — change them in **Settings**.

### From source

```bash
python -m venv .venv && .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e backend

cd frontend && npm install && npm run build && cd ..
python -m cybra --host 127.0.0.1 --port 8000
```

UI development with hot reload: `cd frontend && npm run dev` (proxies `/api`
to port 8000).

### Demo mode

No real API and no heavy tooling required:

```bash
python -m cybra --engine mock
```

Runs against a built-in fixture. Verdicts are synthetic and the UI and reports
are marked accordingly.

## Heavy benchmarks

`garak`, `PyRIT`, `AgentDojo` and `Promptfoo` are not bundled into the image or
the exe: they pull torch or a Node binary measured in gigabytes. CYBRA detects
what is present and shows an honest status in the UI instead of crashing
mid-run.

```bash
python -m cybra setup --tools garak pyrit agentdojo promptfoo
```

Each benchmark installs into an isolated `.tools/<name>` environment. Install
logs are kept and re-running is idempotent.

## How a run works

1. `POST /api/v1/runs` with a profile, models and tool selection.
2. `scan/` spawns `run.py` as a child process and reads its file contract.
3. Progress is published at `GET /runs/{id}/progress` (polled by the UI).
4. On completion `summary.json` and `records.jsonl` are imported into the database.
5. The UI renders the model × benchmark matrix and a printable report.

The evaluation core is deliberately not rewritten: the judge and PASS/FAIL
criteria have already been validated against real models, and reimplementing
them would change what the verdicts mean.

## Datasets and versions

Two editing paths, as required:

- **through the UI** — edit a case in the dataset workspace;
- **by configuration** — upload `jsonl/json/yaml/csv`; keep the file in git next
  to the repository.

Versions are immutable. Any edit creates a new version pointing at its parent,
so an old run is always reproducible. Version diff and export are included.

## Metrics

Eleven metrics, each with a formula, a meaning and an explicit caveat:

| What it shows | Metric |
|---|---|
| Attack success | `attack_success_rate` |
| Share of failed checks | `failed_check_rate` |
| Over-refusals | `refusal_rate` |
| Utility on benign input | `benign_utility_rate` |
| Following injected instructions | `injection_follow_rate` |
| Secret leakage | `leak_rate` |
| Not scored (report confidence) | `unscored_rate` |
| Completeness | `coverage` |
| Safety drop under attack wrappers | `resilience_gap` |
| Utility under injection | `utility_under_attack` |
| Blocked legitimate agent actions | `agent_false_block_rate` |

The full vocabulary is in [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and
[docs/metrics.md](docs/metrics.md).

**No single "security score" is computed.** For garak the unit is a detector
judgement; for the others it is an individual case. Combining them into one
number would present incomparable quantities as comparable.

### Benchmarks vs metrics

These are two different counts and both are correct:

- **8 benchmarks** are the tools that generate test cases and verdicts
  (`security_suite/common.py`, constant `TOOLS`);
- **11 metrics** are the formulas computed over those verdicts
  (`backend/cybra/metrics.py`, constant `CATALOG`).

Six of the eleven are different filters over the same PASS/FAIL stream; only
`resilience_gap`, `utility_under_attack` and `agent_false_block_rate` add
independent signal.

## Roles

| Role | Permissions |
|---|---|
| `viewer` | reads runs and reports |
| `operator` | starts runs, edits endpoints and datasets |
| `admin` | manages users, deletes endpoints |

Passwords use argon2, sessions live in HttpOnly cookies, mutating requests carry
a CSRF token, endpoint keys are Fernet-encrypted and never returned by the API.

## Tests

```bash
pip install pytest httpx ruff
pytest tests/ -q
ruff check backend scan
```

40 tests: API (`test_api.py`), report core (`test_core.py`), scan layer
(`test_scan.py`), metrics (`test_metrics_new.py`). `test_api.py` needs no API
key: it uses the mock engine and covers auth, CSRF, dataset versioning, a full
run and metrics.

CI (`.github/workflows/ci.yml`) runs tests and the linter on every push to
`main` and on pull requests.

## Documentation

| File | Contents |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Full methodology: properties, benchmarks, 11 metrics, verdicts, limits |
| [docs/SUITE.md](docs/SUITE.md) | Running the suite without the console: CLI, profiles, artifacts |
| [docs/metrics.md](docs/metrics.md) | Metric dictionary with formulas |
| [docs/metrics-research.md](docs/metrics-research.md) | Research behind the safety and availability metrics |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Data sources and their licences |
| [docs/VALIDATION-CYBRA.md](docs/VALIDATION-CYBRA.md) | What is verified and what is not |
| [examples/README.md](examples/README.md) | Endpoint configuration examples |

Russian documentation: [docs/ru/METHODOLOGY.md](docs/ru/METHODOLOGY.md) and
friends in the same folder.

## Limitations

The report does not cover ACLs, tenant isolation, authorisation bypass, real RAG
indexing, browsing or external side effects. `COMPLETE` refers to the selected
profile, not to every attack a benchmark offers, and is not a security
certificate.

## Licence

Apache-2.0. Third-party data and tools — see `licenses/` and
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
