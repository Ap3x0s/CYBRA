"""Проверка безопасности Ansible: опасные модули и утечки в логах.

Этап 5 схемы DevSecOps для infra-пайплайна. Обычный SAST (bandit, ruff)
про Ansible ничего не знает, а именно playbook получает доступ к
секретам и к целевому хосту.

Что проверяется:

  * `shell`/`command` с подстановкой внешних данных: это путь к инъекции
    команд на целевом хосте. Оправданные случаи помечаются комментарием
    `# noqa: ansible-shell`;
  * `become: yes` без указания пользователя — деплой от root без
    необходимости расширяет последствия ошибки;
  * `no_log` отсутствует на задачах, работающих с секретами: значение
    попадёт в лог CI, который читают люди;
  * `validate_certs: no` и `StrictHostKeyChecking=no` — отключение
    проверки TLS и хоста;
  * секрет, вписанный значением в YAML, а не через переменную.

Запуск:
    python scripts/check_ansible_security.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = ROOT / 'infra' / 'ansible'

problems: list[str] = []
checked = 0


def note(path: Path, message: str) -> None:
    relative = path.relative_to(ROOT).as_posix()
    problems.append(f'{relative}: {message}')


def walk_tasks(data, path: Path) -> None:
    """Обойти дерево задач, включая block/rescue/always и include_tasks."""
    global checked
    if isinstance(data, list):
        for item in data:
            walk_tasks(item, path)
        return
    if not isinstance(data, dict):
        return

    # Задача — это словарь с модулем и, возможно, name.
    module_keys = [key for key in data
                   if key not in ('name', 'when', 'register', 'tags', 'become',
                                  'become_user', 'no_log', 'loop', 'with_items',
                                  'ignore_errors', 'changed_when', 'failed_when',
                                  'until', 'retries', 'delay', 'vars', 'environment',
                                  'notify', 'args', 'delegate_to', 'run_once',
                                  'check_mode', 'any_errors_fatal', 'listen',
                                  'block', 'rescue', 'always')]

    if module_keys:
        checked += 1
        module = module_keys[0]
        text = str(data)

        # shell/command с внешними данными.
        #
        # Важное различие, которое первая версия не учитывала: `cmd:`
        # строкой уходит в shell и подставляет туда переменные — это путь
        # к инъекции. `argv:` передаёт аргументы списком, shell не
        # участвует, и подстановка безопасна. Ругаться на argv — значит
        # заставлять добавлять noqa там, где всё в порядке.
        if module in ('shell', 'ansible.builtin.shell', 'command',
                      'ansible.builtin.command'):
            payload = data.get(module)
            uses_shell = module in ('shell', 'ansible.builtin.shell')
            is_string_cmd = isinstance(payload, str)
            if is_string_cmd or uses_shell:
                cmd = str(payload if is_string_cmd else data.get('cmd', ''))
                if re.search(r'\{\{\s*\w+', cmd) and 'noqa: ansible-shell' not in text:
                    note(path, f'задача {data.get("name", module)!r}: '
                               f'{module} строкой с подстановкой переменных — '
                               f'значение уходит в shell. Используйте форму '
                               f'`argv:` или добавьте `# noqa: ansible-shell`')

        # no_log на задачах с секретами.
        #
        # Первая версия искала слова secret/password/token/key в тексте
        # задачи целиком и потому ругалась на «Добавить ключ репозитория
        # Docker» (gpg-ключ, не секрет) и на задачи, где просто сказано
        # «секрет». Проверяем только имена переменных, а не прозу:
        # {{ cybra_secret_key }} — да, «ключ репозитория» — нет.
        variable_names = re.findall(r'\{\{\s*([A-Za-z_][A-Za-z0-9_]*)', text)
        secret_words = ('secret', 'password', 'passwd', 'token', 'api_key',
                        'private_key')
        touches_secret = any(
            word in name.lower() for name in variable_names
            for word in secret_words)
        if touches_secret and not data.get('no_log'):
            note(path, f'задача {data.get("name", module)!r}: работает с '
                       f'секретом ({", ".join(n for n in variable_names if any(w in n.lower() for w in secret_words))}), '
                       f'но без `no_log: true` — значение попадёт в лог CI')

        # become без пользователя.
        if data.get('become') and not data.get('become_user'):
            note(path, f'задача {data.get("name", module)!r}: become без '
                       f'become_user — выполнится от root')

        # Проверки сертификатов.
        if data.get('validate_certs') is False:
            note(path, f'задача {data.get("name", module)!r}: '
                       f'validate_certs выключена')

    for key in ('block', 'rescue', 'always'):
        if key in data:
            walk_tasks(data[key], path)
    if 'tasks' in data:
        walk_tasks(data['tasks'], path)


def check_playbook(path: Path) -> None:
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except yaml.YAMLError as error:
        note(path, f'YAML не разбирается — {error}')
        return
    walk_tasks(data, path)


def check_ssh_settings() -> None:
    """StrictHostKeyChecking не должен быть отключён."""
    config = ANSIBLE / 'ansible.cfg'
    if not config.exists():
        note(config, 'файл отсутствует')
        return
    text = config.read_text(encoding='utf-8')
    if re.search(r'StrictHostKeyChecking\s*=\s*no', text, re.I):
        note(config, 'StrictHostKeyChecking=no — проверка ключа хоста '
                     'отключена, подмена хоста не будет замечена')
    if 'UserKnownHostsFile' in text and '/dev/null' in text:
        note(config, 'UserKnownHostsFile указывает на /dev/null — '
                     'проверка ключа теряет смысл')


def check_plain_secrets() -> None:
    """Секрет значением в YAML, а не через lookup или переменную."""
    patterns = (
        re.compile(r'(?i)(password|secret|token)\s*:\s*(?![\'"{{])'
                   r'[A-Za-z0-9+/_\-]{16,}'),
    )
    for path in ANSIBLE.rglob('*.yml'):
        for number, line in enumerate(
                path.read_text(encoding='utf-8').splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#') or '{{' in stripped or '$' in stripped:
                continue
            for pattern in patterns:
                if pattern.search(stripped):
                    note(path, f'строка {number}: похоже на секрет значением — '
                               f'используйте lookup или CI-переменную')


def main() -> int:
    print('=== playbooks и роли ===')
    files = sorted(ANSIBLE.rglob('*.yml'))
    files = [path for path in files
             if 'requirements' not in path.name]
    for path in files:
        before = len(problems)
        check_playbook(path)
        status = 'OK' if len(problems) == before else 'см. ниже'
        print(f'  {path.relative_to(ROOT).as_posix()}: {status}')

    print()
    print('=== настройки подключения ===')
    before = len(problems)
    check_ssh_settings()
    print(f'  ansible.cfg: {"OK" if len(problems) == before else "см. ниже"}')

    print()
    print('=== секреты значением ===')
    check_plain_secrets()

    print()
    if problems:
        print(f'НАЙДЕНО: {len(problems)}')
        for problem in problems:
            print(f'  {problem}')
        return 1

    print(f'задач проверено: {checked} — замечаний нет')
    return 0


if __name__ == '__main__':
    sys.exit(main())
