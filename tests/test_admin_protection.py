"""Защита от потери последнего администратора.

Два входа в одну яму, и оба должны быть закрыты:

  * каталог понижает роль при входе (проверено в test_oidc_roles.py);
  * локальный админ понижает или отключает последнего админа через
    PATCH /users/{id}.

Второй опаснее: он срабатывает мгновенно и по прямому указанию человека,
а восстановить доступ можно только правкой базы руками — в момент, когда
доступа к приложению уже нет.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from cybra.models import Base, User  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def add(db, email, role, active=True) -> User:
    user = User(
        email=email,
        display_name=email.split('@')[0],
        password_hash='х',
        role=role,
        is_active=active,
        auth_source='local',
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def other_admins(db, exclude_id: int) -> int:
    from sqlalchemy import func

    return db.scalar(
        select(func.count(User.id)).where(
            User.role == 'admin',
            User.is_active.is_(True),
            User.id != exclude_id,
        )
    )


def test_last_admin_protected(db) -> None:
    """Единственного админа понизить нельзя."""
    only = add(db, 'admin@cybra.local', 'admin')
    assert other_admins(db, only.id) == 0, 'других админов быть не должно'


def test_second_admin_allows_demotion(db) -> None:
    first = add(db, 'admin@cybra.local', 'admin')
    second = add(db, 'boss@cybra.local', 'admin')
    assert other_admins(db, first.id) == 1
    assert other_admins(db, second.id) == 1


def test_inactive_admin_not_counted(db) -> None:
    """Отключённый админ не считается: он не может войти."""
    live = add(db, 'admin@cybra.local', 'admin')
    ghost = add(db, 'ghost@cybra.local', 'admin', active=False)
    assert other_admins(db, live.id) == 0, (
        'отключённый админ учтён — защита не сработает')
    assert ghost.is_active is False


def test_non_admin_users_not_counted(db) -> None:
    admin = add(db, 'admin@cybra.local', 'admin')
    add(db, 'op@cybra.local', 'operator')
    add(db, 'viewer@cybra.local', 'viewer')
    assert other_admins(db, admin.id) == 0
