"""Проверка IaC: Dockerfile, compose, пайплайны.

Этап 7 схемы DevSecOps — «проверка IaC, манифестов Kubernetes и описания
конвейера». Kubernetes у нас нет, поэтому проверяются три вещи, которые
есть: Dockerfile обоих сервисов, compose и YAML пайплайнов.

Зачем отдельный скрипт, а не линтер: обычные линтеры YAML проверяют
синтаксис, но не знают наших правил. Здесь ловятся ошибки, которые уже
случались в этом проекте и не находились ничем:

  * элемент `script` оказался словарём из-за незакавыченного двоеточия —
    GitLab отвечает `script config should be a string`, и это выглядит
    как проблема GitLab, а не YAML;
  * образ без `entrypoint: [""]` там, где ENTRYPOINT — сам бинарь
    (kaniko, gitleaks, trivy): job падает с `unknown command "sh"`;
  * `needs` на job, которого нет (опечатка в имени);
  * секрет, попавший в YAML вместо переменной.

Скрипт ничего не правит: только список находок и код возврата.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Образы, у которых ENTRYPOINT — исполняемый файл, а не shell. Для них
# обязательно `entrypoint: [""]`, иначе GitLab подставит свой скрипт и
# контейнер ответит `unknown command "sh"`.
NEEDS_ENTRYPOINT_OVERRIDE = (
    'kaniko',
    'gitleaks',
    'trivy',
    'cosign',
)

# Признаки секрета в открытом виде. Проверяем только значения, похожие на
# настоящие ключи: длинные строки без переменных.
SECRET_PATTERNS = (
    re.compile(r'(?i)(secret|token|password|passwd|api[_-]?key)\s*[:=]\s*'
               r'["\']?(?!\$\{?)[A-Za-z0-9+/_\-]{16,}'),
)

problems: list[str] = []
checked: list[str] = []


def note(path: Path, message: str) -> None:
    problems.append(f'{path.relative_to(ROOT).as_posix()}: {message}')


def load_yaml(path: Path) -> dict | None:
    """Прочитать YAML. Ошибка разбора — тоже находка, а не исключение."""
    try:
        text = path.read_text(encoding='utf-8')
        # GitLab разрешает `!reference` и прочие теги, которых нет в
        # стандартном безопасном загрузчике. Для проверки структуры они не
        # нужны: подменяем на строку, чтобы разбор не падал на них.
        text = re.sub(r'!\S+', '', text)
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        note(path, f'YAML не разбирается: {error}')
        return None
    except OSError as error:
        note(path, f'не читается: {error}')
        return None
    if not isinstance(data, dict):
        note(path, 'ожидался словарь верхнего уровня')
        return None
    return data


def check_script_items(path: Path, data: dict) -> None:
    """Каждый элемент script должен быть строкой.

    Незакавыченное двоеточие внутри строки YAML превращает её в словарь
    `{text: rest}`. GitLab в таком случае отвечает `script config should
    be a string`, указывая на пайплайн целиком, а не на строку.
    """
    for name, job in data.items():
        if not isinstance(job, dict):
            continue
        for key in ('script', 'before_script', 'after_script'):
            items = job.get(key)
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if not isinstance(item, str):
                    note(path, f'{name}.{key}[{index}] не строка, а '
                               f'{type(item).__name__} — незакавыченное '
                               f'двоеточие? GitLab ответит '
                               f'`script config should be a string`')


def check_entrypoints(path: Path, data: dict) -> None:
    """Образы с бинарём в ENTRYPOINT должны переопределять entrypoint."""
    for name, job in data.items():
        if not isinstance(job, dict):
            continue
        image = job.get('image')
        image_name = ''
        override = None
        if isinstance(image, str):
            image_name = image
        elif isinstance(image, dict):
            image_name = str(image.get('name', ''))
            override = image.get('entrypoint')
        else:
            continue

        needs = any(token in image_name for token in NEEDS_ENTRYPOINT_OVERRIDE)
        if needs and override != ['']:
            note(path, f'{name}: образ {image_name} требует '
                       f'`entrypoint: [""]` — иначе `unknown command "sh"`')


def check_needs(path: Path, data: dict) -> None:
    """`needs` не должен ссылаться на несуществующий job.

    Опечатка в имени даёт ошибку на этапе создания пайплайна и выглядит
    как проблема GitLab, а не как опечатка.
    """
    known = {name for name in data if not name.startswith('.')}
    # Расширения include тоже содержат job'ы — их имена собираем заранее.
    for included in data.get('include', []) or []:
        if isinstance(included, dict) and 'local' in included:
            included_path = ROOT / str(included['local']).lstrip('/')
            included_data = load_yaml(included_path) if included_path.exists() else None
            if included_data:
                known |= {n for n in included_data if not n.startswith('.')}

    for name, job in data.items():
        if not isinstance(job, dict):
            continue
        needs = job.get('needs')
        if not isinstance(needs, list):
            continue
        for entry in needs:
            target = entry.get('job') if isinstance(entry, dict) else entry
            if not isinstance(target, str):
                continue
            if target not in known:
                note(path, f'{name}.needs: job `{target}` не существует')


def check_secrets(path: Path, text: str) -> None:
    """Секрет, вписанный в YAML значением, а не через переменную.

    Ложные срабатывания возможны, поэтому проверка не блокирует: она
    печатает находку, и человек смотрит. Здесь важнее не пропустить.
    """
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith('#') or '${' in stripped or '$' in stripped:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(stripped):
                note(path, f'строка {number}: похоже на секрет в открытом '
                           f'виде — используйте переменную CI')


def check_dockerfile(path: Path) -> None:
    """Проверки Dockerfile: пользователь, healthcheck, базовый образ."""
    text = path.read_text(encoding='utf-8')
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.strip().startswith('#')]

    if not any(line.startswith('FROM') for line in lines):
        note(path, 'нет ни одной инструкции FROM')
        return

    base_images = [line.split()[1] for line in lines
                   if line.upper().startswith('FROM ')]
    for image in base_images:
        if image.endswith(':latest'):
            note(path, f'базовый образ {image} на теге latest — '
                       f'пересборка может изменить содержимое без правок')

    # USER проверяем только в финальной стадии: промежуточные собирают
    # артефакт и наружу не уезжают.
    last_from = max(index for index, line in enumerate(lines)
                    if line.upper().startswith('FROM '))
    final = [line.upper() for line in lines[last_from:]]
    if not any(line.startswith('USER ') for line in final):
        note(path, 'в финальной стадии нет USER — контейнер работает от root')

    if not any(line.startswith('HEALTHCHECK') for line in final):
        note(path, 'в финальной стадии нет HEALTHCHECK')

    if 'latest' in text and any('FROM' in line and 'latest' in line
                                for line in lines):
        pass  # уже отмечено выше, не дублируем


def main() -> int:
    print('=== Dockerfile ===')
    for name in ('docker/Dockerfile', 'frontend/Dockerfile'):
        path = ROOT / name
        if not path.exists():
            note(path, 'файл отсутствует')
            continue
        before = len(problems)
        check_dockerfile(path)
        print(f'  {name}: {"OK" if len(problems) == before else "см. ниже"}')
        checked.append(name)

    print()
    print('=== compose ===')
    compose_path = ROOT / 'infra' / 'compose.yaml'
    if compose_path.exists():
        data = load_yaml(compose_path)
        if data:
            services = data.get('services', {})
            for service, spec in services.items():
                if not isinstance(spec, dict):
                    continue
                image = str(spec.get('image', ''))
                # Образ без digest или с обязательной переменной — норма
                # для compose: digest подставляет Ansible из манифеста.
                if spec.get('build'):
                    note(compose_path, f'{service}: секция build в файле '
                                       f'развёртывания — соберёт не то, что '
                                       f'пришло из CI')
                if not image:
                    note(compose_path, f'{service}: нет image')
            print(f'  infra/compose.yaml: {len(services)} сервисов')
            checked.append('infra/compose.yaml')
    else:
        note(compose_path, 'файл отсутствует')

    print()
    print('=== пайплайны ===')
    pipelines = sorted((ROOT / '.gitlab' / 'ci').rglob('*.yml'))
    pipelines.append(ROOT / '.gitlab-ci.yml')
    for path in pipelines:
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        data = load_yaml(path)
        if data:
            check_script_items(path, data)
            check_entrypoints(path, data)
            check_needs(path, data)
        check_secrets(path, text)
        print(f'  {path.relative_to(ROOT).as_posix()}')
        checked.append(path.relative_to(ROOT).as_posix())

    print()
    print('=== workflows GitHub ===')
    for path in sorted((ROOT / '.github' / 'workflows').glob('*.yml')):
        data = load_yaml(path)
        if data:
            # У GitHub Actions script — обычная строка, но структуру job'ов
            # проверить полезно: опечатка в needs ломает workflow целиком.
            jobs = data.get('jobs', {})
            if not isinstance(jobs, dict):
                note(path, 'секция jobs отсутствует или не словарь')
            else:
                for name, job in jobs.items():
                    if not isinstance(job, dict):
                        continue
                    for entry in job.get('needs', []) or []:
                        if entry not in jobs:
                            note(path, f'{name}.needs: job `{entry}` не существует')
        print(f'  {path.relative_to(ROOT).as_posix()}')

    print()
    if problems:
        print(f'НАЙДЕНО: {len(problems)}')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'проверено файлов: {len(checked)} — замечаний нет')
    return 0


if __name__ == '__main__':
    sys.exit(main())
