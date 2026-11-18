#!/bin/sh
# Установить git-хук pre-commit для этапа 0 схемы DevSecOps.
#
# Хук вызывает scripts/precommit.sh: линтер, аудит переводов и тесты. Это те
# же проверки, что гоняет CI, но локально и за секунды — дешевле, чем ждать
# пайплайн, чтобы узнать про опечатку.
#
# Идемпотентен: перезаписывает хук, если он уже есть.
set -e

ROOT=$(git rev-parse --show-toplevel)
HOOK="$ROOT/.git/hooks/pre-commit"

if [ ! -d "$ROOT/.git" ]; then
  echo "FAIL: $ROOT не git-репозиторий" >&2
  exit 1
fi

cat > "$HOOK" <<'EOF'
#!/bin/sh
# Установлено scripts/install_git_hooks.sh — этап 0 схемы DevSecOps.
exec sh "$(git rev-parse --show-toplevel)/scripts/precommit.sh"
EOF
chmod +x "$HOOK"

echo "установлено: $HOOK"
echo "проверки: ruff → аудит i18n → pytest"
echo "отключить разово: git commit --no-verify"
