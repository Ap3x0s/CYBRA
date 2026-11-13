"""Entry point for adapters that must run in a tool's own interpreter.

PyRIT и AgentDojo импортируют свои пакеты напрямую. В основном venv их нет —
они живут в .tools/<tool>. Поэтому native.py запускает этот модуль нужным
интерпретатором, передавая имя инструмента и путь к job.json.

Запуск: python -m security_suite.native_entry <tool> <job.json>
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print('usage: python -m security_suite.native_entry <tool> <job.json>',
              file=sys.stderr)
        return 2
    tool, job_path = args

    from .common import read_json
    job = read_json(job_path)

    from . import native
    impl = getattr(native, tool + '_impl', None)
    if impl is None:
        print(f'no implementation for {tool}', file=sys.stderr)
        return 2
    impl(job)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
