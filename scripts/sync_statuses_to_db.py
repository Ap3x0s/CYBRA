"""Обновить статусы шагов в базе после пересчёта на диске.

Пересборка summary.json меняет файлы, но интерфейс читает базу. Здесь
переносим статусы из status.json в таблицу run_steps, чтобы страница
отчёта показывала «полно» там, где шаг действительно полон.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from cybra.db import DATABASE_URL  # noqa: E402
from cybra.models import Run, RunStep  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

RUN = '20261120T113444Z'


def main() -> int:
    engine = create_engine(DATABASE_URL, future=True)
    with Session(engine) as session:
        run = session.scalars(
            select(Run).where(Run.run_id.like(f'{RUN}%'))).first()
        if run is None:
            print('прогон не найден:', RUN)
            return 1
        session_dir = Path(run.out_dir)
        if not (session_dir / 'summary.json').exists():
            nested = [c for c in session_dir.iterdir()
                      if c.is_dir() and (c / 'summary.json').exists()]
            if nested:
                session_dir = nested[0]

        # Берём статусы из пересобранного summary.json — это источник правды.
        summary = json.loads(
            (session_dir / 'summary.json').read_text(encoding='utf-8'))
        statuses = {}
        for model in summary.get('models', {}).values():
            for tool in model.get('tools', []):
                statuses[tool['tool']] = tool['status']

        steps = session.scalars(
            select(RunStep).where(RunStep.run_id == run.id)).all()
        changed = 0
        for step in steps:
            new = statuses.get(step.tool)
            if new and step.completeness != new:
                print(f'  {step.tool:20} {step.completeness:9} -> {new}')
                step.completeness = new
                changed += 1
        session.commit()
        print()
        print('обновлено шагов:', changed)

        # Итоговый статус прогона: если все шаги COMPLETE, прогон полный.
        final = session.get(Run, run.id)
        if all(s.completeness == 'COMPLETE' for s in steps):
            if final.status != 'COMPLETE':
                print(f'  прогон: {final.status} -> COMPLETE')
                final.status = 'COMPLETE'
                session.commit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
