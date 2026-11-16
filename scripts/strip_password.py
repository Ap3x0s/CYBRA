"""Убрать пароль администратора из скриптов: читать из окружения.

Причина: пароль был захардкожен в семи скриптах и попал в публичный
репозиторий. Скрипты утилитарные (проверки вёрстки, монитор прогона,
запуск набора), но пароль в них — настоящий, рабочий.

Логин admin@cybra.local не является секретом (он одинаков на всех
установках и печатается при первом старте), поэтому его оставляем
дефолтом. Пароль — только из окружения CYBRA_PASSWORD.

Файлы делятся на три формы, и каждую надо править по-своему:
  1. константа PASSWORD = '...'
  2. аргумент sys.argv[2] с захардкоженным дефолтом
  3. прямой литерал внутри page.fill(..., '...')
"""
from __future__ import annotations

import re
from pathlib import Path

OLD = '__CYBRA_PASSWORD__'

FILES = [
    'scripts/audit_layout.py',
    'scripts/bench_field.py',
    'scripts/probe_field_crash.py',
    'scripts/run_all8.py',
    'scripts/verify_field.py',
    'scripts/verify_topbar.py',
    'scripts/watch_run.py',
]


def ensure_import(src: str) -> str:
    """Гарантировать наличие import os (после from __future__, если он есть)."""
    if re.search(r'^import os$', src, re.MULTILINE):
        return src
    # Вставить после блока from __future__, иначе в начало
    m = re.search(r'^(from __future__ import [^\n]+\n)+', src, re.MULTILINE)
    if m:
        end = m.end()
        return src[:end] + 'import os\n' + src[end:]
    return 'import os\n' + src


def patch(path: str) -> bool:
    p = Path(path)
    src = p.read_text(encoding='utf-8')
    if OLD not in src:
        print(f'  {path}: пароля нет, пропуск')
        return False

    orig = src

    # 1. Константа: PASSWORD = '...'
    src = re.sub(
        r"^(\s*)PASSWORD\s*=\s*'__CYBRA_PASSWORD__'",
        r"\1# Пароль только из окружения: в репозитории ему не место.\n"
        r"\1PASSWORD = os.environ.get('CYBRA_PASSWORD', '')",
        src, flags=re.MULTILINE,
    )

    # 2. sys.argv[2] с дефолтом-паролем
    src = re.sub(
        r"sys\.argv\[2\]\s+if\s+len\(sys\.argv\)\s*>\s*2\s+else\s+'__CYBRA_PASSWORD__'",
        "sys.argv[2] if len(sys.argv) > 2 else os.environ.get('CYBRA_PASSWORD', '')",
        src,
    )

    # 3. Прямой литерал в вызове
    src = src.replace(
        "page.fill('input[type=password]', '__CYBRA_PASSWORD__')",
        "page.fill('input[type=password]', os.environ.get('CYBRA_PASSWORD', ''))",
    )

    if OLD in src:
        # что-то осталось — покажем, чтобы не пропустить молча
        for i, line in enumerate(src.splitlines(), 1):
            if OLD in line:
                print(f'  {path}:{i}: НЕ ЗАМЕНЕНО → {line.strip()[:80]}')
        return False

    src = ensure_import(src)

    # Проверка: файл не сломан
    if src.count('(') != src.count(')'):
        print(f'  {path}: расхождение скобок, НЕ ЗАПИСАН')
        return False

    if src != orig:
        p.write_text(src, encoding='utf-8', newline='\n')
        print(f'  {path}: очищен')
        return True
    return False


def main() -> int:
    print('чистка пароля из скриптов:')
    changed = sum(1 for f in FILES if patch(f))

    print('\nконтрольная проверка:')
    leftover = []
    for f in FILES:
        if OLD in Path(f).read_text(encoding='utf-8'):
            leftover.append(f)
    if leftover:
        print('  ПАРОЛЬ ОСТАЛСЯ В:', leftover)
        return 1
    print(f'  пароля нет ни в одном из {len(FILES)} файлов')
    print(f'  изменено файлов: {changed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
