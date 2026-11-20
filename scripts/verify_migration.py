"""Сверить SQLite и PostgreSQL построчно после миграции.

Считать таблицы недостаточно: строка может приехать с потерей полей —
JSON в SQLite лежит текстом, даты тоже, и ошибка разбора проявится только
на чтении. Здесь сверяем количество, а затем содержимое ключевых строк.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

from cybra.models import (  # noqa: E402
    DatasetCase,
    DatasetVersion,
    Endpoint,
    Finding,
    Run,
    RunStep,
    Target,
    User,
)
from cybra.models import Session as DbSession  # noqa: E402

TABLES = [
    (User, 'users'), (DbSession, 'sessions'), (Endpoint, 'endpoints'),
    (Target, 'targets'), (DatasetVersion, 'dataset_versions'),
    (DatasetCase, 'dataset_cases'), (Run, 'runs'), (RunStep, 'run_steps'),
    (Finding, 'findings'),
]


def main() -> int:
    sqlite_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'var/cybra.sqlite3')
    pg_url = os.environ.get(
        'CYBRA_TARGET_DATABASE_URL',
        'postgresql+psycopg://cybra:cybra@127.0.0.1:5433/cybra')

    src_engine = create_engine(f'sqlite:///{sqlite_path}', future=True)
    dst_engine = create_engine(pg_url, future=True)

    mismatches = 0
    with Session(src_engine) as src, Session(dst_engine) as dst:
        # Границы id в источнике: строки сверх них появились в приёмнике уже
        # ПОСЛЕ миграции (например, сессия от проверочного входа в API), и
        # считать их потерей или дублем нельзя.
        source_max = {}
        for model, table in TABLES:
            source_max[table] = src.scalar(select(func.max(model.id))) or 0

        print(f'{"таблица":20} {"sqlite":>8} {"postgres":>9}  сверка')
        for model, table in TABLES:
            a = src.scalar(select(func.count()).select_from(model))
            b = dst.scalar(select(func.count()).select_from(model))
            extra = dst.scalar(
                select(func.count()).select_from(model)
                .where(model.id > source_max[table]))
            # Допустимо: ровно столько же строк, сколько было, плюс новые.
            ok = a + extra == b
            if not ok:
                mismatches += 1
            note = 'OK' if ok else 'РАСХОЖДЕНИЕ'
            if extra:
                note += f' (+{extra} новых после миграции)'
            print(f'{table:20} {a:>8} {b:>9}  {note}')

        print()
        print('=== содержимое ключевых строк ===')

        # 1. Администратор: пароль должен остаться прежним хешем.
        user_s = src.scalars(select(User)).first()
        user_d = dst.scalars(select(User)).first()
        if user_s and user_d:
            same_hash = user_s.password_hash == user_d.password_hash
            print(f'пользователь {user_d.email}: '
                  f'хеш совпадает: {same_hash}, роль {user_d.role}')
            if not same_hash:
                mismatches += 1

        # 2. Прогон с вердиктом: JSON обязан приехать разобранным.
        run_s = src.scalars(
            select(Run).where(Run.verdicts.is_not(None)).limit(1)).first()
        run_d = dst.get(Run, run_s.id) if run_s else None
        if run_s and run_d:
            same = run_s.verdicts == run_d.verdicts
            print(f'прогон {run_d.run_id}: вердикт совпадает: {same} '
                  f'({type(run_d.verdicts).__name__})')
            if not same:
                mismatches += 1

        # 3. Дата: SQLite хранит строку, Postgres — timestamp.
        run_time_s = src.scalars(select(Run.id).limit(1)).first()
        run_time_d = dst.get(Run, run_time_s)
        if run_time_d:
            print(f'дата создания: {run_time_d.created_at} '
                  f'({type(run_time_d.created_at).__name__})')

        # 4. Findings: проверяем первую и последнюю по id.
        for label, order in (('первая', Finding.id), ('последняя', Finding.id.desc())):
            f_s = src.scalars(select(Finding).order_by(order).limit(1)).first()
            f_d = dst.get(Finding, f_s.id) if f_s else None
            if f_s and f_d:
                same = (f_s.case_id == f_d.case_id
                        and f_s.verdict == f_d.verdict
                        and f_s.answer == f_d.answer)
                print(f'finding {label}: id={f_d.id} совпадает: {same}')
                if not same:
                    mismatches += 1

    print()
    print('расхождений:', mismatches)
    return 0 if mismatches == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
