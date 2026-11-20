"""Пересчитать статусы шагов в уже выполненных прогонах.

Фикс «UNSCORED с пометкой disputed_reference — это завершённый вердикт»
применялся только к новым прогонам. Прогоны, сделанные раньше, остались с
PARTIAL там, где шаг на самом деле полон: 12 спорных кейсов BIPIA помечены
на диске, ошибок нет.

Данные на диске уже содержат флаг disputed_reference, поэтому пересчёт не
требует повторного запуска бенчмарков: пересобираем summary.json и
обновляем статусы шагов в базе.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))

from security_suite.report import consolidate  # noqa: E402


def settled(row: dict) -> bool:
    """Завершённая запись: вердикт есть или кейс сознательно исключён."""
    if row.get('status') in ('PASS', 'FAIL'):
        return True
    return row.get('status') == 'UNSCORED' and bool(row.get('disputed_reference'))


def recompute(session: Path, dry: bool = False) -> dict:
    """Пересчитать status.json каждого шага и пересобрать отчёт."""
    changes = {}
    for status_path in session.rglob('status.json'):
        tool = status_path.parent.name
        records_path = status_path.parent / 'records.jsonl'
        if not records_path.exists():
            continue
        rows = [json.loads(line) for line in
                records_path.read_text(encoding='utf-8').splitlines()
                if line.strip()]
        if not rows:
            continue
        status = json.loads(status_path.read_text(encoding='utf-8'))
        old = status.get('status')
        # Старые прогоны не писали worker_complete, зато писали note с
        # настоящей причиной неполноты: «завершена проба X, остальные не
        # успели до отмены». Это подлинный PARTIAL, и пересчитывать его по
        # записям нельзя: незавершённые пробы вообще не оставили строк,
        # поэтому по данным шаг выглядит полным.
        note = str(status.get('note') or '').lower()
        if note and any(word in note for word in
                        ('отмен', 'не успел', 'cancel', 'interrupt')):
            continue
        if old == 'PARTIAL' and 'worker_complete' not in status and note:
            continue
        # Правило то же, что в run.py: сбой воркера и ошибки транспорта
        # оставляют шаг неполным, а сознательно исключённые кейсы — нет.
        complete = (status.get('worker_complete', True)
                    and not status.get('transport_errors')
                    and all(settled(row) for row in rows))
        new = 'COMPLETE' if complete else ('PARTIAL' if rows else 'ERROR')
        if old != new:
            changes[tool] = (old, new)
            if not dry:
                status['status'] = new
                status['recomputed_from_records'] = True
                status_path.write_text(
                    json.dumps(status, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8')
    return changes


def main() -> int:
    dry = '--apply' not in sys.argv
    if dry:
        print('РЕЖИМ ПРОВЕРКИ (ничего не меняется). Для записи: --apply')
        print()

    runs = sorted(p for p in (ROOT / 'var' / 'runs').iterdir() if p.is_dir())
    total = 0
    for run in runs:
        session = run
        if not (session / 'summary.json').exists():
            nested = [c for c in run.iterdir()
                      if c.is_dir() and (c / 'summary.json').exists()]
            if not nested:
                continue
            session = nested[0]
        changes = recompute(session, dry)
        if not changes:
            continue
        print(f'{run.name}:')
        for tool, (old, new) in changes.items():
            print(f'  {tool:20} {old:9} -> {new}')
        total += len(changes)
        if not dry:
            summary = consolidate(session)
            models = list(summary.get('models', {}).values())
            if models:
                statuses = {t['tool']: t['status'] for t in models[0]['tools']}
                print(f'  пересобран отчёт, статусы: {statuses}')

    print()
    print(f'шагов, требующих пересчёта: {total}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
