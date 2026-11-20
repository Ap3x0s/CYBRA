"""Что реально происходит в пайплайнах GitLab: статусы job'ов и причины падений.

Зачем отдельный скрипт: `check_ci.py` показывает только итог пайплайна
(«success»/«failed»). Из него не видно, ЧТО именно упало и на какой строке —
а пайплайн может быть красным не из-за кода, а из-за раннера.

Печатает по каждому job'у: стадию, статус, длительность. Для упавших
подтягивает хвост лога, чтобы причина была видна сразу.

Запуск:  python scripts/check_gitlab_jobs.py [sha]

Пуши в default branch пайплайн не запускают (правило when: never), поэтому
для проверки конкретного коммита его надо запустить через API — скрипт
подсказывает, если для коммита прогона нет.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = urllib.parse.quote('Ap3x0/cybra', safe='')


def token() -> str:
    url = subprocess.run(['git', 'remote', 'get-url', 'gitlab'],
                         cwd=ROOT, capture_output=True, text=True).stdout
    match = re.search(r'glpat-[^@]+', url)
    if not match:
        raise SystemExit('в remote gitlab нет токена glpat-…')
    return match.group(0)


def api(path: str, raw: bool = False):
    request = urllib.request.Request(
        f'https://gitlab.com/api/v4/projects/{PROJECT}{path}',
        headers={'PRIVATE-TOKEN': token()})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(f'GitLab API {path}: {error.code} {error.reason}') from error
    return body.decode(errors='replace') if raw else json.loads(body)


def main() -> int:
    sha = sys.argv[1] if len(sys.argv) > 1 else subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT,
        capture_output=True, text=True).stdout.strip()
    print(f'коммит: {sha[:7]}')

    pipelines = api(f'/pipelines?sha={sha}')
    if not pipelines:
        print('пайплайна на этот коммит нет.')
        print('push в default branch его не создаёт (правило when: never).')
        print('запуск через API: POST /projects/:id/pipeline?ref=main')
        return 1

    pipeline = pipelines[0]
    print(f"пайплайн #{pipeline['id']}: {pipeline['status']} "
          f"({pipeline['ref']}, {pipeline['created_at']})")
    print()

    jobs = api(f"/pipelines/{pipeline['id']}/jobs?per_page=100")
    ok = skipped = failed = 0
    for job in sorted(jobs, key=lambda item: item['id']):
        status = job['status']
        duration = job.get('duration')
        took = f"{duration:6.1f}s" if duration else "     —"
        print(f"  {job['stage']:14} {job['name']:24} {status:10} {took}")
        if status == 'success':
            ok += 1
        elif status in {'skipped', 'manual', 'canceled'}:
            skipped += 1
        elif status in {'failed', 'canceled'}:
            failed += 1
            trace = api(f"/jobs/{job['id']}/trace", raw=True)
            tail = [line for line in trace.splitlines() if line.strip()][-15:]
            print('    --- хвост лога ---')
            for line in tail:
                print(f'    {line}')

    print()
    print(f'итого: успешно {ok}, пропущено/вручную {skipped}, упало {failed}')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
