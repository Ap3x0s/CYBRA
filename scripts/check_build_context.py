"""Что реально попадёт в контекст сборки образа.

Проверяем не «есть ли .env в .dockerignore», а матчится ли паттерн на
конкретные файлы так, как это делает Docker (shell-подобные glob:
* ? и литералы, без ** и без рекурсии по имени).

Зачем: .dockerignore содержит `.env`, но `.env.development` под него НЕ
подпадает — Docker сравнивает полный путь, а не имя файла. Такая проверка
находится в минуту, а секрет в образе — навсегда.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = ROOT / '.dockerignore'

# Файлы, которых в образе быть не должно ни при каких условиях.
FORBIDDEN = [
    'frontend/.env.development',
    'frontend/.env',
    'frontend/.env.local',
    '.env',
    'jira/.env',
    'var/secret.key',
    'var-test/secret.key',
    'cookies.txt',
    'frontend/node_modules/react/package.json',
    'backend/static/index.html',
    '.git/config',
    'docs/media/console.png',
]

# Файлы, которые в образе НУЖНЫ: их случайное исключение ломает сборку.
REQUIRED = [
    'frontend/package.json',
    'backend/pyproject.toml',
    'backend/cybra/main.py',
    'scan/engine.py',
    'run.py',
    'datasets/harmbench.csv',
]


def patterns() -> list[str]:
    return [line.strip() for line in IGNORE.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.startswith('#')]


def ignored(rel: str, pats: list[str]) -> str | None:
    """Первый паттерн, который исключает путь. None — файл идёт в контекст.

    ** в .dockerignore означает «любая глубина», а fnmatch такого синтаксиса
    не знает. Обрабатываем сами: шаблон **/имя совпадает, если имя есть
    ЛЮБЫМ сегментом пути, а не только с начала.
    """
    for pattern in pats:
        if pattern.startswith('**/'):
            tail = pattern[3:]
            # **/node_modules — исключает каталог на любой глубине.
            if any(fnmatch.fnmatch(part, tail) for part in rel.split('/')):
                return pattern
            continue
        if fnmatch.fnmatch(rel, pattern):
            return pattern
        if rel.startswith(pattern.rstrip('/') + '/'):
            return pattern
    return None


def main() -> int:
    pats = patterns()
    print(f'.dockerignore: {len(pats)} паттернов\n')

    problems = 0

    print('=== не должно попадать в образ ===')
    for rel in FORBIDDEN:
        hit = ignored(rel, pats)
        if hit:
            print(f'  OK   {rel:42} ← {hit}')
        else:
            print(f'  FAIL {rel:42} ПОПАДЁТ В КОНТЕКСТ')
            problems += 1

    print('\n=== должно попадать (иначе сборка сломается) ===')
    for rel in REQUIRED:
        hit = ignored(rel, pats)
        if hit:
            print(f'  FAIL {rel:42} исключён паттерном {hit}')
            problems += 1
        else:
            print(f'  OK   {rel:42} в контексте')

    if problems:
        print(f'\nпроблем: {problems}')
        return 1
    print('\nконтекст сборки чист: секретов нет, нужные файлы на месте')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
