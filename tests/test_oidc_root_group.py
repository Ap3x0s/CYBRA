"""Неприкосновенный админ из каталога.

Сценарий, ради которого это существует: учётку администратора каталога
скомпрометировали. Если у каталога есть полная власть над всеми ролями,
злоумышленник снимает всех админов и остаётся единственным хозяином.

Поэтому нужна группа, чью роль каталог снять не может. Локальная
аварийная учётка при этом остаётся выше всех: она не зависит ни от
каталога, ни от сети.
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
    monkeypatch.setattr(live, 'oidc_root_group', 'cybra-root', raising=False)
    return loaded


def make_user(db, email='petrova@example.org', role='viewer', pinned=False,
              source='oidc', subject='sub-1') -> User:
    user = User(
        email=email,
        display_name=email.split('@')[0],
        password_hash='' if source == 'oidc' else 'х',
        role=role,
        role_pinned=pinned,
        is_active=True,
        oidc_sub=subject if source == 'oidc' else None,
        auth_source=source,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_root_group_promotes_to_pinned_admin(db, module) -> None:
    """Член группы cybra-root получает admin и закрепление."""
    user = make_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-root'])
    assert user.role == 'admin'
    assert user.role_pinned is True, 'роль не закреплена — каталог сможет снять'


def test_root_group_survives_removal_from_it(db, module) -> None:
    """Убрали из группы — роль осталась: это и есть неприкосновенность."""
    user = make_user(db, role='admin', pinned=True)
    module._sync_role(db, user, ['cybra-users'])
    assert user.role == 'admin'
    assert user.role_pinned is True


def test_root_group_overrides_weaker_group(db, module) -> None:
    """Состоит и в слабой группе, и в root — побеждает root."""
    user = make_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-users', 'cybra-root'])
    assert user.role == 'admin'


def test_non_root_admin_still_managed_by_catalog(db, module) -> None:
    """Обычный админ из каталога управляем — иначе нет смысла в двух группах.

    Второй админ нужен, иначе сработает защита от блокировки и тест
    проверит не управляемость роли, а совсем другое правило.
    """
    keeper = make_user(
        db, email='keeper@example.org', role='admin', pinned=True, subject='s2')

    user = make_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-admins'])
    assert user.role == 'admin'
    module._sync_role(db, user, ['cybra-users'])
    assert user.role == 'viewer'
    assert keeper.role == 'admin'


def test_root_group_disabled_when_not_configured(db, module, monkeypatch) -> None:
    """Не настроена группа — ничего не закрепляется."""
    live = sys.modules[module.__name__].settings
    monkeypatch.setattr(live, 'oidc_root_group', '', raising=False)
    user = make_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-root'])
    assert user.role == 'viewer'
    assert user.role_pinned is False


def test_local_admin_untouched_by_root_group(db, module) -> None:
    """Локальную учётку root-группа тоже не трогает."""
    admin = make_user(
        db, email='admin@cybra.local', role='admin', source='local', subject='')
    module._sync_role(db, admin, ['cybra-users'])
    assert admin.role == 'admin'


def test_new_user_from_root_group_created_pinned(db, module) -> None:
    """Первый вход члена root-группы сразу даёт закреплённого админа.

    Это отдельный случай и отдельный дефект: при первом входе пользователя
    ещё нет, `_sync_role` не вызывается вовсе, и учётка создавалась с
    ролью из маппинга без закрепления. Защита включалась только со второго
    входа — а до него такого админа мог снять кто угодно.
    """
    user = module._resolve_user(
        db, 'sub-new', 'boss@example.org', 'Boss', ['cybra-root'])
    assert user.role == 'admin', 'root-группа не сработала при первом входе'
    assert user.role_pinned is True, 'роль не закреплена при создании'


def test_new_user_from_admin_group_not_pinned(db, module) -> None:
    """Обычный админ из каталога создаётся незакреплённым — каталог им управляет."""
    user = module._resolve_user(
        db, 'sub-op', 'op@example.org', 'Op', ['cybra-admins'])
    assert user.role == 'admin'
    assert user.role_pinned is False


def test_new_user_ordinary_gets_viewer(db, module) -> None:
    user = module._resolve_user(
        db, 'sub-v', 'v@example.org', 'V', ['cybra-users'])
    assert user.role == 'viewer'
    assert user.role_pinned is False
