"""Разобрать garak: почему 27 провалов из 38.

garak считает не кейсы, а решения детекторов, и у него в записях НЕТ текста
ответа модели — только счётчики passed/failed от самого детектора. Значит
провал значит «детектор счёл ответ неудачным», а не «модель согласилась с
атакой». Нужно понять, что за детекторы и что они вообще видят.

Смотрим: какие пробы, какие детекторы, что записано в ответах.
"""
from __future__ import annotations

import collections
import json
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
        steps = [s for s in session.scalars(
            select(RunStep).where(RunStep.run_id == run.id))
            if s.tool == 'garak']
        findings = session.scalars(
            select(Finding).where(
                Finding.step_id.in_([s.id for s in steps]))).all()
        artifacts = [s.artifact_dir for s in steps]

    print('записей garak:', len(findings))
    print()

    by_category: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    for item in findings:
        by_category[item.category][item.verdict] += 1

    print('=== по категориям (проба/детектор) ===')
    total_fail = 0
    for category in sorted(by_category):
        counts = by_category[category]
        fail = counts.get('FAIL', 0)
        total_fail += fail
        print(f'  {category:52} PASS {counts.get("PASS", 0):2}  FAIL {fail:2}')
    print(f'  ИТОГО FAIL: {total_fail}')
    print()

    # Главное: чем garak вообще обосновывает вердикт.
    print('=== что записано в записях (первые 3 провала) ===')
    shown = 0
    for item in findings:
        if item.verdict != 'FAIL' or shown >= 3:
            continue
        shown += 1
        print(f'--- {item.case_id} / {item.category}')
        print('  answer (текст модели) :', repr(item.answer)[:100])
        print('  reason (обоснование)  :', repr(item.reason)[:100])
        print('  raw_json              :',
              json.dumps(item.raw_json or {}, ensure_ascii=False)[:220])
        print()

    # Нативные отчёты garak: там видно, что реально проверял детектор.
    print('=== нативные артефакты garak ===')
    for artifact in artifacts:
        path = Path(artifact)
        if not path.is_absolute():
            path = ROOT / artifact
        if not path.exists():
            print('  нет каталога:', artifact)
            continue
        for name in ('report.jsonl', 'garak-report.jsonl', 'records.jsonl'):
            candidate = path / name
            if candidate.exists():
                print(f'  {name}: {candidate.stat().st_size} байт')
        # Сам garak пишет отчёт в формате report.jsonl с полем passed.
        report = path / 'report.jsonl'
        if report.exists():
            rows = [json.loads(line) for line in
                    report.read_text(encoding='utf-8').splitlines()
                    if line.strip()]
            print(f'  строк в report.jsonl: {len(rows)}')
            if rows:
                sample = rows[0]
                print('  ключи:', sorted(sample)[:14])
                for key in ('probe', 'detector', 'passed', 'status'):
                    if key in sample:
                        print(f'    {key}: {str(sample[key])[:80]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
