"""Добавить раздел «Бенчмарки и метрики — это два разных счёта» в русскую методику.

Английская версия уже содержит этот раздел: он объясняет самое частое
недоразумение — почему в README написано «8 бенчмарков» при наличии
11 метрик. Русская копия должна соответствовать.

Вставка по номеру строки, а не по совпадению текста: заголовок в русском
файле содержит обратные кавычки, и поиск по строке с ними ненадёжен.
"""
from __future__ import annotations

from pathlib import Path

PATH = Path('docs/ru/METHODOLOGY.md')

BLOCK = [
    '### Бенчмарки и метрики — это два разных счёта',
    '',
    'Оба верны и означают разное:',
    '',
    '- **8 бенчмарков** — инструменты, которые порождают тест-кейсы и вердикты',
    '  (`security_suite/common.py`, константа `TOOLS`);',
    '- **11 метрик** — формулы, которые считаются поверх этих вердиктов',
    '  (`backend/cybra/metrics.py`, константа `CATALOG`).',
    '',
    'Шесть из одиннадцати — разные фильтры над одним и тем же потоком PASS/FAIL;',
    'независимый сигнал дают только `resilience_gap`, `utility_under_attack` и',
    '`agent_false_block_rate`.',
    '',
]


def main() -> int:
    text = PATH.read_text(encoding='utf-8')

    if 'Бенчмарки и метрики — это два разных счёта' in text:
        print('раздел уже есть, ничего не делаю')
        return 0

    lines = text.split('\n')

    # Якорь — подраздел «Зачем нужен unscored_rate» в разделе «Как читать».
    # Ищем по вхождению 'unscored' в строке-заголовке третьего уровня.
    idx = None
    for i, line in enumerate(lines):
        if line.startswith('###') and 'unscored' in line and 'Зачем' in line:
            idx = i
            break

    if idx is None:
        print('якорь не найден — вставка отменена')
        return 1

    print(f'вставка перед строкой {idx + 1}: {lines[idx][:60]}')
    lines[idx:idx] = BLOCK
    PATH.write_text('\n'.join(lines), encoding='utf-8', newline='\n')

    result = PATH.read_text(encoding='utf-8')
    n = len([l for l in result.split('\n') if l.startswith('#')])
    print(f'готово: строк {len(result.splitlines())}, заголовков {n}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
