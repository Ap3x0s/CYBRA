#!/bin/sh
# Синхронизация коммита с Jira после успешного коммита.
#
# Зачем hook, а не ручной запуск: если синхронизацию нужно помнить, её будут
# забывать. Hook срабатывает сам, а при недоступной Jira НИКОГДА не мешает
# коммиту — сетевые сбои не должны блокировать работу над кодом.
#
# Ключ задачи берётся из сообщения коммита: CYB-35 в теме или теле.
# Токен лежит в jira/.env (в .gitignore), в репозиторий не попадает.

set -e

# Найти интерпретатор проекта. venv важнее системного: там есть зависимости.
REPO_ROOT=$(git rev-parse --show-toplevel)
PY=""
if [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
  PY="$REPO_ROOT/.venv/Scripts/python.exe"
elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY="$REPO_ROOT/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PY="python"
fi

if [ -z "$PY" ]; then
  exit 0
fi

SCRIPT="$REPO_ROOT/scripts/jira_sync.py"
if [ ! -f "$SCRIPT" ]; then
  exit 0
fi

# Синхронизируем только что созданный коммит. Вывод подавляем, но ошибки
# показываем: молчаливый сбой хука хуже, чем его отсутствие.
"$PY" "$SCRIPT" --range HEAD~1..HEAD 2>&1 | sed 's/^/  jira: /' || true

exit 0
