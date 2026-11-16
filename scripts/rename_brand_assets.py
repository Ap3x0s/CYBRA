"""Переименовать брендовые ассеты с русских имён на английские.

Причина: имена файлов на русском неудобны в командной строке, ломаются
при архивации (zip хранит имена в CP866), требуют экранирования в
скриптах и URL. Английские короткие имена с суффиксом формата решают это
без потери смысла.

Схема имён: <что>[-<вариант>].png
  emblem-trimmed.png   эмблема без подписи, обрезанная (используется)
  emblem-full.png      эмблема вместе с подписью CYBRA (не используется)
  wordmark.png         надпись CYBRA без эмблемы
  app-icon.png         иконка приложения со скруглением
  source-logo.png      исходник на чёрном фоне (уже английское имя)

Скрипт делает три вещи в одном проходе, чтобы не оставить битых ссылок:
  1. git mv (сохраняет историю файла, в отличие от удаления и добавления);
  2. правит пути в скриптах, которые эти файлы читают;
  3. печатает результат и проверяет, что старых ссылок не осталось.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'docs' / 'brand'

RENAME = {
    'Металлическая эмблема без фона.png': 'emblem-trimmed.png',
    'Металлическая эмблема CYBRA без фона.png': 'emblem-full.png',
    'Металлическая надпись CYBRA без фона.png': 'wordmark.png',
    'Премиальная иконка с металлическим шестиугольником и кубом.png': 'app-icon.png',
}

# Скрипты, где встречаются старые имена
SCRIPTS = [
    ROOT / 'scripts' / 'prep_brand_assets.py',
    ROOT / 'scripts' / 'make_favicons.py',
]


def main() -> int:
    print('переименование ассетов:')
    for old, new in RENAME.items():
        src = BRAND / old
        if not src.exists():
            print(f'  {old}: НЕТ НА ДИСКЕ, пропуск')
            continue
        # git mv сохраняет историю
        proc = subprocess.run(
            ['git', 'mv', str(src.relative_to(ROOT)),
             str((BRAND / new).relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f'  {old}: git mv не удался — {proc.stderr.strip()[:80]}')
            continue
        print(f'  {old[:44]:46s} → {new}')

    print('\nправка ссылок в скриптах:')
    for path in SCRIPTS:
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        original = text
        for old, new in RENAME.items():
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding='utf-8', newline='\n')
            print(f'  {path.name}: обновлён')
        else:
            print(f'  {path.name}: ссылок не было')

    print('\nпроверка, что старых имён не осталось:')
    leftovers = []
    for old in RENAME:
        r = subprocess.run(['git', 'grep', '-l', old],
                           cwd=ROOT, capture_output=True, text=True)
        hits = [l for l in r.stdout.split('\n') if l.strip()]
        if hits:
            leftovers.append((old, hits))
    if leftovers:
        for old, hits in leftovers:
            print(f'  ОСТАЛОСЬ {old}: {hits}')
        return 1
    print('  чисто')

    print('\nсодержимое docs/brand:')
    for f in sorted(BRAND.iterdir()):
        if f.is_file():
            print(f'  {f.name:24s} {f.stat().st_size // 1024:5d} KB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
