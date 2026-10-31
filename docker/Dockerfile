# CYBRA — один образ, один порт.
#
# Двухступенчатая сборка: SPA собирается Node, затем кладётся в backend/static
# и раздаётся тем же процессом. Так нет CORS, нет второго контейнера и нет
# отдельного reverse proxy.
#
# Heavy tools (garak, PyRIT, promptfoo) в образ НЕ входят: они тянут torch и
# Node-бинарь на гигабайты. Их ставят поверх командой `cybra setup`, а UI
# честно показывает, чего нет. Для полного стенда см. compose.prod.yaml.

FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
# Build into the stage's own dist; the default config target is only valid in
# the repository layout, where backend/static exists next to frontend/.
ENV CYBRA_UI_OUTDIR=/ui/dist
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CYBRA_DATA_DIR=/data \
    CYBRA_HOST=0.0.0.0 \
    CYBRA_PORT=8000

WORKDIR /app

# Minimal system deps: TLS roots for corporate endpoints, curl for healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/cybra /app/backend/cybra
RUN pip install --no-cache-dir -e /app/backend

COPY scan /app/scan
COPY security_suite /app/security_suite
COPY datasets /app/datasets
COPY vendor /app/vendor
COPY run.py /app/run.py
COPY sources.lock.json /app/sources.lock.json
COPY --from=ui /ui/dist /app/backend/static

RUN useradd --create-home --uid 10001 cybra \
 && mkdir -p /data \
 && chown -R cybra:cybra /data /app
USER cybra

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["python", "-m", "cybra", "--host", "0.0.0.0"]
