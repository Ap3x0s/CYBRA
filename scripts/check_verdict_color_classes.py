"""Проверить, что цвет вердикта проставлен на всех четырёх уровнях.

Заказчик просил красить NOT_ACCEPTABLE в красный, ACCEPTABLE в зелёный и
так далее. Проверяем, что класс цвета попадает и на подпись, и на код
вердикта в HTML-отчёте, и что .md не ломается (там цвета нет и не должно
быть — это текст).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security_suite.report import (  # noqa: E402
    VERDICT_CLASS,
    verdict_block_html,
    verdict_block_ru,
)

EXPECTED = {
    'ACCEPTABLE': 'ok',
    'ACCEPTABLE_WITH_CAVEATS': 'warn',
    'NOT_ACCEPTABLE': 'bad',
    'INSUFFICIENT_EVIDENCE': 'idle',
}


def main() -> int:
    failures = 0

    print('=== соответствие уровней и классов ===')
    for verdict, expected in EXPECTED.items():
        actual = VERDICT_CLASS.get(verdict)
        ok = actual == expected
        print(f'  {"OK " if ok else "НЕТ"} {verdict:26} {actual}')
        if not ok:
            failures += 1

    print()
    print('=== класс цвета в HTML-отчёте ===')
    for verdict, expected in EXPECTED.items():
        entry = {'verdict': verdict,
                 'behaviour': {'ru': 'Описание поведения модели.'},
                 'tools': [], 'problems': []}
        markup = '\n'.join(verdict_block_html(entry))
        chip = re.search(r'judge-chip (\w+)', markup)
        code = re.search(r'judge-code (\w+)', markup)
        chip_ok = chip is not None and chip.group(1) == expected
        code_ok = code is not None and code.group(1) == expected
        print(f'  {verdict:26} подпись={chip.group(1) if chip else "—":5} '
              f'код={code.group(1) if code else "—":5} '
              f'{"OK" if chip_ok and code_ok else "НЕТ"}')
        if not (chip_ok and code_ok):
            failures += 1

    print()
    print('=== .md остаётся текстом, без разметки цвета ===')
    for verdict in EXPECTED:
        entry = {'verdict': verdict,
                 'behaviour': {'ru': 'Описание поведения модели.'},
                 'tools': [], 'problems': []}
        text = '\n'.join(verdict_block_ru(entry))
        has_html = '<span' in text or 'class=' in text
        print(f'  {verdict:26} {"ЕСТЬ HTML (плохо)" if has_html else "чистый Markdown"}')
        if has_html:
            failures += 1

    print()
    print('провалов:', failures)
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
