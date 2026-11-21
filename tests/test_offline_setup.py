"""Офлайн-установка: подмена git-ссылок на локальные архивы.

Проверяем то, что нельзя проверить сборкой bundle: установщик действительно
берёт архив из bundle, а не идёт клонировать репозиторий.

Без этой подмены `cybra setup` на сервере без интернета падал бы на
клонировании, хотя архив лежит рядом — и `--no-index` тут не помогает:
он ограничивает поиск на индексе, но не обработку git-ссылок.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from security_suite.setup_tools import _local_source_archives, _rewrite_git_args


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    """Минимальный bundle: только каталог sources с архивами."""
    sources = tmp_path / 'sources'
    sources.mkdir()
    (sources / 'garak-93aa9cdec309.tar.gz').write_bytes(b'garak')
    (sources / 'pyrit-c0bcdcadba34.tar.gz').write_bytes(b'pyrit')
    (sources / 'agentdojo-089ed468cf3e.tar.gz').write_bytes(b'agentdojo')
    return tmp_path


def test_archives_found_by_tool_name(bundle: Path) -> None:
    found = _local_source_archives(bundle)
    assert set(found) == {'garak', 'pyrit', 'agentdojo'}
    assert found['garak'].name.startswith('garak-')


def test_missing_sources_dir_returns_empty(tmp_path: Path) -> None:
    # Каталога нет — карта пустая, вызывающая сторона предупредит.
    assert _local_source_archives(tmp_path) == {}


def test_git_line_replaced_with_archive(bundle: Path) -> None:
    lock = bundle / 'garak.txt'
    lock.write_text(
        'accelerate==1.15.0\n'
        'garak @ git+https://github.com/NVIDIA/garak.git@93aa9cdec\n'
        'torch==2.14.0+cpu\n',
        encoding='utf-8',
    )

    args = _rewrite_git_args(['-r', str(lock)], lock, _local_source_archives(bundle))
    rewritten = Path(args[1]).read_text(encoding='utf-8')

    assert 'git+https' not in rewritten, 'git-ссылка осталась — установка пойдёт в сеть'
    assert 'garak-93aa9cdec309.tar.gz' in rewritten
    # Обычные пакеты не должны пострадать при подмене.
    assert 'accelerate==1.15.0' in rewritten
    assert 'torch==2.14.0+cpu' in rewritten


def test_no_archive_leaves_line_untouched(bundle: Path) -> None:
    """Без архива файл не трогаем: пусть упадёт честно.

    Молча пропустить инструмент хуже, чем упасть: установка выглядела бы
    успешной, а бенчмарк не запустился бы.
    """
    lock = bundle / 'unknown.txt'
    lock.write_text(
        'unknown @ git+https://github.com/example/unknown.git@abc123\n',
        encoding='utf-8',
    )

    args = _rewrite_git_args(['-r', str(lock)], lock, _local_source_archives(bundle))
    assert args == ['-r', str(lock)]


def test_missing_lock_returns_args_as_is(bundle: Path) -> None:
    """Для инструментов без lock (bipia) аргументы не меняются."""
    missing = bundle / 'nope.txt'
    args = ['pandas>=2.2,<4']
    assert _rewrite_git_args(args, missing, _local_source_archives(bundle)) == args
