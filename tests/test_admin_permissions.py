"""Проверка прав на смену роли: кто кого может снять.

Здесь закрыт дефект, который тесты пропустили: проверка «это
неприкосновенный админ» стояла ВНУТРИ условия «других админов нет».
Значит она не срабатывала никогда, когда другой админ существует — а он
существует всегда, если действует локальный админ. То есть root-админа
из каталога мог снять любой администратор.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
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


def make(db, email, role, source, pinned=False, subject=None) -> User:
    user = User(
        email=email,
        display_name=email.split('@')[0],
        password_hash='' if source == 'oidc' else 'х',
        role=role,
        role_pinned=pinned,
        is_active=True,
        oidc_sub=subject,
        auth_source=source,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def guard(db, target: User, actor: User, new_role: str) -> None:
    """Воспроизвести проверку из update_user без HTTP-слоя."""
    import cybra.api as api_module

    class FakeRequest:
        class state:  # noqa: N801
            session = type('S', (), {'csrf_token': 'x'})()

        headers = {}
        method = 'PATCH'

    # Патчим CSRF и зависимость, чтобы дойти до самих правил.
    original = api_module.check_csrf
    api_module.check_csrf = lambda *a, **k: None
    try:
        api_module.update_user(
            target.id, FakeRequest(), {'role': new_role},
            _admin=actor, db=db)
    finally:
        api_module.check_csrf = original


def test_root_admin_cannot_be_removed_by_another_oidc_admin(db) -> None:
    """Главный случай: root-админ из каталога защищён от другого каталога.

    Здесь ЕСТЬ второй админ — именно на этом условии прежняя проверка
    молчала.
    """
    root = make(db, 'root@example.org', 'admin', 'oidc',
                pinned=True, subject='s-root')
    other = make(db, 'boss@example.org', 'admin', 'oidc',
                 pinned=True, subject='s-boss')

    with pytest.raises(HTTPException) as caught:
        guard(db, root, other, 'viewer')
    assert caught.value.status_code == 403
    assert 'локальная' in caught.value.detail.lower()


def test_root_admin_can_be_removed_by_local_admin(db) -> None:
    """Локальная аварийная учётка выше всех — это её назначение."""
    root = make(db, 'root@example.org', 'admin', 'oidc',
                pinned=True, subject='s-root')
    local = make(db, 'admin@cybra.local', 'admin', 'local')

    guard(db, root, local, 'viewer')
    db.refresh(root)
    assert root.role == 'viewer'


def test_unpinned_catalog_admin_still_removable(db) -> None:
    """Обычного админа из каталога снять можно — иначе нет смысла в двух ролях."""
    regular = make(db, 'reg@example.org', 'admin', 'oidc', subject='s-reg')
    keeper = make(db, 'keeper@cybra.local', 'admin', 'local')

    guard(db, regular, keeper, 'viewer')
    db.refresh(regular)
    assert regular.role == 'viewer'


def test_last_admin_still_protected(db) -> None:
    """Защита от блокировки никуда не делась."""
    only = make(db, 'only@cybra.local', 'admin', 'local')

    with pytest.raises(HTTPException) as caught:
        guard(db, only, only, 'viewer')
    assert caught.value.status_code == 409
