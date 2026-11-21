#!/bin/sh
# Этап 0 схемы DevSecOps: локальные проверки до коммита.
#
# Зачем: красный пайплайн на gitlab.com стоит минут ожидания и одного
# выгоревшего слота раннера. Те же проверки локально занимают секунды и не
# пускают в историю заведомо сломанный коммит.
#
# Установка (один раз):
#   sh scripts/install_git_hooks.sh
#
# Проверки намеренно неполные — быстрые: полный набор гоняет CI. Здесь то,
# что ловит 90 % ошибок и укладывается в несколько секунд.
set -e

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

# Инструменты лежат в .venv и в PATH не попадают, когда git запускает хук из
# своего окружения. Без этого хук падал с «ruff: command not found» — то есть
# не проверял НИЧЕГО и молча пропускал коммит, что хуже отсутствия хука.
if [ -d "$ROOT/.venv/Scripts" ]; then
  PATH="$ROOT/.venv/Scripts:$PATH"
elif [ -d "$ROOT/.venv/bin" ]; then
  PATH="$ROOT/.venv/bin:$PATH"
fi
export PATH

# Если ruff всё равно нет — честно говорим и выходим с ошибкой. Пропустить
# проверку молча значит сделать вид, что она прошла.
if ! command -v ruff > /dev/null 2>&1; then
  echo "FAIL: ruff не найден. Установите: .venv/Scripts/pip install ruff" >&2
  exit 1
fi

echo "== ruff =="
ruff check backend scan

# Формат проверяется тем же ruff: один инструмент, две команды. Только свой
# код — vendor/ сознательно не форматируем, он должен оставаться сравнимым
# с upstream.
echo "== формат =="
ruff format --check backend/cybra scan run.py

echo "== i18n =="
python scripts/audit_i18n_keys.py

echo "== быстрые тесты =="
python -m pytest tests/ -q -x --timeout=120 2>/dev/null || python -m pytest tests/ -q -x

echo "pre-commit: всё чисто"
