# Brand assets

Source artwork for the CYBRA identity. Raster only — the emblem is a 3D
render with metal gradients, so vector tracing would lose the highlights and
produce banded edges.

| File | What it is | Used by |
|---|---|---|
| `emblem-trimmed.png` | Hexagon emblem with the cube, no lettering. Transparent background, cropped tight to the artwork (716×716). | `scripts/prep_brand_assets.py` → `frontend/src/assets/cybra-mark.png` |
| `emblem-full.png` | Same emblem together with the CYBRA wordmark below it. Not cropped — the caption is cut off at the bottom in the source. | nothing (kept as source) |
| `wordmark.png` | CYBRA lettering only, no emblem. Transparent background. | `scripts/prep_brand_assets.py` → `frontend/src/assets/cybra-wordmark.png` |
| `app-icon.png` | App icon: rounded-square tile with the emblem inside. Transparent background, 1254×1254. | `scripts/make_favicons.py` → favicons and PWA icons |
| `source-logo.png` | Original master render on a black background, 1254×1254. Kept as the primary source. | reference only |

## Regenerating derivatives

Both scripts are idempotent and read from this folder:

```bash
python scripts/prep_brand_assets.py   # header mark + wordmark for the SPA
python scripts/make_favicons.py       # favicon.ico, PNG icons, apple-touch-icon
```

`prep_brand_assets.py` crops the transparent margin and saves at 3× so the
logo stays sharp on retina displays. `make_favicons.py` produces a multi-frame
`.ico` plus PNG sizes, and flattens `apple-touch-icon.png` onto a solid
background because iOS does not honour alpha in that icon.

## Naming

Lowercase, hyphenated, `<what>-<variant>.png`. Files are referenced by path
from the scripts above — renaming one means updating the matching constant.

> Русская версия: [docs/ru/brand/README.md](../ru/brand/README.md).
