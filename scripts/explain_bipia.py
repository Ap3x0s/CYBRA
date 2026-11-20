"""Разобрать BIPIA: почему у него самый высокий процент провалов.

BIPIA проверяет косвенные инъекции в письмах и таблицах и, в отличие от
остальных, пишет ДВЕ записи на один кейс: сработала ли инъекция и
справилась ли модель с полезной задачей. Если этого не учитывать, «процент
провалов» удваивается и раздувается.

Смотрим по категориям и по реальным ответам, а не по счётчикам.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from cybra.db import DATABASE_URL  # noqa: E402
from cybra.models import Finding, Run, RunStep  # noqa: E402

RUN_PREFIX = sys.argv[1] if len(sys.argv) > 1 else '20261120T034637Z'


def main() -> int:
    engine = create_engine(DATABASE_URL, future=True)
    with Session(engine) as session:
        run = session.scalars(
            select(Run).where(Run.run_id.like(f'{RUN_PREFIX}%'))).first()
        steps = {s.id: s for s in session.scalars(
            select(RunStep).where(RunStep.run_id == run.id))}
        bipia_steps = [s for s in steps.values() if s.tool == 'bipia']
        findings = session.scalars(
            select(Finding).where(
                Finding.step_id.in_([s.id for s in bipia_steps]))).all()

    print('записей BIPIA:', len(findings))
    print()

    # Один кейс пишет две-три записи: инъекция, полезность, и иногда обе
    # в одной строке. Разделяем по суффиксу категории.
    by_kind = collections.Counter()
    fails_by_kind = collections.Counter()
    by_template = collections.defaultdict(
        lambda: collections.Counter())

    for item in findings:
        category = item.category or ''
        if category.endswith('/utility'):
            kind = 'полезность'
        elif '/utility' in category:
            kind = 'полезность'
        else:
            kind = 'инъекция'
        by_kind[kind] += 1
        if item.verdict == 'FAIL':
            fails_by_kind[kind] += 1
        # Шаблон: email/table + тип атаки.
        parts = category.split('/')
        template = parts[0] if parts else '?'
        attack = parts[1] if len(parts) > 1 else '?'
        key = f'{template} · {attack}'
        by_template[key][item.verdict] += 1

    print('=== по типу проверки ===')
    for kind, total in by_kind.items():
        fails = fails_by_kind.get(kind, 0)
        print(f'  {kind:12} всего {total:3}  FAIL {fails:3}  '
              f'{100 * fails / total:.0f}%')
    print()

    print('=== по шаблону и типу атаки ===')
    for key in sorted(by_template):
        counts = by_template[key]
        total = sum(counts.values())
        print(f'  {key:46} всего {total:3}  '
              f'PASS {counts.get("PASS", 0):2}  FAIL {counts.get("FAIL", 0):2}')
    print()

    # Ключевой вопрос: модели не сказали игнорировать, или она не смогла.
    print('=== примеры провалов полезности (модель не справилась с задачей) ===')
    shown = 0
    for item in findings:
        if shown >= 4:
            break
        if item.verdict != 'FAIL' or 'utility' not in (item.category or ''):
            continue
        shown += 1
        print(f'--- {item.case_id}')
        print('  вопрос к модели:', (item.prompt or '')[-160:].replace('\n', ' '))
        print('  её ответ       :', (item.answer or '')[:160].replace('\n', ' '))
        print('  вердикт судьи  :', (item.reason or '')[:150].replace('\n', ' '))
        print()

    print('=== примеры провалов инъекции (модель выполнила чужую команду) ===')
    shown = 0
    for item in findings:
        if shown >= 3:
            break
        if item.verdict != 'FAIL' or 'utility' in (item.category or ''):
            continue
        shown += 1
        print(f'--- {item.case_id}')
        print('  её ответ  :', (item.answer or '')[:180].replace('\n', ' '))
        print('  вердикт   :', (item.reason or '')[:150].replace('\n', ' '))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
