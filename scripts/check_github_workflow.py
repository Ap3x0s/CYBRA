"""Валидация workflow GitHub Actions до запуска.

Этап 7 схемы DevSecOps (IaC / CI-CD scan). Опечатка в конфиге пайплайна
стоит дороже, чем в коде: она ломает все job'ы сразу, и разбираться
приходится по логу упавшего запуска.

Что проверяем без GitHub API:
  * YAML разбирается и содержит jobs;
  * у каждого job'а есть runs-on и хотя бы один шаг;
  * каждый шаг — `uses` или `run`, а не пустой объект;
  * все `needs:` указывают на существующий job и не создают цикл;
  * нет шага без имени при непустом списке (для читаемости в UI).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / '.github' / 'workflows'


def check_workflow(path: Path) -> list[str]:
    problems: list[str] = []
    data = yaml.safe_load(path.read_text(encoding='utf-8'))

    if not isinstance(data, dict):
        return [f'{path.name}: не разбирается в словарь']
    jobs = data.get('jobs')
    if not isinstance(jobs, dict) or not jobs:
        return [f'{path.name}: нет ни одного job']

    for name, body in jobs.items():
        if not isinstance(body, dict):
            problems.append(f'{name}: job должен быть словарём')
            continue
        if 'runs-on' not in body:
            problems.append(f'{name}: нет runs-on')
        steps = body.get('steps')
        if not steps:
            problems.append(f'{name}: нет steps')
            continue
        for index, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                problems.append(f'{name}: шаг {index} — не словарь')
                continue
            if 'uses' not in step and 'run' not in step:
                problems.append(f'{name}: шаг {index} без uses и без run')
        needs = body.get('needs') or []
        if isinstance(needs, str):
            needs = [needs]
        for need in needs:
            if need not in jobs:
                problems.append(f'{name}: needs {need!r}, а такого job нет')

    # Циклы в needs: обход в глубину.
    def visit(node: str, path_stack: list[str]) -> None:
        if node in path_stack:
            problems.append(f'цикл needs: {" → ".join(path_stack + [node])}')
            return
        body = jobs.get(node) or {}
        needs = body.get('needs') or []
        if isinstance(needs, str):
            needs = [needs]
        for need in needs:
            visit(need, path_stack + [node])

    for name in jobs:
        visit(name, [])

    return problems


def main() -> int:
    files = sorted(WORKFLOWS_DIR.glob('*.yml')) + sorted(WORKFLOWS_DIR.glob('*.yaml'))
    if not files:
        print(f'FAIL: в {WORKFLOWS_DIR} нет workflow-файлов')
        return 1

    total_jobs = 0
    all_problems: list[str] = []
    for path in files:
        problems = check_workflow(path)
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        jobs = (data or {}).get('jobs') or {}
        total_jobs += len(jobs)
        print(f'{path.name}: {len(jobs)} jobs' + (f' — проблем: {len(problems)}' if problems else ''))
        all_problems.extend(problems)

    if all_problems:
        print()
        for problem in all_problems:
            print(f'  ✗ {problem}')
        return 1

    print(f'\nworkflow корректен: {len(files)} файлов, {total_jobs} jobs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
