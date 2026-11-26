# Образ backend-сервиса CYBRA.
#
# Только API и супервизор прогонов. SPA больше не копируется внутрь: с
# разделением на микросервисы её собирает и раздаёт отдельный контейнер
# (см. frontend/Dockerfile). Здесь нет ни node, ни npm.
#
# Почему это важно, а не косметика: раньше правка любого .jsx пересобирала
# весь Python-образ, включая слой с fastapi/uvicorn. Теперь у сервисов
# независимые пайплайны и независимые кеши слоёв (--cache-repo у kaniko),
# и пересборка фронта бэкенд не трогает вовсе.
#
# Heavy tools (garak, PyRIT, promptfoo) в образ НЕ входят: они тянут torch и
# Node-бинарь на гигабайты. Их ставят поверх командой `cybra setup`, а UI
# честно показывает, чего нет. Подробности — docs/OFFLINE.md.

FROM python:3.12-slim AS runtime

# OCI-метаданные образа: кто владелец, под какой лицензией распространяется.
LABEL org.opencontainers.image.title="CYBRA backend" \
      org.opencontainers.image.description="API and run supervisor for CYBRA, LLM security benchmarks" \
      org.opencontainers.image.authors="Ap3x0s" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/Ap3x0s/CYBRA"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CYBRA_DATA_DIR=/data \
    CYBRA_HOST=0.0.0.0 \
    CYBRA_PORT=8000

WORKDIR /app

# Минимальные системные зависимости: корневые сертификаты для корпоративных
# эндпоинтов и curl для healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Зависимости ставим ДО копирования исходников, и только по pyproject.toml.
# Иначе любая правка в cybra/*.py меняет слой COPY и заставляет pip заново
# тянуть fastapi/uvicorn из сети — на пустом кеше это минуты, а зависимостей
# ровно восемь строк, которые меняются куда реже кода.
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN python -c "import tomllib, pathlib; print('\n'.join(tomllib.loads(pathlib.Path('/app/backend/pyproject.toml').read_text())['project']['dependencies']))" > /tmp/requirements.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

COPY backend/cybra /app/backend/cybra
# Без editable-установки: пакет уже лежит по своему боевому пути, а
# `pip install -e` лишь прописывал этот путь в sys.path. PYTHONPATH делает то
# же самое без сборки .pth-файлов и без пересборки слоя при каждой правке.
# Путь важен ещё и потому, что config.root = parents[2] от cybra/config.py,
# то есть /app: оттуда берутся datasets/ и var/. Переезд пакета в
# site-packages сломал бы оба каталога.
ENV PYTHONPATH=/app/backend

# Консольную команду `cybra` ставит entry point из pyproject.toml, а он
# устанавливается только вместе с пакетом. Раз пакет не ставим — даём обёртку:
# подсказки в UI («run: cybra setup --tools garak») остаются верными.
RUN printf '#!/bin/sh\nexec python -m cybra "$@"\n' > /usr/local/bin/cybra \
 && chmod +x /usr/local/bin/cybra

COPY scan /app/scan
COPY security_suite /app/security_suite
COPY datasets /app/datasets
COPY vendor /app/vendor
COPY run.py /app/run.py
COPY sources.lock.json /app/sources.lock.json

RUN useradd --create-home --uid 10001 cybra \
 && mkdir -p /data \
 && chown -R cybra:cybra /data /app
USER cybra

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["python", "-m", "cybra", "--host", "0.0.0.0"]
