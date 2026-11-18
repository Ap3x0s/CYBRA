"""Собрать favicon из фирменной иконки.

Задача из ревью: иконка во вкладке выглядит меньше, чем у DNS или Wildberries.
Разобрался в причине, и она не в размере файла — он честный 16/32/48.

Что реально происходит. В исходнике docs/brand/app-icon.png (1254x1254)
скруглённая плитка занимает 714x692, то есть 57 % холста, а внутри плитки
эмблема занимает её на 100 %. То есть эмблема уже максимальна для своего
знака — увеличивать её значит ломать пропорции шестиугольника.

Разница с DNS и WB в другом: у них иконка — яркий сплошной квадрат на весь
холст, у нас тёмная плитка. На тёмной панели вкладок тёмная плитка
растворяется, и глаз видит только серебряный контур в её середине.

Что делает скрипт:
  * обрезает холст по плитке (убирает 43 % пустых полей вокруг);
  * для favicon вписывает плитку в холст ВПРИТЫК, без полей — 32x32
    заполняется целиком (было 32x30 из-за исходных пропорций);
  * для PWA (192/512) и apple-touch оставляет плитку как есть: там она
    читается и является частью бренда.

Скрипт идемпотентен: перезаписывает файлы.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'docs' / 'brand' / 'app-icon.png'
PUBLIC = ROOT / 'frontend' / 'public'


def tile_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    """Границы непрозрачной плитки — она же граница эмблемы."""
    bbox = im.split()[-1].getbbox()
    return bbox if bbox else (0, 0, im.width, im.height)


def fill_canvas(crop: Image.Image, side: int) -> Image.Image:
    """Вписать в квадрат side x side так, чтобы заполнить его целиком.

    Ключевой момент: масштабируем по БОЛЬШЕЙ стороне и центруем. Исходник
    714x692 (не квадрат), поэтому наивное resize исказило бы знак, а
    resize с сохранением полей оставил бы его меньше холста.
    """
    scale = side / max(crop.size)
    width = round(crop.width * scale)
    height = round(crop.height * scale)
    resized = crop.resize((width, height), Image.LANCZOS)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((side - width) // 2, (side - height) // 2))
    return canvas


def main() -> int:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert('RGBA')
    plate = src.crop(tile_bbox(src))
    print(f'источник: {src.size}, плитка/эмблема: {plate.size} '
          f'({100 * plate.width // src.width} % холста)')

    # --- favicon: плитка впритык к краям холста ---
    for name, side in (('favicon-16x16.png', 16),
                       ('favicon-32x32.png', 32),
                       ('favicon-48x48.png', 48)):
        fill_canvas(plate, side).save(PUBLIC / name, optimize=True)
        print(f'  {name}: {side}x{side}, заполнение 100 %')
    # ICO собираем из одного кадра 48: PIL пересэмплирует остальные размеры.
    fill_canvas(plate, 48).save(
        PUBLIC / 'favicon.ico', format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
    print('  favicon.ico: 16/32/48')

    # --- PWA: плитка целиком, как в оригинале ---
    for name, side in (('icon-192.png', 192), ('icon-512.png', 512)):
        fill_canvas(plate, side).save(PUBLIC / name, optimize=True)
        print(f'  {name}: {side}x{side}')

    # --- apple-touch: iOS не понимает альфу, заливаем фоном плитки ---
    side = 180
    apple = fill_canvas(plate, side)
    bg = apple.getpixel((side // 2, int(side * 0.94)))
    bg = (bg[0], bg[1], bg[2], 255)
    flat = Image.new('RGBA', (side, side), bg)
    flat.alpha_composite(apple)
    flat.convert('RGB').save(PUBLIC / 'apple-touch-icon.png', optimize=True)
    print(f'  apple-touch-icon.png: {side}x{side}, фон {bg[:3]}')

    print(f'\nвсё в {PUBLIC}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
