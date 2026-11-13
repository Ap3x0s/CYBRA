"""Установить git-hook для синхронизации с Jira.

Копирует scripts/jira_hook.sh в .git/hooks/post-commit и делает исполняемым.
Hook в .git не попадает в репозиторий, поэтому его нужно ставить на каждом
клоне — для этого и нужен скрипт.

Использование:
    python scripts/install_jira_hook.py
    python scripts/install_jira_hook.py --remove
"""
from __future__ import annotations

import io
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    remove = '--remove' in args

    try:
        hooks_dir = Path(subprocess.run(
            ['git', 'rev-parse', '--git-path', 'hooks'],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print('Не git-репозиторий')
        return 1
    if not hooks_dir.is_absolute():
        hooks_dir = (ROOT / hooks_dir).resolve()

    target = hooks_dir / 'post-commit'

    if remove:
        if target.exists():
            target.unlink()
            print(f'Удалён {target}')
        else:
            print('Hook не установлен')
        return 0

    source = ROOT / 'scripts' / 'jira_hook.sh'
    if not source.exists():
        print(f'Не найден {source}')
        return 1

    hooks_dir.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix('.bak')
        shutil.copy2(target, backup)
        print(f'Прежний hook сохранён как {backup.name}')

    shutil.copy2(source, target)
    # Права на исполнение. На Windows chmod частично игнорируется, но Git Bash
    # (в котором запускаются хуки) читает флаг из индекса.
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # Перевод строк в LF: CRLF в shell-скрипте ломает запуск на Unix.
    content = target.read_text(encoding='utf-8')
    target.write_text(content.replace('\r\n', '\n'), encoding='utf-8', newline='\n')

    print(f'Hook установлен: {target}')
    print('Теперь при коммите с ключом CYB-NN в сообщении задача получит')
    print('комментарий со ссылкой на коммит.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
