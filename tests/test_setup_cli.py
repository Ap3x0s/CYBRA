"""Разбор `cybra setup`: синтаксис команды установки инструментов.

Проверяем то, что было сломано: документация, подсказки в UI и
capabilities.py обещали `cybra setup --tools garak`, а argparse эту форму
не принимал — «unrecognized arguments». Подсказка в интерфейсе вела в
ошибку, до всякой сети.

Теперь поддерживаются обе формы, и они должны давать одинаковый результат.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))

import cybra.__main__ as cli  # noqa: E402
import security_suite.setup_tools as setup_tools  # noqa: E402


@pytest.fixture()
def captured(monkeypatch) -> list[list[str]]:
    """Перехватить вызов установки, не запуская её."""
    calls: list[list[str]] = []

    def fake_setup(tools):
        calls.append(list(tools))
        return {}

    monkeypatch.setattr(setup_tools, 'setup', fake_setup)
    return calls


def test_tools_flag_parsed(captured: list[list[str]]) -> None:
    """Форма из документации: cybra setup --tools garak pyrit."""
    assert cli._setup(['setup', '--tools', 'garak', 'pyrit']) == 0
    assert captured == [['garak', 'pyrit']]


def test_positional_form_still_works(captured: list[list[str]]) -> None:
    """Прежняя форма без флага не должна сломаться."""
    assert cli._setup(['setup', 'garak', 'pyrit']) == 0
    assert captured == [['garak', 'pyrit']]


def test_both_forms_equivalent(captured: list[list[str]]) -> None:
    """Ради этого всё и делалось: обе формы — один результат."""
    cli._setup(['setup', '--tools', 'garak'])
    cli._setup(['setup', 'garak'])
    assert captured[0] == captured[1] == ['garak']


def test_no_arguments_installs_everything(captured: list[list[str]]) -> None:
    """`cybra setup` без имён ставит все четыре тяжёлых инструмента."""
    assert cli._setup(['setup']) == 0
    assert captured == [['garak', 'pyrit', 'agentdojo', 'promptfoo']]


def test_short_flag_alias(captured: list[list[str]]) -> None:
    assert cli._setup(['setup', '-t', 'garak']) == 0
    assert captured == [['garak']]


def test_unknown_tool_rejected(captured: list[list[str]]) -> None:
    """Опечатка должна ловиться, а не превращаться в «всё установлено».

    `setup()` пропускает неизвестные имена молча, поэтому проверка нужна в
    CLI: иначе `cybra setup garakk` бодро рапортует успех, ничего не поставив.
    """
    assert cli._setup(['setup', '--tools', 'garakk']) == 2
    assert captured == []


def test_known_tools_include_all_installable(captured: list[list[str]]) -> None:
    assert {'garak', 'pyrit', 'agentdojo', 'promptfoo', 'bipia'} == setup_tools.KNOWN_TOOLS


def test_help_returns_zero(capsys) -> None:
    """`cybra setup --help` не должен считаться неизвестным флагом."""
    assert cli._setup(['setup', '--help']) == 0
    out = capsys.readouterr().out
    # В справке должны быть и обе формы, и офлайн-режим: это то, что
    # администратор ищет в первую очередь.
    assert '--tools' in out
    assert 'CYBRA_OFFLINE_DIR' in out
