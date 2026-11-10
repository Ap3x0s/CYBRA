"""Close the GitHub backlog and strip its labels.

Context: the issue list was created as a backlog mirror of Jira. GitHub's REST
API cannot delete issues at all — DELETE /repos/{owner}/{repo}/issues/{n}
returns 404 even for a freshly created issue owned by the token's user. The
GraphQL ``deleteIssue`` mutation does work, and is what actually removed the
list; see ``delete_github_issues.py``.

This script is kept because it is the REST-only fallback: closing every issue
and removing its labels, for when GraphQL is unavailable.

Token comes from the environment, never from this file.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get('GITHUB_TOKEN')
if not TOKEN:
    sys.exit('GITHUB_TOKEN is not set')
REPO = os.environ.get('GITHUB_REPO', 'Ap3x0s/CYBRA')
BASE = f'https://api.github.com/repos/{REPO}'
HEADERS = {
    'Authorization': 'Bearer ' + TOKEN,
    'User-Agent': 'cybra-backlog',
    'Accept': 'application/vnd.github+json',
}


def call(method: str, path: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        print(f'  ! HTTP {error.code} on {method} {path}', file=sys.stderr)
        return None


def main() -> int:
    issues = call('GET', '/issues?state=all&per_page=100') or []
    print(f'issues: {len(issues)}')

    for issue in issues:
        number = issue['number']
        if issue['state'] == 'open':
            call('PATCH', f'/issues/{number}', {'state': 'closed', 'state_reason': 'not_planned'})
            print(f'  closed #{number}')
        # Labels made the list look like a live backlog; drop them.
        for label in issue.get('labels', []):
            call('DELETE', f"/issues/{number}/labels/{urllib.parse.quote(label['name'])}")

    remaining = call('GET', '/issues?state=open&per_page=100') or []
    print(f'open after: {len(remaining)}')
    return 0


if __name__ == '__main__':
    import urllib.parse  # noqa: E402  (used above)
    raise SystemExit(main())
