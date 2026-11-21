# Delivery and deployment

> Russian version: [docs/ru/DEPLOYMENT.md](ru/DEPLOYMENT.md).

CYBRA is a web console: one process serves both the SPA and the API. There is no
desktop build and no separate frontend container. This page explains what the
artefact is, how it is produced, and what to run on the target machine.

## What ships

A single container image. Inside it:

| Layer | Contents |
|---|---|
| Python 3.12 | FastAPI app, run supervisor |
| PostgreSQL | Application database, outside the image (see below) |
| Static SPA | React build, served by the same process from `backend/static` |
| Entrypoint | `python -m cybra --host 0.0.0.0` |

### Database

The application talks to PostgreSQL through `CYBRA_DATABASE_URL`, for example:

```
CYBRA_DATABASE_URL=postgresql+psycopg://cybra:secret@db:5432/cybra
```

The driver (`psycopg[binary]`) is part of the image, so no extra install step is
needed and no compiler or `libpq-dev` is required.

The database is **not** part of the image: it is a separate service, so it
survives container replacement and can be backed up on its own schedule.

`docker/compose.prod.yaml` ships a PostgreSQL service under the `db` profile. It
is off by default so that a first run needs nothing but one secret:

```
# SQLite in the volume, no second service
docker compose -f docker/compose.prod.yaml up -d

# PostgreSQL, with CYBRA_DATABASE_URL pointing at the `db` service
printf 'POSTGRES_PASSWORD=...\nCYBRA_DATABASE_URL=postgresql+psycopg://cybra:...@db:5432/cybra\n' >> docker/.env
docker compose -f docker/compose.prod.yaml --profile db up -d
```

See [`docker/.env.example`](../docker/.env.example) for every variable.

If `CYBRA_DATABASE_URL` is not set, the app falls back to SQLite in
`/data/cybra.sqlite3`. That mode exists for a local run without Docker and for
the test suite, where starting a database server per test is disproportionate.
It is not recommended for a production stand: the whole state then lives in one
file that a container restart can take with it.

Moving an existing SQLite install to PostgreSQL:

```
python scripts/migrate_to_postgres.py /path/to/cybra.sqlite3
python scripts/verify_migration.py /path/to/cybra.sqlite3
```

The migration keeps every row and all ids; sequences are advanced past the
maximum id afterwards, so the first insert through the API does not collide.
The verification script compares both databases row by row and checks password
hashes, JSON fields and timestamps, not just row counts.

The image does **not** contain `garak`, `PyRIT`, `AgentDojo`, `Promptfoo` or
`HarmBench`. They pull torch or a Node binary measured in gigabytes. The console
detects what is present and shows an honest status instead of crashing mid-run;
install them inside a running container with `cybra setup --tools …` if the
deployment needs real benchmarks.

## How the artefact is produced

```
merge request
   │
   ├── validate:precommit  ruff check + audit_i18n + pytest -q
   ├── format:check        ruff format --check (own code only)
   ├── lint:frontend       npm ci && npm run build
   ├── test:unit           pytest tests/ -q            (104 tests, no API key needed)
   ├── security:sast       ruff + bandit (HIGH)
   ├── security:secrets    gitleaks
   ├── security:iac        Dockerfile, .dockerignore, both pipelines
   ├── build:image         kaniko → :<commit-sha> always, :latest only from main/tag
   ├── build:sbom          syft reads the image from the registry
   ├── security:sca        pip-audit + licenses
   ├── security:image      trivy reads the image from the registry
   └── deploy:test         pull :<sha>, start it, wait for /api/v1/health
```

On a git tag the release stage adds `release:artifacts` — cosign keyless
signature over the image digest and the SBOM — and `release:publish`, which
copies `:<sha>` to `:<tag>`.

Defined in [`.gitlab-ci.yml`](../.gitlab-ci.yml). GitHub Actions runs the same
stages with the same builder; only the registry differs (ghcr.io there, the
GitLab registry here). Publishing from both to the same name would give two
different "latest" tags, so each platform publishes to its own.

Of the 18 stages in the reference DevSecOps scheme, 17 are implemented. The
one that is not is DAST (stage 11): it needs a live deployment with a model
attached, and running a model inside CI costs gigabytes and hours. It stays a
manual procedure in [VALIDATION-CYBRA.md](VALIDATION-CYBRA.md).

### Signing without a key

`release:artifacts` signs with cosign in keyless mode. There is no private key
anywhere: GitLab issues an OIDC token (`id_tokens` with `aud: sigstore`),
Sigstore exchanges it for a short-lived certificate, and the signature lands in
the transparency log. This needs the project to live on GitLab.com — a
self-managed instance would need its own Sigstore deployment.

The digest is signed, not the tag. A tag can be repointed at a different image;
a digest cannot. The SBOM is signed too, otherwise the component list could be
swapped without touching the signed image.

Verified on tag v0.2.3: both signatures reached the transparency log
(`tlog entry created with index: 4027397135`), and `cosign verify` reported
`The cosign claims were validated`.

Getting there took four tag runs, each exposing one missing piece. Recorded
because each one is a trap worth recognising:

| Run | Failure | Cause |
|---|---|---|
| v0.2.0 | `sha256sum: SHA256SUMS: No such file` | No `python3` in alpine; the script line hid it behind `\|\| echo` |
| v0.2.1 | `digest неизвестен` | `image-digest.txt` did not cross the stage boundary; needs explicit `artifacts: true` |
| v0.2.2 | `Cannot connect to the Docker daemon` | `docker-cli` provides the command, not a daemon — and this job must not have one |
| v0.2.3 | success | cosign installed as a binary instead of run as a container |

The pattern in the first three: a check that reports success when it fails.
`|| echo` substitutes a message for a real failure; an empty digest is passed
onward as if it were a value. Both now `exit 1`.

Notes that cost time to rediscover:

- **Builds use kaniko, not `docker build`.** The canonical GitLab recipe
  (`docker:dind` as a service) needs a privileged runner, which shared runners
  do not provide. kaniko builds in userspace: no daemon, no privilege. The
  image is `ghcr.io/osscontainertools/kaniko`, the maintained fork — Google
  archived `GoogleContainerTools/kaniko` in June 2025. The version is pinned;
  `latest` on a builder means the pipeline can turn red with no change in the
  repository.
- **Layer cache lives in the registry** (`--cache-repo`), because there is no
  daemon between jobs to hold it. A second build reuses all eight layers.
- **kaniko does not honour `**/__pycache__` below the second directory level.**
  Docker does. Without the extra `**/__pycache__/**` and `**/*.pyc` rules, the
  developer's `.pyc` files ship inside the image — verified on a real build.
- Image scans read the image **from the registry**, so they need `needs` on the
  build. Without it the tag does not exist yet, trivy fails with
  `MANIFEST_UNKNOWN`, and the failure hides behind `allow_failure`.
- `deploy:test` pulls the image back and starts it. A build that compiles but
  does not boot fails there, not in production.

## Deploying

```bash
# 1. One-time secret. Losing it makes stored endpoint keys undecryptable.
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 2. Pull and run
docker pull ap3x0/cybra:latest

docker run -d --name cybra \
  -p 8000:8000 \
  -v cybra-data:/data \
  -e CYBRA_SECRET_KEY="<the key from step 1>" \
  -e CYBRA_COOKIE_SECURE=1 \
  ap3x0/cybra:latest
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
CYBRA_IMAGE=ap3x0/cybra:latest \
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

Two separate things to back up, and they have different schedules:

```
PostgreSQL          users, endpoints, datasets, runs, steps, findings
                    (a separate service: see Database above)
```

```
CYBRA_DATA_DIR/
  runs/            one directory per run: manifest, progress, records, report
  secret.key       only if CYBRA_SECRET_KEY was not set
  cybra.sqlite3    ONLY when running without CYBRA_DATABASE_URL
```

Back up both. The database holds the console state and the run artefacts hold
the evidence the reports point at; one without the other is not reproducible.
The container itself is disposable.

Do not copy `cybra.sqlite3` expecting a backup of a PostgreSQL install: in that
mode the file does not exist at all, and the database lives in its own service.

## Updating

```bash
docker pull ap3x0/cybra:latest
docker compose -f docker/compose.prod.yaml up -d
```

The schema is created on start. Adding a nullable column does not need a
release step: `create_all()` handles new tables and `db.py` adds missing
columns idempotently (`_ADDED_COLUMNS`), so an existing install picks them up
on the next start without a fresh data directory. A change that renames or
retypes a column goes beyond that rule and still needs a manual migration.
This is recorded in [VALIDATION-CYBRA.md](VALIDATION-CYBRA.md) as a known
limitation rather than a guarantee.

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
