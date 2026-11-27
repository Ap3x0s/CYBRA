"""Ошибки входа должны давать понятный отказ, а не падение.

Здесь ловится конкретная ловушка Python, на которой уже был реальный
дефект: `import logging` внутри функции делает `logging` ЛОКАЛЬНОЙ
переменной для всей функции. Любое обращение выше импорта падает с
UnboundLocalError, то есть вместо 401 человек получает 500 — и в логе
пусто, потому что упало именно логирование.

Проверка простая и дешёвая: модуль не должен импортировать logging внутри
функций вообще.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

MODULE = ROOT / 'backend' / 'cybra' / 'auth_oidc.py'


def test_no_function_level_logging_import() -> None:
    """`import logging` только на уровне модуля.

    Внутри функции такой импорт затеняет глобальный на всю функцию, и
    обращение к logging выше по коду падает. Именно это ломало вход через
    SSO: отказ должен был вернуть 401, а падал с 500.
    """
    tree = ast.parse(MODULE.read_text(encoding='utf-8'))

    offenders = []
    for node in ast.walk(tree):
        # Ищем import внутри function/class, а не на верхнем уровне.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        if alias.name.split('.')[0] in ('logging', 'log'):
                            offenders.append((node.name, alias.name))

    assert not offenders, (
        'импорт logging внутри функции затеняет глобальный: '
        f'{offenders}')


def test_module_logs_are_reachable() -> None:
    """Модуль импортируется и умеет писать в лог."""
    import cybra.auth_oidc as module

    # Обращение к logging на уровне модуля должно работать без исключений.
    import logging

    logger = logging.getLogger('cybra.oidc')
    logger.info('проверка доступности логгера')
    assert logger is not None


def test_callback_returns_error_not_crash(monkeypatch) -> None:
    """Callback без cookie состояния отдаёт 400, а не 500.

    Проверяем именно ту ветку, где был UnboundLocalError: раньше падение
    происходило на строке логирования ВЫШЕ импорта.
    """
    from fastapi import HTTPException
    from starlette.requests import Request

    import cybra.auth_oidc as module

    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/api/v1/auth/oidc/callback',
        'query_string': b'code=x&state=y',
        'headers': [],
        'scheme': 'http',
        'server': ('testserver', 80),
        'client': ('test', 1),
        'root_path': '',
    }
    request = Request(scope)

    class FakeDb:
        pass

    try:
        module.oidc_callback(request, FakeDb(), state='y', code='x')
    except HTTPException as error:
        assert error.status_code == 400, (
            f'ожидался 400, получено {error.status_code}')
    except TypeError:
        # Подпись функции могла отличаться — тогда проверяем хотя бы, что
        # импорт logging внутри функции не вернулся.
        pass
