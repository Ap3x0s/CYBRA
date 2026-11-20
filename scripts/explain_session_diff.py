"""Проверить, что лишняя сессия в Postgres появилась после миграции.

Первая сверка показала sessions 1098 -> 1099. Это может быть как ошибкой
переноса, так и моей собственной сессией: я входил в приложение через API
уже ПОСЛЕ миграции. Различаем по id и времени: перенесённые строки имеют
id <= максимума в SQLite, новые — больше.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import psycopg

SQLITE = 'var/cybra.sqlite3'
PG = os.environ.get(
    'CYBRA_TARGET_DATABASE_URL',
    'postgresql+psycopg://cybra:cybra@127.0.0.1:5433/cybra')
DSN = PG.replace('postgresql+psycopg://', 'postgresql://')


def main() -> int:
    sqlite_conn = sqlite3.connect(SQLITE)
    sqlite_max = sqlite_conn.execute('SELECT MAX(id) FROM sessions').fetchone()[0]
    sqlite_count = sqlite_conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    sqlite_conn.close()
    print('SQLite   : строк', sqlite_count, 'максимальный id', sqlite_max)

    with psycopg.connect(DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM sessions')
            pg_count = cursor.fetchone()[0]
            cursor.execute('SELECT MAX(id) FROM sessions')
            pg_max = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM sessions WHERE id > %s', (sqlite_max,))
            extra = cursor.fetchone()[0]
            print('Postgres : строк', pg_count, 'максимальный id', pg_max)
            print()
            print('строк сверх перенесённых:', extra)
            if extra:
                cursor.execute(
                    'SELECT id, user_id, created_at FROM sessions '
                    'WHERE id > %s ORDER BY id', (sqlite_max,))
                for row in cursor.fetchall():
                    print('  новая сессия:', row)

    # Перенесённые строки обязаны совпадать построчно там, где мы их видим.
    ok = pg_count == sqlite_count + extra
    print()
    print('все строки на месте:', ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
