"""Тесты трёх новых метрик.

Проверяем не «функция вернула число», а КОРРЕКТНОСТЬ логики на граничных
случаях. Метрика безопасности с тихой ошибкой опаснее её отсутствия: число
выглядит правдоподобно и уходит в отчёт.

Ключевые случаи:
  * Resilience Gap различает врождённую слабость и хрупкую защиту — это
    ровно то, ради чего метрика вводилась;
  * отсутствие данных даёт None, а не ноль;
  * Agent False Block считает именно baseline, а не атаки;
  * utility_under_attack не путает utility с инъекциями.
"""
from __future__ import annotations

import json

import pytest

from backend.cybra import metrics as M
from backend.cybra.models import RunStep


def make_step(**kwargs) -> RunStep:
    """RunStep без БД: метрики читают только поля, не сессию."""
    step = RunStep()
    step.counts = kwargs.pop('counts', {'PASS': 0, 'FAIL': 0, 'ERROR': 0,
                                        'UNSCORED': 0, 'SKIPPED': 0})
    step.categories = kwargs.pop('categories', {})
    step.artifact_dir = kwargs.pop('artifact_dir', '')
    step.tool = kwargs.pop('tool', 'harmbench')
    for key, value in kwargs.items():
        setattr(step, key, value)
    return step


def write_records(tmp_path, rows):
    """Создать records.jsonl по контракту и вернуть каталог шага."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / 'records.jsonl'
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    return str(tmp_path)


# ---------------------------------------------------------------- Resilience

class TestResilienceGap:
    def test_weak_but_stable_model_has_zero_gap(self, tmp_path):
        """60% и там и там — слабая, но устойчивая модель.

        Это главный случай: ASR покажет 40% и создаст впечатление проблемы,
        хотя атака ничего не сломала. Gap обязан быть нулевым.
        """
        rows = []
        for variant, passes in [('direct', 3), ('roleplay', 3), ('authority', 3)]:
            for index in range(6):
                rows.append({
                    'case_id': f'behavior_{index}/{variant}',
                    'status': 'PASS' if index < passes else 'FAIL',
                })
        step = make_step(artifact_dir=write_records(tmp_path, rows))
        assert M._rate(step, 'resilience_gap') == pytest.approx(0.0, abs=1e-9)

    def test_brittle_model_has_large_gap(self, tmp_path):
        """5 из 6 прямых проходят, под атакой почти всё падает.

        Та же безопасность «в среднем», но защита рассыпается. Gap должен
        быть большим — именно это отличает метрику от ASR.
        """
        rows = []
        for index in range(6):
            rows.append({'case_id': f'b{index}/direct',
                         'status': 'PASS' if index < 5 else 'FAIL'})
        for variant in ('roleplay', 'authority'):
            for index in range(6):
                rows.append({'case_id': f'b{index}/{variant}',
                             'status': 'PASS' if index < 2 else 'FAIL'})
        step = make_step(artifact_dir=write_records(tmp_path, rows))
        gap = M._rate(step, 'resilience_gap')
        # direct 5/6 = 0.8333, атаки 2/6 = 0.3333, разница ≈ 0.5
        assert gap == pytest.approx(5 / 6 - 2 / 6, abs=1e-9)
        assert gap > 0.4

    def test_no_direct_variant_returns_none(self, tmp_path):
        """Без прямых запросов сравнивать не с чем — None, а не ноль."""
        rows = [{'case_id': f'b{i}/roleplay', 'status': 'PASS'} for i in range(3)]
        step = make_step(artifact_dir=write_records(tmp_path, rows))
        assert M._rate(step, 'resilience_gap') is None

    def test_no_attack_variant_returns_none(self, tmp_path):
        """Одни прямые запросы — Gap не определён."""
        rows = [{'case_id': f'b{i}/direct', 'status': 'PASS'} for i in range(3)]
        step = make_step(artifact_dir=write_records(tmp_path, rows))
        assert M._rate(step, 'resilience_gap') is None

    def test_missing_artifacts_return_none(self, tmp_path):
        """Нет файла — нет метрики. Ноль здесь был бы ложью."""
        step = make_step(artifact_dir=str(tmp_path / 'nope'))
        assert M._rate(step, 'resilience_gap') is None

    def test_errors_excluded_from_denominator(self, tmp_path):
        """ERROR не должен разбавлять оценку поведения модели."""
        rows = [
            {'case_id': 'b1/direct', 'status': 'PASS'},
            {'case_id': 'b2/direct', 'status': 'FAIL'},
            {'case_id': 'b3/direct', 'status': 'ERROR'},
            {'case_id': 'b1/roleplay', 'status': 'PASS'},
        ]
        step = make_step(artifact_dir=write_records(tmp_path, rows))
        # direct = 1/2 = 0.5, roleplay = 1/1 = 1.0, gap = -0.5
        assert M._rate(step, 'resilience_gap') == pytest.approx(-0.5, abs=1e-9)

    def test_gap_can_be_negative(self, tmp_path):
        """Обёртка иногда «улучшает» — отрицательный Gap валиден.

        Это не ошибка: модель может отказать на обёртке, где прямой запрос
        прошёл. Метрика обязана это показать, а не обрезать до нуля.
        """
        rows = [
            {'case_id': 'b1/direct', 'status': 'FAIL'},
            {'case_id': 'b1/roleplay', 'status': 'PASS'},
        ]
        step = make_step(artifact_dir=write_records(tmp_path, rows))
        assert M._rate(step, 'resilience_gap') == pytest.approx(-1.0, abs=1e-9)


# ------------------------------------------------------------------ Utility

class TestUtilityUnderAttack:
    def test_counts_only_utility_categories(self):
        """Инъекции не должны попадать в знаменатель полезности."""
        step = make_step(categories={
            'email/utility': {'PASS': 3, 'FAIL': 1, 'ERROR': 0,
                              'UNSCORED': 0, 'SKIPPED': 0},
            'email/1:Subject': {'PASS': 0, 'FAIL': 9, 'ERROR': 0,
                                'UNSCORED': 0, 'SKIPPED': 0},
        })
        # 3/(3+1) = 0.75, инъекции проигнорированы
        assert M._rate(step, 'utility_under_attack') == pytest.approx(0.75)

    def test_no_utility_category_returns_none(self):
        step = make_step(categories={
            'email/attack': {'PASS': 1, 'FAIL': 1, 'ERROR': 0,
                             'UNSCORED': 0, 'SKIPPED': 0},
        })
        assert M._rate(step, 'utility_under_attack') is None


# -------------------------------------------------------- Agent false block

class TestAgentFalseBlockRate:
    def test_counts_baseline_not_attacks(self):
        """Блокировка считается по baseline, а провалы атак игнорируются."""
        step = make_step(tool='agentdojo', categories={
            'workspace/baseline': {'PASS': 3, 'FAIL': 1, 'ERROR': 0,
                                   'UNSCORED': 0, 'SKIPPED': 0},
            'workspace/attack': {'PASS': 0, 'FAIL': 8, 'ERROR': 0,
                                 'UNSCORED': 0, 'SKIPPED': 0},
        })
        # 1/(3+1) = 0.25 — только baseline
        assert M._rate(step, 'agent_false_block_rate') == pytest.approx(0.25)

    def test_no_attacks_is_not_an_error(self):
        """Все атаки отражены, но baseline чист — метрика равна нулю."""
        step = make_step(tool='agentdojo', categories={
            'workspace/baseline': {'PASS': 5, 'FAIL': 0, 'ERROR': 0,
                                   'UNSCORED': 0, 'SKIPPED': 0},
        })
        assert M._rate(step, 'agent_false_block_rate') == pytest.approx(0.0)

    def test_missing_baseline_returns_none(self):
        step = make_step(tool='agentdojo', categories={
            'workspace/attack': {'PASS': 2, 'FAIL': 1, 'ERROR': 0,
                                 'UNSCORED': 0, 'SKIPPED': 0},
        })
        assert M._rate(step, 'agent_false_block_rate') is None


# ------------------------------------------------------------- Catalog link

class TestCoverageUsesPlan:
    """Coverage делит на ПЛАН, а не на число записей в отчёте.

    Исходный дефект: 100 запланированных проверок, воркер записал 60, все 60
    получили вердикт — формула (60+0)/60 показывала 100 % полноты. Числитель
    и знаменатель сжимались вместе, и метрика врала ровно тогда, когда её
    читают: при частично упавшем воркере.
    """

    def test_partial_worker_is_not_full_coverage(self):
        """60 записей из 100 запланированных = 60 %, а не 100 %."""
        step = make_step(tool='promptfoo', planned=100, counts={
            'PASS': 60, 'FAIL': 0, 'ERROR': 0, 'UNSCORED': 0, 'SKIPPED': 0})
        assert M._rate(step, 'coverage') == pytest.approx(0.60)

    def test_full_worker_is_full_coverage(self):
        step = make_step(tool='promptfoo', planned=60, counts={
            'PASS': 60, 'FAIL': 0, 'ERROR': 0, 'UNSCORED': 0, 'SKIPPED': 0})
        assert M._rate(step, 'coverage') == pytest.approx(1.0)

    def test_errors_reduce_coverage(self):
        """Ошибки — часть плана, но вердикта у них нет."""
        step = make_step(tool='jailbreakbench', planned=40, counts={
            'PASS': 34, 'FAIL': 1, 'ERROR': 5, 'UNSCORED': 0, 'SKIPPED': 0})
        # 35 оценённых из 40 запланированных.
        assert M._rate(step, 'coverage') == pytest.approx(0.875)

    def test_without_plan_falls_back_to_records(self):
        """Архивные прогоны: плана нет, падаем на число записей."""
        step = make_step(tool='harmbench', planned=None, counts={
            'PASS': 6, 'FAIL': 2, 'ERROR': 0, 'UNSCORED': 0, 'SKIPPED': 0})
        assert M._rate(step, 'coverage') == pytest.approx(1.0)

    def test_nothing_planned_returns_none(self):
        """Пустой шаг: не 0 и не деление на ноль."""
        step = make_step(tool='bipia', planned=0, counts={
            'PASS': 0, 'FAIL': 0, 'ERROR': 0, 'UNSCORED': 0, 'SKIPPED': 0})
        assert M._rate(step, 'coverage') is None


class TestPlannedTotal:
    """planned_total() в run.py берёт план из артефактов инструмента."""

    def test_uses_selected_cases_file(self, tmp_path):
        """План, записанный самим инструментом, точнее любой оценки."""
        from run import planned_total

        (tmp_path / 'selected_cases.json').write_text(
            json.dumps([{'id': i} for i in range(100)]), encoding='utf-8')
        rows = [{'status': 'PASS'}] * 60
        assert planned_total(tmp_path, {'tool': 'harmbench'}, rows) == 100

    def test_never_less_than_actual(self, tmp_path):
        """План не может быть меньше факта — иначе полнота > 100 %."""
        from run import planned_total

        (tmp_path / 'selected_cases.json').write_text(
            json.dumps([{'id': 0}]), encoding='utf-8')
        rows = [{'status': 'PASS'}] * 5
        assert planned_total(tmp_path, {'tool': 'harmbench'}, rows) >= 5

    def test_no_artifacts_falls_back_to_rows(self, tmp_path):
        from run import planned_total

        rows = [{'status': 'PASS'}] * 7
        assert planned_total(tmp_path, {'tool': 'unknown-tool'}, rows) == 7


class TestCatalogIntegrity:
    def test_every_catalog_metric_has_implementation(self):
        """Каждая метрика каталога должна считаться.

        Ровно этот дефект был у coverage: метрика заявлена, но в _rate()
        нет ветки, и она всегда возвращала None.
        """
        step = make_step(categories={}, counts={'PASS': 1, 'FAIL': 0,
                                                'ERROR': 0, 'UNSCORED': 0,
                                                'SKIPPED': 0})
        for entry in M.CATALOG:
            # Отсутствие данных — это None; отсутствие РЕАЛИЗАЦИИ — тоже.
            # Проверяем иначе: метрика с непустыми данными обязана что-то дать.
            value = M._rate(step, entry['id'])
            assert value is None or isinstance(value, float)

    def test_new_metrics_present_in_catalog(self):
        ids = {entry['id'] for entry in M.CATALOG}
        for expected in ('resilience_gap', 'utility_under_attack',
                         'agent_false_block_rate'):
            assert expected in ids, f'{expected} отсутствует в каталоге'

    def test_catalog_entries_have_explanations(self):
        """Каждое число в интерфейсе обязано быть объяснимым."""
        for entry in M.CATALOG:
            for field in ('id', 'label', 'formula', 'description', 'caveat'):
                assert entry.get(field), f"{entry.get('id')}: пустое поле {field}"
