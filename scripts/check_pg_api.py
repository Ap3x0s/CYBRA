"""Проверить, что приложение на PostgreSQL отдаёт перенесённые данные."""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit('Задайте пароль: $env:CYBRA_PASSWORD = "..."')


def main() -> int:
    request = urllib.request.Request(
        BASE + '/api/v1/auth/login',
        data=json.dumps({'email': EMAIL, 'password': PASSWORD}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        cookie = (response.headers.get('Set-Cookie') or '').split(';')[0]
    print('вход выполнен')

    def get(path: str):
        req = urllib.request.Request(BASE + path, headers={'Cookie': cookie})
        with urllib.request.urlopen(req, timeout=40) as response:
            return json.load(response)

    runs = get('/api/v1/runs?limit=100')
    print('прогонов через API :', len(runs))

    datasets = get('/api/v1/datasets')
    cases = sum(d.get('case_count', 0) for d in datasets)
    print('версий датасетов   :', len(datasets))
    print('кейсов всего       :', cases)

    targets = get('/api/v1/targets')
    print('моделей            :', len(targets))

    with_verdict = [r for r in runs if r.get('verdicts')]
    print('прогонов с вердиктом:', len(with_verdict))
    if with_verdict:
        sample = with_verdict[0]
        entries = sample['verdicts']
        first = next(iter(entries.values()))
        print(f"  {sample['run_id']}: {first['verdict']} "
              f"({type(entries).__name__})")

    steps = sum(len(r.get('steps') or []) for r in runs)
    print('шагов всего        :', steps)
    return 0


if __name__ == '__main__':
    sys.exit(main())
