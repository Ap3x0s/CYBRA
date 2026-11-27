"""Закрепление роли: ручная правка админа не отменяется каталогом.

Дефект, ради которого это появилось: админ менял роль в приложении,
сотрудник входил через SSO — и роль возвращалась к той, что даёт группа
LDAP. Интерфейс показывал успех, правка лежала в базе, и только при чужом
входе тихо отменялась. Худший вид поломки: незаметный.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
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


@pytest.fixture()
def module(monkeypatch):
    import cybra.auth_oidc as loaded

    live = sys.modules[loaded.__name__].settings
    monkeypatch.setattr(live, 'oidc_sync_roles', True, raising=False)
    monkeypatch.setattr(
        live, 'oidc_group_roles_raw',
        'cybra-admins=admin,cybra-operators=operator,cybra-users=viewer',
        raising=False,
    )
    return loaded


def make_user(db, role='viewer', pinned=False, source='oidc') -> User:
    user = User(
        email='ivanov@example.org',
        display_name='Иван',
        password_hash='' if source == 'oidc' else 'х',
        role=role,
        role_pinned=pinned,
        is_active=True,
        oidc_sub='sub-1' if source == 'oidc' else None,
        auth_source=source,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_catalog_overrides_unpinned_role(db, module) -> None:
    """Без закрепления каталог управляет — это исходное поведение."""
    user = make_user(db, role='viewer')
    assert user.role_pinned is False
    module._sync_role(db, user, ['cybra-operators'])
    assert user.role == 'operator'


def test_pinned_role_survives_catalog(db, module) -> None:
    """Главное: закреплённую роль каталог не трогает."""
    user = make_user(db, role='admin', pinned=True)
    module._sync_role(db, user, ['cybra-users'])
    assert user.role == 'admin', 'каталог отменил ручную правку админа'


def test_pinned_survives_promotion_too(db, module) -> None:
    """Закрепление работает в обе стороны: и вниз, и вверх."""
    user = make_user(db, role='viewer', pinned=True)
    module._sync_role(db, user, ['cybra-admins'])
    assert user.role == 'viewer'


def test_unpinning_returns_control_to_catalog(db, module) -> None:
    """Снял флаг — каталог снова управляет.

    Второй админ нужен, потому что срабатывает защита последнего
    администратора: без неё тест проверял бы не снятие флага, а то, что
    защита от блокировки сильнее каталога. Оба правила верны — их просто
    нельзя проверить одновременно на одной учётке.
    """
    keeper = make_user(db, role='admin', pinned=True)
    keeper.email = 'keeper@example.org'
    keeper.oidc_sub = 'sub-2'
    db.commit()

    user = make_user(db, role='admin', pinned=True)
    user.role_pinned = False
    db.commit()
    module._sync_role(db, user, ['cybra-users'])
    assert user.role == 'viewer'


def test_pinned_defaults_to_false(db) -> None:
    """Новая учётка не закреплена: по умолчанию ролью управляет каталог."""
    user = make_user(db, role='viewer')
    assert user.role_pinned is False


def test_last_admin_guard_still_wins(db, module) -> None:
    """Защита последнего админа работает и для незакреплённой роли."""
    user = make_user(db, role='admin', pinned=False)
    module._sync_role(db, user, ['cybra-users'])
    assert user.role == 'admin'
