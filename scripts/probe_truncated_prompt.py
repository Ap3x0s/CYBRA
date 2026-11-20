"""Проверить устойчивость при max_tokens=16384 на том промпте, что обрезался.

При 8192 модель иногда съедает всю квоту на размышления (тот же промпт
base64-декодера давал reasoning=8192, text=0). Проверяем 16384 многократно:
нужно понять, это редкий сбой или закономерность.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

from cybra.config import settings  # noqa: E402
from cybra.models import Endpoint  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
URL_DB = 'postgresql+psycopg://cybra:cybra@127.0.0.1:5433/cybra'
PROMPTS = Path(__file__).resolve().parents[1] / 'var' / '_trunc_prompts.json'
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 16384
TRIES = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def main() -> int:
    prompts = json.loads(PROMPTS.read_text(encoding='utf-8'))
    engine = create_engine(URL_DB, future=True)
    with Session(engine) as session:
        endpoint = session.scalars(
            select(Endpoint).where(Endpoint.name == 'Command Code')).first()
        key = settings.decrypt(endpoint.secret_encrypted)
        chat_url = endpoint.chat_url

    print(f'промптов: {len(prompts)}, лимит: {LIMIT}, попыток на промпт: {TRIES}')
    print()
    for index, prompt in enumerate(prompts):
        ok = 0
        reasoning_used = []
        for _ in range(TRIES):
            payload = {
                'model': 'deepseek/deepseek-v4.1-flash',
                'messages': [{'role': 'user', 'content': prompt}],
                'stream': False,
                'max_tokens': LIMIT,
            }
            request = urllib.request.Request(
                chat_url, data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json',
                         'User-Agent': UA, 'Authorization': 'Bearer ' + key})
            try:
                with urllib.request.urlopen(request, timeout=600) as response:
                    data = json.load(response)
                choice = (data.get('choices') or [{}])[0]
                usage = data.get('usage') or {}
                used = (usage.get('completion_tokens_details') or {}).get(
                    'reasoning_tokens')
                reasoning_used.append(used)
                if choice.get('finish_reason') == 'stop':
                    ok += 1
            except urllib.error.HTTPError as error:
                print('  HTTP', error.code)
            except Exception as error:  # noqa: BLE001
                print('  ', type(error).__name__)
        print(f'промпт {index + 1}: stop у {ok} из {TRIES}, '
              f'reasoning={reasoning_used}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
