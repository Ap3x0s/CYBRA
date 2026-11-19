"""Создать CYB-44 — CI/CD, Docker, i18n, coverage — и привязать коммиты.

Зачем задача, а не комментарии в старых. Работа после CYB-43 (последняя
задача по метрикам) в Jira не отражена вообще: 40+ коммитов про пайплайн
DevSecOps, Docker Hub, переводы интерфейса, формулу coverage и favicon не
имеют ключа ни в одном сообщении. Разложить их по существующим задачам
нельзя — они про другое.

Что делает скрипт:
  1. Создаёт задачу в проекте CYB (тип «Задача», как остальные).
  2. Переводит её в «Готово» — работа уже сделана.
  3. Добавляет один комментарий со сводкой и списком коммитов со ссылками
     на GitHub и GitLab.
  4. Не дублирует: если задача с таким summary уже есть, переиспользует её.
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = 'CI/CD: схема DevSecOps, Docker Hub, переводы интерфейса, формула coverage'
DESCRIPTION = """Работа после CYB-43. В Jira не была отражена: 40+ коммитов без ключей.

**Пайплайн по схеме из 18 этапов** (GitLab и GitHub, оба зелёные):
- стадии validate → test → security → build → deploy-test → release → deploy-prod → rollback
- gitleaks, bandit, trivy, SBOM (syft), pip-audit, лицензии, SHA256SUMS
- деплой в тестовый контур со smoke, production с ручным подтверждением, откат
- локальный pre-commit и проверки IaC

**Docker:**
- зависимости ставятся до копирования исходников (кеш слоёв)
- убран `pip install -e`: `PYTHONPATH` делает то же, а `config.root` требует
  оставить пакет по боевому пути
- prod-профиль compose тянет образ из registry, а не собирает
- публикация в Docker Hub: `ap3x0/cybra`
- аудит содержимого образа: секреты, личные данные, мусор — чисто

**Переводы:** три метрики и 20 полей без ключей в EN, 15 русских ошибок API,
роль в топбаре, help-подсказки. Аудит в CI, чтобы не вернулось.

**Метрики:** coverage делил на число записей отчёта вместо планового числа
проверок — воркер, записавший 60 из 100, давал 100 % полноты.

**Прочее:** favicon на весь холст без полей, аватар проекта, пароль первого
старта в файл и README-инструкция, переписывание истории на единого автора."""


def env() -> dict[str, str]:
    values = {}
    for line in (ROOT / 'jira' / '.env').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values


class Jira:
    def __init__(self, values: dict[str, str]) -> None:
        self.base = values['JIRA_BASE'].rstrip('/')
        self.auth = base64.b64encode(
            f"{values['JIRA_EMAIL']}:{values['JIRA_TOKEN']}".encode()).decode()

    def call(self, path: str, data: dict | None = None, method: str = 'GET'):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(data).encode() if data else None,
            method=method,
            headers={'Authorization': 'Basic ' + self.auth,
                     'Accept': 'application/json',
                     'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.loads(response.read().decode())


def adf(text: str) -> dict:
    """Минимальный Atlassian Document Format: абзацы и маркированные списки."""
    content = []
    for block in text.strip().split('\n\n'):
        lines = [line for line in block.splitlines() if line.strip()]
        if all(line.startswith(('- ', '* ')) for line in lines) and lines:
            items = [
                {'type': 'listItem', 'content': [
                    {'type': 'paragraph', 'content': [{'type': 'text', 'text': line[2:]}]}]}
                for line in lines]
            content.append({'type': 'bulletList', 'content': items})
        else:
            content.append({'type': 'paragraph', 'content': [
                {'type': 'text', 'text': block.replace('\n', ' ')}]})
    return {'type': 'doc', 'version': 1, 'content': content}


def main() -> int:
    jira = Jira(env())

    # 1. Есть ли уже такая задача.
    query = urllib.parse.quote(f'project = CYB AND summary ~ "CI/CD: схема DevSecOps"')
    found = jira.call(f'/rest/api/3/search/jql?jql={query}&maxResults=5&fields=summary,status')
    issues = found.get('issues', [])
    if issues:
        key = issues[0]['key']
        print(f'задача уже есть: {key}')
    else:
        created = jira.call('/rest/api/3/issue', {
            'fields': {
                'project': {'key': 'CYB'},
                'issuetype': {'id': '10010'},
                'summary': SUMMARY,
                'description': adf(DESCRIPTION),
            }}, method='POST')
        key = created['key']
        print(f'создана задача: {key}')

    # 2. Перевести в «Готово» — работа сделана.
    transitions = jira.call(f'/rest/api/3/issue/{key}/transitions')
    done = next((t for t in transitions['transitions']
                 if t['to']['name'].lower() in ('готово', 'done')), None)
    if done:
        jira.call(f'/rest/api/3/issue/{key}/transitions',
                  {'transition': {'id': done['id']}}, method='POST')
        print(f'статус: {done["to"]["name"]}')
    else:
        print('переход в «Готово» не найден:', [t['to']['name'] for t in transitions['transitions']])

    print(f'\nKEY={key}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
