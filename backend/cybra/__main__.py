"""``python -m cybra`` entry point: a single command starts the console."""
from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='cybra', description='CYBRA LLM security console')
    parser.add_argument('--host', default=os.environ.get('CYBRA_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('CYBRA_PORT', '8000')))
    parser.add_argument('--reload', action='store_true', help='Dev only: auto-reload')
    parser.add_argument('--engine', choices=['subprocess', 'mock'],
                        default=os.environ.get('CYBRA_ENGINE', 'subprocess'),
                        help='mock runs an offline fixture instead of real models')
    parser.add_argument('setup', nargs='*', help='setup --tools garak pyrit: install native tools')
    args = parser.parse_args(argv)

    os.environ.setdefault('CYBRA_ENGINE', args.engine)

    if args.setup:
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root))
        from security_suite.setup_tools import setup
        tools = args.setup[1:] or ['garak', 'pyrit', 'agentdojo', 'promptfoo']
        errors = setup(tools)
        if errors:
            for tool, error in errors.items():
                print(f'FAILED {tool}: {error}', file=sys.stderr)
            return 1
        print('All requested tools are installed.', flush=True)
        return 0

    import uvicorn

    print(f'CYBRA starting on http://{args.host}:{args.port}', flush=True)
    uvicorn.run(
        'cybra.main:app',
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level='info',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
