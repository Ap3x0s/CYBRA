# Проверка CYBRA: что подтверждено, а что нет

Документ фиксирует, что реально проверено на этой машине, а что осталось
непроверенным. Нужен, чтобы отчёт лиду не выдавал желаемое за факт.

## Проверено

| Что | Как | Результат |
|---|---|---|
| Backend API | `pytest tests/test_api.py` | 10 тестов, включая полный прогон |
| Scan-слой | `pytest tests/test_scan.py` | 6 тестов: контракт артефактов, отмена, capabilities |
| Линт | `ruff check backend scan` | без замечаний |
| Сборка SPA | `npm run build` | 242 КБ JS, 11.6 КБ CSS |
| Запуск приложения | uvicorn + curl | health 200, SPA отдаётся, API 401 без сессии |
| Авторизация | curl + браузер | логин, CSRF-токен, роли |
| Демо-прогон | `scripts/seed_demo.py` | 2 модели × 3 инструмента, 10 шагов |
| Метрики | `/metrics/series` + браузер | 8 точек, график строится |
| Отчёт | `/runs/1/report?fmt=md` | 3427 байт |
| Версионирование датасетов | браузер, e2e | правка кейса → v0.0.2 с родителем v0.0.1 |
| Все экраны UI | Playwright + скриншоты | 9 экранов, ошибок в консоли нет |
| Dockerfile | `scripts/check_dockerfile.py` | 11 COPY-источников, USER, HEALTHCHECK |

## Не проверено

**Сборка Docker-образа.** Docker Desktop на этой машине не поднимает движок:
`com.docker.service` в состоянии Stopped, `docker ps` возвращает 500 по API.
Та же проблема зафиксирована в `TRANSFER.md` этого репозитория при переносе
стенда. Dockerfile проверен статически и включён в CI, где сборка и smoke-тест
выполнятся на чистом раннере.

**Реальные модели.** Все прогоны выше — в режиме `mock`, против встроенной
фикстуры. Реальный `run.py` против настоящего endpoint не запускался: на машине
нет ни API-ключа, ни настроенного LiteLLM/OpenWebUI. Это значит, что проверена
интеграция (пути, параметры, разбор артефактов), но не качество оценок.

**Тяжёлые инструменты.** garak, PyRIT, AgentDojo и Promptfoo не установлены
(нет `uv` и Node-зависимостей в нужной конфигурации). Проверено только то, что
`capabilities` корректно сообщает об их отсутствии.

**exe-сборка.** PyInstaller-конфигурация не создавалась: по решению из спеки
exe — второй канал доставки, сначала делается docker-путь.

## Как воспроизвести проверку

```bash
python -m venv .venv
.venv/bin/pip install -e backend pytest httpx ruff

# backend + scan
.venv/bin/pytest tests/test_api.py tests/test_scan.py -q
.venv/bin/ruff check backend scan

# UI
cd frontend && npm install && npm run build && cd ..

# сервер + демо-данные
python -m cybra --engine mock &
python scripts/seed_demo.py admin@cybra.local <пароль из консоли запуска>

# скриншоты (нужен Chrome)
pip install playwright
python scripts/screenshots.py admin@cybra.local <пароль>
```

## Ограничения методики

Отчёт не покрывает ACL, изоляцию арендаторов, обход авторизации, RAG-индексацию,
браузер и внешние side effects. `COMPLETE` относится к выбранному профилю, а не
ко всем атакам инструмента. Подробнее — `docs/metrics.md` и `docs/METHODOLOGY.md`.
