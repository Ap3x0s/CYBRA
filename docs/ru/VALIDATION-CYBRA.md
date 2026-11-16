# Проверка CYBRA: что подтверждено, а что нет

> English version: [docs/VALIDATION-CYBRA.md](../VALIDATION-CYBRA.md).

Документ фиксирует, что реально проверено на этой машине, а что осталось
непроверенным. Нужен, чтобы отчёт лиду не выдавал желаемое за факт.

## Проверено

| Что | Как | Результат |
|---|---|---|
| Backend API | `pytest tests/test_api.py` | авторизация, CSRF, версионирование датасетов, полный прогон |
| Ядро отчётов | `pytest tests/test_core.py` | консолидация, экранирование, парные метрики |
| Scan-слой | `pytest tests/test_scan.py` | контракт артефактов, отмена, capabilities |
| Метрики | `pytest tests/test_metrics_new.py` | 15 тестов на `resilience_gap`, `utility_under_attack`, `agent_false_block_rate` |
| Весь набор | `pytest tests/ -q` | **40 тестов, все проходят** |
| Линт | `ruff check backend scan` | без замечаний |
| Сборка SPA | `npm run build` | Vite, без ошибок |
| Запуск приложения | uvicorn + curl | health 200, SPA отдаётся, API 401 без сессии |
| Авторизация | curl + браузер | логин, CSRF-токен, роли |
| Тяжёлые инструменты | `python -m cybra setup --tools …` | garak, PyRIT, AgentDojo, Promptfoo установлены в `.tools/` |
| Реальные прогоны | UI + `run.py` | 19 прогонов в БД, включая прогон на 8 бенчмарках |
| Метрики на реальных данных | `/metrics/series` | 11 метрик, включая три новые |
| Отчёт | `/runs/{id}/report?fmt=md` и `pdf` | Markdown и HTML, печать без разрыва таблиц |
| Версионирование датасетов | браузер, e2e | правка кейса → новая версия с родителем |
| Все экраны UI | Playwright + скриншоты | 9 экранов, ошибок в консоли нет |
| Dockerfile | статическая проверка | COPY-источники, USER, HEALTHCHECK |
| CI | GitHub Actions | тесты и линтер на push и PR |

## Не проверено

**Сборка Docker-образа.** Docker Desktop на машине разработки не поднимает
движок: `com.docker.service` в состоянии Stopped, `docker ps` возвращает 500 по
API. Dockerfile проверен статически и включён в CI, где сборка и smoke-тест
выполнятся на чистом раннере.

**Официальные leaderboard scores.** HarmBench и JailbreakBench используют
официальные данные, но не свои штатные классификаторы и оптимизаторы атак.
BIPIA использует штатные builders, но не штатные evaluators. Поэтому полученные
значения — результат нашего судьи, а не официальная метрика бенчмарка.

**Качество судьи.** Согласованность судьи с человеческой разметкой не
измерялась. ASR — это вердикт модели-судьи, а не измеренная истина. Все FAIL и
случайную выборку PASS следует просматривать вручную.

**exe-сборка.** PyInstaller-конфигурация не создавалась: exe — второй канал
доставки, сначала делается docker-путь.

## Как воспроизвести проверку

```bash
python -m venv .venv
.venv/bin/pip install -e backend pytest httpx ruff

# весь набор
.venv/bin/pytest tests/ -q
.venv/bin/ruff check backend scan

# UI
cd frontend && npm install && npm run build && cd ..

# сервер + демо-данные
python -m cybra --engine mock &
python scripts/seed_demo.py admin@cybra.local "$CYBRA_PASSWORD"

# скриншоты (нужен Chrome)
pip install playwright
python scripts/shot_docs.py admin@cybra.local "$CYBRA_PASSWORD"
```

Пароль передаётся через переменную окружения `CYBRA_PASSWORD`: в скриптах
значения нет, в репозитории его тоже больше нет.

## Ограничения методики

Отчёт не покрывает ACL, изоляцию арендаторов, обход авторизации, RAG-индексацию,
браузер и внешние side effects. `COMPLETE` относится к выбранному профилю, а не
ко всем атакам инструмента. Подробнее — `docs/METHODOLOGY.md`.
