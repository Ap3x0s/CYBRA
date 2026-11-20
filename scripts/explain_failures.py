"""Разложить провалы прогона по инструментам, категориям и причинам.

Заказчик спросил, нормален ли высокий процент провалов и можно ли ждать,
что модель «либо отказывается, либо соглашается». Чтобы ответить данными,
а не мнением, нужно понять, ЧТО именно падает: защита, полезность или
инфраструктура. Это три принципиально разные вещи.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from cybra.db import DATABASE_URL  # noqa: E402
from cybra.models import Finding, Run, RunStep  # noqa: E402

RUN = sys.argv[1] if len(sys.argv) > 1 else '20261120T034638Z'


def kind_of(category: str) -> str:
    """К какому классу относится категория.

    Это ключ к ответу: провал в injection/secret_leak — дефект защиты,
    а провал в benign/utility — избыточный отказ или потеря полезности.
    Смешивать их в «процент провалов» нельзя.
    """
    low = (category or '').lower()
    if any(word in low for word in ('benign', 'utility', 'baseline')):
        return 'полезность'
    if 'inject' in low or 'leak' in low or 'pii' in low:
        return 'защита'
    if low.startswith('harmful') or low in {
            'chemical_biological', 'cybercrime_intrusion', 'harassment_bullying',
            'illegal', 'misinformation_disinformation', 'copyright', 'harmful'}:
        return 'защита'
    return 'прочее'


def main() -> int:
    engine = create_engine(DATABASE_URL, future=True)
    with Session(engine) as session:
        run = session.scalars(
            select(Run).where(Run.run_id.like(f'{RUN}%'))).first()
        if run is None:
            print('прогон не найден:', RUN)
            return 1
        print('прогон:', run.run_id, '| статус:', run.status)
        print()

        steps = session.scalars(
            select(RunStep).where(RunStep.run_id == run.id)).all()
        by_tool = {step.id: step.tool for step in steps}

        findings = session.scalars(
            select(Finding).where(Finding.step_id.in_(by_tool))).all()

        # Сводка по классам: где настоящий дефект, а где потеря полезности.
        classes: collections.Counter = collections.Counter()
        fails_by_class: collections.Counter = collections.Counter()
        for item in findings:
            kind = kind_of(item.category)
            classes[kind] += 1
            if item.verdict == 'FAIL':
                fails_by_class[kind] += 1

        print('=== все записи по классам проверки ===')
        print(f'{"класс":14}{"всего":>8}{"FAIL":>8}{"доля":>9}')
        for kind in ('защита', 'полезность', 'прочее'):
            total = classes.get(kind, 0)
            fails = fails_by_class.get(kind, 0)
            share = f'{100 * fails / total:.1f}%' if total else '—'
            print(f'{kind:14}{total:>8}{fails:>8}{share:>9}')
        print()

        # Детализация: что именно упало и в какой категории.
        print('=== провалы по инструментам и категориям ===')
        detail: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        for item in findings:
            if item.verdict == 'FAIL':
                detail[(by_tool[item.step_id], item.category)].append(item.case_id)
        for (tool, category), cases in sorted(detail.items()):
            kind = kind_of(category)
            print(f'{tool:20} {category:34} {kind:12} {len(cases):3} '
                  f'например {cases[0][:40]}')
        print()

        # Ошибки: это не провал модели, а сбой проверки.
        errors = [f for f in findings if f.verdict == 'ERROR']
        print('=== ERROR (сбой проверки, не дефект модели) ===')
        if not errors:
            print('  нет')
        for item in errors:
            print(f"  {by_tool[item.step_id]:20} {item.case_id:30} "
                  f"{(item.reason or '')[:70]}")

        # Примеры реальных ответов на провалах — чтобы видеть, что там.
        print()
        print('=== что модель ответила на провалах (первые 3) ===')
        shown = 0
        for item in findings:
            if item.verdict != 'FAIL' or shown >= 3:
                continue
            if kind_of(item.category) != 'защита':
                continue
            shown += 1
            print(f'--- {by_tool[item.step_id]} / {item.category} / {item.case_id}')
            print('  ответ:', (item.answer or '')[:220].replace('\n', ' '))
            print('  судья:', (item.reason or '')[:160].replace('\n', ' '))
    return 0


if __name__ == '__main__':
    sys.exit(main())
