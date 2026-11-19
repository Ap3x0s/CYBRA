"""Разобрать неотслеживаемые файлы: что удалить, что игнорировать, что вести.

Заказчик спросил «убрать или в gitignore». Ответ зависит от природы файла,
поэтому сначала смотрим, что это:

* секреты и ключи (secret.key, пароли в скриптах) — удалить, они не должны
  существовать ни в репозитории, ни на виду;
* одноразовые отладочные скрипты — удалить, их работа закончена;
* артефакты прогонов и локальные данные — в .gitignore, они появляются снова;
* страница предпросмотра иконок и запасной логотип — решить отдельно.

Скрипт только показывает раскладку, ничего не трогает.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Отладочные скрипты: каждый писался под одну проверку и уже её сделал.
ONE_OFF = {
    '.fix_ci2.py': 'правил workflow, правка внесена и проверена actionlint',
    '.probe_lang.py': 'разовая проверка языка интерфейса',
    '.probe_site.py': 'разовая проверка сайта (и содержит пароль)',
    'scripts/add_logo_topbar.py': 'разовая правка шапки',
    'scripts/check_all_md.py': 'разовая проверка .md (и содержит пароль)',
    'scripts/check_initial_password_perm.py': 'проверка прав маркера, есть тест',
    'scripts/check_jira_not_in_image.py': 'проверка jira, есть check_build_context',
    'scripts/check_md_chars.py': 'разовый разбор символов .md',
    'scripts/check_md_name.py': 'разовая проверка имени .md',
    'scripts/cleanup_accent_preview.py': 'чистка превью акцента',
    'scripts/compare_accent.py': 'сравнение двух акцентов',
    'scripts/deep_md_check.py': 'глубокий разбор одного .md',
    'scripts/fix_md_format.py': 'правка формата, внесена в report.py',
    'scripts/fix_react_print.py': 'правка печати, внесена',
    'scripts/prepare_logo.py': 'подготовка логотипа, заменена следующей версией',
    'scripts/prepare_logo2.py': 'подготовка логотипа, заменена следующей версией',
    'scripts/prepare_logo3.py': 'подготовка логотипа, финальная версия применена',
    'scripts/purge_secret_history.py': 'чистка истории выполнена',
    'scripts/restore_logo_placeholder.py': 'разовое восстановление заглушки',
    'scripts/wrap_missing_t.py': 'обёртка t(), правка внесена',
}

# Артефакты и локальные данные: появляются снова, поэтому в .gitignore.
IGNORE = {
    'var-test-initpass/': 'временная база прогонов с secret.key и паролем',
}

# Требует решения человека.
ASK = {
    'frontend/src/pages/IconsPreview.jsx': 'страница предпросмотра иконок, 42 КБ, не подключена в роутинг',
    'docs/brand/small-app-icon.png': 'запасной вариант иконки, нигде не используется',
    'scripts/make_avatar_variants.py': 'генератор вариантов аватара, может пригодиться',
}


def untracked() -> list[str]:
    result = subprocess.run(
        ['git', 'status', '--porcelain'], cwd=ROOT,
        capture_output=True, text=True, encoding='utf-8')
    paths = []
    for line in result.stdout.splitlines():
        if line.startswith('??'):
            paths.append(line[3:].strip())
    return paths


def main() -> int:
    present = untracked()
    print(f'неотслеживаемых: {len(present)}\n')

    print('УДАЛИТЬ (одноразовые, и два содержат пароль):')
    total = 0
    for path in present:
        key = path if path in ONE_OFF else None
        if key is None:
            continue
        size = (ROOT / path).stat().st_size if (ROOT / path).exists() else 0
        total += size
        print(f'  {path:44} {size:>7} B  {ONE_OFF[key]}')
    print(f'  освободится: {total / 1024:.0f} КБ\n')

    print('В .GITIGNORE (артефакты, появятся снова):')
    for path, why in IGNORE.items():
        print(f'  {path:44} {why}')
    print()

    print('РЕШИТЬ ОТДЕЛЬНО:')
    for path, why in ASK.items():
        exists = 'есть' if (ROOT / path).exists() else 'нет'
        print(f'  {path:44} [{exists}] {why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
