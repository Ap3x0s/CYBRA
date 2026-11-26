"""Проверка структуры репозитория после разделения на микросервисы.

Приложение разделено на два сервиса, и у каждого своя зона
ответственности. Этот скрипт проверяет, что границы не разъехались:
фронтенд не тянет питон, бэкенд не собирает SPA, а образы собираются из
правильных контекстов.

Почему это отдельная проверка, а не договорённость: соблазн «положить
общий файл в корень» появляется на второй день, и через месяц бэкенд
снова начинает зависеть от фронтенда. Дешевле поймать это здесь.

Запуск:
    python scripts/check_repo_structure.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

problems: list[str] = []
checks: list[str] = []

# Файлы, которые обязаны существовать после разделения.
REQUIRED = (
    'docker/Dockerfile',            # образ бэкенда
    'frontend/Dockerfile',          # образ фронтенда
    'frontend/nginx.conf',          # прокси и статика
    'infra/compose.yaml',           # состав приложения
    'infra/ansible/playbooks/deploy.yml',
    'infra/releases/cybra-0.1.0.yml',
    '.gitlab/ci/pipelines/backend.yml',
    '.gitlab/ci/pipelines/frontend.yml',
    '.gitlab/ci/pipelines/infra.yml',
    '.gitlab/ci/templates/base.yml',
)

# Каталоги сервисов: что именно проверяем на чистоту границ.
BACKEND_DIRS = ('backend', 'scan', 'security_suite')
FRONTEND_DIR = 'frontend'


def check_required() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    if missing:
        for name in missing:
            problems.append(f'отсутствует обязательный файл: {name}')
    else:
        checks.append(f'обязательных файлов на месте: {len(REQUIRED)}')


def check_backend_is_python_only() -> None:
    """В бэкенде не должно быть JS-ИСХОДНИКОВ.

    Важная оговорка: `backend/static` — это артефакт сборки фронтенда,
    который Vite кладёт туда для локального запуска `python -m cybra`.
    Каталог в .gitignore, в образ не попадает (его собирает отдельный
    сервис) и исходником не является. Считать его нарушением значило бы
    требовать убрать единственный способ запустить приложение из
    исходников без двух контейнеров.
    """
    offenders = []
    for directory in BACKEND_DIRS:
        path = ROOT / directory
        if not path.exists():
            continue
        for file in path.rglob('*'):
            if not file.is_file() or file.suffix not in ('.jsx', '.tsx', '.js', '.ts'):
                continue
            relative = file.relative_to(ROOT)
            # Артефакты сборки — не исходный код.
            if 'static' in relative.parts:
                continue
            offenders.append(str(relative))
    if offenders:
        for name in offenders:
            problems.append(f'бэкенд содержит JS-исходник: {name}')
    else:
        checks.append('бэкенд не содержит JS-исходников (артефакты сборки не в счёт)')


def check_backend_dockerfile_has_no_ui_stage() -> None:
    """Dockerfile бэкенда не должен собирать SPA."""
    path = ROOT / 'docker' / 'Dockerfile'
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    # Ищем инструкции, а не упоминания в комментариях: в комментарии
    # объяснено, почему стадии больше нет, и это не нарушение.
    instructions = [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]
    uses_node = any(
        line.upper().startswith('FROM ') and 'node' in line.lower()
        for line in instructions)
    copies_ui = any(
        line.upper().startswith('COPY --FROM') and 'ui' in line.lower()
        for line in instructions)
    if uses_node:
        problems.append('docker/Dockerfile собирает Node-стадию — фронт '
                        'должен собираться в frontend/Dockerfile')
    if copies_ui:
        problems.append('docker/Dockerfile копирует статику из UI-стадии')
    if not uses_node and not copies_ui:
        checks.append('docker/Dockerfile собирает только бэкенд')


def check_frontend_dockerfile() -> None:
    """Dockerfile фронтенда: две стадии и nginx в финале.

    Проверяются только инструкции, не комментарии: в комментарии
    объяснено, ПОЧЕМУ фронт больше не внутри Python-образа, и слово
    «python» там — часть объяснения, а не нарушение.
    """
    path = ROOT / 'frontend' / 'Dockerfile'
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    instructions = [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]
    body = '\n'.join(instructions)

    if 'FROM node' not in body:
        problems.append('frontend/Dockerfile не собирает SPA стадией Node')
    if 'FROM nginx' not in body:
        problems.append('frontend/Dockerfile не раздаёт статику через nginx')
    if 'python' in body.lower():
        problems.append('frontend/Dockerfile содержит Python — граница поехала')
    else:
        checks.append('frontend/Dockerfile: Node → nginx, без Python')


def check_nginx_proxies_api() -> None:
    """nginx обязан проксировать /api — иначе SPA не работает."""
    path = ROOT / 'frontend' / 'nginx.conf'
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    if 'proxy_pass' not in text:
        problems.append('frontend/nginx.conf не проксирует /api — SPA не '
                        'сможет обратиться к бэкенду')
    elif not re.search(r'location\s+/api/', text):
        problems.append('frontend/nginx.conf: прокси есть, но не для /api/')
    else:
        checks.append('nginx проксирует /api на бэкенд')

    # Форма proxy_pass с переменной. Прямая форма `http://backend:8000`
    # разрешает имя один раз при разборе конфига: `nginx -t` падает при
    # сборке образа, а после перезапуска бэкенда nginx ходит на старый IP.
    #
    # Проверяем только действующие директивы, не комментарии: в комментарии
    # старая форма приведена как объяснение, почему от неё отказались.
    active = '\n'.join(
        line for line in text.splitlines()
        if not line.strip().startswith('#'))

    if re.search(r'proxy_pass\s+http://backend:\d+', active):
        problems.append('nginx.conf: proxy_pass с прямым именем хоста — '
                        'имя разрешается один раз, nginx -t не пройдёт без '
                        'запущенного бэкенда. Используйте resolver + '
                        'переменную')
    elif 'resolver' in active and '$backend_upstream' in active:
        checks.append('proxy_pass через resolver — имя разрешается на каждый запрос')

    if 'try_files' not in text:
        problems.append('frontend/nginx.conf без try_files — перезагрузка на '
                        'маршруте react-router даст 404')


def check_api_client_relative() -> None:
    """Фронтенд должен обращаться к относительному /api, а не к домену.

    Абсолютный URL в api.js означал бы CORS и отдельную настройку cookie:
    сессия живёт в HttpOnly-cookie на origin фронтенда, и SameSite не
    пропустит её на чужой домен.
    """
    path = ROOT / 'frontend' / 'src' / 'api.js'
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    match = re.search(r"fetch\(\s*['\"]([^'\"]+)", text)
    if not match:
        return
    url = match.group(1)
    if url.startswith('http'):
        problems.append(f'frontend/src/api.js обращается к абсолютному URL '
                        f'({url}) — это CORS и сломанная cookie-сессия')
    elif url.startswith('/api'):
        checks.append(f'клиент использует относительный путь ({url})')
    else:
        problems.append(f'frontend/src/api.js: неожиданный базовый путь {url}')


def check_single_image_references() -> None:
    """Старый единый compose не должен притворяться рабочим.

    После разделения `docker/compose.prod.yaml` описывал бы только бэкенд:
    стенд, где API отвечает, а открыть нечего. Допустимы два состояния:
    файла нет вовсе, либо он явно помечен устаревшим и указывает на новый.
    Молчаливо рабочий вид — худший вариант: команда из старой документации
    отработает без ошибки и развернёт половину приложения.
    """
    path = ROOT / 'docker' / 'compose.prod.yaml'
    if not path.exists():
        checks.append('старого compose.prod.yaml нет — состав только в infra/')
        return
    text = path.read_text(encoding='utf-8')
    marked = ('устарел' in text.lower() or 'obsolete' in text.lower()
              or 'infra/compose.yaml' in text)
    if not marked:
        problems.append(
            'docker/compose.prod.yaml выглядит рабочим, но описывает '
            'только один сервис — после разделения он не развернёт фронтенд. '
            'Пометьте его устаревшим или удалите: состав живёт в '
            'infra/compose.yaml')
    else:
        checks.append('старый compose.prod.yaml помечен устаревшим')


def main() -> int:
    print('=== структура репозитория ===')
    check_required()
    check_backend_is_python_only()
    check_backend_dockerfile_has_no_ui_stage()
    check_frontend_dockerfile()
    check_nginx_proxies_api()
    check_api_client_relative()
    check_single_image_references()

    print()
    for message in checks:
        print(f'  ok   {message}')

    print()
    if problems:
        print(f'НАЙДЕНО: {len(problems)}')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'проверок пройдено: {len(checks)} — границы сервисов на месте')
    return 0


if __name__ == '__main__':
    sys.exit(main())
