"""Синхронизация коммитов с Jira: ключ задачи в сообщении → комментарий.

Как работает:
  1. Читает коммиты из git (по диапазону или последние N).
  2. Ищет в теме и теле ключи вида CYB-12.
  3. Для каждого ключа добавляет в задачу комментарий с хешем, веткой, автором
     и ссылкой на GitHub.
  4. Повторно не дублирует: в комментарии есть маркер `[cybra-sync:<sha>]`.

Настройка — через переменные окружения (или jira/.env, который в .gitignore):
    JIRA_BASE   https://<your-org>.atlassian.net
    JIRA_EMAIL  <your-account-email>
    JIRA_TOKEN <api token>

Использование:
    python scripts/jira_sync.py --dry-run          # показать, что будет
    python scripts/jira_sync.py                    # последние 20 коммитов
    python scripts/jira_sync.py --range HEAD~5..HEAD

Токен НЕ хранится в репозитории. Файл jira/.env уже в .gitignore.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_RE = re.compile(r'\b([A-Z][A-Z0-9]+)-(\d+)\b')
MARKER = '[cybra-sync:{sha}]'


def load_env() -> None:
    """Подхватить jira/.env, если переменные не заданы в окружении."""
    env_file = ROOT / 'jira' / '.env'
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"\'')


def jira_request(path: str, method: str = 'GET', body=None, *, fail_ok=False):
    """Запрос к Jira REST API v3."""
    base = os.environ.get('JIRA_BASE', '').rstrip('/')
    email = os.environ.get('JIRA_EMAIL', '')
    token = os.environ.get('JIRA_TOKEN', '')
    if not (base and email and token):
        raise SystemExit(
            'Не заданы JIRA_BASE / JIRA_EMAIL / JIRA_TOKEN. '
            'Положите их в jira/.env (файл в .gitignore).'
        )
    auth = base64.b64encode(f'{email}:{token}'.encode()).decode()
    headers = {'Authorization': f'Basic {auth}', 'Accept': 'application/json'}
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode('utf-8')
    request = urllib.request.Request(base + path, headers=headers,
                                     data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read(500).decode('utf-8', errors='replace')
        if fail_ok:
            return {'error': error.code, 'detail': detail}
        raise SystemExit(f'Jira {method} {path} -> {error.code}: {detail}') from error


def git(*args: str) -> str:
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8')
    if result.returncode != 0:
        raise SystemExit(f'git {" ".join(args)}: {result.stderr.strip()}')
    return result.stdout.strip()


def collect_commits(rev_range: str | None, limit: int) -> list[dict]:
    """Вернуть [{'sha','short','subject','body','author','date','branch'}]."""
    spec = [rev_range] if rev_range else ['-n', str(limit)]
    # %x00 разделяет КОММИТЫ, %x1f — поля. Одного %x1f мало: тело коммита
    # содержит переносы строк, и разбиение по ним рвало запись на части.
    raw = git('log', *spec, '--pretty=format:%H%x1f%s%x1f%b%x1f%an%x1f%aI%x00', '--')
    if not raw:
        return []
    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    commits = []
    for chunk in raw.split('\x00'):
        chunk = chunk.strip('\n')
        if not chunk.strip():
            continue
        parts = chunk.split('\x1f')
        if len(parts) < 5:
            continue
        sha, subject, body, author, date = parts[:5]
        commits.append({
            'sha': sha,
            'short': sha[:7],
            'subject': subject,
            'body': body,
            'author': author,
            'date': date,
            'branch': branch,
        })
    return commits


def already_synced(issue_key: str, sha: str) -> bool:
    """Есть ли уже комментарий для этого коммита. Проверяем по маркеру."""
    marker = MARKER.format(sha=sha[:7])
    data = jira_request(f'/rest/api/3/issue/{issue_key}/comment?maxResults=100',
                        fail_ok=True)
    if not data or 'comments' not in data:
        return False
    for comment in data['comments']:
        text = json.dumps(comment.get('body', {}), ensure_ascii=False)
        if marker in text:
            return True
    return False


def build_comment(commit: dict) -> dict:
    """Комментарий в формате Atlassian Document Format (ADF)."""
    remote = ''
    try:
        remote = git('remote', 'get-url', 'origin')
    except SystemExit:
        pass
    link = ''
    if 'github.com' in remote:
        slug = remote.rstrip('.git').split('github.com/')[-1]
        link = f'https://github.com/{slug}/commit/{commit["sha"]}'

    marker = MARKER.format(sha=commit['short'])
    content = [
        {
            'type': 'paragraph',
            'content': [
                {'type': 'text', 'text': commit['subject'],
                 'marks': [{'type': 'strong'}]},
            ],
        },
        {
            'type': 'paragraph',
            'content': [
                {'type': 'text', 'text': 'Коммит '},
                {'type': 'text', 'text': commit['short'],
                 'marks': [{'type': 'code'}]},
                {'type': 'text', 'text': f' · ветка {commit["branch"]}'
                                          f' · {commit["author"]}'},
            ],
        },
    ]
    if link:
        content.append({
            'type': 'paragraph',
            'content': [
                {'type': 'text', 'text': 'Открыть на GitHub',
                 'marks': [{'type': 'link', 'attrs': {'href': link}}]},
            ],
        })
    content.append({
        'type': 'paragraph',
        'content': [{'type': 'text', 'text': marker,
                     'marks': [{'type': 'em'}]}],
    })
    return {'body': {'type': 'doc', 'version': 1, 'content': content}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Синхронизация коммитов с Jira')
    parser.add_argument('--range', help='диапазон git, например HEAD~5..HEAD')
    parser.add_argument('--limit', type=int, default=20,
                        help='сколько последних коммитов смотреть (по умолчанию 20)')
    parser.add_argument('--dry-run', action='store_true',
                        help='показать, что будет сделано, без записи в Jira')
    parser.add_argument('--project', default='CYB',
                        help='ключ проекта для фильтрации (по умолчанию CYB)')
    args = parser.parse_args(argv)

    load_env()
    commits = collect_commits(args.range, args.limit)
    if not commits:
        print('Коммитов не найдено')
        return 0

    key_pattern = re.compile(
        rf'\b({re.escape(args.project)}-\d+)\b', re.IGNORECASE)
    planned = []
    for commit in commits:
        text = (commit['subject'] + '\n' + commit['body'])
        keys = sorted(set(k.upper() for k in key_pattern.findall(text)))
        for key in keys:
            planned.append((key, commit))

    if not planned:
        print(f'В {len(commits)} коммитах нет ссылок на {args.project}-*')
        print('Добавьте ключ в сообщение, например: CYB-35 fix nav')
        return 0

    print(f'Найдено связей: {len(planned)}')
    sent = 0
    skipped = 0
    for key, commit in planned:
        if not args.dry_run and already_synced(key, commit['sha']):
            print(f'  {key:9s} {commit["short"]} — уже синхронизирован')
            skipped += 1
            continue
        if args.dry_run:
            print(f'  {key:9s} {commit["short"]} {commit["subject"][:60]}')
            continue
        result = jira_request(f'/rest/api/3/issue/{key}/comment', method='POST',
                              body=build_comment(commit))
        if result and result.get('id'):
            print(f'  {key:9s} {commit["short"]} — комментарий добавлен')
            sent += 1
        else:
            print(f'  {key:9s} {commit["short"]} — не удалось')

    if args.dry_run:
        print('\nРежим проверки: в Jira ничего не записано')
    else:
        print(f'\nОтправлено: {sent}, пропущено как дубли: {skipped}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
