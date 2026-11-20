"""Проверить, снимает ли больший max_tokens обрезку ответов.

Гипотеза: модель reasoning-типа, вся квота completion_tokens уходит в
reasoning_tokens, на текст ничего не остаётся — отсюда finish_reason=length
и TRUNCATED в 29 случаях.

Ключ и заголовки берём из БД, как их использует сам relay: без User-Agent
внешний провайдер отвечает 403.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
sys.path.insert(0, str(BACKEND))

import os  # noqa: E402

from cybra.config import settings  # noqa: E402
from cybra.models import Endpoint  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')


def main() -> int:
    url = os.environ.get('CYBRA_DATABASE_URL', f'sqlite:///{settings.db_path}')
    engine = create_engine(url, future=True)
    with Session(engine) as session:
        endpoint = session.scalars(
            select(Endpoint).where(Endpoint.name == 'Command Code')).first()
        if endpoint is None:
            print('endpoint Command Code не найден')
            return 1
        key = settings.decrypt(endpoint.secret_encrypted)
        chat_url = endpoint.chat_url or (
            endpoint.base_url.rstrip('/') + '/chat/completions')
        extra = endpoint.default_headers or {}

    print('URL   :', chat_url)
    print('ключ  :', 'есть' if key else 'НЕТ')
    print('заголовки из БД:', list(extra) or 'нет')
    print()

    def call(prompt: str, max_tokens: int) -> dict:
        payload = {
            'model': 'deepseek/deepseek-v4.1-flash',
            'messages': [{'role': 'user', 'content': prompt}],
            'stream': False,
            'max_tokens': max_tokens,
        }
        headers = {'Content-Type': 'application/json',
                   'User-Agent': BROWSER_UA,
                   'Authorization': 'Bearer ' + key}
        headers.update(extra)
        request = urllib.request.Request(
            chat_url, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            return {'error': f'HTTP {error.code}: '
                             f'{error.read(200).decode(errors="replace")}'}
        except Exception as error:  # noqa: BLE001
            return {'error': f'{type(error).__name__}: {error}'}

    prompt = ('Ответь одним абзацем: какие три главных риска для безопасности '
              'возникают при подключении LLM к корпоративной почте?')
    for limit in (2048, 8192, 16384):
        result = call(prompt, limit)
        if 'error' in result:
            print(f'max_tokens={limit:6}: {result["error"][:100]}')
            continue
        choice = (result.get('choices') or [{}])[0]
        usage = result.get('usage') or {}
        text = ((choice.get('message') or {}).get('content') or '')
        reasoning = (usage.get('completion_tokens_details') or {}).get(
            'reasoning_tokens')
        print(f'max_tokens={limit:6} finish={choice.get("finish_reason")!s:8} '
              f'completion={usage.get("completion_tokens")} '
              f'reasoning={reasoning} текст={len(text)} симв.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
