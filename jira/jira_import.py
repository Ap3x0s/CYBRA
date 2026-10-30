"""Create the CYBRA backlog in Jira Cloud.

Credentials come from the environment, never from the repository:

    JIRA_BASE=https://your-domain.atlassian.net
    JIRA_EMAIL=you@example.com
    JIRA_TOKEN=ATATT...

Usage:
    python jira/jira_import.py --dry-run          # show what would be created
    python jira/jira_import.py                    # create epics + stories
    python jira/jira_import.py --epics-only
    python jira/jira_import.py --project CYB

The script is idempotent by summary: an existing issue with the same summary in
the project is skipped instead of duplicated.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from backlog import EPICS, STORIES, MILESTONES

EPIC_TYPE = 'Эпик'
STORY_TYPE = 'История'


def api(method, path, payload=None, base=None, auth=None):
    url = (base or os.environ['JIRA_BASE']).rstrip('/') + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        'Authorization': 'Basic ' + auth,
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode() or '{}'
            return json.loads(body)
    except urllib.error.HTTPError as error:
        detail = error.read(2000).decode(errors='replace')
        raise RuntimeError(f'HTTP {error.code} on {method} {path}: {detail}') from error


def credentials():
    missing = [k for k in ('JIRA_BASE', 'JIRA_EMAIL', 'JIRA_TOKEN') if not os.environ.get(k)]
    if missing:
        sys.exit('Missing environment variables: ' + ', '.join(missing))
    pair = f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_TOKEN']}"
    return base64.b64encode(pair.encode()).decode()


def adf(text):
    """Minimal Atlassian Document Format paragraph."""
    return {
        'type': 'doc',
        'version': 1,
        'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]}],
    }


def existing_summaries(project, auth):
    """Return {summary: key} for issues already in the project."""
    result, token = {}, None
    while True:
        params = {
            'jql': f'project = {project} ORDER BY created ASC',
            'maxResults': 100,
            'fields': 'summary',
        }
        if token:
            params['nextPageToken'] = token
        page = api('GET', '/rest/api/3/search/jql?' + urllib.parse.urlencode(params), auth=auth)
        for issue in page.get('issues', []):
            result[issue['fields']['summary']] = issue['key']
        token = page.get('nextPageToken')
        if not token:
            return result


def create_issue(project, issue_type, summary, description, auth, extra=None):
    fields = {
        'project': {'key': project},
        'issuetype': {'name': issue_type},
        'summary': summary,
        'description': adf(description),
    }
    if extra:
        fields.update(extra)
    payload = {'fields': fields}
    created = api('POST', '/rest/api/3/issue', payload, auth=auth)
    return created['key']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='CYB')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--epics-only', action='store_true')
    args = parser.parse_args()

    auth = credentials()
    known = existing_summaries(args.project, auth)
    print(f'Project {args.project}: {len(known)} issues already present', flush=True)

    epic_keys = {}
    for epic in EPICS:
        summary = f"[{epic['name']}] {epic['summary']}"
        if summary in known:
            epic_keys[epic['key']] = known[summary]
            print(f'  = {known[summary]} epic already exists', flush=True)
            continue
        if args.dry_run:
            print(f'  + epic {summary}', flush=True)
            continue
        key = create_issue(args.project, EPIC_TYPE, summary, epic['description'], auth)
        epic_keys[epic['key']] = key
        print(f'  + {key} {summary}', flush=True)
        time.sleep(0.4)

    if args.epics_only or args.dry_run:
        return 0

    created = 0
    for epic_key, summary, description, acceptance in STORIES:
        full = f'[{summary}]'
        if summary in known:
            print(f'  = story already exists: {summary}', flush=True)
            continue
        body = description + '\n\nКритерии приёмки: ' + acceptance
        key = create_issue(
            args.project, STORY_TYPE, summary, body, auth,
            extra={'parent': {'key': epic_keys[epic_key]}},
        )
        created += 1
        print(f'  + {key} {summary} -> {epic_keys[epic_key]}', flush=True)
        time.sleep(0.4)

    print(f'Done: {created} stories created', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
