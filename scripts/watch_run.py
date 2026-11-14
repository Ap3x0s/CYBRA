# -*- coding: utf-8 -*-
"""Монитор длинного прогона: ждёт завершения и печатает итог.

Скрипт run_all8.py прекращает опрос через 3 часа, но сам прогон продолжается
на сервере. Этот монитор не ограничен по времени: он проверяет статус, пока
прогон не завершится, и только потом печатает результаты.

Использование:
    python scripts/watch_run.py            # ждать последний прогон
    python scripts/watch_run.py --id 17    # ждать конкретный
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:8000'
EMAIL = 'admin@cybra.local'
PASSWORD = '__CYBRA_PASSWORD__'


class Client:
    def __init__(self):
        self.cookies = {}
        self.csrf = ''

    def _headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.cookies:
            headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        if self.csrf:
            headers['x-csrf-token'] = self.csrf
        return headers

    def _absorb(self, response):
        for raw in response.headers.get_all('Set-Cookie') or []:
            pair = raw.split(';')[0]
            if '=' in pair:
                key, value = pair.split('=', 1)
                self.cookies[key.strip()] = value.strip()

    def call(self, path, data=None, method=None, timeout=180):
        verb = method or ('POST' if data is not None else 'GET')
        request = urllib.request.Request(
            BASE + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=self._headers(), method=verb)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            self._absorb(response)
            body = response.read()
            return json.loads(body) if body else None

    def login(self):
        self.call('/api/v1/auth/login', {'email': EMAIL, 'password': PASSWORD})
        me = self.call('/api/v1/auth/me')
        self.csrf = me.get('csrf_token', '')


def server_alive() -> bool:
    try:
        with socket.create_connection(('127.0.0.1', 8000), timeout=3):
            return True
    except OSError:
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=int, default=None, help='id прогона')
    parser.add_argument('--interval', type=int, default=120,
                        help='интервал опроса, сек')
    args = parser.parse_args(argv)

    client = Client()
    client.login()

    runs = client.call('/api/v1/runs?limit=10')
    if args.id:
        target = next((r for r in runs if r['id'] == args.id), None)
    else:
        target = runs[0] if runs else None
    if target is None:
        print('Прогон не найден')
        return 1

    run_id = target['id']
    print(f'Слежу за прогоном #{run_id}: {target["label"]}', flush=True)

    started = time.monotonic()
    last_line = ''
    while True:
        if not server_alive():
            print('Сервер недоступен — ждём', flush=True)
            time.sleep(args.interval)
            continue
        try:
            current = client.call(f'/api/v1/runs/{run_id}')
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
            print(f'  ошибка опроса: {type(error).__name__}', flush=True)
            time.sleep(args.interval)
            continue

        status = current['status']
        elapsed = int(time.monotonic() - started)
        steps = current.get('steps') or []
        line = (f'[{elapsed // 3600}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}] '
                f'{status} шагов={len(steps)}')
        if line != last_line:
            print(line, flush=True)
            last_line = line

        if status in ('COMPLETE', 'PARTIAL', 'ERROR', 'CANCELLED'):
            break
        time.sleep(args.interval)

    # --- Итог -----------------------------------------------------------
    final = client.call(f'/api/v1/runs/{run_id}')
    print()
    print('=== ИТОГ ===')
    print(f"  статус      : {final['status']}")
    print(f"  длительность: {final.get('duration_seconds')}")
    print(f"  ошибка      : {final.get('error')!r}")
    steps = final.get('steps') or []
    print()
    print(f"{'инструмент':22s} {'полнота':10s} {'PASS':>5s} {'FAIL':>5s} "
          f"{'ERROR':>6s} {'UNSC':>5s} {'SKIP':>5s}")
    for step in steps:
        counts = step.get('counts') or {}
        print(f"{step['tool']:22s} {step['completeness']:10s} "
              f"{counts.get('PASS', 0):>5d} {counts.get('FAIL', 0):>5d} "
              f"{counts.get('ERROR', 0):>6d} {counts.get('UNSCORED', 0):>5d} "
              f"{counts.get('SKIPPED', 0):>5d}")

    print()
    print('=== МЕТРИКИ ===')
    for metric in ('resilience_gap', 'utility_under_attack',
                   'agent_false_block_rate', 'attack_success_rate',
                   'failed_check_rate', 'benign_utility_rate', 'coverage'):
        rows = client.call(
            f'/api/v1/metrics/series?metric={metric}&limit=100') or []
        mine = [r for r in rows if r['run_pk'] == run_id]
        by_tool = {r['tool']: round(r['value'], 4) for r in mine}
        print(f'  {metric:24s} {by_tool if by_tool else "нет данных"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
