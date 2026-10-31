"""Seed a demo stand: one endpoint, two models, one mock run.

Used to show the console without a real model server. Everything it creates is
marked as demo in the labels.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8000/api/v1'
COOKIE = ''


def call(method, path, payload=None, csrf=''):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type': 'application/json'}
    if csrf:
        headers['x-csrf-token'] = csrf
    if COOKIE:
        headers['Cookie'] = COOKIE
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raise SystemExit(f'{method} {path}: HTTP {error.code} {error.read(800).decode()}')


def main():
    global COOKIE
    email = sys.argv[1] if len(sys.argv) > 1 else 'admin@cybra.local'
    password = sys.argv[2] if len(sys.argv) > 2 else ''

    cookie_jar = {}
    login_request = urllib.request.Request(
        BASE + '/auth/login',
        data=json.dumps({'email': email, 'password': password}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(login_request, timeout=30) as response:
        for header, value in response.getheaders():
            if header.lower() == 'set-cookie':
                cookie_jar[value.split('=', 1)[0]] = value.split(';', 1)[0].split('=', 1)[1]
        body = json.loads(response.read().decode())
    COOKIE = '; '.join(f'{k}={v}' for k, v in cookie_jar.items())
    csrf = body['csrf_token']
    print('logged in as', body['email'])

    endpoint = call('POST', '/endpoints', {
        'name': 'Mock LiteLLM',
        'base_url': 'http://127.0.0.1:8765/v1',
        'api_key': 'sk-demo-not-a-real-key',
        'notes': 'Демо-стенд для показа интерфейса',
    }, csrf)
    print('endpoint', endpoint['id'], endpoint['name'])

    targets = []
    for model_id, label in (('gpt-4o-demo', 'Demo GPT'), ('qwen-demo', 'Demo Qwen')):
        target = call('POST', '/targets', {
            'endpoint_id': endpoint['id'],
            'model_id': model_id,
            'label': label,
            'group_name': 'prod',
        }, csrf)
        targets.append(target['id'])
        print('target', target['id'], label)

    versions = call('GET', '/datasets')
    corporate = [v for v in versions if v['name'] == 'corporate'][0]

    run = call('POST', '/runs', {
        'label': 'Квартальная проверка пула',
        'target_ids': targets,
        'judge_target_id': targets[0],
        'tools': ['harmbench', 'jailbreakbench', 'security-regression'],
        'dataset_version_ids': [corporate['id']],
        'engine_mode': 'mock',
        'limit': 8,
        'seed': 42,
    }, csrf)
    run_id = run['id']
    print('run', run_id, run['status'])

    for _ in range(180):
        current = call('GET', f'/runs/{run_id}')
        if current['status'] not in ('PENDING', 'RUNNING'):
            break
        time.sleep(0.5)
    final = call('GET', f'/runs/{run_id}')
    print('final status:', final['status'], '| steps:', len(final['steps']))
    for step in final['steps']:
        counts = step['counts']
        print(f"  {step['model_label']:>12} {step['tool']:<22} PASS={counts.get('PASS',0)} FAIL={counts.get('FAIL',0)}")

    # A second, older-looking run so the trend chart has two points.
    run2 = call('POST', '/runs', {
        'label': 'Повторная проверка после фикса',
        'target_ids': targets[:1],
        'judge_target_id': targets[0],
        'tools': ['harmbench', 'security-regression'],
        'engine_mode': 'mock',
        'limit': 6,
        'seed': 7,
    }, csrf)
    for _ in range(180):
        current = call('GET', f"/runs/{run2['id']}")
        if current['status'] not in ('PENDING', 'RUNNING'):
            break
        time.sleep(0.5)
    print('second run:', call('GET', f"/runs/{run2['id']}")['status'])
    print('DEMO READY')


if __name__ == '__main__':
    main()
