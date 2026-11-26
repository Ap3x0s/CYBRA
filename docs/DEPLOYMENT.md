# Delivery and deployment

> Russian version: [docs/ru/DEPLOYMENT.md](ru/DEPLOYMENT.md).

CYBRA ships as **two services** — a backend API and a frontend nginx that
serves the SPA and proxies `/api`. There is no desktop build and no
separate reverse proxy: nginx plays that role. See
[ARCHITECTURE.md](ARCHITECTURE.md) for why the boundary is drawn there.

## What ships

Two container images:

| Image | Contents | Port |
|---|---|---|
| `cybra-backend` | Python 3.12, FastAPI app, run supervisor | 8000 (internal) |
| `cybra-frontend` | nginx, the built SPA, proxy for `/api` | 8080 (published) |

Only the frontend publishes a port. The backend is reachable solely
through the frontend's proxy on the compose network — there is no second
open port and no way around the proxy.

Both images are built by CI from the same commit and referenced by digest
in `infra/releases/*.yml`.

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

That command downloads from PyPI, npm and GitHub. On a stand with no internet it
cannot work: the packages have to be carried in. See
[OFFLINE.md](OFFLINE.md) for building and installing from a bundle.

## How the artefact is produced

The parent pipeline is a dispatcher; the 18 stages live in three child
pipelines, one per service:

```
merge request
   │
   ├── repo:precommit      hook present, i18n audit                      (step 0)
   ├── repo:secrets        gitleaks, once per repository                 (step 6)
   ├── repo:iac            Dockerfile + compose + all pipelines          (step 7)
   │
   ├── backend  → .gitlab/ci/pipelines/backend.yml
   │     validate, format, lint, test, sast, secrets, iac, build, sbom,
   │     sca, image-scan, deploy-test, dast, sign, release, approve,
   │     deploy-prod, smoke-prod, rollback
   │
   ├── frontend → .gitlab/ci/pipelines/frontend.yml
   │     same 18 steps, different commands: npm ci instead of pip,
   │     nginx.conf instead of ruff, smoke checks the /api proxy
   │
   └── infra    → .gitlab/ci/pipelines/infra.yml
         compose config, ansible --syntax-check, release manifest schema
```

`rules: changes` decides which child pipelines run: an edit under
`frontend/**` never runs pytest.

On a git tag the release stage adds `backend:sign` / `frontend:sign` —
cosign keyless signature over the image digest and the SBOM — and
`*:release`, which copies `:<sha>` to `:<tag>`.

Defined in [`.gitlab-ci.yml`](../.gitlab-ci.yml) and the three files under
[`.gitlab/ci/pipelines/`](../.gitlab/ci/pipelines/). GitHub Actions runs
the same stages as two workflows, `backend.yml` and `frontend.yml`, with
`paths:` filters doing what `rules: changes` does here. The registry
differs: ghcr.io there, the GitLab registry here. Publishing from both to
the same name would give two different "latest" tags, so each platform
publishes to its own.

Of the 18 stages in the reference DevSecOps scheme, 17 are implemented for
each service. The one that is not is DAST (stage 11): it needs a live
deployment with a model attached, and running a model inside CI costs
gigabytes and hours. It stays a manual procedure in
[VALIDATION-CYBRA.md](VALIDATION-CYBRA.md). The infra pipeline implements
15 of 18 — it has nothing to build or sign, and the file says so rather
than leaving the gaps unexplained.

### Signing without a key

`backend:sign` and `frontend:sign` sign with cosign in keyless mode. There
is no private key anywhere: GitLab issues an OIDC token (`id_tokens` with
`aud: sigstore`), Sigstore exchanges it for a short-lived certificate, and
the signature lands in the transparency log. This needs the project to live
on GitLab.com — a
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

Deployment is done by Ansible from `infra/`, driven by a release manifest.
The manifest fixes each image **by digest**, so what runs on the host is
exactly what CI built:

```bash
# 1. One-time secret. Losing it makes stored endpoint keys undecryptable.
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 2. Deploy a release to an environment
ansible-playbook -i infra/inventories/dev/hosts.yml \
  infra/ansible/playbooks/deploy.yml \
  -e release_id=cybra-0.1.0 \
  -e target_env=dev \
  -e backend_image=registry.gitlab.com/ap3x0/cybra/backend@sha256:<digest> \
  -e frontend_image=registry.gitlab.com/ap3x0/cybra/frontend@sha256:<digest>
```

The playbook validates its inputs, renders `.env` from
`infra/configurations/`, runs `docker compose config`, pulls, brings the
stack up and waits for health. A missing secret or a malformed digest stops
it before anything is downloaded.

`CYBRA_COOKIE_SECURE=1` is required behind HTTPS. Without it the session cookie
is sent over plain HTTP — `infra/configurations/environments/prod-lab.yml`
sets it, dev and stage do not.

Manually, without Ansible, for a quick local check:

```bash
cd infra
printf 'BACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\nFRONTEND_PORT=8080\n' \
  "<backend@sha256:...>" "<frontend@sha256:...>" > .env
printf 'CYBRA_SECRET_KEY=%s\n' "<key>" > backend.env
printf 'FRONTEND_PORT=8080\n' > frontend.env
docker compose --env-file .env -f compose.yaml up -d
```

`infra/compose.yaml` deliberately has no `build:` section. It pulls. With
`build:` compose quietly assembles the image from the local context and
overwrites the same tag, so two machines end up running two different builds
under one name — the exact thing a shared container deployment is meant to
prevent. Only CI builds and publishes.

`docker/compose.prod.yaml` from the monolith era is kept only as a marked
stub: it would deploy the backend without the frontend, which is a stand
where the API answers and there is nothing to open.

Point the file at a specific registry with `CYBRA_IMAGE`:

```bash
CYBRA_IMAGE=ap3x0/cybra:latest \
  docker compose -f docker/compose.prod.yaml up -d
```

`pull_policy` defaults to `always` for the same reason: if the image is
missing locally, compose would otherwise try to build it from the context
and fail with an obscure error. It is overridable through
`CYBRA_PULL_POLICY` so a local stack built by `docker build` can be tested
before its images reach a registry.

Open `http://<host>:8080`. On first start the admin password is printed to the
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

Deploy a newer release manifest — the same playbook, a different
`release_id`:

```bash
ansible-playbook -i infra/inventories/dev/hosts.yml \
  infra/ansible/playbooks/deploy.yml \
  -e release_id=cybra-0.2.0 -e target_env=dev \
  -e backend_image=<...>@sha256:<digest> -e frontend_image=<...>@sha256:<digest>
```

Only changed containers are recreated. `state: present` with compose v2
leaves unchanged services alone, so an update of one service does not
restart the other.

Rolling back means deploying the previous manifest: the digests are
already recorded there, so nothing is rebuilt. That is the whole point of
pinning by digest rather than by tag.

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
