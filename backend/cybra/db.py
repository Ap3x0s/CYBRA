"""Database session handling and bootstrap."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
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


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[OrmSession]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
