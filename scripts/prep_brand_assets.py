"""Подготовить бренд-ассеты из docs/brand для фронтенда.

В папке brand лежат исходники с большими прозрачными полями. Для вёрстки
нужны обрезанные изображения без полей: тогда высота картинки в CSS
совпадает с реальной высотой знака, и выравнивать по базовой линии легко.

Делаем два ассета:
  cybra-mark.png     — эмблема (гексагон с кубом), только знак, без подписи;
  cybra-wordmark.png — надпись CYBRA нашим шрифтом.

Каждый сохраняем в 3x от целевого размера, чтобы на ретине не мылить:
  знак     32px  → 96px
  надпись  16px  → 48px
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'docs' / 'brand'
OUT = ROOT / 'frontend' / 'src' / 'assets'

MARK_SRC = BRAND / 'emblem-trimmed.png'
WORD_SRC = BRAND / 'wordmark.png'


def trim(im: Image.Image) -> Image.Image:
    """Обрезать по альфа-каналу, затем снять 1px по краям от сглаживания."""
    im = im.convert('RGBA')
    bbox = im.split()[-1].getbbox()
    if not bbox:
        return im
    return im.crop(bbox)


def resize_hi(im: Image.Image, target_h: int, scale: int = 3) -> Image.Image:
    """Уменьшить с высоким качеством до target_h * scale по высоте."""
    h = target_h * scale
    w = round(im.width * h / im.height)
    return im.resize((w, h), Image.LANCZOS)


def report(name: str, im: Image.Image) -> None:
    print(f'  {name}: {im.width}x{im.height}  '
          f'(h/w = {im.height/im.width:.3f})')


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    mark = trim(Image.open(MARK_SRC))
    word = trim(Image.open(WORD_SRC))
    print('после обрезки:')
    report('mark', mark)
    report('wordmark', word)

    # Знак: цель 32px в шапке (было 28 у заглушки, делаем заметно крупнее)
    mark_out = resize_hi(mark, 32, scale=3)
    mark_out.save(OUT / 'cybra-mark.png', optimize=True)

    # Надпись: цель 16px по высоте букв. Общая ширина выйдет
    # 16 * (word.width/word.height) — посчитаем и покажем.
    word_out = resize_hi(word, 16, scale=3)
    word_out.save(OUT / 'cybra-wordmark.png', optimize=True)

    print('\nсохранено в 3x (для ретины):')
    print(f'  cybra-mark.png     {mark_out.width}x{mark_out.height}  '
          f'→ в CSS 32 x {32 * mark_out.height / mark_out.width:.1f}')
    print(f'  cybra-wordmark.png {word_out.width}x{word_out.height}  '
          f'→ в CSS {16 * word_out.width / word_out.height:.0f} x 16')
    print(f'\n  размеры файлов: '
          f'{(OUT / "cybra-mark.png").stat().st_size // 1024} KB, '
          f'{(OUT / "cybra-wordmark.png").stat().st_size // 1024} KB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
