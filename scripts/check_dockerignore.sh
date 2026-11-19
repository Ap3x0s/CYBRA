#!/bin/sh
# Этап 7 схемы DevSecOps: .dockerignore не должен пускать секреты в образ.
#
# Проверка вынесена из .gitlab-ci.yml в файл: конструкция с кавычками и
# скобками внутри YAML-строки ломала парсер CI Lint («script config should be
# a string or a nested array of strings»). Скрипт читается, а не парсится.
set -e

IGNORE=.dockerignore

if [ ! -f "$IGNORE" ]; then
  echo "FAIL: $IGNORE отсутствует — контекст сборки не ограничен" >&2
  exit 1
fi

missing=0
for pattern in '.env' '*.pem' '*.key'; do
  if ! grep -qxF "$pattern" "$IGNORE"; then
    echo "FAIL: '$pattern' не исключён из контекста сборки" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  exit 1
fi

echo ".dockerignore исключает секреты: .env, *.pem, *.key"
echo "проверено строк: $(wc -l < "$IGNORE")"
