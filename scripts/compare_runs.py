"""Сравнить два прогона: до и после исправления лимита токенов.

Показывает, что именно изменил фикс max_tokens 2048 -> 8192. Отдельно
выводит ошибки транспорта: это главная метрика, потому что обрезка ответа
превращала рабочую проверку в ERROR и искажала вывод об инструменте.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOOLS = ['harmbench', 'jailbreakbench', 'bipia', 'security-regression',
         'promptfoo', 'garak', 'pyrit', 'agentdojo']

RUNS = {
    'до (2048)': '20261120T003051Z-cecf1b4a',
    'после (8192)': '20261120T022849Z-573fa71f',
}


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
    result = {'errors': 0, 'tools': {}, 'truncated': 0, 'requests': 0}
    for model in summary.get('models', {}).values():
        for tool in model.get('tools', []):
            name = tool['tool']
            counts = tool.get('counts') or {}
            result['tools'][name] = {
                'status': tool.get('status'),
                'pass': counts.get('PASS', 0),
                'fail': counts.get('FAIL', 0),
                'error': counts.get('ERROR', 0),
            }
    # Ошибки транспорта лежат в status.json каждого шага.
    for path in session.rglob('status.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        for error in data.get('transport_errors') or []:
            result['errors'] += 1
            if 'TRUNCATED' in str(error):
                result['truncated'] += 1
    for path in session.rglob('http.jsonl'):
        result['requests'] += sum(
            1 for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip())
    return result


def main() -> int:
    data = {label: stats(run) for label, run in RUNS.items()}
    labels = list(data)

    print(f'{"":22}' + ''.join(f'{label:>16}' for label in labels))
    print('-' * (22 + 16 * len(labels)))

    for key, name in (('requests', 'запросов всего'),
                      ('errors', 'ошибок транспорта'),
                      ('truncated', 'из них TRUNCATED')):
        row = ''.join(f'{data[label].get(key, 0):>16}' for label in labels)
        print(f'{name:22}{row}')

    print()
    print(f'{"инструмент":22}' + ''.join(f'{label:>18}' for label in labels))
    print('-' * (22 + 18 * len(labels)))
    for tool in TOOLS:
        cells = []
        for label in labels:
            info = data[label].get('tools', {}).get(tool)
            if not info:
                cells.append(f'{"—":>18}')
            else:
                cells.append(f'{info["status"] + " " + str(info["pass"]) + "/" + str(info["fail"]):>18}')
        print(f'{tool:22}' + ''.join(cells))

    # Итог по вердикту судьи.
    print()
    for label, run in RUNS.items():
        session = session_of(run)
        if session is None:
            continue
        summary = json.loads((session / 'summary.json').read_text(encoding='utf-8'))
        verdicts = summary.get('verdicts') or {}
        for entry in verdicts.values():
            problems = entry.get('problems') or []
            note = f' ({problems[0][:60]})' if problems else ''
            print(f'{label:14} вердикт: {entry.get("verdict")}{note}')

    before = data[labels[0]]
    after = data[labels[1]]
    print()
    print('TRUNCATED было', before.get('truncated', 0),
          '-> стало', after.get('truncated', 0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
