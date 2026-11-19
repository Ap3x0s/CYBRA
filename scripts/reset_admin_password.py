"""Сбросить пароль администратора.

Почему это нужно: bootstrap_admin() при первом старте генерирует пароль
через secrets.token_urlsafe(12) и печатает его в stdout. Дальше он нигде не
хранится — только argon2-хеш. Баннер ловится лишь тем, кто запускал процесс:
если консоль потеряна или пароль затем сменили, восстановить его невозможно
ни из БД, ни из логов, ни из репозитория.

Скрипт ставит НОВЫЙ пароль (или генерирует и печатает, если не задан
аргументом). Аргумент — только для локального стенда: пароль не должен
попадать в историю команд, поэтому по умолчанию печатаем сгенерированный.
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from sqlalchemy import select  # noqa: E402

from cybra.db import SessionLocal, init_db  # noqa: E402
from cybra.models import User  # noqa: E402
from cybra.security import hash_password  # noqa: E402


def main(argv: list[str]) -> int:
    email = argv[0] if argv else 'admin@cybra.local'
    password = argv[1] if len(argv) > 1 else secrets.token_urlsafe(12)

    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f'пользователь {email} не найден', file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        db.commit()
        print(f'пароль для {email} установлен:')
        print(f'  {password}')
        print('смените его в «Настройках» после входа.')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
