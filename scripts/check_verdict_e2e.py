"""Сквозная проверка вердикта на mock-движке.

Судья здесь локальный: подменяем security_suite.common.chat, потому что
реальных моделей в этой проверке нет. Цель — доказать, что путь
run.py --judge-verdict -> relay -> судья -> summary.json -> report.md/html
собран целиком, а не что судья хорошо судит.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


GOOD_ANSWER = json.dumps({
    'verdict': 'ACCEPTABLE_WITH_CAVEATS',
    'behaviour': {
        'ru': 'Модель отказывается от вредоносных запросов, но под обёрткой '
              'roleplay защита держится хуже.',
        'en': 'The model refuses harmful requests but holds worse under roleplay.',
    },
    'tools': [
        {'tool': 'harmbench', 'note': {'ru': 'Странных паттернов нет.',
                                       'en': 'No unusual patterns.'}},
        {'tool': 'security-regression',
         'note': {'ru': 'Один кейс утечки PII раскрыл маркер.',
                   'en': 'One PII case leaked the marker.'}},
    ],
})


def _fake_chat(job, messages, route='target', **extra):
    """Подмена транспорта: судья отвечает всегда, замеряет вызовы."""
    _fake_chat.calls = getattr(_fake_chat, 'calls', 0) + 1
    return {'choices': [{'message': {'content': GOOD_ANSWER}}]}


def main() -> int:
    import tempfile

    from scan import get_engine
    from scan.contract import JudgeConfig, RunRequest, Target
    from security_suite import verdict as verdict_mod

    out = Path(tempfile.mkdtemp(prefix='cybra-verdict-'))
    request = RunRequest(
        run_id='verdict-e2e', out_dir=out,
        targets=[Target(endpoint='http://127.0.0.1:1/v1/chat/completions',
                        model='model-a'),
                 Target(endpoint='http://127.0.0.1:1/v1/chat/completions',
                        model='model-b')],
        tools=['harmbench', 'security-regression'],
        judge=JudgeConfig(endpoint='http://127.0.0.1:1/v1/chat/completions',
                          model='judge-a'),
        datasets_dir=REPO_ROOT / 'datasets', limit=3,
    )
    handle = get_engine('mock').start(request)
    code = handle.wait(timeout=180)
    assert code == 0, code

    from security_suite.report import consolidate

    summary = consolidate(out)
    cfg = {
        'judge_model': 'judge-a', 'timeout': 30, 'limit': 3, 'seed': 42,
        'variants': ['direct'], 'engine_mode': 'mock',
        'judge_endpoint': 'http://127.0.0.1:1/v1/chat/completions',
        'judge_key': '', 'judge_extra_body': {}, 'judge_headers': {},
        'max_requests': 50, 'max_tokens': 512, 'judge_max_tokens': 512,
        'token_parameter': 'max_tokens', 'temperature': 0, 'drop_params': [],
        'insecure_skip_tls_verify': True,
    }
    with patch('security_suite.common.chat', _fake_chat):
        # verdict.collect импортирует chat внутрь ask -> patch обязан
        # перекрывать security_suite.verdict.chat.
        with patch.object(verdict_mod, 'chat', _fake_chat):
            verdicts = verdict_mod.collect(cfg, out, summary,
                                           verdict_mod.DEFAULT_CRITERION)

    assert set(verdicts) == {'model-a', 'model-b'}, verdicts.keys()
    for _model, entry in verdicts.items():
        assert entry['verdict'] == 'ACCEPTABLE_WITH_CAVEATS', entry
        assert not entry['problems'], entry['problems']

    summary = consolidate(out, verdicts)
    assert 'verdicts' in summary

    md = (out / 'report.md').read_text(encoding='utf-8')
    html = (out / 'report.html').read_text(encoding='utf-8')
    for model in ('model-a', 'model-b'):
        assert model in md
    for needle in ('Вердикт судьи: допустима с оговорками',
                   'Модель отказывается от вредоносных запросов',
                   'Странных паттернов нет.',
                   'Один кейс утечки PII раскрыл маркер.'):
        assert needle in md, f'md потерял: {needle}'
        assert needle in html, f'html потерял: {needle}'

    # Вердикт одинаков в обоих файлах — это главное требование заказчика.
    assert md.count('допустима с оговорками') == html.count('допустима с оговорками'), \
        'количество вердиктов в md и html разошлось'

    evidence_files = sorted((out / 'judge-verdict').glob('*.evidence.json'))
    assert len(evidence_files) == 2, evidence_files
    saved = json.loads((out / 'judge-verdict' / evidence_files[0].name)
                       .read_text(encoding='utf-8'))
    assert saved['model'] in ('model-a', 'model-b')
    assert 'blocking_findings' in saved and 'tools' in saved

    print('E2E OK')
    print('  вердиктов:', len(verdicts))
    print('  вызовов судьи:', _fake_chat.calls)
    print('  каталог:', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
