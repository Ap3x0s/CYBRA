# Architecture: two microservices

CYBRA runs as two services instead of one image. This page explains what
each service owns, where the boundary sits, and why it is drawn there.

## Why it was split

The first version shipped a single image: Node built the SPA, the result
was copied into the Python stage, and fastapi served both the API and the
static files. That was the right trade-off for a monolith — one port, no
CORS, no second container — and the wrong one the moment the two halves
started changing at different rates.

Two concrete costs of the single image:

| Problem | Effect |
|---|---|
| Any `.jsx` edit changed the `COPY` layer of the Python image | `pip install` of fastapi and uvicorn re-ran on every UI tweak |
| One pipeline ran every check for both stacks | a CSS fix ran `pytest` for 30 seconds; a backend fix rebuilt the SPA |
| One image tag for two artefacts | backend and frontend could not version independently |

## The two services

| Service | Image | Port | Stack |
|---|---|---|---|
| `backend` | `cybra-backend` | 8000 | Python 3.12, FastAPI, uvicorn |
| `frontend` | `cybra-frontend` | 8080 | Node 22 (build) → nginx (serve) |

```
             ┌────────────────────────────────┐
  browser ──▶│  frontend — nginx :8080        │
             │    /        → /usr/share/nginx │
             │    /assets/ → long cache       │
             │    /healthz → 200 ok (nginx)   │
             │    /api/*   → proxy_pass       │──┐
             └────────────────────────────────┘  │
                                                  ▼
                                 ┌──────────────────────────────┐
                                 │  backend — uvicorn :8000     │
                                 │    /api/v1/*                 │
                                 │    не публикует порт наружу  │
                                 └──────────────────────────────┘
```

The backend publishes **no port**. The only way in is through the
frontend, which proxies `/api`. There is no second open port to forget to
close, and no way around the proxy.

## Why nginx proxies rather than the browser calling the backend

`frontend/src/api.js` calls the relative path `/api/v1`, so the browser
talks to the origin it loaded the page from. That single decision removes
three problems at once:

- **No CORS.** Two origins would need `Access-Control-Allow-Origin`,
  preflight handling and `credentials: include` on every request.
- **The session cookie works.** It is `HttpOnly` on the frontend origin.
  A cross-origin call would not carry it under the default `SameSite`
  policy, and the user would be silently logged out.
- **One public port.** The backend stays on the internal compose network.

## Things that look like details and are not

**`resolver` and a variable in `proxy_pass`.** The obvious form is
`proxy_pass http://backend:8000;`. nginx resolves that name **once**, when
the configuration is parsed, and fails with
`host not found in upstream "backend"` if the backend is not up yet. Two
consequences, both bad: `nginx -t` cannot run at image build time (which
is where a config error is cheapest to find), and after a backend restart
with a new IP, nginx keeps dialling the old one and returns 502 until it is
restarted too. The config therefore uses:

```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
set $backend_upstream "backend:8000";
proxy_pass http://$backend_upstream;
```

**`pid` moved to `/tmp`.** nginx:alpine writes `/run/nginx.pid` and
temporary files under `/var/cache/nginx`, both owned by root. Running as
`nginx` the daemon dies on start with
`open() "/run/nginx.pid" failed (13: Permission denied)`. From outside the
container that looks like "healthcheck not answering", so the diagnosis
happens in the wrong place. `frontend/Dockerfile` rewrites the path and
`nginx -t` verifies the result at build time.

**`try_files`.** Without it, reloading the page on `/runs/123` returns
404 even though clicking through inside the app works — the route exists
only in react-router, not on disk.

## Repository layout

The task allowed a single repository, so service boundaries are
reproduced by directories and pipelines rather than by separate GitLab
projects:

| Roadmap repository | Here | How the boundary is kept |
|---|---|---|
| `ci-templates` | `.gitlab/ci/templates/` | `include:` + `extends:` |
| `docker-images` | not split out | official `python:3.12-slim` / `node:22-alpine` cover it |
| `applications/infra` | `infra/` | compose, Ansible, inventories, releases |
| `configurations` | `infra/configurations/` | Jinja2 `.env.j2` templates |
| `microservices/backend` | `backend/`, `scan/`, `security_suite/` | child pipeline `backend` |
| `microservices/frontend` | `frontend/` | child pipeline `frontend` |

`scripts/check_repo_structure.py` enforces the boundary: it fails if the
backend gains a JS source file, if `docker/Dockerfile` starts building a
Node stage, or if `frontend/nginx.conf` loses its `/api` proxy.

## Two pipelines

The parent `.gitlab-ci.yml` is a dispatcher. It decides **which** pipeline
to run and performs checks common to both services. The 18 stages of the
DevSecOps scheme live in the child files:

```
.gitlab-ci.yml
├── repo:precommit        one hook check for the repository
├── repo:secrets          gitleaks, once
├── repo:iac              Dockerfile + compose + all pipelines
│
├── backend   → .gitlab/ci/pipelines/backend.yml    (18 steps)
├── frontend  → .gitlab/ci/pipelines/frontend.yml   (18 steps)
└── infra     → .gitlab/ci/pipelines/infra.yml      (CD: 15 of 18)
```

`rules: changes` is what makes the split real: an edit under `frontend/**`
does not run pytest at all.

On GitHub the same split is two workflows, `backend.yml` and
`frontend.yml`, with `paths:` filters doing the same job.

### What differs between the two pipelines

The scheme is shared; the content is not.

| Step | backend | frontend |
|---|---|---|
| 2 Format | `ruff format --check` | Vite config parses, build succeeds |
| 3 Lint | `ruff check` | build resolves every import |
| 4 Tests | `pytest --junitxml` | production build structure + JUnit |
| 5 SAST | ruff-B + bandit (HIGH) | `npm audit --audit-level=high` |
| 7 IaC | Dockerfile, compose | **nginx.conf**: directives, brace balance |
| 9 SCA | pip-audit + licenses | license-checker, GPL check |
| 12 Smoke | health + 401 without session | SPA **+ /api through nginx** + fallback |

The frontend smoke is the one that matters most: it starts both services
and requests `/api/v1/health` **through nginx**. A forgotten `proxy_pass`
is caught there rather than at the customer site.

## Infra

```
infra/
├── compose.yaml                  both services + postgres profile
├── ansible/
│   ├── playbooks/deploy.yml      validate → render → pull → up → health
│   └── roles/
│       ├── preflight/            docker, compose plugin, directories, secrets
│       └── deploy_compose/       render .env, compose config, pull, up, check
├── inventories/{dev,stage,prod-lab}/hosts.yml
├── configurations/
│   ├── templates/*.env.j2        Jinja2, rendered at deploy time
│   └── environments/*.yml        non-secret parameters per environment
└── releases/cybra-0.1.0.yml      manifest: digest of each service
```

The manifest is the centre of the model. It fixes each service **by
digest**, not by tag, so "what is deployed" has exactly one answer. The
same digest travels from dev to stage to prod-lab without a rebuild.

`scripts/update_release.py` fills the digest in from kaniko's output;
`scripts/check_release.py` refuses a manifest that still contains a
placeholder.

## What is not covered

| Item | Why |
|---|---|
| Kubernetes | The roadmap states it is out of scope for this route |
| Ansible against a real host | No target host exists; the playbook is syntax-checked in CI and verified locally |
| Vault | Secrets come from CI variables; Vault is the "harden the CD host" branch |
| DAST (step 11) | Needs a live stand with a model attached — gigabytes and hours in CI |
| Database migrations | Separate branch of the roadmap, after container rollback is proven |

## See also

- [DEPLOYMENT.md](DEPLOYMENT.md) — how the artefact is produced and deployed
- [OFFLINE.md](OFFLINE.md) — installing the heavy benchmarks without internet
