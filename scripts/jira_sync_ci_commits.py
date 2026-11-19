"""Переписать комментарий в CYB-44: убрать битую разметку и лишние блоки.

Что было не так в первой версии:
  • «Прочее — 10» — под этот блок попали коммиты, у которых префикс не
    совпал с моим списком, включая feat(run) и feat(tooling), хотя это
    отдельные осмысленные изменения;
  • порядок блока и пунктов читался странно: heading с числом без контекста;
  • ссылки дублировались текстом «GitLab» на каждой строке — шум.

Что делаем: удаляем прежний комментарий по маркеру и пишем один новый:
заголовок, краткое описание, затем блоки «название — N коммитов», внутри —
сообщения со ссылкой на GitHub. GitLab-ссылка одна в шапке блока.
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUE = 'CYB-44'
MARKER = '[cybra-sync:ci-devsecops]'
AFTER = 'e249a92'

BLOCKS = [
    ('ci', 'Пайплайн DevSecOps — GitLab и GitHub'),
    ('docker', 'Docker: слои, compose, registry, аудит образа'),
    ('fix(i18n)', 'Переводы: метрики, ошибки API, роли, help'),
    ('fix(ui)', 'Переводы: createContext без импорта React'),
    ('fix(metrics)', 'Метрика coverage: план вместо числа записей'),
    ('fix(backend)', 'Backend: миграции SQLite'),
    ('fix(report)', 'Отчёт: печать, кодировка, статусы'),
    ('brand', 'Бренд: знак, favicon, акцент'),
    ('docs', 'Документация и скриншоты EN/RU'),
    ('security', 'Безопасность: пароль в скриптах и файле первого старта'),
    ('login', 'Экран входа: центрирование, пароль в README'),
    ('legal', 'Лицензия и копирайт'),
    ('style', 'Приведение кода к ruff'),
    ('test', 'Тесты метрик и пароля'),
    ('feat', 'Функциональность: прогоны и утилиты'),
    ('chore', 'Гигиена репозитория'),
    ('merge', 'Слияние с GitHub'),
]
EXTRA = {'Update README.md badges': 'Документация и скриншоты EN/RU'}


def classify(subject: str) -> str:
    if subject in EXTRA:
        return EXTRA[subject]
    for prefix, title in BLOCKS:
        if subject.startswith(prefix):
            return title
    return 'Прочие изменения'


def main() -> int:
    commits = [line.split('|', 1) for line in subprocess.run(
        ['git', 'log', f'{AFTER}..HEAD', '--reverse', '--format=%h|%s'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
        if '|' in line]

    grouped: dict[str, list[tuple[str, str]]] = {}
    for sha, subject in commits:
        grouped.setdefault(classify(subject), []).append((sha, subject))

    env = {}
    for line in (ROOT / 'jira' / '.env').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    auth = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode()).decode()
    base = env['JIRA_BASE'].rstrip('/')

    def api(path: str, data: dict | None = None, method: str = 'GET'):
        request = urllib.request.Request(
            base + path, data=json.dumps(data).encode() if data else None,
            method=method,
            headers={'Authorization': 'Basic ' + auth, 'Accept': 'application/json',
                     'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}

    # Удаляем прежний комментарий по маркеру.
    existing = api(f'/rest/api/3/issue/{ISSUE}/comment?maxResults=100')
    for comment in existing.get('comments', []):
        if MARKER in json.dumps(comment['body'], ensure_ascii=False):
            api(f"/rest/api/3/issue/{ISSUE}/comment/{comment['id']}", method='DELETE')
            print('прежний комментарий удалён')

    github = 'https://github.com/Ap3x0s/CYBRA/commit/'

    content: list[dict] = [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text':
            f'{len(commits)} коммитов после CYB-43 не имели ключа и не были '
            'отражены в Jira. Ниже — по логическим блокам; каждое сообщение '
            'ведёт на коммит в GitHub, история синхронизирована с GitLab.'}]},
    ]

    for title, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        content.append({'type': 'heading', 'attrs': {'level': 3},
                        'content': [{'type': 'text', 'text': f'{title} ({len(items)})'}]})
        content.append({'type': 'bulletList', 'content': [
            {'type': 'listItem', 'content': [{'type': 'paragraph', 'content': [
                {'type': 'text', 'text': subject[:110], 'marks': [
                    {'type': 'link', 'attrs': {'href': github + sha}}]}]}]}
            for sha, subject in items]})

    content.append({'type': 'paragraph', 'content': [
        {'type': 'text', 'text': MARKER}]})

    api(f'/rest/api/3/issue/{ISSUE}/comment',
        {'body': {'type': 'doc', 'version': 1, 'content': content}}, method='POST')

    print(f'комментарий перезаписан: {len(commits)} коммитов, {len(grouped)} блоков')
    for title, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        print(f'  {title}: {len(items)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
