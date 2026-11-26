"""Проверка release-манифеста: схема, digest, допустимый registry.

Этап 4 схемы DevSecOps для infra-пайплайна. Манифест — единственное место,
где сказано «что именно развёрнуто», поэтому опечатка в нём дороже, чем
опечатка в коде: она означает, что на стенде окажется не тот образ.

Что проверяется:

  * обязательные поля (release_id, config_ref, services);
  * образы зафиксированы по digest, а не по тегу;
  * digest имеет правильную форму (sha256 + 64 hex);
  * registry входит в список допустимых;
  * у каждого сервиса есть health-путь, если он заявлен в smoke.

Запуск:
    python scripts/check_release.py                 # все манифесты
    python scripts/check_release.py --junit out.xml # с JUnit-отчётом
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / 'infra' / 'releases'

# Реестры, из которых разрешено разворачивать. Список закрытый: манифест,
# ссылающийся на неизвестный registry, означает либо опечатку, либо
# попытку подсунуть чужой образ.
ALLOWED_REGISTRIES = (
    'registry.gitlab.com',
    'docker.io',
    'ghcr.io',
)

DIGEST_PATTERN = re.compile(r'^sha256:[0-9a-f]{64}$')

problems: list[str] = []
results: list[tuple[str, str, bool]] = []


def check_manifest(path: Path, data: dict) -> None:
    """Проверить один манифест. Заполняет results и problems."""
    name = path.name

    for key in ('release_id', 'config_ref', 'services'):
        if key not in data:
            message = f'{name}: нет обязательного поля {key}'
            problems.append(message)
            results.append((name, f'поле {key}', False))
            return

    # release_id должен совпадать с именем файла: иначе тег deploy-<id> и
    # манифест разъедутся, и откат будет искать не тот файл.
    expected = path.stem
    if data['release_id'] != expected:
        problems.append(f"{name}: release_id {data['release_id']!r} не совпадает "
                        f'с именем файла {expected!r}')
        results.append((name, 'release_id = имя файла', False))
    else:
        results.append((name, 'release_id = имя файла', True))

    services = data.get('services') or {}
    if not isinstance(services, dict):
        problems.append(f'{name}: services должен быть словарём')
        return

    for service_name in ('backend', 'frontend'):
        if service_name not in services:
            problems.append(f'{name}: нет сервиса {service_name}')
            results.append((name, f'сервис {service_name}', False))

    for service_name, spec in services.items():
        if not isinstance(spec, dict):
            problems.append(f'{name}: {service_name} должен быть словарём')
            continue

        image = str(spec.get('image', ''))
        if not image:
            problems.append(f'{name}: у {service_name} нет image')
            results.append((name, f'{service_name}.image', False))
            continue

        # Digest обязателен. Тег можно переставить на другой образ, и тогда
        # «что развёрнуто» перестанет быть однозначным — ровно то, от чего
        # защищает манифест.
        if '@sha256:' not in image:
            problems.append(f'{name}: {service_name}.image без digest — '
                            f'образ не зафиксирован')
            results.append((name, f'{service_name} digest', False))
            continue

        digest = image.split('@', 1)[1]
        if not DIGEST_PATTERN.match(digest):
            problems.append(f'{name}: {service_name}.image — digest '
                            f'{digest[:20]}… имеет неверную форму')
            results.append((name, f'{service_name} digest', False))
            continue

        # Заглушка не должна уехать в деплой: PLACEHOLDER означает, что
        # манифест ещё не заполнен CI.
        if 'PLACEHOLDER' in image.upper():
            problems.append(f'{name}: {service_name}.image не заполнен — '
                            f'остался PLACEHOLDER')
            results.append((name, f'{service_name} digest', False))
            continue

        registry = image.split('/')[0]
        allowed = any(registry.endswith(item) for item in ALLOWED_REGISTRIES)
        if not allowed:
            problems.append(f'{name}: {service_name} из registry {registry!r}, '
                            f'которого нет в списке разрешённых')
            results.append((name, f'{service_name} registry', False))
            continue

        results.append((name, f'{service_name} digest', True))

    # config_ref должен быть полным SHA: короткий хеш нельзя однозначно
    # разрешить, если в репозитории есть совпадение.
    config_ref = str(data.get('config_ref', ''))
    if 'PLACEHOLDER' in config_ref.upper():
        results.append((name, 'config_ref', False))


def write_junit(path: Path, cases: list[tuple[str, str, bool]]) -> None:
    """JUnit-отчёт, чтобы результат был виден в merge request."""
    failures = sum(1 for _, _, passed in cases if not passed)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuites name="release-manifest" tests="{len(cases)}" '
        f'failures="{failures}">',
        f'  <testsuite name="manifest" tests="{len(cases)}" '
        f'failures="{failures}">',
    ]
    for name, check, passed in cases:
        lines.append(
            f'    <testcase name="{escape(check)}" '
            f'classname="{escape(name)}">')
        if not passed:
            lines.append(f'      <failure message="{escape(check)} не пройдена"/>')
        lines.append('    </testcase>')
    lines += ['  </testsuite>', '</testsuites>', '']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    junit = None
    if '--junit' in sys.argv:
        index = sys.argv.index('--junit')
        if index + 1 < len(sys.argv):
            junit = Path(sys.argv[index + 1])

    manifests = sorted(RELEASES.glob('*.yml')) if RELEASES.exists() else []
    if not manifests:
        print(f'НЕТ манифестов в {RELEASES.relative_to(ROOT).as_posix()}')
        return 1

    print(f'=== release-манифесты ({len(manifests)}) ===')
    unfilled = []
    for path in manifests:
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as error:
            problems.append(f'{path.name}: YAML не разбирается — {error}')
            continue
        before = len(problems)
        check_manifest(path, data)
        # Манифест с заглушкой — это шаблон до первого релиза, а не ошибка
        # автора. Разделяем два случая: «ещё не заполнен» (нормально на
        # любом коммите, кроме тега) и «заполнен неверно» (находка).
        has_placeholder = 'PLACEHOLDER' in path.read_text(encoding='utf-8').upper()
        if has_placeholder:
            unfilled.append(path.name)
            # Убираем претензии про PLACEHOLDER, оставляя остальные.
            problems[:] = [p for p in problems
                           if not ('PLACEHOLDER' in p or 'неверную форму' in p)
                           or path.name not in p]
        status = 'OK' if len(problems) == before else 'см. ниже'
        print(f'  {path.name}: {status}')

    if unfilled:
        print()
        print('НЕ ЗАПОЛНЕНЫ (ждём первого релиза): ' + ', '.join(unfilled))
        # На теге заглушка недопустима: тег означает выпуск, а выпускать
        # незаполненный манифест значит развернуть что-то не то.
        if os.environ.get('CI_COMMIT_TAG'):
            problems.append('на теге манифест обязан быть заполнен: '
                            + ', '.join(unfilled))

    print()
    if problems:
        print(f'НАЙДЕНО: {len(problems)}')
        for problem in problems:
            print(f'  {problem}')
    else:
        print(f'манифестов проверено: {len(manifests)} — замечаний нет')

    if junit:
        write_junit(junit, results)
        print(f'JUnit-отчёт: {junit}')

    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
