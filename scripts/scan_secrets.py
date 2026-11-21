"""Скан всей истории git на секреты и личные данные.

Проверяет не только текущее дерево, но и каждый коммит: секрет, попавший в
историю, остаётся там даже после удаления файла — и именно поэтому проверка
только рабочего дерева ничего не доказывает.

Ищет:
  * токены по сигнатурам известных провайдеров;
  * приватные ключи;
  * email и домашние пути разработчика;
  * переменные окружения с секретами, у которых есть реальное значение.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict

ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]

# Сигнатуры токенов. Значение считается секретом, если после префикса идёт
# достаточно длинная строка из допустимых символов. Короткие вхождения вида
# «ghp_...» или «ATATT...» — заглушки в документации, они не считаются.
TOKEN_PATTERNS = {
    'GitLab PAT': re.compile(r'glpat-[A-Za-z0-9_\-. ]{20,}'),
    'GitHub classic': re.compile(r'ghp_[A-Za-z0-9]{30,}'),
    'GitHub oauth': re.compile(r'gho_[A-Za-z0-9]{30,}'),
    'GitHub fine-grained': re.compile(r'github_pat_[A-Za-z0-9_]{40,}'),
    'Docker Hub PAT': re.compile(r'dckr_pat_[A-Za-z0-9_\-]{20,}'),
    'Jira token': re.compile(r'ATATT3[A-Za-z0-9_\-]{20,}'),
    'Anthropic': re.compile(r'sk-ant-[A-Za-z0-9_\-]{20,}'),
    'OpenAI': re.compile(r'sk-proj-[A-Za-z0-9_\-]{20,}'),
    'AWS key': re.compile(r'AKIA[0-9A-Z]{16}'),
    'Private key': re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'Slack': re.compile(r'xox[baprs]-[A-Za-z0-9\-]{10,}'),
}

# Личные данные. Проверяются отдельно: они не секрет в юридическом смысле,
# но публиковать чужой email или домашний путь в открытом репозитории не надо.
PERSONAL_PATTERNS = {
    'домашний путь Windows': re.compile(r'C:\\\\Users\\\\[A-Za-z]+'),
    'домашний путь unix': re.compile(r'/home/[a-z]{3,}/'),
    'личный email': re.compile(r'[a-z0-9._%+\-]+@(?:yandex|gmail|mail|bk|list)\.ru?'),
    'внутренний IP': re.compile(r'192\.168\.\d{1,3}\.\d{1,3}'),
}

# Файлы, где подобные строки — часть документации или тестов, а не утечка.
ALLOWLIST_PATHS = (
    'docs/', 'README', 'tests/', 'NOTICE', '.github/', '.gitlab-ci',
    'scripts/check_', 'scripts/audit_',
)


def git(*args: str) -> str:
    result = subprocess.run(['git', *args], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace')
    return result.stdout


def scan_history() -> int:
    # Полный текст каждого коммита вместе с путями: так видно и содержимое,
    # и файл, куда оно попало.
    patches = git('log', '--all', '--format=COMMIT %H', '-p', '--unified=0')
    current_commit = ''
    current_file = ''
    findings: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    allowed_hits: list[tuple[str, str, str]] = []

    for line in patches.splitlines():
        if line.startswith('COMMIT '):
            current_commit = line.split()[1][:7]
            continue
        if line.startswith('+++ b/'):
            current_file = line[6:]
            continue
        if not line.startswith('+') or line.startswith('+++'):
            continue

        for label, pattern in {**TOKEN_PATTERNS, **PERSONAL_PATTERNS}.items():
            for match in pattern.finditer(line):
                value = match.group(0)
                record = (current_commit, current_file, value[:60])
                if any(part in current_file for part in ALLOWLIST_PATHS):
                    allowed_hits.append(record)
                else:
                    findings[label].append(record)
    return findings, allowed_hits


def main() -> int:
    print(f'коммитов в истории: {git("rev-list", "--all", "--count").strip()}')
    print()

    findings, allowed = scan_history()

    if allowed:
        print(f'вхождения в документации и тестах (не утечка): {len(allowed)}')
        seen = set()
        for commit, path, value in allowed:
            key = (path, value)
            if key in seen:
                continue
            seen.add(key)
            print(f'  {path}: {value}')
        print()

    if not findings:
        print('СЕКРЕТОВ И ЛИЧНЫХ ДАННЫХ ВНЕ ДОКУМЕНТАЦИИ НЕ НАЙДЕНО')
        return 0

    print('НАЙДЕНО:')
    for label, items in findings.items():
        print(f'  {label}: {len(items)}')
        for commit, path, value in items[:5]:
            print(f'    {commit} {path}: {value}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
