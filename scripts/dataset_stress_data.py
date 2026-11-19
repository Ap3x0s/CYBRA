"""Временные версии датасетов для проверки прокрутки: добавить или убрать."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'var' / 'cybra.sqlite3'
PREFIX = 'zz-stress'


def add(count: int) -> int:
    connection = sqlite3.connect(DB)
    try:
        have = connection.execute(
            'SELECT COUNT(*) FROM dataset_versions WHERE name LIKE ?',
            (f'{PREFIX}%',)).fetchone()[0]
        for index in range(have, count):
            connection.execute(
                "INSERT INTO dataset_versions "
                "(name, version, description, origin, sha256, changelog, created_at) "
                "VALUES (?, ?, '', 'ui', '', 'stress', datetime('now'))",
                (f'{PREFIX}-{index:03d}', 'v0.0.1'))
        connection.commit()
        return connection.execute(
            'SELECT COUNT(*) FROM dataset_versions').fetchone()[0]
    finally:
        connection.close()


def remove() -> int:
    connection = sqlite3.connect(DB)
    try:
        connection.execute('DELETE FROM dataset_versions WHERE name LIKE ?',
                           (f'{PREFIX}%',))
        connection.commit()
        return connection.execute(
            'SELECT COUNT(*) FROM dataset_versions').fetchone()[0]
    finally:
        connection.close()


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'add'
    if action == 'add':
        print('всего версий:', add(int(sys.argv[2]) if len(sys.argv) > 2 else 45))
    else:
        print('осталось версий:', remove())
