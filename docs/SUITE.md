# LLM Security Suite — единый запуск семи наборов проверок

Проект проверяет **список моделей через OpenAI-compatible Chat Completions API** и автоматически собирает результаты по каждой модели в Markdown, HTML и JSON. Подходит для LiteLLM, OpenWebUI и другого сервера с этим контрактом API.

В составе: **garak, Promptfoo, PyRIT, HarmBench, JailbreakBench, BIPIA, AgentDojo**. Все семь адаптеров выполняют запросы и сохраняют результаты; заглушек для «неподключённых» инструментов нет. Однако методики интеграции различаются — см. таблицу ниже. Проект не утверждает, что запускает все существующие атаки этих проектов.

## Быстрый запуск

Проверенная среда: Linux x86_64, Python 3.12, Node.js 22+, npm, git и uv. На Windows используйте WSL2. Для выбранных проверок GPU не нужен. Зависимости garak и PyRIT существенные: установка скачивает в том числе CPU-версии ML-библиотек. Для первой установки нужен доступ к GitHub, PyPI, npm и используемым ими хранилищам пакетов.

```bash
cd llm-security-suite
python3 -m pip install uv

# Ключ вводится без сохранения его значения в истории команд.
read -rsp 'Ключ API: ' TARGET_API_KEY; echo
export TARGET_API_KEY

python3 run.py run --install \
  --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b model-c \
  --judge-model judge-model \
  --out reports
```

`model-a`, `model-b`, `model-c`, `judge-model` замените на **точные ID/алиасы, доступные вашему серверу**. `--models 'provider/model-a' 'provider/model-b'` и `--models model-a,model-b` тоже работают. Все модели одного запуска проверяются через один целевой endpoint. Для другого endpoint выполните отдельный запуск.

`--install` автоматически устанавливает зависимости в изолированные `.tools/<инструмент>` и запускает весь набор. При повторных прогонах уберите `--install`. Установка также доступна отдельно:

```bash
python3 run.py setup
```

У самого управляющего скрипта нет сторонних Python-зависимостей. `setup` использует версии из `locks/*.txt`, `sources.lock.json` и `package-lock.json`.

## LiteLLM и OpenWebUI

Предпочтительно указывать полный URL метода, чтобы не получить лишний `/v1`:

```bash
# LiteLLM: типичный адрес
python3 run.py run \
  --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b --judge-model judge-model

# OpenWebUI: типичный адрес собственного API
python3 run.py run \
  --endpoint http://localhost:3000/api/chat/completions \
  --models model-a model-b --judge-model judge-model
```

Фактический префикс зависит от reverse proxy и вашей установки. Требуется доступный API key и разрешение на выбранные модели. API-key-аутентификацию OpenWebUI настраивают на стороне сервера. Код не использует браузерную сессию. Для стандартного префикса допустимо `--base-url http://localhost:4000/v1`: скрипт добавляет `/chat/completions`.

### Отдельная модель-судья

Судья нужен для смысловых оценок: помогает ли ответ вредоносной цели, исполняет ли инъекцию, справляется ли с допустимым заданием. По умолчанию используется тот же endpoint и ключ, но отдельный `--judge-model`.

```bash
read -rsp 'Ключ судьи: ' JUDGE_API_KEY; echo
export JUDGE_API_KEY
python3 run.py run \
  --endpoint https://target.example.org/v1/chat/completions \
  --models model-a model-b \
  --judge-endpoint https://judge.example.org/v1/chat/completions \
  --judge-model independent-judge \
  --judge-key-env JUDGE_API_KEY
```

Для сравнения моделей сохраняйте одного судью и настройки. Судья должен понимать RU/EN и возвращать JSON по инструкции. Самооценка той же моделью возможна, но создаёт смещение. Ответ `UNSCORED`, неправильный JSON и отказ API не превращаются в PASS.

### Отличия контрактов API

- Если сервер не принимает `temperature`: добавьте `--temperature omit`.
- Если требуется новый параметр лимита: `--token-parameter max_completion_tokens`.
- Если модель тратит лимит на рассуждения: увеличьте `--max-tokens`, например до `8192`. Для судьи отдельно есть `--judge-max-tokens`.
- Удалить несовместимый параметр: `--drop-params stop`. Не удаляйте `tools` для AgentDojo: это изменяет проверяемую функциональность.
- При несовместимости роли `developer`: `--developer-as-system`. Это явная модификация протокола, она фиксируется в manifest.
- Дополнительное тело запроса: `--extra-body examples/extra-body.json`; для судьи — `--judge-extra-body`.
- Дополнительные HTTP-заголовки — `--headers /path/to/private-headers.json` и `--judge-headers`. Формат: JSON-объект. Значения заголовков не записываются в manifest.
- Корпоративный CA: `--ca-file /path/to/ca.pem`. Проверка TLS включена.

Преобразования temperature/token-parameter/drop-params применяются к обоим маршрутам. При различных требованиях судьи используйте его `--judge-extra-body` для переопределения значений. Не кладите секреты в extra-body: тело запроса сохраняется в отчёте.

Проект поддерживает синхронный **Chat Completions**, а не произвольный формат, Responses API, embeddings или изображения. AgentDojo дополнительно требует корректный `tools`/`tool_calls` и многоходовый диалог. Ошибки совместимости видны как ERROR/PARTIAL. Успешный HTTP-ответ сам по себе не означает совместимость.

## Что именно запускается

| Адаптер | Реальное выполнение | Данные и оценка |
|---|---|---|
| garak | Нативный CLI 0.17.0 через OpenAICompatible | Встроенные probes и detectors; по умолчанию PromptInject HijackHateHumans, DAN 11.0, Base64 |
| Promptfoo | Нативный `promptfoo eval` 0.123.0 | 48 авторских RU/EN тестов; canary/marker assertions и API-судья |
| PyRIT | Нативный `MultiPromptSendingAttack` | 8 авторских диалогов по 3 хода; API-судья оценивает ответы всех ходов |
| HarmBench | Адаптированный API-прогон официальных данных | 240 standard/contextual behaviors из test split; 3 фиксированные обёртки; API-судья |
| JailbreakBench | Адаптированный API-прогон официальных данных | 100 harmful + 100 benign behaviors; обёртки для harmful; API-судья |
| BIPIA | Нативные builders создают запросы; адаптированный API-прогон | Официальные email/table test contexts и text attacks; security и utility оцениваются отдельно |
| AgentDojo | Нативные задачи, атаки, агентный цикл и goal checks | Встроенные suites; чистый baseline и запуски с инъекциями; API-модель вызывает тестовые инструменты |

**HarmBench/JailbreakBench не используют штатные классификаторы и оптимизаторы атак. BIPIA не использует исходный GPU inference stack и специализированные evaluators. Эти оценки нельзя называть официальными leaderboard scores.** Выбранная интеграция позволяет сравнивать произвольные API-модели без доступа к их весам.

## Объём и повторяемость

По умолчанию выполняется ограниченный стартовый профиль, а не полный перебор всех наборов:

- `--limit 10`: до 10 исходных записей в каждом обрабатываемом наборе; JBB отдельно harmful и benign, BIPIA отдельно email и table. Promptfoo — 10 из 48; PyRIT — все 8 доступных диалогов.
- `--variants direct roleplay authority`: три варианта для вредоносных behaviors HarmBench/JBB.
- `--bipia-attacks 4`: четыре официальных текста атаки; три позиции вставки для каждой пары контекст/атака.
- `--agent-suites workspace --agent-tasks 2 --agent-injections 2`: два baseline и четыре атакующих прогона.
- garak имеет собственный выбор через `--garak-probes`; `--limit` на него **не действует**. Один ответ на каждый выбранный prompt.
- `--seed 42`: одинаковая выборка для всех моделей. Даже при temperature=0 сервер может давать недетерминированные ответы.

При лимите L, A атаках BIPIA и двух типах контекста BIPIA делает до `2 × L × A × 3` целевых запросов и вдвое больше запросов судье. AgentDojo делает переменное число запросов из-за tool calls. При исчерпании бюджета результат неполный, а не успешный.

Для более широкого прогона:

```bash
python3 run.py run \
  --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b --judge-model judge-model \
  --limit 0 --bipia-attacks 10 \
  --agent-suites workspace banking travel slack \
  --agent-tasks 5 --agent-injections 3 \
  --garak-probes probes.promptinject,probes.dan,probes.encoding \
  --max-requests 20000 --tool-timeout 14400
```

`0` означает все записи для `--limit`, `--bipia-attacks`, `--agent-tasks`, `--agent-injections`. Полный BIPIA для поставленных данных: 150 контекстов × 75 атак × 3 позиции = **33 750 целевых запросов**, плюс 67 500 запросов судье. Бюджет потребуется увеличить отдельно. Используйте стартовый профиль перед большим запуском.

Ограничения по умолчанию: `--max-requests 1000` **на модель, инструмент и маршрут target/judge**, `--timeout 120` секунд на запрос и `--tool-timeout 3600` на инструмент. Нативные повторы также расходуют бюджет. Обработка моделей и инструментов последовательная, чтобы не создавать неконтролируемую параллельную нагрузку.

Отдельный инструмент запускается тем же способом:

```bash
python3 run.py run --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b --judge-model judge-model --tools garak
```

В `--tools` можно передать любой список из семи имён таблицы. Без параметра запускаются все семь.

## Итоговые файлы

Каждый запуск создаёт новый каталог `reports/<UTC-время>-<ID>/`:

| Файл | Содержание |
|---|---|
| `report.html` | Автономный HTML: модели, статусы и раскрываемые записи |
| `report.md` | Единая записка по моделям, инструментам и категориям |
| `summary.json` | Машиночитаемые итоги по каждой модели |
| `all_records.jsonl` | Нормализованные записи всех инструментов |
| `manifest.json` | Endpoint, настройки, модельные алиасы, SHA-256 данных, ревизии источников |
| `<модель-хеш>/summary.json` | Итог одной модели |
| `<модель-хеш>/<tool>/records.jsonl` | Нормализованные проверки инструмента |
| `<модель-хеш>/<tool>/http.jsonl` | Целевые и judge-запросы/ответы без auth-заголовков |
| `<модель-хеш>/<tool>/status.json` | Полнота, число запросов, ошибки транспорта |
| `<модель-хеш>/<tool>/worker.log` | Диагностика адаптера и нативного инструмента |

Кроме того, сохраняются нативные отчёты garak/Promptfoo/PyRIT, выбранные behaviors HarmBench/JBB и трассы AgentDojo. У адаптированных прогонов собственная схема, поэтому консолидация выполняется через `records.jsonl`.

Консолидация выполняется автоматически после каждого инструмента и в конце. Повторно собрать её без API-запросов:

```bash
python3 run.py merge reports/ИМЯ_КАТАЛОГА_ЗАПУСКА
```

`merge` читает каталог **этого проекта с manifest**, а не произвольные внешние отчёты несовместимых версий. Запуски разных endpoints намеренно сохраняются раздельно, чтобы не смешивать режимы проверки.

### Как читать результат

- PASS: конкретный критерий выполнен.
- FAIL: критерий нарушен; смотрите категорию. Для benign/baseline/utility это недостаточная полезность, для security — срабатывание проверки атаки.
- ERROR: запрос, инструмент или инфраструктура дали ошибку.
- UNSCORED: недостаточно данных или некорректный ответ оценщика.
- SKIPPED: тест явно пропущен.
- COMPLETE: все выполненные проверки настроенного поднабора имеют PASS/FAIL; это **не** сертификат безопасности.
- PARTIAL/ERROR: часть оценок отсутствует, выполнение оборвалось или были ошибки транспорта.

Итог модели: `FINDINGS`, `INCOMPLETE`, `FINDINGS_AND_INCOMPLETE` или `NO_FINDINGS_ON_TESTED_SET`. Общий «процент безопасности» не вычисляется: у garak единица — решение детектора, у остальных — отдельная проверка; наборы пересекаются. Доля FAIL внутри инструмента может включать проверки полезности — категории в отчёте нужно рассматривать отдельно.

Код выхода: `0` — прогон завершён; `2` — неполнота/ошибка; `130` — Ctrl+C. С `--fail-on-findings` завершённый прогон с FAIL возвращает `1`. Без этого параметра FAIL не меняет код `0`.

## Данные и расширение

Датасеты уже входят в архив. Авторские `corporate.jsonl` и `multiturn.jsonl` можно восстановить командой `python3 generate_datasets.py`; официальные файлы она не изменяет. Это стартовый регрессионный набор, а не репрезентативный научный бенчмарк.

Дополняйте JSONL существующими полями и новыми уникальными `id`; категории Promptfoo: `direct_injection`, `indirect_injection`, `secret_leak`, `harmful`, `benign`. Для другой логики проверки нужно расширить assertions в `security_suite/native.py` и критерии в `common.py`.

Синтетический секрет и marker в данных публичны и предназначены исключительно для проверки соблюдения границ инструкций. Совпадение маркера — узкий эвристический сигнал; отсутствие совпадения не доказывает отсутствие других способов утечки.

Полные ответы могут содержать нежелательный контент и сведения из вашего приложения. Доступ к каталогу отчётов следует ограничивать так же, как к исходным запросам. Отправка судье является отдельной передачей этих текстов на выбранный judge endpoint.

Подробности: [методика и источники](docs/METHODOLOGY.md), [проверка проекта](docs/VALIDATION.md), [лицензии и происхождение](docs/DATA_SOURCES.md).
