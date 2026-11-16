"""Собрать набор favicon из фирменной иконки приложения.

Источник: docs/brand/Премиальная иконка с металлическим шестиугольником
и кубом.png — скруглённый квадрат с эмблемой, 1254x1254, прозрачный фон,
непрозрачная часть 716x694.

Что делаем и почему:

1. Обрезаем прозрачные поля. В исходнике 70% прозрачных пикселей; если
   масштабировать как есть, во вкладке браузера значок занял бы треть
   отведённого места.

2. favicon.ico — многокадровый (16/32/48). Именно ICO, а не только PNG:
   Chrome и Firefox читают PNG, но Safari и часть встроенных браузеров
   надёжнее берут ICO. Дублирование не вредит — браузер выберет сам.

3. PNG 32 и 16 — для современных браузеров, с явным указанием sizes.

4. apple-touch-icon 180x180 — для «Добавить на главный экран» в iOS.
   Здесь прозрачность убираем: iOS не поддерживает альфу в этой иконке,
   прозрачные углы он заливает чёрным, получается двойное скругление с
   грязной каймой. Подкладываем фон, снятый с самой иконки.

5. icon-192 и icon-512 — для PWA-манифеста.

Скрипт идемпотентен: просто перезаписывает файлы.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'docs' / 'brand' / (
    'app-icon.png')
PUBLIC = ROOT / 'frontend' / 'public'


def trim(im: Image.Image) -> Image.Image:
    """Обрезать по альфа-каналу и привести к квадрату."""
    bbox = im.split()[-1].getbbox()
    if not bbox:
        return im
    im = im.crop(bbox)

    # Квадрат: иконка почти квадратная (716x694), но не идеально.
    # Дополняем до квадрата прозрачным, чтобы при уменьшении не исказить.
    side = max(im.width, im.height)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return canvas


def rounded_mask(side: int, radius_ratio: float = 0.22) -> Image.Image:
    """Маска со скруглением — для apple-touch-icon."""
    from PIL import ImageDraw
    mask = Image.new('L', (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, side - 1, side - 1),
        radius=int(side * radius_ratio), fill=255)
    return mask


def main() -> int:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert('RGBA')
    base = trim(src)
    print(f'источник: {src.size}, после обрезки: {base.size}')

    # --- PNG для браузера (прозрачность сохраняем) ---
    sizes = {'favicon-16x16.png': 16, 'favicon-32x32.png': 32,
             'icon-192.png': 192, 'icon-512.png': 512}
    for name, side in sizes.items():
        base.resize((side, side), Image.LANCZOS).save(
            PUBLIC / name, optimize=True)
        print(f'  {name}: {side}x{side}')

    # --- ICO многокадровый ---
    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    base.save(PUBLIC / 'favicon.ico', format='ICO', sizes=ico_sizes)
    print(f'  favicon.ico: {ico_sizes}')

    # --- apple-touch-icon: без прозрачности ---
    # Фон берём с самой иконки — нижняя часть скруглённого квадрата,
    # там самый тёмный участок градиента.
    #
    # Заливаем квадрат ЦЕЛИКОМ, а не только под альфой: у исходной иконки
    # собственное скругление, и если просто подложить фон под прозрачные
    # пиксели, по углам останется светлая кайма от антиалиасинга — iOS
    # показывает её как грязную рамку вокруг иконки.
    bg = base.getpixel((base.width // 2, int(base.height * 0.88)))
    bg = (bg[0], bg[1], bg[2], 255)
    side = 180
    apple = base.resize((side, side), Image.LANCZOS)
    flat = Image.new('RGBA', (side, side), bg)
    flat.alpha_composite(apple)
    flat.convert('RGB').save(PUBLIC / 'apple-touch-icon.png', optimize=True)
    print(f'  apple-touch-icon.png: 180x180, фон {bg[:3]}')

    print(f'\nвсё в {PUBLIC}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
