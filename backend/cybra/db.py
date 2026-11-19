"""Database session handling and bootstrap."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import Base

engine = create_engine(
    f'sqlite:///{settings.db_path}',
    connect_args={'check_same_thread': False, 'timeout': 30},
    future=True,
)


@event.listens_for(engine, 'connect')
def _sqlite_pragmas(dbapi_connection, _record):
    """WAL keeps readers alive during a run; foreign keys are off by default."""
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.execute('PRAGMA busy_timeout=30000')
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Колонки, добавленные после первого релиза. create_all() создаёт только
# отсутствующие ТАБЛИЦЫ и ничего не делает с существующими, поэтому у
# работающей установки новая колонка появлялась в модели, но не в БД: любой
# SELECT падал с 500 (no such column). Миграций в проекте нет, и заводить
# alembic ради одной nullable-колонки несоразмерно — добавляем идемпотентно.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # таблица, колонка, тип
    ('run_steps', 'planned', 'INTEGER'),
    ('runs', 'verdicts', 'JSON'),
)


def _migrate(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    for table, column, sql_type in _ADDED_COLUMNS:
        if table not in tables:
            continue  # create_all уже создаст таблицу целиком
        existing = {col['name'] for col in inspector.get_columns(table)}
        if column in existing:
            continue
        connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {sql_type}'))
        connection.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        _migrate(connection)


def get_db() -> Iterator[OrmSession]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
