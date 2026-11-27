"""Роли из каталога: синхронизация и защита локального админа.

Тесты проверяют не «счастливый путь», а правила, каждое из которых
существует из-за конкретной поломки:

  * каталог повышает и понижает тех, кто пришёл из каталога;
  * локальную учётку каталог не трогает никогда;
  * последнего админа понизить нельзя — иначе стенд останется без
    единого человека, способного войти в настройки;
  * при нескольких группах побеждает сильнейшая, а не первая в токене;
  * без настроенного маппинга роль не меняется вовсе.

Каждый тест работает с настоящей БД в памяти и настоящей моделью, а не с
моками: правила про роли слишком легко «проверить» так, что они
перестанут работать в бою.
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
    """Настоящая БД в памяти: правила про роли проверяются на данных."""
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def module(monkeypatch):
    """Модуль OIDC с заданным маппингом групп.

    Берём модуль и `settings` из `sys.modules`, а не с уровня файла.

    Почему: pytest держит все тесты в одном процессе, и другой тест
    (test_initial_password) перезагружает пакет `cybra` со своим sys.path.
    После этого в памяти живут ДВА объекта модуля и ДВА объекта settings, и
    monkeypatch, применённый к одному, не виден функции из другого. Тесты
    при этом проходят в одиночку и падают в общем прогоне — ровно эта
    ловушка уже стоила времени в test_oidc.py.
    """
    import cybra.auth_oidc as loaded

    live_settings = sys.modules[loaded.__name__].settings
    monkeypatch.setattr(live_settings, 'oidc_sync_roles', True, raising=False)
    monkeypatch.setattr(
        live_settings, 'oidc_group_roles_raw',
        'cybra-admins=admin,cybra-operators=operator,cybra-viewers=viewer',
        raising=False,
    )
    monkeypatch.setattr(
        live_settings, 'oidc_default_role', 'viewer', raising=False)
    return loaded


def make_oidc_user(db, email='ivanov@example.org', role='viewer',
                   subject='sub-1') -> User:
    user = User(
        email=email,
        display_name='Иван',
        password_hash='',
        role=role,
        is_active=True,
        oidc_sub=subject,
        auth_source='oidc',
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_local_user(db, email='admin@cybra.local', role='admin') -> User:
    user = User(
        email=email,
        display_name='Администратор',
        password_hash='argon2-hash-not-used-here',
        role=role,
        is_active=True,
        auth_source='local',
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ----------------------------------------------------------------------
# Синхронизация работает
# ----------------------------------------------------------------------

def test_group_promotes_user(db, module) -> None:
    user = make_oidc_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-operators'])
    assert user.role == 'operator'


def test_group_demotes_user(db, module) -> None:
    """Понижение тоже нужно: увольнение из группы должно снимать права."""
    admin = make_local_user(db, email='other@cybra.local', role='admin')
    user = make_oidc_user(db, role='operator')
    module._sync_role(db, user, ['cybra-viewers'])
    assert user.role == 'viewer'
    assert admin.role == 'admin'


def test_full_ldap_path_understood(db, module) -> None:
    """Keycloak может отдать полный DN, а не короткое имя."""
    user = make_oidc_user(db, role='viewer')
    module._sync_role(
        db, user, ['cn=cybra-operators,ou=groups,dc=example,dc=org'])
    assert user.role == 'operator'


def test_strongest_group_wins(db, module) -> None:
    """Несколько групп: побеждает сильнейшая, а не первая в списке.

    Порядок групп в токене не определён, поэтому «первая совпавшая» давала
    бы разную роль между входами на одних и тех же данных.
    """
    user = make_oidc_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-viewers', 'cybra-admins'])
    assert user.role == 'admin'

    user2 = make_oidc_user(
        db, email='petrova@example.org', role='viewer', subject='sub-2')
    module._sync_role(db, user2, ['cybra-admins', 'cybra-viewers'])
    assert user2.role == 'admin'


def test_unknown_group_ignored(db, module) -> None:
    """Группа не из маппинга ничего не меняет."""
    user = make_oidc_user(db, role='viewer')
    module._sync_role(db, user, ['совсем-другая-группа'])
    assert user.role == 'viewer'


def test_typo_in_role_ignored(db, module, monkeypatch) -> None:
    """Опечатка в роли из конфига не выдаёт прав."""
    live = sys.modules[module.__name__].settings
    monkeypatch.setattr(
        live, 'oidc_group_roles_raw', 'cybra-admins=admn', raising=False)
    user = make_oidc_user(db, role='viewer')
    module._sync_role(db, user, ['cybra-admins'])
    assert user.role == 'viewer'


# ----------------------------------------------------------------------
# Защита: локальный админ главный
# ----------------------------------------------------------------------

def test_local_user_never_touched(db, module) -> None:
    """Локальную учётку каталог не трогает, даже если группы совпали."""
    admin = make_local_user(db, role='admin')
    module._sync_role(db, admin, ['cybra-viewers'])
    assert admin.role == 'admin'


def test_local_operator_not_demoted_by_catalog(db, module) -> None:
    operator = make_local_user(db, email='op@cybra.local', role='operator')
    module._sync_role(db, operator, ['cybra-viewers'])
    assert operator.role == 'operator'


def test_last_admin_cannot_be_demoted_by_catalog(db, module) -> None:
    """Каталог не может оставить систему без администратора.

    Сценарий реальный: в LDAP переименовали группу или рассинхронизировали
    федерацию. Без этой защиты единственный админ стал бы наблюдателем и
    потерял доступ к настройкам — а починить это можно было бы только
    правкой базы руками.
    """
    only_admin = make_oidc_user(
        db, email='boss@example.org', role='admin', subject='sub-boss')
    module._sync_role(db, only_admin, ['cybra-viewers'])
    assert only_admin.role == 'admin', 'последний админ понижен — блокировка'


def test_admin_demoted_when_another_exists(db, module) -> None:
    """Если админ не один — понижение проходит: это уже не блокировка."""
    make_local_user(db, email='keeper@cybra.local', role='admin')
    second = make_oidc_user(
        db, email='boss@example.org', role='admin', subject='sub-boss')
    module._sync_role(db, second, ['cybra-viewers'])
    assert second.role == 'viewer'


def test_inactive_admin_not_counted(db, module) -> None:
    """Отключённый админ не спасает от блокировки."""
    ghost = make_local_user(db, email='ghost@cybra.local', role='admin')
    ghost.is_active = False
    db.commit()

    only_active = make_oidc_user(
        db, email='boss@example.org', role='admin', subject='sub-boss')
    module._sync_role(db, only_active, ['cybra-viewers'])
    assert only_active.role == 'admin'


# ----------------------------------------------------------------------
# Выключатели
# ----------------------------------------------------------------------

def test_sync_can_be_disabled(db, module, monkeypatch) -> None:
    """CYBRA_OIDC_SYNC_ROLES=0 — каталог не перезаписывает роли."""
    live = sys.modules[module.__name__].settings
    monkeypatch.setattr(live, 'oidc_sync_roles', False, raising=False)
    user = make_oidc_user(db, role='operator')
    module._sync_role(db, user, ['cybra-viewers'])
    assert user.role == 'operator'


def test_no_mapping_leaves_role_alone(db, module, monkeypatch) -> None:
    """Без маппинга роль не меняется — иначе SSO молча понизил бы всех."""
    live = sys.modules[module.__name__].settings
    monkeypatch.setattr(live, 'oidc_group_roles_raw', '', raising=False)
    user = make_oidc_user(db, role='admin')
    module._sync_role(db, user, ['cybra-viewers'])
    assert user.role == 'admin'


def test_empty_groups_leaves_role_alone(db, module) -> None:
    user = make_oidc_user(db, role='operator')
    module._sync_role(db, user, [])
    assert user.role == 'operator'


# ----------------------------------------------------------------------
# Разбор конфигурации
# ----------------------------------------------------------------------

def test_group_roles_parsed(module, monkeypatch) -> None:
    live = sys.modules[module.__name__].settings
    monkeypatch.setattr(
        live, 'oidc_group_roles_raw',
        ' a=admin , b=operator ,, c = viewer , мусор ', raising=False)
    assert live.oidc_group_roles == {'a': 'admin', 'b': 'operator', 'c': 'viewer'}


def test_group_roles_empty(module, monkeypatch) -> None:
    live = sys.modules[module.__name__].settings
    monkeypatch.setattr(live, 'oidc_group_roles_raw', '', raising=False)
    assert live.oidc_group_roles == {}
