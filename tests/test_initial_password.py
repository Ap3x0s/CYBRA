"""Пароль первого старта: два канала, права 600, сброс из CLI.

Почему это тестируется. Пароль администратора генерируется при первом
старте и больше нигде не хранится — только argon2-хеш. Мы уже теряли
доступ на своём стенде: консоль закрылась, в базе хеш, восстановить нельзя.
Эти тесты фиксируют, что оба канала (лог и файл) работают и что файл
закрыт от посторонних.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'backend'))


@pytest.fixture()
def fresh_data_dir(tmp_path, monkeypatch):
    """Отдельный каталог данных: bootstrap создаёт админа только в пустой БД."""
    monkeypatch.setenv('CYBRA_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('CYBRA_SECRET_KEY', 'test-key-for-initial-password')

    # Модули читают настройки при импорте — перезагружаем их на каждый тест.
    for name in list(sys.modules):
        if name == 'cybra' or name.startswith('cybra.'):
            del sys.modules[name]

    from cybra.db import init_db
    from cybra.main import bootstrap_admin

    init_db()
    bootstrap_admin()
    return tmp_path


def test_password_written_to_file(fresh_data_dir, capsys):
    """Первый старт создаёт /data/initial-password рядом с базой."""
    path = fresh_data_dir / 'initial-password'
    assert path.exists(), 'файл пароля не создан'

    password = path.read_text(encoding='utf-8').strip()
    assert len(password) >= 12

    # Пароль из файла должен подходить к созданному администратору.
    from cybra.db import SessionLocal
    from cybra.models import User
    from cybra.security import verify_password
    from sqlalchemy import select

    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == 'admin@cybra.local'))
        assert admin is not None
        assert verify_password(admin.password_hash, password)
    finally:
        db.close()

    # И он же напечатан в лог — второй канал проверяет отдельный тест:
    # bootstrap_admin вызывается из фикстуры, и её stdout pytest относит к
    # отдельной фазе, куда capsys.readouterr() не достаёт.


def test_banner_goes_to_stdout(fresh_data_dir):
    """Баннер с паролем печатается в stdout — второй канал для оператора.

    Проверяем перехватом самого print, а не capsys: bootstrap_admin
    вызывается из фикстуры, и pytest относит её вывод к отдельной фазе,
    куда readouterr() не достаёт.
    """
    from unittest.mock import patch

    from cybra.main import bootstrap_admin

    old_password = (fresh_data_dir / 'initial-password').read_text(encoding='utf-8').strip()

    # Удалять пользователя через ORM нельзя: на него ссылаются сессии и
    # версии датасетов. Проще выполнить INSERT в чистой БД — но её создаёт
    # фикстура. Поэтому проверяем баннер на ПЕРВОМ старте: временно убираем
    # признак «админ существует» подменой селекта.
    printed: list[str] = []
    fake_no_admin = type('R', (), {'scalar': lambda self, *a, **k: None})()

    class FakeSession:
        def add(self, *a, **k):
            pass

        def commit(self):
            pass

        def close(self):
            pass

        def scalar(self, *a, **k):
            return None

    with patch('builtins.print', side_effect=lambda *a, **k: printed.append(' '.join(map(str, a)))), \
         patch('cybra.main.SessionLocal', return_value=FakeSession()), \
         patch('cybra.main._seed_datasets'):
        bootstrap_admin()

    output = '\n'.join(printed)
    assert 'создан администратор' in output
    assert 'initial-password' in output, 'в баннере нет пути к файлу'
    # Оба канала несут ОДИН пароль: тот, что только что записан в файл.
    written = (fresh_data_dir / 'initial-password').read_text(encoding='utf-8').strip()
    assert written in output, 'пароль в баннере и в файле различаются'
    # И он действительно новый: мок-сессия не нашла админа, bootstrap его создал.
    assert written != old_password, 'пароль не пересоздан при создании админа'


def test_password_file_is_private(fresh_data_dir):
    """Файл с паролем читает только владелец каталога данных."""
    path = fresh_data_dir / 'initial-password'
    mode = stat.S_IMODE(path.stat().st_mode)
    if os.name == 'posix':
        assert mode == 0o600, f'ожидались права 600, получено {oct(mode)}'
    else:
        # На Windows unix-режим не выставляется через chmod; проверяем, что
        # вызов не уронил запись и файл доступен.
        assert path.exists()


def test_second_start_does_not_regenerate(fresh_data_dir):
    """Повторный старт не создаёт нового админа и не перезаписывает пароль."""
    path = fresh_data_dir / 'initial-password'
    first = path.read_text(encoding='utf-8')

    from cybra.main import bootstrap_admin

    bootstrap_admin()  # админ уже есть
    assert path.read_text(encoding='utf-8') == first, 'пароль перезаписан'


def test_reset_password_command_changes_hash(fresh_data_dir):
    """CLI reset-password ставит новый пароль, который подходит."""
    from sqlalchemy import select

    from cybra.__main__ import main as cli

    assert cli(['reset-password', 'admin@cybra.local', 'brand-new-pass-123']) == 0

    from cybra.db import SessionLocal
    from cybra.models import User
    from cybra.security import verify_password

    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == 'admin@cybra.local'))
        assert verify_password(admin.password_hash, 'brand-new-pass-123')
    finally:
        db.close()


def test_reset_password_unknown_user(fresh_data_dir):
    """Неизвестный email — код 1 и понятное сообщение, без трейсбека."""
    from cybra.__main__ import main as cli

    assert cli(['reset-password', 'nobody@example.com']) == 1
