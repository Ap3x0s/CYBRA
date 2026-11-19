"""``python -m cybra`` entry point: a single command starts the console.

Команды:

  cybra                           запустить консоль
  cybra reset-password [EMAIL]    сбросить пароль администратора
  cybra setup --tools garak …     установить тяжёлые бенчмарки

Почему reset-password нужен как отдельная команда. Пароль первого старта
печатается в лог и пишется в <data_dir>/initial-password, но если оба
канала потеряны, вернуть доступ было нельзя вообще: в базе лежит только
argon2-хеш, а API смены пароля требует текущий пароль. Ровно на это мы
наткнулись на своём стенде.
"""
from __future__ import annotations

import argparse
import os
import sys


def _reset_password(argv: list[str]) -> int:
    """Сбросить пароль администратора. Аргумент — новый пароль, необязательный.

    По умолчанию генерируем: пароль, переданный в командной строке, остаётся
    в истории оболочки и в `docker inspect`, а это лишний канал утечки.
    """
    import secrets

    from sqlalchemy import select

    from .db import SessionLocal, init_db
    from .models import User
    from .security import hash_password

    email = argv[1] if len(argv) > 1 else 'admin@cybra.local'
    password = argv[2] if len(argv) > 2 else secrets.token_urlsafe(12)

    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f'пользователь {email} не найден', file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        db.commit()
    finally:
        db.close()

    print(f'пароль для {email} установлен:', flush=True)
    print(f'  {password}', flush=True)
    print('смените его в «Настройках» после входа.', flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # reset-password разбираем до argparse: иначе его позиционные аргументы
    # конфликтуют с `setup`, который объявлен как nargs='*'.
    if argv and argv[0] == 'reset-password':
        return _reset_password(argv)

    parser = argparse.ArgumentParser(prog='cybra', description='CYBRA LLM security console')
    parser.add_argument('--host', default=os.environ.get('CYBRA_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('CYBRA_PORT', '8000')))
    parser.add_argument('--reload', action='store_true', help='Dev only: auto-reload')
    parser.add_argument('--engine', choices=['subprocess', 'mock'],
                        default=os.environ.get('CYBRA_ENGINE', 'subprocess'),
                        help='mock runs an offline fixture instead of real models')
    parser.add_argument('setup', nargs='*',
                        help='setup --tools garak pyrit: install native tools; '
                             'reset-password [EMAIL] [PASSWORD]: reset the admin password')
    args = parser.parse_args(argv)

    os.environ.setdefault('CYBRA_ENGINE', args.engine)

    if args.setup:
        if args.setup[0] == 'reset-password':
            return _reset_password(['reset-password', *args.setup[1:]])

        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root))
        from security_suite.setup_tools import setup
        tools = args.setup[1:] or ['garak', 'pyrit', 'agentdojo', 'promptfoo']
        errors = setup(tools)
        if errors:
            for tool, error in errors.items():
                print(f'FAILED {tool}: {error}', file=sys.stderr)
            return 1
        print('All requested tools are installed.', flush=True)
        return 0

    import uvicorn

    print(f'CYBRA starting on http://{args.host}:{args.port}', flush=True)
    uvicorn.run(
        'cybra.main:app',
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level='info',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
