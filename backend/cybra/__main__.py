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

    email = argv[1] if len(argv) > 1 else "admin@cybra.local"
    password = argv[2] if len(argv) > 2 else secrets.token_urlsafe(12)

    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"пользователь {email} не найден", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        db.commit()
    finally:
        db.close()

    print(f"пароль для {email} установлен:", flush=True)
    print(f"  {password}", flush=True)

    # Обновляем файл первого старта, если он есть: иначе там останется
    # прежний пароль, и следующий оператор пойдёт читать именно файл —
    # это первое, что советует README. Файл не создаём заново: он нужен
    # только для первичного доступа, а после сброса пароль уже напечатан.
    from .config import settings

    marker = settings.data_dir / "initial-password"
    if marker.exists():
        try:
            marker.write_text(password + "\n", encoding="utf-8")
            marker.chmod(0o600)
            print(f"  файл обновлён: {marker}", flush=True)
        except OSError:
            pass

    print("смените его в «Настройках» после входа.", flush=True)
    return 0


def _setup(argv: list[str]) -> int:
    """Разобрать `cybra setup …` и установить инструменты.

    Разбираем вручную, до argparse. Причина: `setup` объявлен как nargs='*',
    и argparse съедает всё подряд — флаг --tools после него не распознаётся
    («unrecognized arguments»). А документация, подсказки в UI и
    capabilities.py обещают именно `cybra setup --tools garak`.

    Поддерживаются оба написания:
        cybra setup --tools garak pyrit
        cybra setup garak pyrit
        cybra setup                    (все четыре)

    Молча поддерживать два синтаксиса — не роскошь: первый обещан в 15
    местах, второй работал раньше, и ломать его без нужды незачем.
    """
    rest = argv[1:]
    tools: list[str] = []
    parsing_flags = True

    index = 0
    while index < len(rest):
        item = rest[index]
        if item in ("-h", "--help"):
            print(
                "usage: cybra setup [--tools] [TOOL ...]\n"
                "\n"
                "Установить тяжёлые бенчмарки. Без имён ставит все четыре.\n"
                "\n"
                "Доступные инструменты:\n"
                "  garak       сканер уязвимостей LLM (NVIDIA)\n"
                "  pyrit       фреймворк атак (Microsoft)\n"
                "  agentdojo   атаки на агентов с инструментами\n"
                "  promptfoo   проверки промптов (Node.js)\n"
                "  bipia       indirect prompt injection (venv проекта)\n"
                "\n"
                "Примеры:\n"
                "  cybra setup                        все четыре\n"
                "  cybra setup --tools garak pyrit    только указанные\n"
                "  cybra setup garak                  то же, без флага\n"
                "\n"
                "Офлайн-установка: задайте CYBRA_OFFLINE_DIR перед запуском.\n"
                "  export CYBRA_OFFLINE_DIR=/opt/cybra/offline-bundle\n"
                "  cybra setup --tools garak\n"
                "Колёса и архивы берутся из bundle, сеть не используется.",
                flush=True)
            return 0
        if item in ("--tools", "-t"):
            # Флаг принимает все следующие позиции до другого флага.
            parsing_flags = False
            index += 1
            continue
        if item.startswith("-") and parsing_flags:
            print(f"unknown option for setup: {item}", file=sys.stderr)
            print("run 'cybra setup --help' for usage", file=sys.stderr)
            return 2
        tools.append(item)
        index += 1

    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from security_suite.setup_tools import KNOWN_TOOLS, setup

    unknown = [tool for tool in tools if tool not in KNOWN_TOOLS]
    if unknown:
        # Опечатка в имени инструмента должна ловиться здесь, а не превращаться
        # в «READY» ни для чего: setup пропускает неизвестные молча.
        print(f"unknown tool(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(sorted(KNOWN_TOOLS))}", file=sys.stderr)
        return 2

    if not tools:
        tools = ["garak", "pyrit", "agentdojo", "promptfoo"]

    errors = setup(tools)
    if errors:
        for tool, error in errors.items():
            print(f"FAILED {tool}: {error}", file=sys.stderr)
        return 1
    print("All requested tools are installed.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # reset-password и setup разбираем до argparse: у обоих позиционные
    # аргументы, которые конфликтуют с объявлением `setup` как nargs='*'.
    if argv and argv[0] == "reset-password":
        return _reset_password(argv)
    if argv and argv[0] == "setup":
        return _setup(argv)

    parser = argparse.ArgumentParser(prog="cybra", description="CYBRA LLM security console")
    parser.add_argument("--host", default=os.environ.get("CYBRA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYBRA_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="Dev only: auto-reload")
    parser.add_argument(
        "--engine",
        choices=["subprocess", "mock"],
        default=os.environ.get("CYBRA_ENGINE", "subprocess"),
        help="mock runs an offline fixture instead of real models",
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("CYBRA_ENGINE", args.engine)

    import uvicorn

    print(f"CYBRA starting on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(
        "cybra.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
