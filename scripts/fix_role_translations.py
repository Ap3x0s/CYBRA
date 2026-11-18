"""Переводы значений роли, которые приходят с бэкенда.

Бэкенд отдаёт user.role как admin/operator/viewer. Топбар рендерил его без t(),
поэтому роль оставалась английской в русском интерфейсе (а в английском
показывалась русская подпись — она приходила другим путём). В словаре были
только ключи 'Администратор'/'администратор', а значение — 'admin'.

Отдельный случай от остальных: ключ и русское, и английское значение берутся
из одного и того же идентификатора, поэтому 'admin': 'admin' формально
перевод, фактически нет. Правим оба словаря.
"""
from __future__ import annotations

import re
from pathlib import Path

I18N = Path('frontend/src/i18n.js')

# ключ (значение с бэкенда) -> подпись
RU_LABELS = {
    'admin': 'Администратор',
    'operator': 'Оператор',
    'viewer': 'Наблюдатель',
}
EN_LABELS = {
    'admin': 'Administrator',
    'operator': 'Operator',
    'viewer': 'Viewer',
}


def patch(block: str, labels: dict[str, str]) -> tuple[str, list[str]]:
    """Заменить существующие ключи на нужные подписи, вернув список правок."""
    changed = []
    for key, label in labels.items():
        pattern = re.compile(r"^(\s*)'" + re.escape(key) + r"'(\s*):(\s*)'[^']*'", re.MULTILINE)
        match = pattern.search(block)
        if not match:
            changed.append(f'{key}: ключа нет, пропущен')
            continue
        old = match.group(0)
        new = f"{match.group(1)}'{key}'{match.group(2)}:{match.group(3)}'{label}'"
        if old == new:
            continue
        block = block[:match.start()] + new + block[match.end():]
        changed.append(f'{key} -> {label}')
    return block, changed


def main() -> int:
    text = I18N.read_text(encoding='utf-8')
    ru_start = text.index('export const RU = {')
    en_start = text.index('export const EN = {')
    en_end = text.index('export const DICT')

    ru_block = text[ru_start:en_start]
    en_block = text[en_start:en_end]

    ru_block, ru_changes = patch(ru_block, RU_LABELS)
    en_block, en_changes = patch(en_block, EN_LABELS)

    I18N.write_text(ru_block + en_block + text[en_end:], encoding='utf-8', newline='\n')

    print('RU:', ru_changes or 'без изменений')
    print('EN:', en_changes or 'без изменений')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
