"""Database session handling and bootstrap.

Поддерживаются два движка: PostgreSQL и SQLite.

Почему PostgreSQL по умолчанию для развёртывания, но SQLite остаётся:
Postgres снимает ограничение «одна установка — одна машина» и переживает
одновременные записи лучше, а WAL в SQLite на этом и спотыкался при
долгих прогонах. SQLite при этом не выбрасывается: он остаётся рабочим
вариантом для локального запуска без docker и для тестов, где поднимать
сервер БД на каждый тест несоразмерно.

Выбор — переменная CYBRA_DATABASE_URL. Если она не задана, берётся SQLite
в каталоге данных: так `python -m cybra` работает из коробки, без сервера.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import Base


def _database_url() -> str:
    """Строка подключения: явная, из окружения, или SQLite по умолчанию."""
    explicit = os.environ.get('CYBRA_DATABASE_URL', '').strip()
    if explicit:
        return explicit
    return f'sqlite:///{settings.db_path}'


DATABASE_URL = _database_url()
_IS_SQLITE = DATABASE_URL.startswith('sqlite')


def _make_engine(url: str) -> Engine:
    if url.startswith('sqlite'):
        return create_engine(
            url,
            connect_args={'check_same_thread': False, 'timeout': 30},
            future=True,
        )
    # pool_pre_ping: соединение в пуле могло умереть, пока шёл долгий прогон;
    # без проверки первый же запрос после паузы падает с OperationalError.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10,
                         future=True)


engine = _make_engine(DATABASE_URL)


if _IS_SQLITE:
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
#
# Тип указан для SQLite; в PostgreSQL тот же смысл даёт JSONB, и разница
# важна: SQLite хранит JSON строкой, а Postgres — настоящим jsonb, который
# умеет индексироваться и отдаётся драйвером уже разобранным.
_ADDED_COLUMNS: tuple[tuple[str, str, str, str], ...] = (
    # таблица, колонка, тип для SQLite, тип для PostgreSQL
    ('run_steps', 'planned', 'INTEGER', 'INTEGER'),
    ('runs', 'verdicts', 'JSON', 'JSONB'),
)


def _migrate(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    for table, column, sqlite_type, pg_type in _ADDED_COLUMNS:
        if table not in tables:
            continue  # create_all уже создаст таблицу целиком
        existing = {col['name'] for col in inspector.get_columns(table)}
        if column in existing:
            continue
        sql_type = sqlite_type if _IS_SQLITE else pg_type
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
