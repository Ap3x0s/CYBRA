"""Показать состояние текущего прогона: статус, шаги, прогресс."""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit('Задайте пароль: $env:CYBRA_PASSWORD = "..."')


def login() -> str:
    request = urllib.request.Request(
        BASE + '/api/v1/auth/login',
        data=json.dumps({'email': 'admin@cybra.local',
                         'password': PASSWORD}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return (response.headers.get('Set-Cookie') or '').split(';')[0]


def get(path: str, cookie: str):
    request = urllib.request.Request(BASE + path,
                                     headers={'Cookie': cookie})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> int:
    cookie = login()
    runs = get('/api/v1/runs?limit=3', cookie)
    for run in runs[:2]:
        steps = run.get('steps') or []
        print(f"прогон {run['id']} {run['run_id']} {run['status']} "
              f"шагов={len(steps)}")
        for step in steps:
            counts = step.get('counts') or {}
            print(f"   {step['tool']:20} {step['completeness']:9} "
                  f"P={counts.get('PASS', 0)} F={counts.get('FAIL', 0)} "
                  f"E={counts.get('ERROR', 0)}")
        try:
            progress = get(f"/api/v1/runs/{run['id']}/progress", cookie)
            print('   прогресс:', json.dumps(progress, ensure_ascii=False)[:220])
        except Exception as error:  # noqa: BLE001
            print('   прогресс недоступен:', error)
    return 0


if __name__ == '__main__':
    sys.exit(main())
