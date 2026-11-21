#!/usr/bin/env python
"""Этап 0 схемы DevSecOps: локальные проверки до коммита.

Зачем: красный пайплайн стоит минут ожидания и выгоревшего слота раннера.
Те же проверки локально занимают секунды и не пускают в историю заведомо
сломанный коммит.

Почему Python, а не shell. Первая версия была на /bin/sh и на Windows не
запускалась вовсе: `sh` в системе нет. Хук «существовал», но не выполнялся —
и формат кода уехал в CI, сделав прогон красным. Проверка, которая молча не
работает, хуже отсутствующей: на неё рассчитывают.

Запуск:
    python scripts/precommit.py

Установка хука: scripts/install_git_hooks.sh
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_bin() -> Path | None:
    """Каталог с исполняемыми файлами venv, если он есть."""
    for candidate in (ROOT / '.venv' / 'Scripts', ROOT / '.venv' / 'bin'):
        if candidate.is_dir():
            return candidate
    return None


def run(label: str, args: list[str], env: dict[str, str]) -> bool:
    """Выполнить шаг и напечатать результат. True — прошёл."""
    print(f'== {label} ==', flush=True)
    result = subprocess.run(args, cwd=ROOT, env=env)
    if result.returncode != 0:
        print(f'FAIL: {label}', file=sys.stderr)
        return False
    return True


def main() -> int:
    env = dict(os.environ)
    binaries = venv_bin()
    if binaries:
        # Инструменты лежат в venv и в PATH не попадают, когда git запускает
        # хук из своего окружения. Без этого шага не находился ruff.
        env['PATH'] = str(binaries) + os.pathsep + env.get('PATH', '')

    python = sys.executable
    if binaries:
        candidate = binaries / ('python.exe' if os.name == 'nt' else 'python')
        if candidate.exists():
            python = str(candidate)

    ruff = binaries / ('ruff.exe' if os.name == 'nt' else 'ruff') if binaries else None
    if ruff is None or not ruff.exists():
        print('FAIL: ruff не найден в .venv. Установите: '
              './.venv/bin/pip install ruff  (или .venv\\Scripts\\pip install ruff)',
              file=sys.stderr)
        return 1

    steps = [
        ('ruff', [str(ruff), 'check', 'backend', 'scan']),
        ('формат', [str(ruff), 'format', '--check', 'backend/cybra',
                   'scan', 'run.py']),
        ('i18n', [python, 'scripts/audit_i18n_keys.py']),
        ('быстрые тесты', [python, '-m', 'pytest', 'tests/', '-q', '-x']),
    ]

    for label, args in steps:
        if not run(label, args, env):
            return 1

    print('pre-commit: всё чисто')
    return 0


if __name__ == '__main__':
    sys.exit(main())
