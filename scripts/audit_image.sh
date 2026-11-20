#!/bin/busybox/sh
# Аудит содержимого образа — выполняется НАД распакованной файловой системой.
#
# Раньше проверка запускалась внутри собранного образа (`docker run --entrypoint
# python`). После перехода на kaniko локального образа в демоне нет: сборщик
# отдаёт tar и digest, а не объект в docker. Поэтому смотрим на сам tar —
# это ровно те файлы, что уедут заказчику.
#
# Почему shell, а не python: у образа kaniko нет python3 (проверено), и
# доставить его туда нечем — образ собран FROM scratch, пакетного менеджера
# тоже нет. Зато есть busybox: find, grep, tar.
#
# Аргумент: путь к распакованному rootfs.
#
# Код возврата: 0 — чисто, 1 — найдены проблемы. В CI вызывается с `|| true`,
# потому что это отчёт, а не блокирующая проверка (как и security:image).

set -u

ROOTFS="${1:-}"
if [ -z "$ROOTFS" ] || [ ! -d "$ROOTFS" ]; then
  echo "использование: $0 <распакованный rootfs>" >&2
  exit 2
fi

problems=0

echo "=== содержимое образа ==="

# 1. Секреты и ключи. Ищем по имени файла в приложении и данных.
echo "--- секреты ---"
found_secrets=0
for pattern in '*.env' '*.pem' '*.key' '*.p12' 'id_rsa' 'secret.key' 'cookies.txt' '*.bundle'; do
  # shellcheck disable=SC2086
  matches=$(find "$ROOTFS/app" "$ROOTFS/data" -name "$pattern" 2>/dev/null || true)
  if [ -n "$matches" ]; then
    found_secrets=1
    echo "$matches" | while IFS= read -r path; do
      echo "  FAIL секрет: ${path#"$ROOTFS"}"
    done
  fi
done
[ "$found_secrets" -eq 0 ] && echo "  чисто" || problems=$((problems + 1))

# 2. Личные данные: логины, почта, домашние пути разработчика.
# Сравниваем только текстовые файлы: в бинарниках совпадение случайно.
echo "--- личные данные ---"
found_personal=0
for needle in 'ap3x0kantor' 'evgenykantor' 'C:\Users\evgen' '192.168.1.'; do
  matches=$(grep -rl -F "$needle" \
      --include='*.py' --include='*.js' --include='*.json' \
      --include='*.md' --include='*.txt' --include='*.yml' --include='*.yaml' \
      "$ROOTFS/app" 2>/dev/null || true)
  if [ -n "$matches" ]; then
    found_personal=1
    echo "$matches" | while IFS= read -r path; do
      echo "  FAIL личные данные «$needle»: ${path#"$ROOTFS"}"
    done
  fi
done
[ "$found_personal" -eq 0 ] && echo "  чисто" || problems=$((problems + 1))

# 3. Мусор репозитория, который не должен уезжать в образ.
echo "--- мусор репозитория ---"
found_junk=0
for junk in node_modules __pycache__ .pytest_cache .venv '.git'; do
  matches=$(find "$ROOTFS/app" -name "$junk" 2>/dev/null || true)
  if [ -n "$matches" ]; then
    found_junk=1
    echo "$matches" | while IFS= read -r path; do
      echo "  FAIL мусор: ${path#"$ROOTFS"}"
    done
  fi
done
[ "$found_junk" -eq 0 ] && echo "  чисто" || problems=$((problems + 1))

# 4. Приложение действительно на месте: пустой «успешный» образ хуже, чем
#    отсутствующий. Проверяем точку входа и собранный UI.
echo "--- комплектность ---"
if [ -f "$ROOTFS/app/run.py" ]; then
  echo "  run.py: есть"
else
  echo "  FAIL run.py отсутствует"; problems=$((problems + 1))
fi
if [ -d "$ROOTFS/app/backend/cybra" ]; then
  echo "  пакет cybra: есть"
else
  echo "  FAIL пакет cybra отсутствует"; problems=$((problems + 1))
fi
if [ -f "$ROOTFS/app/backend/static/index.html" ]; then
  echo "  собранный SPA: есть"
else
  echo "  FAIL SPA отсутствует — собирался ли фронт?"; problems=$((problems + 1))
fi

echo
echo "проблем: $problems"
[ "$problems" -eq 0 ]
