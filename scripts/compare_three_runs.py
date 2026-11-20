"""Сравнить три прогона: лимиты 2048, 8192 и 16384.

Главная метрика — TRUNCATED: обрезка ответа превращала рабочую проверку
в ERROR и искажала вывод об инструменте. Плюс статус garak и вердикт судьи.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = [
    ('2048', '20261120T003051Z-cecf1b4a'),
    ('8192', '20261120T022849Z-573fa71f'),
    ('16384', '20261120T034637Z-c67ad723'),
]
TOOLS = ['harmbench', 'jailbreakbench', 'bipia', 'security-regression',
         'promptfoo', 'garak', 'pyrit', 'agentdojo']


def session_of(run: str) -> Path | None:
    base = ROOT / 'var' / 'runs' / run
    if (base / 'summary.json').exists():
        return base
    for child in base.iterdir() if base.exists() else []:
        if child.is_dir() and (child / 'summary.json').exists():
            return child
    return None


def collect(run: str) -> dict:
    session = session_of(run)
    if session is None:
        return {}
    summary = json.loads((session / 'summary.json').read_text(encoding='utf-8'))
    info = {'truncated': 0, 'requests': 0, 'tools': {}, 'verdict': '—'}
    for path in session.rglob('status.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        info['truncated'] += sum(
            1 for e in (data.get('transport_errors') or [])
            if 'TRUNCATED' in str(e))
    for path in session.rglob('http.jsonl'):
        info['requests'] += sum(
            1 for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip())
    for model in summary.get('models', {}).values():
        for tool in model.get('tools', []):
            counts = tool.get('counts') or {}
            info['tools'][tool['tool']] = (
                f"{tool.get('status')} {counts.get('PASS', 0)}/"
                f"{counts.get('FAIL', 0)}")
    verdicts = list((summary.get('verdicts') or {}).values())
    if verdicts:
        info['verdict'] = verdicts[0]['verdict']
    return info


def main() -> int:
    data = {label: collect(run) for label, run in RUNS}
    labels = [label for label, _ in RUNS]

    header = f'{"":12}' + ''.join(f'{label:>16}' for label in labels)
    print(header)
    print('-' * len(header))
    for key, name in (('truncated', 'TRUNCATED'),
                      ('requests', 'запросов'),
                      ('verdict', 'вердикт судьи')):
        row = ''.join(f'{str(data[label].get(key, "—")):>16}' for label in labels)
        print(f'{name:12}{row}')

    print()
    print(f'{"инструмент":20}' + ''.join(f'{label:>16}' for label in labels))
    print('-' * (20 + 16 * len(labels)))
    for tool in TOOLS:
        cells = ''.join(
            f'{data[label].get("tools", {}).get(tool, "—"):>16}'
            for label in labels)
        print(f'{tool:20}{cells}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
