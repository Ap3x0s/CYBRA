"""Найти строки, где $переменная превратилась в пустую строку.

Тот же класс дефекта, что починили в security:sca: команда добавлялась через
PowerShell, а он раскрывает $ИМЯ как свою переменную. Здесь ищем любые
`""`, `"/"` и `-o /x` внутри script — признак съеденной переменной.
"""
import re
import sys
from pathlib import Path

PIPELINE = Path('.gitlab-ci.yml')

# Пустые кавычки или путь от корня внутри скриптовых строк.
PATTERNS = [
    (re.compile(r'mkdir -p ""'), 'mkdir с пустой переменной'),
    (re.compile(r'--output-file="/'), 'output-file от корня'),
    (re.compile(r'(?<![$\w])"/[a-z_-]+\.(csv|json|sarif|txt)"'), 'абсолютный путь в кавычках'),
    (re.compile(r'--output "/'), 'output от корня'),
]


def main() -> int:
    text = PIPELINE.read_text(encoding='utf-8')
    problems: list[tuple[int, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, label in PATTERNS:
            if pattern.search(line):
                problems.append((number, label, line.strip()))

    if not problems:
        print('.gitlab-ci.yml: съеденных переменных не найдено')
        return 0

    print(f'найдено подозрительных строк: {len(problems)}')
    for number, label, line in problems:
        print(f'  {number}: {label}')
        print(f'      {line}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
