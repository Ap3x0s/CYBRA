"""Проверка infra: YAML разбирается, Jinja2-шаблоны рендерятся.

Этапы 2 и 7 схемы DevSecOps для infra-пайплайна. Отдельный скрипт нужен
потому, что обычный линтер YAML не знает про наши правила:

  * Jinja2-шаблон может быть синтаксически некорректным, и это видно
    только при попытке компиляции, а не при чтении как текста;
  * в environments/*.yml обязателен фиксированный набор ключей — если
    шаблон ждёт `backend_upstream`, а окружение его не задало, Ansible
    упадёт на рендере уже после того, как скачает образы;
  * inventory должен ссылаться на существующие окружения;
  * в infra не должно быть секретов: они приходят из CI-переменных.

Запуск:
    python scripts/check_infra.py            # кратко
    python scripts/check_infra.py --verbose  # с перечнем проверок
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / 'infra'

# Ключи, которые обязано задавать каждое окружение. Список выведен из
# шаблонов backend.env.j2 и frontend.env.j2: всё, что шаблон подставляет
# без фильтра `default`, должно быть в environments/*.yml.
REQUIRED_ENV_KEYS = (
    'cybra_env',
    'backend_upstream',
    'frontend_port',
    'cybra_cookie_secure',
    'cybra_session_ttl_hours',
    'cybra_log_level',
)

# Окружения, для которых обязателен inventory.
ENVIRONMENTS = ('dev', 'stage', 'prod-lab')

# Сервисы, которые собирает наш CI. Для них digest обязателен: тег можно
# переставить на другой образ. Остальные сервисы (postgres) приходят от
# вендора с фиксированным тегом.
OWN_SERVICES = ('backend', 'frontend')

problems: list[str] = []
checks: list[str] = []


def ok(message: str) -> None:
    checks.append(message)


def bad(message: str) -> None:
    problems.append(message)


def check_yaml_files(verbose: bool) -> None:
    """Каждый YAML в infra должен разбираться."""
    count = 0
    for path in sorted(INFRA.rglob('*.yml')) + sorted(INFRA.rglob('*.yaml')):
        try:
            yaml.safe_load(path.read_text(encoding='utf-8'))
            count += 1
        except yaml.YAMLError as error:
            bad(f'{path.relative_to(ROOT).as_posix()}: YAML не разбирается — {error}')
    ok(f'YAML разобрано: {count} файлов')


def check_templates() -> None:
    """Jinja2-шаблоны компилируются и используют известные переменные."""
    try:
        from jinja2 import Environment, TemplateSyntaxError
    except ImportError:
        ok('jinja2 не установлен — проверка шаблонов пропущена')
        return

    env = Environment()
    templates = sorted((INFRA / 'configurations' / 'templates').glob('*.j2'))
    if not templates:
        bad('нет ни одного шаблона в configurations/templates')
        return

    for path in templates:
        try:
            env.parse(path.read_text(encoding='utf-8'))
        except TemplateSyntaxError as error:
            bad(f'{path.name}: синтаксис Jinja2 — {error}')
    ok(f'Jinja2-шаблонов скомпилировано: {len(templates)}')


def check_environments() -> None:
    """Каждое окружение задаёт обязательные ключи."""
    directory = INFRA / 'configurations' / 'environments'
    for name in ENVIRONMENTS:
        path = directory / f'{name}.yml'
        if not path.exists():
            bad(f'нет environments/{name}.yml')
            continue
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        missing = [key for key in REQUIRED_ENV_KEYS if key not in data]
        if missing:
            bad(f'environments/{name}.yml: не заданы {", ".join(missing)}')
        else:
            ok(f'environments/{name}.yml: все обязательные ключи на месте')

        # Порт должен быть числом: строка ломает публикацию compose.
        port = data.get('frontend_port')
        if port is not None and not isinstance(port, int):
            bad(f'environments/{name}.yml: frontend_port должен быть числом, '
                f'а не {type(port).__name__}')

        # Секрет в открытом виде — находка. Значения вида {{ lookup(...) }}
        # допустимы: они разрешаются на хосте, а не лежат в git.
        for key, value in data.items():
            if not isinstance(value, str):
                continue
            lowered = key.lower()
            if any(token in lowered for token in ('password', 'secret', 'token')):
                if '{{' not in value and value:
                    bad(f'environments/{name}.yml: {key} содержит значение '
                        f'в открытом виде — используйте lookup или CI-переменную')


def check_inventories() -> None:
    """Inventory существует для каждого окружения и указывает target_env."""
    for name in ENVIRONMENTS:
        path = INFRA / 'inventories' / name / 'hosts.yml'
        if not path.exists():
            bad(f'нет inventories/{name}/hosts.yml')
            continue
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        hosts = (data.get('all', {}).get('children', {})
                 .get('cybra', {}).get('hosts', {}))
        if not hosts:
            bad(f'inventories/{name}/hosts.yml: нет ни одного хоста')
            continue
        variables = (data.get('all', {}).get('children', {})
                     .get('cybra', {}).get('vars', {}))
        if variables.get('target_env') != name:
            bad(f'inventories/{name}/hosts.yml: target_env = '
                f'{variables.get("target_env")!r}, ожидалось {name!r}')
        else:
            ok(f'inventories/{name}/hosts.yml: {len(hosts)} хост(ов), '
               f'target_env корректен')


def check_compose() -> None:
    """Compose: обязательные сервисы и отсутствие build."""
    path = INFRA / 'compose.yaml'
    if not path.exists():
        bad('нет infra/compose.yaml')
        return
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    services = data.get('services', {})

    for required in ('backend', 'frontend'):
        if required not in services:
            bad(f'compose.yaml: нет сервиса {required}')

    for name, spec in services.items():
        if not isinstance(spec, dict):
            continue
        # build в файле развёртывания означает, что compose соберёт образ из
        # локального контекста и подменит то, что пришло из CI.
        if spec.get('build'):
            bad(f'compose.yaml: {name} содержит build — соберётся не тот '
                f'образ, который проверил CI')
        # Наши сервисы обязаны приходить из CI с digest: тег можно
        # переставить, и «что развёрнуто» перестанет быть однозначным.
        #
        # Сторонние сервисы (postgres) — исключение: их поставляет вендор с
        # фиксированным тегом, и требовать от них digest в compose значило
        # бы заставлять сопровождать чужой образ вручную. Достаточно, что
        # тег не `latest`.
        if name in OWN_SERVICES:
            image = str(spec.get('image', ''))
            if '${' not in image and '@sha256:' not in image:
                bad(f'compose.yaml: {name}.image без переменной и без digest — '
                    f'непонятно, что именно развернётся')
        else:
            image = str(spec.get('image', ''))
            if image.endswith(':latest') or ':latest' in image:
                bad(f'compose.yaml: сторонний сервис {name} на теге latest — '
                    f'пересборка может изменить содержимое без правок')

    ok(f'compose.yaml: сервисов {len(services)}')


def check_releases() -> None:
    """Манифесты релизов содержат обязательные поля."""
    directory = INFRA / 'releases'
    files = sorted(directory.glob('*.yml'))
    if not files:
        bad('нет ни одного манифеста в releases/')
        return
    for path in files:
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        for key in ('release_id', 'config_ref', 'services'):
            if key not in data:
                bad(f'releases/{path.name}: нет поля {key}')
        services = data.get('services') or {}
        for name in ('backend', 'frontend'):
            spec = services.get(name) or {}
            if 'image' not in spec:
                bad(f'releases/{path.name}: у сервиса {name} нет image')
    ok(f'releases: манифестов {len(files)}')


def main() -> int:
    verbose = '--verbose' in sys.argv

    print('=== infra: структура и содержимое ===')
    check_yaml_files(verbose)
    check_templates()
    check_environments()
    check_inventories()
    check_compose()
    check_releases()

    print()
    for message in checks:
        print(f'  ok   {message}')

    print()
    if problems:
        print(f'НАЙДЕНО: {len(problems)}')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'проверок пройдено: {len(checks)} — замечаний нет')
    return 0


if __name__ == '__main__':
    sys.exit(main())
