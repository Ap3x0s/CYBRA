from __future__ import annotations

import json
from pathlib import Path

from suite.evaluators.leakage import find_leak


DATASET_DIR = Path("datasets/security_regression")


def load_cases(limit: int | None = None) -> list[dict]:
    cases: list[dict] = []

    for dataset_path in sorted(DATASET_DIR.glob("*.jsonl")):
        with dataset_path.open(encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                cases.append(json.loads(line))

                if limit is not None and len(cases) >= limit:
                    return cases

    return cases


def run_security_regression(
    *,
    model: str,
    client,
    output_file: Path,
    limit: int | None = None,
) -> dict:
    cases = load_cases(limit)
    counts = {
        "PASS": 0,
        "FAIL": 0,
        "ERROR": 0,
        "UNSCORED": 0,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as output:
        for case in cases:
            try:
                answer = client.chat(
                    model=model,
                    messages=case["messages"],
                    temperature=0,
                )

                if not answer or not answer.strip():
                    status = "UNSCORED"
                    reason = "Модель вернула пустой ответ."
                    evidence = None
                else:
                    leak = find_leak(
                        answer=answer,
                        forbidden=case["forbidden"],
                        encodings=case.get(
                            "encodings",
                            ["plain", "compact", "base64"],
                        ),
                    )

                    if leak:
                        status = "FAIL"
                        reason = (
                            "Модель раскрыла защищённый синтетический "
                            f"PII-маркер в формате {leak['encoding']}."
                        )
                        evidence = leak["evidence"]
                    else:
                        status = "PASS"
                        reason = (
                            "Защищённые PII-маркеры в ответе "
                            "не обнаружены."
                        )
                        evidence = None

                record = {
                    "schema_version": 1,
                    "model": model,
                    "tool": "security-regression",
                    "mode": "deterministic synthetic canary evaluation",
                    "case_id": case["id"],
                    "category": case["category"],
                    "severity": case.get("severity", "medium"),
                    "status": status,
                    "unit": "case",
                    "prompt": case["messages"][-1]["content"],
                    "answer": answer,
                    "reason": reason,
                    "evidence": evidence,
                }

            except Exception as error:
                status = "ERROR"
                record = {
                    "schema_version": 1,
                    "model": model,
                    "tool": "security-regression",
                    "mode": "deterministic synthetic canary evaluation",
                    "case_id": case["id"],
                    "category": case["category"],
                    "severity": case.get("severity", "medium"),
                    "status": status,
                    "unit": "case",
                    "reason": f"{type(error).__name__}: {error}",
                }

            counts[status] += 1

            output.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    return {
        "status": "COMPLETE",
        "counts": counts,
        "cases": len(cases),
    }