"""Почему вердикт судьи не вынесен: разбор ошибок транспорта в прогоне.

Судья получает не только счётчики, но и выдержки из ответов модели — а они
длинные. Если ответы обрезаются по лимиту токенов, судья возвращает мусор,
и вердикт честно становится INSUFFICIENT_EVIDENCE. Проверяем, сколько таких
ошибок и где именно они возникают.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = sys.argv[1] if len(sys.argv) > 1 else '20261120T003051Z-cecf1b4a'


def main() -> int:
    run_dir = ROOT / 'var' / 'runs' / RUN
    session = next((p for p in run_dir.iterdir()
                    if p.is_dir() and (p / 'summary.json').exists()), None)
    if session is None:
        print('сессия не найдена')
        return 1
    print('сессия:', session.name)

    # 1. Ошибки транспорта по всем шагам.
    reasons: collections.Counter = collections.Counter()
    per_tool: dict[str, collections.Counter] = {}
    for status_path in session.rglob('status.json'):
        tool = status_path.parent.name
        data = json.loads(status_path.read_text(encoding='utf-8'))
        errors = data.get('transport_errors') or []
        counter = per_tool.setdefault(tool, collections.Counter())
        for error in errors:
            text = str(error)
            if 'TRUNCATED' in text:
                key = 'TRUNCATED (finish_reason=length)'
            elif 'EMPTY' in text:
                key = 'EMPTY_OUTPUT/CHOICES'
            elif 'HTTP 4' in text:
                key = 'HTTP 4xx (ключ/лимит)'
            elif 'HTTP 5' in text:
                key = 'HTTP 5xx'
            elif 'timeout' in text.lower() or 'timed out' in text.lower():
                key = 'timeout'
            else:
                key = text[:60]
            counter[key] += 1
            reasons[key] += 1

    print()
    print('=== ошибки транспорта по инструментам ===')
    for tool in sorted(per_tool):
        counter = per_tool[tool]
        if not counter:
            print(f'  {tool:20} чисто')
            continue
        total = sum(counter.values())
        detail = ', '.join(f'{k}: {v}' for k, v in counter.most_common(3))
        print(f'  {tool:20} {total:3}  {detail}')

    print()
    print('=== итого ===')
    for reason, count in reasons.most_common():
        print(f'  {count:4}  {reason}')

    # 2. Прогон вердикта: были ли http-запросы к судье и с каким статусом.
    verdict_dir = session / 'judge-verdict'
    if verdict_dir.exists():
        print()
        print('=== запросы судьи вердикта ===')
        http_log = verdict_dir / 'http.jsonl'
        if http_log.exists():
            statuses = collections.Counter()
            for line in http_log.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                statuses[row.get('http_status')] += 1
            for status, count in statuses.most_common():
                print(f'  HTTP {status}: {count}')
        for path in verdict_dir.glob('*.json'):
            if path.name.endswith('.evidence.json'):
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
            print(f"  {path.stem}: {data.get('verdict')} "
                  f"проблем: {(data.get('problems') or ['—'])[0][:90]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
