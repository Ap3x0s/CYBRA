#!/usr/bin/env python
"""Установить git-хук pre-commit для этапа 0 схемы DevSecOps.

Хук вызывает scripts/precommit.py: линтер, проверка формата, аудит переводов
и тесты. Это те же проверки, что гоняет CI, но локально и за секунды.

Почему Python, а не shell. Прежняя версия была на /bin/sh и на Windows не
запускалась: `sh` в системе нет. Хук при этом «существовал» — и формат кода
уехал в CI, сделав прогон красным. Проверка, которая молча не работает,
хуже отсутствующей.

Идемпотентен: перезаписывает хук, если он уже есть.

Запуск:
    python scripts/install_git_hooks.py
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / '.git' / 'hooks' / 'pre-commit'

# Хук минимальный: определить интерпретатор и передать управление.
# На Windows .venv/Scripts/python.exe, на Unix — python3 из PATH.
TEMPLATE = """#!/bin/sh
# Установлено scripts/install_git_hooks.py — этап 0 схемы DevSecOps.
# Проверки: ruff, формат, аудит i18n, быстрые тесты.

ROOT=$(git rev-parse --show-toplevel)
if [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  exec "$ROOT/.venv/Scripts/python.exe" "$ROOT/scripts/precommit.py"
elif [ -x "$ROOT/.venv/bin/python" ]; then
  exec "$ROOT/.venv/bin/python" "$ROOT/scripts/precommit.py"
else
  exec python "$ROOT/scripts/precommit.py"
fi
"""


def main() -> int:
    if not (ROOT / '.git').is_dir():
        print(f'FAIL: {ROOT} не git-репозиторий', file=sys.stderr)
        return 1

    HOOK.parent.mkdir(parents=True, exist_ok=True)
    HOOK.write_text(TEMPLATE, encoding='utf-8', newline='\n')

    # Права на исполнение: без них git молча игнорирует хук.
    mode = HOOK.stat().st_mode
    HOOK.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f'установлено: {HOOK}')
    print('проверки: ruff → формат → i18n → pytest')
    print('отключить разово: git commit --no-verify')
    return 0


if __name__ == '__main__':
    sys.exit(main())
