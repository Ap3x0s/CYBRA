"""Create the CYBRA backlog as GitHub issues.

Credentials come from the environment, never from the repository:

    GITHUB_TOKEN=ghp_...        # fine-grained or classic token with `issues: write`
    GITHUB_REPO=Ap3x0s/CYBRA

Usage:
    python github_import.py --dry-run
    python github_import.py
    python github_import.py --labels-only

Idempotent by title: an existing issue with the same title is skipped.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from backlog import EPICS, STORIES, MILESTONES

API = 'https://api.github.com'


def call(method, path, payload=None, token=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'cybra-backlog',
        'Content-Type': 'application/json',
    }
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        detail = error.read(2000).decode(errors='replace')
        raise RuntimeError(f'HTTP {error.code} on {method} {path}: {detail}') from error


def labels_for(epic_key):
    return ['epic:' + epic_key]


def ensure_labels(repo, token, dry_run):
    wanted = {}
    for epic in EPICS:
        wanted['epic:' + epic['key']] = '1D4ED8'
    wanted['story'] = '0E7490'
    wanted['cybra'] = '111827'
    for name, color in wanted.items():
        if dry_run:
            print(f'  label would be ensured: {name}', flush=True)
            continue
        try:
            call('POST', f'/repos/{repo}/labels', {'name': name, 'color': color}, token)
            print(f'  + label {name}', flush=True)
        except RuntimeError as error:
            if 'HTTP 422' in str(error):
                print(f'  = label exists: {name}', flush=True)
            else:
                raise
        time.sleep(0.2)


def existing_titles(repo, token):
    titles, page = set(), 1
    while True:
        issues = call('GET', f'/repos/{repo}/issues?state=all&per_page=100&page={page}', token=token)
        if not issues:
            return titles
        for issue in issues:
            titles.add(issue['title'])
        if len(issues) < 100:
            return titles
        page += 1


def create_issue(repo, token, title, body, labels):
    return call('POST', f'/repos/{repo}/issues',
                {'title': title, 'body': body, 'labels': labels}, token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--labels-only', action='store_true')
    args = parser.parse_args()

    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO', 'Ap3x0s/CYBRA')
    if not token:
        sys.exit('Missing GITHUB_TOKEN')
    print(f'Repository: {repo}', flush=True)

    ensure_labels(repo, token, args.dry_run)
    if args.labels_only or args.dry_run:
        for epic in EPICS:
            print(f'  + epic #{epic["key"]}: {epic["summary"]}', flush=True)
        for epic_key, summary, _description, _acceptance in STORIES:
            print(f'  + {summary} [{epic_key}]', flush=True)
        return 0

    titles = existing_titles(repo, token)
    print(f'{len(titles)} issues already present', flush=True)

    epic_numbers = {}
    for epic in EPICS:
        title = f"Эпик: {epic['name']}"
        if title in titles:
            print(f'  = {title} exists', flush=True)
            continue
        body = epic['description'] + '\n\n' + epic['summary']
        issue = create_issue(repo, token, title, body, ['epic:' + epic['key'], 'cybra'])
        epic_numbers[epic['key']] = issue['number']
        print(f'  + #{issue["number"]} {title}', flush=True)
        time.sleep(0.6)

    created = 0
    for epic_key, summary, description, acceptance in STORIES:
        if summary in titles:
            continue
        body = (
            description
            + '\n\n**Критерии приёмки:** ' + acceptance
            + f'\n\n<sub>Эпик: {epic_key}</sub>'
        )
        issue = create_issue(repo, token, summary, body, ['story', 'epic:' + epic_key, 'cybra'])
        created += 1
        print(f'  + #{issue["number"]} {summary}', flush=True)
        time.sleep(0.6)

    print(f'Done: {created} stories created', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
