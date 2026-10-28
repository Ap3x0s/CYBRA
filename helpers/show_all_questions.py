"""
Запускается для вывода всех пар вопросов-ответов

Example usage: python helpers/show_all_questions.py reports/reports-garak/
"""

from pathlib import Path
import json
import sys

root = Path(sys.argv[1])
number = 0

for path in root.rglob("*.jsonl"):
    if path.name == "records.jsonl":
        continue

    for line in path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if record.get("entry_type") != "attempt":
            continue

        number += 1

        print("\n" + "=" * 100)
        print(f"ATTEMPT: {number}")
        print(f"PROBE: {record.get('probe')}")
        print(f"GOAL: {record.get('goal')}")

        print("\nPROMPT:")
        print(json.dumps(
            record.get("prompt"),
            ensure_ascii=False,
            indent=2,
        ))

        print("\nOUTPUT:")
        outputs = record.get("outputs")
        if outputs is None:
            outputs = record.get("output")
        print(json.dumps(
            outputs,
            ensure_ascii=False,
            indent=2,
        ))

        print("\nDETECTORS:")
        print(json.dumps(
            record.get("detector_results"),
            ensure_ascii=False,
            indent=2,
        ))

print(f"\nВсего attempts: {number}")