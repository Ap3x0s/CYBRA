"""Во сколько проверок инструмент ПЛАНИРУЕТ уложиться при данном job.

Зачем это нужно. Метрика coverage считала (PASS+FAIL)/всего_записей, где
«всего записей» — то, что воркер УСПЕЛ записать. Воркер, упавший после 60 из
100 запланированных проверок, давал 100 % полноты при 40 % фактического
покрытия: знаменатель уменьшался вместе с числителем. Метрика врала ровно в
тот момент, ради которого её читают.

Знаменатель должен быть плановым. Точное плановое число знает только сам
инструмент: у text_benchmark это selected_cases.json, у BIPIA — кратность
размножения контекстов, у garak — свои пробы. Поэтому воркер сам пишет план в
status.json, а не бэкенд угадывает его по limit и variants.

Здесь — оценочный расчёт для инструментов, которые план не пишут. Он нужен,
чтобы coverage не исчез совсем, но честнее прочитать planned из status.json.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def estimate_planned(job: dict) -> int | None:
    """Сколько проверок инструмент планирует при данном job. None = неизвестно.

    Повторяет выборку из security_suite/adapted.py: balanced() по категории,
    одни и те же seed и limit. Это не дублирование логики ради красоты, а
    единственный способ узнать число, не запуская инструмент: выборка
    детерминирована, поэтому расчёт совпадает с тем, что реально пойдёт в работу.
    """
    tool = job.get('tool')
    limit = int(job.get('limit') or 0)
    variants = job.get('variants') or ['direct']
    seed = int(job.get('seed') or 42)

    try:
        from security_suite.common import balanced
    except Exception:  # noqa: BLE001 — импорт из корня репозитория может не найтись
        import sys

        sys.path.insert(0, str(ROOT))
        try:
            from security_suite.common import balanced
        except Exception:  # noqa: BLE001
            return None

    if tool == 'harmbench':
        rows = _csv_rows(ROOT / 'datasets/harmbench.csv')
        applicable = [r for r in rows if r.get('FunctionalCategory') in ('standard', 'contextual')]
        chosen = balanced(applicable, limit, key='SemanticCategory', seed=seed)
        return len(chosen) * len(variants)

    if tool == 'jailbreakbench':
        harmful = _csv_rows(ROOT / 'datasets/jbb-harmful-behaviors.csv')
        benign = _csv_rows(ROOT / 'datasets/jbb-benign-behaviors.csv')
        h = balanced(harmful, limit, key='Category', seed=seed)
        # У benign в adapted.py variants не размножаются: только direct.
        b = balanced(benign, limit, key='Category', seed=seed)
        return len(h) * len(variants) + len(b)

    if tool == 'security-regression':
        # Свой набор кейсов; план пишется в selected_cases.json самим модулем.
        return None

    if tool == 'promptfoo':
        rows = []
        path = ROOT / 'datasets/corporate.jsonl'
        if path.exists():
            import json

            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        return len(balanced(rows, limit, seed=seed))

    # garak, pyrit, agentdojo, bipia: план зависит от внутренней логики
    # инструмента (пробы, шаги агента, кратность размножения контекстов).
    # Угадывать не будем — пусть воркер напишет точное число.
    return None
