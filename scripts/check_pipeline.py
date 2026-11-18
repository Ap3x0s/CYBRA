"""Проверка .gitlab-ci.yml до запуска пайплайна.

Этап 7 схемы DevSecOps (IaC / CI-CD scan). Опечатка в конфиге пайплайна
стоит дороже, чем в коде: она ломает все job'ы сразу, и разбираться
приходится по логу упавшего запуска.

Что проверяем без самого GitLab CI Lint API:
  * YAML разбирается;
  * у каждого job'а есть stage из объявленных;
  * нет job'а без script/trigger/extends (тогда он «висит» без дела);
  * все `extends:` указывают на существующий шаблон;
  * `needs` ссылается на существующий job.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / '.gitlab-ci.yml'

RESERVED = {'stages', 'variables', 'default', 'include', 'workflow', 'image',
            'services', 'cache', 'before_script', 'after_script'}


def main() -> int:
    data = yaml.safe_load(PIPELINE.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        print('FAIL: .gitlab-ci.yml не разбирается в словарь')
        return 1

    stages = data.get('stages') or []
    if not stages:
        print('FAIL: stages не объявлены')
        return 1

    jobs = {name: body for name, body in data.items()
            if not name.startswith('.') and name not in RESERVED
            and isinstance(body, dict) and 'stage' in body}
    templates = {name for name in data if name.startswith('.')}

    problems: list[str] = []

    for name, body in jobs.items():
        stage = body.get('stage')
        if stage not in stages:
            problems.append(f'{name}: stage {stage!r} не объявлен в {stages}')
        # Job без работы: есть только stage и переменные.
        if not any(key in body for key in ('script', 'trigger', 'extends')):
            problems.append(f'{name}: нет script, trigger или extends')
        parent = body.get('extends')
        if parent and parent not in templates:
            problems.append(f'{name}: extends {parent!r}, а такого шаблона нет')
        for need in body.get('needs') or []:
            target = need if isinstance(need, str) else need.get('job')
            if target and target not in jobs:
                problems.append(f'{name}: needs {target!r}, а такого job нет')

    if not jobs:
        problems.append('в пайплайне нет ни одного job')

    by_stage: dict[str, list[str]] = {}
    for name, body in jobs.items():
        by_stage.setdefault(body['stage'], []).append(name)

    print(f'stages: {stages}')
    print(f'jobs: {len(jobs)}, шаблонов: {len(templates)}')
    for stage in stages:
        names = sorted(by_stage.get(stage, []))
        print(f'  {stage:14} {", ".join(names) if names else "—"}')

    if problems:
        print(f'\nпроблем: {len(problems)}')
        for problem in problems:
            print(f'  ✗ {problem}')
        return 1

    print('\n.gitlab-ci.yml корректен')
    return 0


if __name__ == '__main__':
    sys.exit(main())
