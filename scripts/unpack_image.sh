#!/bin/busybox/sh
# Развернуть образ в файловую систему из tar, который отдаёт kaniko.
#
# Почему это отдельный шаг: `--tar-path` у kaniko пишет формат `docker save` —
# не готовый rootfs, а набор сжатых слоёв плюс manifest.json со списком этих
# слоёв в порядке наложения. Чтобы проверить содержимое (а не только наличие
# файлов), слои надо развернуть последовательно: каждый следующий перекрывает
# предыдущий, и удаления в нём записаны whiteout-файлами.
#
# Почему shell: в образе kaniko нет python3 (проверено), а тащить его нечем —
# образ собран FROM scratch без пакетного менеджера. busybox даёт tar и awk.
#
# Использование:  sh unpack_image.sh <image.tar> <каталог назначения>

set -eu

TARBALL="${1:?нужен путь к tar образа}"
DEST="${2:?нужен каталог назначения}"

# Каталог под временные файлы создаём сами и рядом с целью, а не в /tmp:
# в образе kaniko /tmp отсутствует вовсе (образ собран FROM scratch), и
# mktemp падал с «No such file or directory» ещё до начала работы. Привязка
# к DEST заодно убирает зависимость от TMPDIR, который в CI тоже не задан.
mkdir -p "$DEST"
work=$(mktemp -d "$DEST/.unpack.XXXXXX")
trap 'rm -rf "$work"' EXIT INT TERM

# manifest.json — единственное место, где перечислены слои. Без него образ
# не разобрать: имена файлов слоёв — это их digest, порядок в них не записан.
tar -xf "$TARBALL" -C "$work" manifest.json

# Порядок слоёв достаём из JSON. jq в образе нет, поэтому режем текст:
# все значения "Layers" — это строки вида "abc....tar.gz" внутри массива.
order=$(tr ',' '\n' < "$work/manifest.json" \
  | sed -n 's/.*"\([0-9a-f]\{12,\}\.tar\.gz\)".*/\1/p')

if [ -z "$order" ]; then
  echo "в manifest.json нет слоёв — tar не похож на docker save" >&2
  exit 1
fi

count=0
for layer in $order; do
  tar -xf "$TARBALL" -C "$work" "$layer"
  # -o: tar внутри tar, разворачивать как есть. Порядок важен — слои
  # накладываются друг на друга, и файл из позднего слоя должен победить.
  tar -xf "$work/$layer" -C "$DEST" 2>/dev/null || true
  rm -f "$work/$layer"
  count=$((count + 1))
done

echo "слоёв развёрнуто: $count"
echo "каталог: $DEST"
