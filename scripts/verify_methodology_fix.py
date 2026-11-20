"""Проверить, что исправление методики действительно снизило провалы.

Сравниваем прогон ДО правки (27) и ПОСЛЕ (28). Ожидание заказчика:
«если правило встанет, меньше не станет — значит что-то не так».

Проверяем три вещи:
  1) garak: 27 провалов -> должно стать столько же, сколько проваленных
     проверок (единицы), а не решения детекторов;
  2) BIPIA: спорные кейсы ушли в UNSCORED, провалов стало меньше;
  3) общий процент провалов упал.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEFORE = '20261120T034637Z-c67ad723'   # до правки методики
AFTER = '20261120T113444Z-cac84519'    # после


def session_of(run: str) -> Path | None:
    base = ROOT / 'var' / 'runs' / run
    if (base / 'summary.json').exists():
        return base
    for child in base.iterdir() if base.exists() else []:
        if child.is_dir() and (child / 'summary.json').exists():
            return child
    return None


def stats(run: str) -> dict:
    session = session_of(run)
    if session is None:
        return {}
    summary = json.loads((session / 'summary.json').read_text(encoding='utf-8'))
    out = {'tools': {}, 'pass': 0, 'fail': 0, 'unscored': 0}
    for model in summary.get('models', {}).values():
        for tool in model.get('tools', []):
            counts = tool.get('counts') or {}
            out['tools'][tool['tool']] = {
                'status': tool.get('status'),
                'pass': counts.get('PASS', 0),
                'fail': counts.get('FAIL', 0),
                'unscored': counts.get('UNSCORED', 0),
                'checks': tool.get('checks'),
                'judgements': tool.get('detector_judgements'),
            }
            out['pass'] += counts.get('PASS', 0)
            out['fail'] += counts.get('FAIL', 0)
            out['unscored'] += counts.get('UNSCORED', 0)
    return out


def main() -> int:
    before = stats(BEFORE)
    after = stats(AFTER)
    if not before or not after:
        print('нет одного из прогонов')
        return 1

    print('=== ОБЩИЕ ЧИСЛА ===')
    header = f'{"":22}{"до":>12}{"после":>12}'
    print(header)
    print('-' * len(header))
    for key, name in (('pass', 'PASS'), ('fail', 'FAIL'),
                      ('unscored', 'UNSCORED')):
        print(f'{name:22}{before.get(key, 0):>12}{after.get(key, 0):>12}')

    scored_b = before['pass'] + before['fail']
    scored_a = after['pass'] + after['fail']
    rate_b = 100 * before['fail'] / scored_b if scored_b else 0
    rate_a = 100 * after['fail'] / scored_a if scored_a else 0
    print(f'{"доля провалов":22}{rate_b:>11.1f}%{rate_a:>11.1f}%')

    print()
    print('=== GARAK: проверки вместо решений детекторов ===')
    for label, data in (('до', before), ('после', after)):
        tool = data['tools'].get('garak', {})
        print(f"  {label:6} FAIL={tool.get('fail', 0):3}  "
              f"проверок={tool.get('checks')}  "
              f"решений детекторов={tool.get('judgements')}")

    print()
    print('=== BIPIA: спорные кейсы ушли в UNSCORED ===')
    for label, data in (('до', before), ('после', after)):
        tool = data['tools'].get('bipia', {})
        print(f"  {label:6} PASS={tool.get('pass', 0):3} "
              f"FAIL={tool.get('fail', 0):3} "
              f"UNSCORED={tool.get('unscored', 0):3}")

    print()
    print('=== СТАТУСЫ ИНСТРУМЕНТОВ ===')
    tools = sorted(set(before['tools']) | set(after['tools']))
    print(f'{"инструмент":20}{"до":>12}{"после":>12}')
    for tool in tools:
        a = before['tools'].get(tool, {}).get('status', '—')
        b = after['tools'].get(tool, {}).get('status', '—')
        print(f'{tool:20}{a:>12}{b:>12}')

    print()
    ok = (after['fail'] < before['fail']
          or after.get('unscored', 0) > before.get('unscored', 0))
    print('фикс привёл к перераспределению:', 'ДА' if ok else 'НЕТ')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
