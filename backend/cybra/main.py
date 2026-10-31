"""FastAPI application factory.

The SPA is served by the same process: one container, one port, no CORS puzzle
in production. During development Vite proxies /api to this server.
"""
from __future__ import annotations

import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .api import router
from .config import settings
from .db import SessionLocal, init_db
from .models import User
from .security import hash_password

STATIC_DIR = Path(__file__).resolve().parents[1] / 'static'


def bootstrap_admin() -> None:
    """Create the first admin and print the one-time password.

    Printing to stdout is deliberate: it is the only channel an operator has on
    a fresh install, and it is visible only to whoever started the process.
    """
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.role == 'admin')) is not None:
            # Self-heal: seed datasets once an admin exists.
            _seed_datasets(db)
            return
        password = secrets.token_urlsafe(12)
        admin = User(
            email='admin@cybra.local',
            display_name='Администратор',
            password_hash=hash_password(password),
            role='admin',
        )
        db.add(admin)
        db.commit()
        banner = (
            '\n' + '=' * 64 + '\n'
            '  CYBRA: создан администратор\n'
            '  email:    admin@cybra.local\n'
            f'  пароль:   {password}\n'
            '  Смените пароль после первого входа.\n'
            + '=' * 64 + '\n'
        )
        print(banner, flush=True)
        _seed_datasets(db)
    finally:
        db.close()


def _seed_datasets(db) -> None:
    """Import the bundled datasets the first time the app starts."""
    from sqlalchemy import func

    from . import datasets as dataset_service
    from .models import DatasetVersion

    if db.scalar(select(func.count()).select_from(DatasetVersion)):
        return
    admin = db.scalar(select(User).where(User.role == 'admin'))
    datasets_dir = settings.root / 'datasets'
    for name in dataset_service.BUILTIN_SOURCES:
        try:
            dataset_service.import_builtin(
                db, datasets_dir, name, created_by=admin.id if admin else None)
        except Exception as error:  # noqa: BLE001 - a missing file must not block start
            print(f'  ! dataset {name} skipped: {error}', file=sys.stderr, flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    bootstrap_admin()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title='CYBRA', version='0.1.0', lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # noqa: ANN001
        # Never leak a traceback to the browser; keep it in the server log.
        import traceback
        traceback.print_exc()
        return JSONResponse({'detail': 'Внутренняя ошибка сервера'}, status_code=500)

    if STATIC_DIR.exists():
        assets = STATIC_DIR / 'assets'
        if assets.exists():
            app.mount('/assets', StaticFiles(directory=assets), name='assets')

        @app.get('/{full_path:path}', include_in_schema=False)
        async def spa(full_path: str):
            candidate = STATIC_DIR / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            index = STATIC_DIR / 'index.html'
            if not index.exists():
                return JSONResponse(
                    {'detail': 'UI не собран. Выполните: cd frontend && npm run build'},
                    status_code=503)
            return FileResponse(index)

    return app


app = create_app()
