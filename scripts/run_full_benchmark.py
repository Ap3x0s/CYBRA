"""Прогон всех 8 бенчмарков с лимитом 12 на реальном движке.

Запускается через API, как это сделал бы оператор в интерфейсе: создаём
прогон, ждём финального статуса, затем разбираем файл вывода.

Датасеты передаём явно — все версии из базы, — чтобы прогон не зависел от
того, что лежит в комплекте.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get('CYBRA_BASE', 'http://127.0.0.1:8000')
EMAIL = os.environ.get('CYBRA_EMAIL', 'admin@cybra.local')
PASSWORD = os.environ.get('CYBRA_PASSWORD', '')
if not PASSWORD:
    raise SystemExit('Задайте пароль: $env:CYBRA_PASSWORD = "..."')

ALL_TOOLS = ['harmbench', 'jailbreakbench', 'bipia', 'security-regression',
             'promptfoo', 'garak', 'pyrit', 'agentdojo']
LIMIT = 12


def main() -> int:
    login = urllib.request.Request(
        BASE + '/api/v1/auth/login',
        data=json.dumps({'email': EMAIL, 'password': PASSWORD}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(login, timeout=30) as response:
        cookie = (response.headers.get('Set-Cookie') or '').split(';')[0]

    def call(path: str, payload: dict | None = None, token: str = ''):
        headers = {'Cookie': cookie, 'Content-Type': 'application/json'}
        if token:
            headers['x-csrf-token'] = token
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(BASE + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            print('HTTP', error.code, error.read(600).decode(errors='replace'))
            return {}

    me = call('/api/v1/auth/me')
    csrf = me.get('csrf_token', '')

    targets = call('/api/v1/targets')
    # Берём модель Command Code: её endpoint внешний, и адрес лежит в
    # chat_url, а не в base_url. Первая проверка по base_url (localhost:4000)
    # давала ложный вывод «недоступен»: локальный порт не слушается, но
    # реальный запрос уходит на api.commandcode.ai.
    real = [t for t in targets
            if t['model_id'] == 'deepseek/deepseek-v4.1-flash']
    if not real:
        real = [t for t in targets if 'demo' not in t['model_id']]
    if not real:
        print('нет настоящей модели, только демо')
        return 2
    target = real[0]
    print('модель  :', target['model_id'], '|', target.get('endpoint_name'))

    datasets = call('/api/v1/datasets')
    versions = [d['id'] for d in datasets]
    print('датасеты:', len(versions), 'версий')

    payload = {
        'label': f'Полный прогон, лимит {LIMIT}',
        'target_ids': [target['id']],
        'judge_target_id': target['id'],
        'tools': ALL_TOOLS,
        'dataset_version_ids': versions,
        'engine_mode': 'subprocess',
        'limit': LIMIT,
        'seed': 42,
        'max_requests': 3000,
        'judge_verdict': True,
        'judge_verdict_prompt': '',
    }
    created = call('/api/v1/runs', payload, csrf)
    if not created.get('id'):
        print('прогон не создан')
        return 1
    run = created
    print('прогон  :', run['id'], run['run_id'])
    print('статус  :', run['status'])

    last = ''
    for _ in range(480):
        time.sleep(15)
        state = call(f"/api/v1/runs/{run['id']}")
        status = state.get('status', '')
        steps = len(state.get('steps') or [])
        if status != last or steps:
            print(f'  {time.strftime("%H:%M:%S")} {status:10} шагов={steps}', flush=True)
            last = status
        if status in ('COMPLETE', 'PARTIAL', 'ERROR', 'CANCELLED'):
            break

    state = call(f"/api/v1/runs/{run['id']}")
    print()
    print('итог   :', state.get('status'))
    print('ошибка :', state.get('error') or '—')
    for step in state.get('steps') or []:
        counts = step.get('counts') or {}
        print(f"  {step['tool']:20} {step['completeness']:9} "
              f"PASS={counts.get('PASS', 0):3} FAIL={counts.get('FAIL', 0):3} "
              f"ERROR={counts.get('ERROR', 0):3} UNSCORED={counts.get('UNSCORED', 0):3}")
    print()
    print('RUN_ID=' + str(run['id']))
    print('OUT_DIR=' + str(state.get('out_dir') or ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
