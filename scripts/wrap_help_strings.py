"""Обернуть в t() русские help-строки, которые рендерятся как есть.

Найдено аудитом «в обход t()»: в NewRun.jsx часть подсказок под полями
передаётся как help={t('...')}, а часть — как help="...", поэтому в английском
интерфейсе подсказки оставались русскими. Один и тот же экран, половина
переведена, половина нет — заметнее, чем полностью непереведённый.

Правим только атрибуты help= с кириллицей. label= и прочее не трогаем: там
встречаются технические значения вроде label="Seed", которые переводить не надо.
"""
from __future__ import annotations

import re
from pathlib import Path

TARGETS = ['frontend/src/pages/NewRun.jsx']

# help="текст с кириллицей" → help={t('текст с кириллицей')}
HELP = re.compile(r"""help="([^"]*[А-Яа-яЁё][^"]*)\"""")


def main() -> int:
    total = 0
    for rel in TARGETS:
        path = Path(rel)
        text = path.read_text(encoding='utf-8')

        def wrap(match: re.Match) -> str:
            nonlocal total
            total += 1
            value = match.group(1).replace('\\', '\\\\').replace("'", "\\'")
            return f'help={{t({value!r})}}'.replace('"', "'")

        new = HELP.sub(wrap, text)
        if new != text:
            path.write_text(new, encoding='utf-8', newline='\n')
            print(f'{rel}: обёрнуто help-строк: {total}')
        else:
            print(f'{rel}: изменений нет')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
