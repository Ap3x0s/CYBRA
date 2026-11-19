"""Что из jira попадает в контекст сборки образа.

Проверяем отдельно от образа: .dockerignore действует на КОНТЕКСТ, то есть
на то, что Docker отправляет демону перед сборкой. Файл может не попасть в
итоговый слой (его не копирует COPY), но всё равно уехать на демон — и при
удалённом демоне это уже передача данных наружу.
"""
from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

IGNORE = Path('.dockerignore')

CANDIDATES = [
    'jira/.env',
    'jira/backlog.py',
    'jira/README.md',
    'jira/sync_status.py',
    'jira/jira_import.py',
    'jira/github_import.py',
    # Скрипты вне папки: они в репозитории, но в образ не копируются.
    'scripts/jira_sync.py',
    'scripts/jira_hook.sh',
    'scripts/jira_create_ci_task.py',
    'scripts/jira_sync_ci_commits.py',
]


def patterns() -> list[str]:
    return [line.strip() for line in IGNORE.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.startswith('#')]


def excluded(rel: str, pats: list[str]) -> str | None:
    for pattern in pats:
        if pattern.startswith('**/'):
            tail = pattern[3:]
            if any(fnmatch.fnmatch(part, tail) for part in rel.split('/')):
                return pattern
            continue
        if fnmatch.fnmatch(rel, pattern) or rel.startswith(pattern.rstrip('/') + '/'):
            return pattern
    return None


def main() -> int:
    pats = patterns()
    problems = 0
    print('.dockerignore: правило jira/ ->', 'есть' if 'jira' in pats else 'НЕТ')
    print()
    for rel in CANDIDATES:
        hit = excluded(rel, pats)
        if hit:
            print(f'  исключён  {rel:32} ← {hit}')
        else:
            print(f'  В КОНТЕКСТЕ {rel:32} (но COPY его не берёт)')
            problems += 1
    print(f'\nв контекст попадает: {problems}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
