"""Показать, откуда берутся проценты в интерфейсе.

Заказчик видит garak 60% и bipia 38.9% и спрашивает, почему я говорю про
снижение. Проверяем математику по каждому инструменту и общую сумму.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = sys.argv[1] if len(sys.argv) > 1 else '20261120T113444Z'


def main() -> int:
    base = ROOT / 'var' / 'runs' / RUN
    base = next((p for p in [base] if p.exists()), None) or \
        sorted(ROOT.glob(f'var/runs/{RUN}*'))[0]
    session = base if (base / 'summary.json').exists() else next(
        child for child in base.iterdir()
        if child.is_dir() and (child / 'summary.json').exists())
    summary = json.loads((session / 'summary.json').read_text(encoding='utf-8'))

    print('прогон:', base.name)
    print()
    header = 'инструмент            PASS  FAIL  UNSC  внутри   доля'
    print(header)
    print('-' * len(header))

    total_pass = total_fail = total_unscored = 0
    for model in summary.get('models', {}).values():
        for tool in model.get('tools', []):
            counts = tool.get('counts') or {}
            passed = counts.get('PASS', 0)
            failed = counts.get('FAIL', 0)
            unscored = counts.get('UNSCORED', 0)
            scored = passed + failed
            rate = f'{100 * failed / scored:.1f}%' if scored else '—'
            print(f'{tool["tool"]:20}{passed:>6}{failed:>6}{unscored:>6}'
                  f'{scored:>8}{rate:>9}')
            total_pass += passed
            total_fail += failed
            total_unscored += unscored

    print()
    scored = total_pass + total_fail
    print(f'ИТОГО: PASS={total_pass} FAIL={total_fail} '
          f'UNSCORED={total_unscored}')
    print(f'общая доля провалов: {100 * total_fail / scored:.1f}%')

    # Почему у garak высокий процент при малом числе провалов.
    print()
    print('Важно: у garak знаменатель маленький — 5 проверок.')
    print('Один провал даёт сразу 20 процентных пункта. Это не «модель')
    print('плохая на 60%», а «из 5 проверок 3 провалены».')
    return 0


if __name__ == '__main__':
    sys.exit(main())
