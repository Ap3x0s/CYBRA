"""Delete GitHub issues — the only route that actually works.

The REST API cannot do this: ``DELETE /repos/{owner}/{repo}/issues/{n}`` returns
404 for every issue, including a fresh one created by the token's own user, with
``permissions.admin`` true. That 404 is not a permissions problem — the endpoint
simply does not exist for issues. The GraphQL ``deleteIssue`` mutation does work
and removes the issue and its timeline from the repository.

The backlog was mirrored from Jira into 34 issues, so the activity feed filled
with issue events. This script cleared them.

Token comes from Windows Credential Manager via ``git credential fill`` or from
GITHUB_TOKEN. It is never written to disk or printed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get('GITHUB_OWNER', 'Ap3x0s')
NAME = os.environ.get('GITHUB_REPO_NAME', 'CYBRA')


def token() -> str:
    value = os.environ.get('GITHUB_TOKEN')
    if value:
        return value
    result = subprocess.run(['git', 'credential', 'fill'],
                            input='protocol=https\nhost=github.com\n\n',
                            capture_output=True, text=True, check=False)
    for line in result.stdout.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1]
    sys.exit('no GitHub token: set GITHUB_TOKEN or let git credential fill resolve it')


def gql(query: str, variables: dict | None = None) -> dict:
    payload: dict = {'query': query}
    if variables:
        payload['variables'] = variables
    request = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + TOKEN,
                 'Content-Type': 'application/json',
                 'User-Agent': 'cybra-backlog'},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return {'http_error': error.code, 'body': error.read().decode()[:300]}


def collect() -> list[dict]:
    found: list[dict] = []
    cursor = None
    while True:
        query = '''query($after:String){ repository(owner:"%s", name:"%s") {
                     issues(first:50, after:$after, states:[OPEN,CLOSED]) {
                       pageInfo { hasNextPage endCursor }
                       nodes { number id state title } } } }''' % (OWNER, NAME)
        result = gql(query, {'after': cursor})
        repo = result.get('data', {}).get('repository')
        if not repo:
            sys.exit('query failed: ' + json.dumps(result)[:300])
        found.extend(repo['issues']['nodes'])
        page = repo['issues']['pageInfo']
        if not page['hasNextPage']:
            return found
        cursor = page['endCursor']


def main() -> int:
    global TOKEN
    TOKEN = token()

    issues = collect()
    print(f'{len(issues)} issue(s) to delete', flush=True)

    deleted = failed = 0
    for issue in issues:
        result = gql(
            'mutation($id:ID!){ deleteIssue(input:{issueId:$id}) { clientMutationId } }',
            {'id': issue['id']},
        )
        if result.get('data', {}).get('deleteIssue') is not None:
            deleted += 1
        else:
            failed += 1
            print(f"  ! #{issue['number']} {json.dumps(result)[:200]}", flush=True)

    print(f'deleted: {deleted}, failed: {failed}')
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
