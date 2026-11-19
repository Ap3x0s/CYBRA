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

echo "== ruff =="
ruff check backend scan

echo "== i18n =="
python scripts/audit_i18n_keys.py

echo "== быстрые тесты =="
python -m pytest tests/ -q -x --timeout=120 2>/dev/null || python -m pytest tests/ -q -x

echo "pre-commit: всё чисто"
