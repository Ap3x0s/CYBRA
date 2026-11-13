"""Полноценный прогон на всех 8 бенчмарках, лимит 8 кейсов.

Запускается через API, как это делает интерфейс: создание прогона, ожидание,
импорт результатов. По завершении печатает сводку по шагам и метрикам.

Ключевое отличие от прошлого теста: здесь все восемь инструментов, включая
четыре только что исправленных (garak, PyRIT, AgentDojo, Promptfoo).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8000'
EMAIL = 'admin@cybra.local'
PASSWORD = '__CYBRA_PASSWORD__'

import os
TOOLS = os.environ.get('CYBRA_TOOLS','harmbench,jailbreakbench,bipia,security-regression,promptfoo,garak,pyrit,agentdojo').split(',')
LIMIT = int(os.environ.get('CYBRA_LIMIT','8'))
VARIANTS = os.environ.get('CYBRA_VARIANTS','direct,roleplay,authority').split(',')
LABEL = os.environ.get('CYBRA_LABEL', '')


class Client:
    def __init__(self):
        self.cookies = {}
        self.csrf = ''

    def _hdr(self):
        return '; '.join(f'{k}={v}' for k, v in self.cookies.items())

    def _absorb(self, r):
        for raw in r.headers.get_all('Set-Cookie') or []:
            pair = raw.split(';')[0]
            if '=' in pair:
                k, v = pair.split('=', 1)
                self.cookies[k.strip()] = v.strip()

    def call(self, path, data=None, method=None, timeout=120):
        headers = {'Content-Type': 'application/json'}
        if self.cookies:
            headers['Cookie'] = self._hdr()
        verb = method or ('POST' if data is not None else 'GET')
        if self.csrf and verb in ('POST', 'PUT', 'DELETE'):
            headers['x-csrf-token'] = self.csrf
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers, method=verb)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                self._absorb(r)
                body = r.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'{verb} {path} -> {e.code}: '
                               f'{e.read(400).decode(errors="replace")}') from e

    def login(self):
        self.call('/api/v1/auth/login', {'email': EMAIL, 'password': PASSWORD})
        me = self.call('/api/v1/auth/me')
        self.csrf = me.get('csrf_token', '')
        return me


def main() -> int:
    c = Client()
    me = c.login()
    print(f'вошли: {me.get("email")}', flush=True)

    targets = c.call('/api/v1/targets')
    real = [t for t in targets if 'demo' not in t['model_id'].lower()]
    if not real:
        print('нет реальной модели')
        return 1
    chosen = real[0]
    print(f"модель: {chosen['label'] or chosen['model_id']} "
          f"-> {chosen['endpoint_name']}", flush=True)
    print(f'инструменты ({len(TOOLS)}): {", ".join(TOOLS)}', flush=True)
    print(f'варианты обёрток ({len(VARIANTS)}): {", ".join(VARIANTS)}', flush=True)

    spec = {
        'label': LABEL or f'бенчмарков {len(TOOLS)}, лимит {LIMIT}',
        'target_ids': [chosen['id']],
        'judge_target_id': chosen['id'],
        'tools': TOOLS,
        'dataset_version_ids': [],
        'engine_mode': 'subprocess',
        'limit': LIMIT,
        'seed': 42,
        'max_requests': 5000,
        # Обёртки обязательны для resilience_gap: метрика сравнивает
        # безопасность на прямых запросах и под атакой.
        'variants': VARIANTS,
        'timeout': 180,
        'tool_timeout': 7200,
    }
    run = c.call('/api/v1/runs', spec)
    print(f"\nзапущен #{run['id']} {run['run_id']}", flush=True)

    started = time.monotonic()
    last = ''
    while True:
        time.sleep(15)
        cur = c.call(f"/api/v1/runs/{run['id']}")
        try:
            prog = c.call(f"/api/v1/runs/{run['id']}/progress")
        except Exception:                              # noqa: BLE001
            prog = {}
        elapsed = int(time.monotonic() - started)
        done = len(prog.get('finished_steps') or [])
        line = (f"[{elapsed // 60:3d}m{elapsed % 60:02d}s] {cur['status']:9s} "
                f"готово {done}/8 · {prog.get('current_model') or ''}/"
                f"{prog.get('current_tool') or ''} · "
                f"requests={prog.get('requests')}")
        if line != last:
            print(line, flush=True)
            last = line
        if cur['status'] in ('COMPLETE', 'PARTIAL', 'ERROR', 'CANCELLED'):
            break
        if elapsed > 10800:
            print('  3 часа — прекращаем опрос, прогон продолжается', flush=True)
            break

    fin = c.call(f"/api/v1/runs/{run['id']}")
    print('\n=== ИТОГ ===')
    print(f"  status           : {fin['status']}")
    print(f"  duration_seconds : {fin.get('duration_seconds')}")
    print(f"  error            : {fin.get('error')!r}")
    steps = fin.get('steps') or []
    print(f'  шагов в БД       : {len(steps)}')
    print()
    print(f"{'инструмент':22s} {'полнота':10s} {'PASS':>5s} {'FAIL':>5s} "
          f"{'ERROR':>6s} {'UNSC':>5s} {'SKIP':>5s}")
    for st in steps:
        cnt = st.get('counts') or {}
        print(f"{st['tool']:22s} {st['completeness']:10s} "
              f"{cnt.get('PASS', 0):>5d} {cnt.get('FAIL', 0):>5d} "
              f"{cnt.get('ERROR', 0):>6d} {cnt.get('UNSCORED', 0):>5d} "
              f"{cnt.get('SKIPPED', 0):>5d}")
        if st.get('error'):
            print(f"    ошибка: {str(st['error'])[:150]}")

    # Метрики по шагам
    print('\n=== МЕТРИКИ ===')
    metrics = ['attack_success_rate', 'failed_check_rate', 'refusal_rate',
               'benign_utility_rate', 'injection_follow_rate', 'leak_rate',
               'unscored_rate', 'coverage']
    for mid in metrics:
        try:
            rows = c.call(f'/api/v1/metrics/series?metric={mid}&limit=40')
        except Exception as exc:                       # noqa: BLE001
            print(f'  {mid}: ошибка {exc}')
            continue
        mine = [r for r in (rows or []) if r['run_pk'] == run['id']]
        by_tool = {r['tool']: round(r['value'], 3) for r in mine}
        print(f"  {mid:22s} {by_tool if by_tool else 'нет данных'}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
