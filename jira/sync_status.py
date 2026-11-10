"""Sync issue status across Jira and GitHub after the MVP milestone.

Marks the delivered scope as done in both trackers. Credentials come from the
environment, as in the import scripts.

Usage:
    python sync_status.py --dry-run
    python sync_status.py
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

# Stories completed by the MVP commit. Keys are Jira-style summaries, which both
# importers used verbatim, so one list drives both trackers.
DONE = [
    'EngineBackend: subprocess-супервизор',
    'Живой прогресс прогона',
    'Отмена прогона',
    'Проверка доступности инструментов (capabilities)',
    'Мок-бэкенд движка для демо и тестов',
    'Модель данных и миграции',
    'Авторизация и роли',
    'CRUD эндпоинтов и моделей',
    'Создание и ведение прогонов',
    'Импорт результатов в нормализованные таблицы',
    'Отчёты и экспорт',
    'Метрики и агрегаты для графиков',
    'Реестр версий датасетов',
    'Импорт датасета конфигурацией',
    'UI-редактор кейсов',
    'Diff и откат версий',
    'Дизайн-система и каркас приложения',
    'Экран входа и управление пользователями',
    'Мастер создания прогона',
    'Экран прогона с живым прогрессом',
    'Детальный отчёт прогона',
    'Дашборд и графики',
    'Экран датасетов',
    'Фон-поле и коробочный дизайн по референсу',
    'Docker-образ на один контейнер',
    'Compose production-профиль',
    'CI: тесты, линт, сборка',
    'Документация и демо-данные',
]

# Deliberately not done: packaged exe. The design puts it after the docker path.
TODO = ['Сборка exe и проверка окружения']


def jira_auth() -> str:
    pair = f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_TOKEN']}"
    return base64.b64encode(pair.encode()).decode()


def jira_call(method, path, payload=None, auth=None):
    base = os.environ['JIRA_BASE'].rstrip('/')
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Authorization': 'Basic ' + auth, 'Accept': 'application/json',
               'Content-Type': 'application/json'}
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode()
        return json.loads(raw) if raw else {}


def jira_transitions(project: str, auth: str) -> list[dict]:
    query = urllib.parse.urlencode({'jql': f'project = {project}', 'maxResults': 100,
                                    'fields': 'summary,status'})
    page = jira_call('GET', '/rest/api/3/search/jql?' + query, auth=auth)
    return page.get('issues', [])


def jira_move(issue_key: str, target_status: str, auth: str) -> bool:
    transitions = jira_call('GET', f'/rest/api/3/issue/{issue_key}/transitions', auth=auth)
    for transition in transitions.get('transitions', []):
        if transition['to']['name'] == target_status:
            jira_call('POST', f'/rest/api/3/issue/{issue_key}/transitions',
                      {'transition': {'id': transition['id']}}, auth=auth)
            return True
    return False


def github_call(method, path, payload=None):
    token = os.environ['GITHUB_TOKEN']
    repo = os.environ.get('GITHUB_REPO', 'Ap3x0s/CYBRA')
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'cybra-sync',
               'Content-Type': 'application/json'}
    request = urllib.request.Request(f'https://api.github.com/repos/{repo}{path}',
                                     data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode()
        return json.loads(raw) if raw else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    done = set(DONE)
    todo = set(TODO)

    # A missing block used to be skipped silently, so the script printed
    # "sync complete" while touching nothing — that is how a run could look
    # successful and leave the trackers untouched. Name what was skipped.
    skipped: list[str] = []

    # --- Jira -------------------------------------------------------
    if not os.environ.get('JIRA_BASE'):
        skipped.append('Jira (JIRA_BASE/JIRA_EMAIL/JIRA_TOKEN are not set)')
    if os.environ.get('JIRA_BASE'):
        auth = jira_auth()
        project = os.environ.get('JIRA_PROJECT', 'CYB')
        for issue in jira_transitions(project, auth):
            summary = issue['fields']['summary']
            status = issue['fields']['status']['name']
            if summary in done:
                if status == 'Готово':
                    continue
                if args.dry_run:
                    print(f'JIRA {issue["key"]}: {status} -> Готово')
                    continue
                ok = jira_move(issue['key'], 'Готово', auth)
                print(f'JIRA {issue["key"]}: {"done" if ok else "no transition"}')
                time.sleep(0.3)
            elif summary in todo and status != 'К выполнению':
                print(f'JIRA {issue["key"]}: {status} (остаётся в работе)')

    # --- GitHub -----------------------------------------------------
    if not os.environ.get('GITHUB_TOKEN'):
        skipped.append('GitHub (GITHUB_TOKEN is not set)')
    if os.environ.get('GITHUB_TOKEN'):
        issues = []
        page = 1
        while True:
            batch = github_call('GET', f'/issues?state=open&per_page=100&page={page}')
            if not batch:
                break
            issues.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        for issue in issues:
            if issue.get('pull_request'):
                continue
            title = issue['title']
            if title in done:
                if args.dry_run:
                    print(f'GH #{issue["number"]}: close {title}')
                    continue
                github_call('PATCH', f'/issues/{issue["number"]}',
                            {'state': 'closed', 'state_reason': 'completed'})
                print(f'GH #{issue["number"]}: closed')
                time.sleep(0.4)

    if skipped:
        for item in skipped:
            print(f'skipped {item}')
        print('sync incomplete: nothing was written for the skipped trackers')
        return 2

    print('sync complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
