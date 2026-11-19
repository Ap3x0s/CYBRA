"""Проверить путь вердикта целиком на mock-движке: без моделей и сети."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from security_suite import verdict  # noqa: E402
from security_suite.report import (  # noqa: E402
    VERDICT_LABELS,
    consolidate,
    verdict_block_html,
    verdict_block_ru,
)


def _session_dir(out_dir: Path) -> Path:
    """Каталог с summary.json: сам out_dir или единственный вложенный."""
    if (Path(out_dir) / 'summary.json').exists():
        return Path(out_dir)
    return next(p for p in Path(out_dir).iterdir()
                if p.is_dir() and (p / 'summary.json').exists())


def sample_entry(value='ACCEPTABLE_WITH_CAVEATS'):    return {
        'verdict': value,
        'behaviour': {
            'ru': 'Модель устойчиво отказывается от вредоносных запросов, но '
                  'иногда отказывает и на допустимых.',
            'en': 'The model reliably refuses harmful requests but sometimes '
                  'refuses legitimate ones.',
        },
        'tools': [
            {'tool': 'harmbench', 'note': {'ru': 'Странных паттернов нет.',
                                           'en': 'No unusual patterns.'}},
        ],
        'problems': [],
    }


def test_labels_cover_every_verdict():
    for value in verdict.VERDICTS:
        assert value in VERDICT_LABELS, value


def test_ru_and_html_render_the_same_words():
    """Одна и та же строка вердикта в md и в html.

    Отчёт печатают и скачивают; если формулировка расходится, читатель
    получает два разных вывода из одного прогона.
    """
    entry = sample_entry()
    ru = '\n'.join(verdict_block_ru(entry))
    html = '\n'.join(verdict_block_html(entry))
    assert 'допустима с оговорками' in ru
    assert 'допустима с оговорками' in html
    assert entry['behaviour']['ru'] in ru
    assert entry['behaviour']['ru'] in html
    assert 'Странных паттернов нет.' in ru
    assert 'Странных паттернов нет.' in html


def test_md_block_ends_with_blank_line_before_the_table():
    """Без пустой строки таблица после врезки ломается в Markdown.

    Первая версия вставки ставила таблицу сразу за строкой blockquote:
    Obsidian, VS Code и GitHub показывали вместо неё строку с чертами.
    """
    lines = verdict_block_ru(sample_entry())
    assert lines[-1] == '', 'врезка вердикта обязана кончаться пустой строкой'
    assert all(line.startswith('>') or line == '' for line in lines)


def test_failed_judge_is_shown_as_insufficient_not_hidden():
    entry = verdict._failed('ответ судьи не разобран как JSON: boom')
    assert entry['verdict'] == 'INSUFFICIENT_EVIDENCE'
    ru = '\n'.join(verdict_block_ru(entry))
    assert 'данных недостаточно' in ru
    assert 'не разобран как JSON' in ru


def test_blocking_categories_come_from_real_data():
    """Список блокирующих категорий обязан покрывать то, что пишут адаптеры."""
    blocking = [
        ('harmbench', 'chemical_biological'),
        ('harmbench', 'harassment_bullying'),
        ('jailbreakbench', 'harmful/Malware/Hacking'),
        ('bipia', 'email/injection'),
        ('bipia', 'table/injection'),
        ('security-regression', 'prompt_injection/direct'),
        ('security-regression', 'secret_leak/api_key'),
        ('security-regression', 'pii_leak/cross_user'),
        ('promptfoo', 'direct_injection'),
        ('agentdojo', 'workspace/attack'),
        ('garak', 'dan.Dan_11_0'),
    ]
    for tool, category in blocking:
        assert verdict.is_blocking(tool, category), (tool, category)

    not_blocking = [
        ('jailbreakbench', 'benign/Privacy'),
        ('promptfoo', 'benign'),
        ('bipia', 'email/utility'),
        ('agentdojo', 'workspace/baseline'),
    ]
    for tool, category in not_blocking:
        assert not verdict.is_blocking(tool, category), (tool, category)


def test_prompt_limit_and_default():
    assert verdict.effective_criterion('') == verdict.DEFAULT_CRITERION
    assert verdict.effective_criterion('   ') == verdict.DEFAULT_CRITERION
    assert verdict.effective_criterion('свой критерий') == 'свой критерий'
    long = 'я' * (verdict.PROMPT_LIMIT + 500)
    assert len(verdict.effective_criterion(long)) == verdict.PROMPT_LIMIT


def test_default_criterion_states_the_incomparable_units_rule():
    """Базовый промт обязан запрещать усреднение: это главная ловушка."""
    text = verdict.DEFAULT_CRITERION
    assert 'несравнимы' in text or 'нельзя усреднять' in text
    assert 'INSUFFICIENT_EVIDENCE' in text
    assert 'NOT_ACCEPTABLE' in text
    assert 'балл' in text.lower() or 'процент' in text.lower()


def test_validate_rejects_invented_tool():
    evidence = {'tools': [{'tool': 'harmbench'}]}
    payload = {
        'verdict': 'ACCEPTABLE',
        'behaviour': {'ru': 'Достаточно длинное описание поведения модели.', 'en': 'long enough'},
        'tools': [{'tool': 'jailbreakbench', 'note': {'ru': 'x'}}],
    }
    problems = verdict._validate(payload, evidence)
    assert any('которого нет в прогоне' in p for p in problems)
    assert any('без разбора' in p for p in problems)


def test_validate_rejects_missing_tool_note():
    evidence = {'tools': [{'tool': 'harmbench'}, {'tool': 'bipia'}]}
    payload = {
        'verdict': 'ACCEPTABLE',
        'behaviour': {'ru': 'Достаточно длинное описание поведения модели.', 'en': 'long enough'},
        'tools': [{'tool': 'harmbench', 'note': {'ru': 'есть'}}],
    }
    problems = verdict._validate(payload, evidence)
    assert any('bipia' in p for p in problems)


def test_parse_strips_markdown_fence():
    parsed, error = verdict._parse('```json\n{"verdict":"ACCEPTABLE"}\n```')
    assert error is None and parsed == {'verdict': 'ACCEPTABLE'}
    parsed, error = verdict._parse('мусор')
    assert parsed is None and error


def test_evidence_keeps_blocking_findings_and_balanced_samples():
    model_result = {
        'conclusion': 'FINDINGS',
        'tools': [
            {'tool': 'harmbench', 'status': 'COMPLETE', 'unit': 'case',
             'counts': {'PASS': 1, 'FAIL': 1}, 'categories': {}},
            {'tool': 'bipia', 'status': 'COMPLETE', 'unit': 'case',
             'counts': {'PASS': 2, 'FAIL': 0}, 'categories': {}},
        ],
    }
    records = [
        {'tool': 'harmbench', 'category': 'harmful', 'case_id': 'a',
         'status': 'FAIL', 'prompt': 'p', 'answer': 'a', 'reason': 'r'},
        {'tool': 'harmbench', 'category': 'benign/x', 'case_id': 'b',
         'status': 'FAIL', 'prompt': 'p', 'answer': 'a', 'reason': 'r'},
        {'tool': 'harmbench', 'category': 'harmful', 'case_id': 'c',
         'status': 'PASS', 'prompt': 'p', 'answer': 'a', 'reason': 'r'},
        {'tool': 'bipia', 'category': 'email/utility', 'case_id': 'd',
         'status': 'PASS', 'prompt': 'p', 'answer': 'a', 'reason': 'r'},
    ]
    evidence = verdict.build_evidence('m', model_result, records, {'limit': 10})
    blocking_ids = {item['case_id'] for item in evidence['blocking_findings']}
    assert blocking_ids == {'a'}, 'допустимый провал не должен попадать в блокирующие'
    # PASS-примеры берутся от разных инструментов, а не первые подряд.
    assert {item['tool'] for item in evidence['evidence_samples']} == {'harmbench', 'bipia'}
    assert evidence['totals']['failed'] == 1


def test_collect_sets_the_relay_key_for_the_judge_call():
    """common.chat ходит через relay и берёт ключ из окружения.

    Первая версия collect() не выставляла SUITE_RELAY_KEY: шаговые relay'и к
    этому моменту закрыты и свой ключ унесли с собой, поэтому каждый вызов
    судьи падал с KeyError и вердикт всегда был «данных недостаточно» —
    тихо, без единой ошибки в UI.
    """
    import os
    import tempfile

    from security_suite import verdict as verdict_mod

    run_dir = Path(tempfile.mkdtemp(prefix='cybra-collect-'))
    summary = {'models': {'model-a': {'conclusion': 'FINDINGS', 'tools': []}}}
    cfg = {
        'judge_model': 'judge-a', 'timeout': 5, 'limit': 1, 'seed': 1,
        'variants': ['direct'], 'max_requests': 5, 'max_tokens': 64,
        'judge_max_tokens': 64, 'token_parameter': 'max_tokens',
        'temperature': 0, 'drop_params': [], 'insecure_skip_tls_verify': True,
        'judge_endpoint': 'http://127.0.0.1:1/v1/chat/completions',
        'judge_key': '', 'judge_extra_body': {}, 'judge_headers': {},
    }

    seen = {}

    def fake_chat(job, messages, route='target', **extra):
        # Именно здесь падала первая версия: без ключа KeyError.
        seen['key'] = os.environ.get('SUITE_RELAY_KEY')
        return {'choices': [{'message': {'content': 'мусор'}}]}

    os.environ.pop('SUITE_RELAY_KEY', None)
    with patch.object(verdict_mod, 'chat', fake_chat):
        results = verdict_mod.collect(cfg, run_dir, summary,
                                      verdict_mod.DEFAULT_CRITERION)

    assert seen.get('key'), 'collect не выставил SUITE_RELAY_KEY'
    assert 'SUITE_RELAY_KEY' not in os.environ, 'ключ остался в окружении'
    # Ответ не разобран — это штатный отказ судьи, а не падение.
    assert results['model-a']['verdict'] == 'INSUFFICIENT_EVIDENCE'
    assert any('JSON' in p for p in results['model-a']['problems'])


def test_consolidate_writes_verdicts_into_summary_and_both_reports(tmp_path):
    """Вердикт обязан попасть в summary.json, report.md и report.html."""
    from scan import get_engine
    from scan.contract import JudgeConfig, RunRequest, Target

    request = RunRequest(
        run_id='verdict-fixture', out_dir=tmp_path / 'run',
        targets=[Target(endpoint='http://127.0.0.1:1/v1/chat/completions',
                        model='model-a')],
        tools=['harmbench', 'security-regression'],
        judge=JudgeConfig(endpoint='http://127.0.0.1:1/v1/chat/completions',
                          model='judge-a'),
        datasets_dir=REPO_ROOT / 'datasets', limit=3,
    )
    handle = get_engine('mock').start(request)
    assert handle.wait(timeout=120) == 0

    verdicts = {'model-a': sample_entry()}
    # mock-движок пишет артефакты прямо в out_dir; реальный run.py создаёт
    # внутри --out ещё каталог сессии. Здесь проверяется рендер, поэтому берём
    # тот каталог, где фактически лежит summary.json.
    session = _session_dir(request.out_dir)
    consolidate(session, verdicts)

    summary = json.loads((session / 'summary.json').read_text(encoding='utf-8'))
    assert summary['verdicts']['model-a']['verdict'] == 'ACCEPTABLE_WITH_CAVEATS'
    md = (session / 'report.md').read_text(encoding='utf-8')
    html = (session / 'report.html').read_text(encoding='utf-8')
    for document in (md, html):
        assert 'допустима с оговорками' in document
        assert 'Модель устойчиво отказывается' in document
        assert 'Странных паттернов нет.' in document
        assert 'ACCEPTABLE_WITH_CAVEATS' in document


def test_consolidate_without_verdicts_changes_nothing(tmp_path):
    """Выключенный вердикт не должен добавлять пустые блоки в отчёт."""
    from scan import get_engine
    from scan.contract import JudgeConfig, RunRequest, Target

    request = RunRequest(
        run_id='no-verdict', out_dir=tmp_path / 'run',
        targets=[Target(endpoint='http://127.0.0.1:1/v1/chat/completions',
                        model='model-a')],
        tools=['harmbench'],
        judge=JudgeConfig(endpoint='http://127.0.0.1:1/v1/chat/completions',
                          model='judge-a'),
        datasets_dir=REPO_ROOT / 'datasets', limit=2,
    )
    handle = get_engine('mock').start(request)
    assert handle.wait(timeout=120) == 0
    session = _session_dir(request.out_dir)
    consolidate(session)
    summary = json.loads((session / 'summary.json').read_text(encoding='utf-8'))
    assert 'verdicts' not in summary
    assert 'Вердикт судьи' not in (session / 'report.md').read_text(encoding='utf-8')
    # CSS блока встроен в каждый отчёт всегда, поэтому проверяем наличие
    # самого блока, а не имени класса.
    assert '<div class="judge-verdict">' not in (
        session / 'report.html').read_text(encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-v']))
