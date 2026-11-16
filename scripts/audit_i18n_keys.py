"""Найти вызовы t('...'), для которых нет ключа в словаре EN.

Причина конкретного бага: в i18n.js ключи записаны со стрелкой —
'метрики →', а в разметке вызывается t('метрики') без неё. Ключ не
находится, t() возвращает входную строку, и в английском интерфейсе
остаётся русский текст.

Проверяем ВСЕ вызовы t() во всех .jsx/.js фронтенда и сравниваем с
ключами словаря EN. Это находит не только три известных случая, но и
любые другие расхождения.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'frontend' / 'src'
I18N = SRC / 'i18n.js'

# Вызов t('строка') или t("строка") — только литералы, не переменные
CALL = re.compile(r"""\bt\(\s*(['"])((?:\\.|(?!\1).)*)\1""")

# Ключи словаря: строки вида 'ключ': 'значение',
KEY = re.compile(r"""^\s*'((?:\\.|[^'\\])*)'\s*:""", re.MULTILINE)


def en_keys() -> set[str]:
    text = I18N.read_text(encoding='utf-8')
    start = text.index('export const EN = {')
    end = text.index('export const DICT')
    block = text[start:end]
    return set(KEY.findall(block))


def main() -> int:
    keys = en_keys()
    print(f'ключей в EN: {len(keys)}\n')

    missing: dict[str, list[str]] = {}
    total_calls = 0

    for path in sorted(list(SRC.rglob('*.jsx')) + list(SRC.rglob('*.js'))):
        if path.name == 'i18n.js':
            continue
        text = path.read_text(encoding='utf-8')
        for _, raw in CALL.findall(text):
            total_calls += 1
            if raw not in keys:
                missing.setdefault(raw, []).append(str(path.relative_to(ROOT)))

    print(f'всего вызовов t(): {total_calls}')
    print(f'строк без ключа в EN: {len(missing)}\n')

    if not missing:
        print('все строки переведены')
        return 0

    for key in sorted(missing):
        files = sorted(set(missing[key]))
        print(f'  ✗ {key!r}')
        for f in files[:3]:
            print(f'      {f}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
