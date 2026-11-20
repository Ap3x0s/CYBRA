"""Перенести данные из SQLite в PostgreSQL, сохранив всё.

Миграция идёт через SQLAlchemy Core, а не через дамп SQL: типы различаются
(SQLite хранит JSON строкой, Postgres ждёт jsonb; даты в SQLite лежат
строками), и перегонять их текстом значило бы ловить ошибки разбора на
каждой таблице.

Порядок важен из-за внешних ключей: сначала справочники, потом то, что на
них ссылается. sessions и findings переливаются пакетами — их тысячи, и
вставлять по одной строке в Postgres слишком медленно.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

# noqa: E402 — импорт ниже sys.path.insert неизбежен: без него cybra не
# найдётся при запуске из корня репозитория.
from cybra.models import (  # noqa: E402
    Base,
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

# Порядок по зависимостям: родитель раньше ребёнка.
ORDER = [
    (User, 'users'),
    (DbSession, 'sessions'),
    (Endpoint, 'endpoints'),
    (Target, 'targets'),
    (DatasetVersion, 'dataset_versions'),
    (DatasetCase, 'dataset_cases'),
    (Run, 'runs'),
    (RunStep, 'run_steps'),
    (Finding, 'findings'),
]

BATCH = 500


def main() -> int:
    sqlite_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'var/cybra.sqlite3')
    pg_url = os.environ.get(
        'CYBRA_TARGET_DATABASE_URL',
        'postgresql+psycopg://cybra:cybra@127.0.0.1:5433/cybra')

    if not sqlite_path.exists():
        print('нет файла SQLite:', sqlite_path)
        return 2

    source = create_engine(f'sqlite:///{sqlite_path}', future=True)
    target = create_engine(pg_url, future=True)

    print('источник :', f'sqlite:///{sqlite_path}')
    print('приёмник :', pg_url.split('@')[-1])
    print()

    # Схему создаём с нуля: у нас чистая база, а create_all не трогает
    # существующие таблицы.
    Base.metadata.create_all(target)

    with Session(source) as src, Session(target) as dst:
        # Проверяем, что приёмник пуст: иначе повторный запуск удвоит строки.
        busy = {}
        for model, table in ORDER:
            count = dst.scalar(select(func.count()).select_from(model))
            if count:
                busy[table] = count
        if busy:
            print('в приёмнике уже есть данные:', busy)
            print('перенос делать некуда — очистите базу и повторите')
            return 1

        for model, table in ORDER:
            rows = src.scalars(select(model)).all()
            if not rows:
                print(f'{table:18} 0 (пропущено)')
                continue
            payload = [_as_dict(row, model) for row in rows]
            # Пакетами: по одной строке в Postgres — это тысячи round-trip.
            for start in range(0, len(payload), BATCH):
                dst.execute(insert(model), payload[start:start + BATCH])
            dst.commit()
            print(f'{table:18} {len(rows)}')

        # После переноса id остались прежними (мы их переносим явно), но
        # последовательности Postgres об этом не знают и начнут с 1 —
        # первая же вставка через API упадёт на дубликате ключа.
        _reset_sequences(target)
    print()
    print('последовательности сброшены на max(id)+1')
    return 0


def _as_dict(row, model) -> dict:
    """Строка ORM -> словарь колонок, без служебного состояния."""
    return {column.name: getattr(row, column.name)
            for column in model.__table__.columns}


def _reset_sequences(engine) -> None:
    """Сдвинуть последовательности за пределы перенесённых id.

    Мы переносим id явно, чтобы ссылки между таблицами остались валидными,
    но последовательности Postgres об этом не знают и начнут с 1: первая же
    вставка через API упала бы на дубликате ключа.
    """
    from sqlalchemy import text

    with engine.begin() as connection:
        for _model, table in ORDER:
            try:
                connection.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
                    f'COALESCE((SELECT MAX(id) FROM "{table}"), 1), true)'))
            except Exception as error:  # noqa: BLE001
                print(f'  {table}: пропущено ({type(error).__name__})')


if __name__ == '__main__':
    sys.exit(main())
