# Delivery and deployment

> Russian version: [docs/ru/DEPLOYMENT.md](ru/DEPLOYMENT.md).

CYBRA is a web console: one process serves both the SPA and the API. There is no
desktop build and no separate frontend container. This page explains what the
artefact is, how it is produced, and what to run on the target machine.

## What ships

A single container image. Inside it:

| Layer | Contents |
|---|---|
| Python 3.12 | FastAPI app, SQLite database, run supervisor |
| Static SPA | React build, served by the same process from `backend/static` |
| Entrypoint | `python -m cybra --host 0.0.0.0` |

The image does **not** contain `garak`, `PyRIT`, `AgentDojo`, `Promptfoo` or
`HarmBench`. They pull torch or a Node binary measured in gigabytes. The console
detects what is present and shows an honest status instead of crashing mid-run;
install them inside a running container with `cybra setup --tools …` if the
deployment needs real benchmarks.

## How the artefact is produced

```
push to main
   │
   ├── lint:backend    ruff check backend scan
   ├── lint:frontend   npm ci && npm run build
   ├── test:backend    pytest tests/ -q            (40 tests, no API key needed)
   ├── build:image     docker build → :<commit-sha> and :latest
   ├── publish:registry  push both tags             (default branch only)
   └── verify:smoke    pull :<sha>, start it, wait for /api/v1/health
```

Defined in [`.gitlab-ci.yml`](../.gitlab-ci.yml). GitHub Actions runs an
equivalent check but does not publish: the public mirror proves the code is
sound, GitLab is the delivery path. Publishing from both would give two
different "latest" tags.

Notes that cost time to rediscover:

- The runner is **not** privileged, so `docker:dind` does not start. Jobs use the
  host daemon through a mounted `/var/run/docker.sock`. Layers therefore survive
  between jobs and the image is not rebuilt from scratch each time.
- `verify` pulls the image back from the registry and starts it. A build that
  compiles but does not boot fails there, not in production.
- The `docker:29` job image has no `curl`; `verify` uses `wget`.
- Port 18080, not 8000: the host usually has a dev server on 8000.

## Deploying

```bash
# 1. One-time secret. Losing it makes stored endpoint keys undecryptable.
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 2. Pull and run
docker login registry.example.com
docker pull registry.example.com/<namespace>/cybra:latest

docker run -d --name cybra \
  -p 8000:8000 \
  -v cybra-data:/data \
  -e CYBRA_SECRET_KEY="<the key from step 1>" \
  -e CYBRA_COOKIE_SECURE=1 \
  registry.example.com/<namespace>/cybra:latest
```

`CYBRA_COOKIE_SECURE=1` is required behind HTTPS. Without it the session cookie
is sent over plain HTTP.

Or with compose, which also sets a restart policy:

```bash
printf 'CYBRA_SECRET_KEY=%s\n' "<key>" > docker/.env
docker compose -f docker/compose.prod.yaml pull
docker compose -f docker/compose.prod.yaml up -d
```

`compose.prod.yaml` deliberately has no `build:` section. It pulls. With
`build:` compose quietly assembles the image from the local context and
overwrites the same tag, so two machines end up running two different builds
under one name — the exact thing a shared container deployment is meant to
prevent. Only CI builds and publishes.

Point the file at a specific registry with `CYBRA_IMAGE`:

```bash
CYBRA_IMAGE=registry.example.com/<namespace>/cybra:latest \
  docker compose -f docker/compose.prod.yaml up -d
```

`pull_policy: always` is set for the same reason: if the image is missing
locally, compose would otherwise try to build it from the context and fail with
an obscure error.

Open `http://<host>:8000`. On first start the admin password is printed to the
log once; change it in **Settings**.

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `CYBRA_SECRET_KEY` | generated into the data dir | Fernet key for endpoint API keys. Set it explicitly in production. |
| `CYBRA_DATA_DIR` | `/data` in the image, `var/` from source | Database, run artefacts, secret fallback |
| `CYBRA_HOST` / `CYBRA_PORT` | `127.0.0.1` / `8000` | Listen address |
| `CYBRA_ENGINE` | `subprocess` | `mock` runs an offline fixture |
| `CYBRA_COOKIE_SECURE` | `0` | `1` behind HTTPS |
| `CYBRA_SESSION_TTL_HOURS` | `12` | Session lifetime |
| `CYBRA_ALLOW_REGISTRATION` | `0` | Self-service sign-up |

### State

Everything lives under `CYBRA_DATA_DIR`:

```
cybra.sqlite3    database (WAL)
runs/            one directory per run: manifest, progress, records, report
secret.key       only if CYBRA_SECRET_KEY was not set
```

Back up that directory. The SQLite database and the run artefacts are the only
state; the container itself is disposable.

## Updating

```bash
docker pull registry.example.com/<namespace>/cybra:latest
docker compose -f docker/compose.prod.yaml up -d
```

The database schema is created on start and has no migrations yet: a release
that changes it needs a fresh `CYBRA_DATA_DIR` or a manual migration. This is
recorded in [VALIDATION-CYBRA.md](VALIDATION-CYBRA.md) as a known limitation
rather than a guarantee.

## What is not built

**Desktop application — decided as "later", not "no".** The design document
lists `cybra.exe` (PyInstaller) as a second delivery channel for offline local
use. It is not implemented. The decision taken: the browser format is the
current deliverable, the exe is a later block of work. The web console works in
a browser on the same machine, so the exe adds convenience (a double-click, no
terminal) rather than capability. When it is built, the honest scope is: UI +
API + clean adapters, no heavy benchmarks — the same trade-off the image makes.

**PWA offline mode.** `frontend/public/manifest.webmanifest` is present, so the
console can be installed to the home screen on a phone or desktop, but there is
no service worker: without a connection the app does not load. The manifest
makes it feel like an app; it is not an offline application. This is deliberate
for now — the benchmarks themselves need network access to reach a model
endpoint, so an offline shell would open onto screens that cannot do anything.
