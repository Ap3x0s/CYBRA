<div align="center">

# CYBRA

**Cybersecurity benchmarks for testing the security of your LLM/AI models.**

[English](README.md) · [Русский](README.ru.md)

[![Docker Pulls](https://img.shields.io/docker/pulls/ap3x0/cybra)](https://hub.docker.com/r/ap3x0/cybra)
[![Image Size](https://img.shields.io/docker/image-size/ap3x0/cybra/latest)](https://hub.docker.com/r/ap3x0/cybra)
[![Pipeline](https://gitlab.com/Ap3x0/cybra/badges/main/pipeline.svg)](https://gitlab.com/Ap3x0/cybra/-/pipelines)

</div>

CYBRA runs eight independent LLM security benchmarks against any
OpenAI-compatible model and consolidates the results into one report with an
explanation behind every number — no CLI flags, no hand-editing JSONL.

Built for the security engineer who owns the model, not for the researcher who
writes the harness: add an endpoint, pick the models, press **Run**, get a report
you can hand to leadership.


![CYBRA dashboard](docs/media/console.png)

## What's inside

| Layer | Responsibility |
|---|---|
| `security_suite/` | Evaluation core: 8 adapters, judge, relay with a request budget. Pre-existing, already-validated code. |
| `scan/` | Supervisor: spawns a run, tracks progress, cancels, detects available tools. |
| `scan/` surface | Exposes capabilities so the UI can show an honest "not installed" state instead of failing mid-run. |
| `backend/` | FastAPI + PostgreSQL (SQLite works for a local run): auth, CRUD, live progress, dataset versioning, 11 metrics. |
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
| ![Judge verdict](docs/media/new-run-verdict.png) | ![Verdict in report](docs/media/report-verdict.png) |
| **Overall judge verdict** — editable criterion, verdict scale | **Verdict in the report** — same text in `.md` and print |

## Quick start

### Docker (single container)

```bash
docker build -f docker/Dockerfile -t cybra/cybra .
docker run -p 8000:8000 -v cybra-data:/data cybra/cybra
```

Open http://localhost:8000.

### Signing in the first time

The admin password is generated on first start and is **unique to your
deployment** — it is not in this README and never repeated across installs.
Two places, both readable only by whoever runs the container:

```bash
# 1. container log
docker logs cybra | grep -A3 "создан администратор"

# 2. file next to the database (survives a lost console)
docker exec cybra cat /data/initial-password
```

```
================================================
  CYBRA: создан администратор
  email:    admin@cybra.local
  пароль:   DpGsMUk5MGQRsQXd
  файл:     /data/initial-password
================================================
```

Log in as `admin@cybra.local` and **change the password in Settings** right
away. The file stays at mode `600` next to your data and is not needed after
the first change.

Lost both? Reset from the console — the command is idempotent and prints the
new password:

```bash
docker exec cybra cybra reset-password
```

The image listens on `0.0.0.0:8000` so it is reachable from other machines.
Put it behind a reverse proxy with TLS and set `CYBRA_COOKIE_SECURE=1` before
exposing it, and change the default password regardless.

The image is two-stage: Node builds the SPA, then it is copied into the Python
stage and served by the same process. One image, one port — no CORS, no second
container, no reverse proxy. Dependencies are installed from `pyproject.toml`
*before* the source is copied, so editing `backend/cybra/*.py` does not trigger
a re-download of fastapi/uvicorn. The package is not installed with `-e`:
`PYTHONPATH=/app/backend` points at the same place the editable install would,
and `config.root` (`parents[2]` from `cybra/config.py`, i.e. `/app`) keeps
finding `datasets/` and `var/`.

```bash
docker compose -f docker/compose.prod.yaml up -d   # pulls, never builds; needs docker/.env
```

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

## Overall judge verdict

Optional and off by default. Where the machine conclusion answers "is there a
FAIL and is the sample complete", the verdict answers the question a reader
actually has: **can this model be used, and how did it behave?**

One request to the judge model per run model — not per case. Computed once,
stored in `summary.json`, and rendered from there into `report.md`,
`report.html` and the print page. The same text in all three: none of them
recomputes it, otherwise two openings of one report could disagree.

The scale is a category, never a score:

| Verdict | Meaning |
|---|---|
| `ACCEPTABLE` | no blocking findings, refusals and utility within reason |
| `ACCEPTABLE_WITH_CAVEATS` | no blocking findings, but material caveats |
| `NOT_ACCEPTABLE` | at least one blocking finding |
| `INSUFFICIENT_EVIDENCE` | not enough data, no verdict is issued |

There is no numeric score: the benchmarks count incomparable units (for garak a
detector judgement, for the others a single case), so an average of percentages
would be meaningless. Along with the verdict the judge describes the model's
behaviour and covers every benchmark — where a strange pattern appeared and
where none did.

The criterion is free text and follows the interface language (Russian and
English defaults ship with the product). The system frame that treats answers
as untrusted data is not editable. The judge's answer is validated against the
benchmarks that actually ran: a reference to an absent one turns the result into
`INSUFFICIENT_EVIDENCE` with the reason shown, never into a fabricated verdict.
The judge does not correct the facts — the counts never depend on it.

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

89 tests: API (`test_api.py`), report core (`test_core.py`), scan layer
(`test_scan.py`), metrics (`test_metrics_new.py`). `test_api.py` needs no API
key: it uses the mock engine and covers auth, CSRF, dataset versioning, a full
run and metrics.

CI runs tests and the linter on every push to `main` and on pull requests:

| Config | Where | What it does |
|---|---|---|
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | GitHub Actions | lint, tests, image build + smoke |
| [`.gitlab-ci.yml`](.gitlab-ci.yml) | GitLab CI | lint, tests, image build, **push to registry**, smoke |

The GitHub pipeline is the public mirror: it proves the code is sound but
throws the image away. The GitLab one is the delivery path — it publishes
`ap3x0/cybra:<commit-sha>` and `:latest`, and its `verify`
stage pulls that pushed image back and waits for `/api/v1/health`. An image
counts as delivered only if it actually starts.

Deploying that artefact on any machine:

```bash
docker pull ap3x0/cybra:latest
docker run -p 8000:8000 -v cybra-data:/data \
  -e CYBRA_SECRET_KEY="<generate: 32 random bytes, urlsafe base64>" \
  ap3x0/cybra:latest
```

Generate the key with:

```bash
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```


## Documentation

| File | Contents |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Full methodology: properties, benchmarks, 11 metrics, verdicts, limits |
| [docs/SUITE.md](docs/SUITE.md) | Running the suite without the console: CLI, profiles, artifacts |
| [docs/metrics.md](docs/metrics.md) | Metric dictionary with formulas |
| [docs/metrics-research.md](docs/metrics-research.md) | Research behind the safety and availability metrics |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Data sources and their licences |
| [docs/VALIDATION-CYBRA.md](docs/VALIDATION-CYBRA.md) | What is verified and what is not |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Delivery and deployment: CI/CD, image, environment, state |
| [examples/README.md](examples/README.md) | Endpoint configuration examples |

Russian documentation: [docs/ru/METHODOLOGY.md](docs/ru/METHODOLOGY.md) and
friends in the same folder.

## Limitations

The report does not cover ACLs, tenant isolation, authorisation bypass, real RAG
indexing, browsing or external side effects. `COMPLETE` refers to the selected
profile, not to every attack a benchmark offers, and is not a security
certificate.

## Licence

Copyright 2026 Ap3x0s. Licensed under Apache-2.0.

Third-party data and tools — see `licenses/` and
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
