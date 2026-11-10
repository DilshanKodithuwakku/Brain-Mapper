"""
DeepSeek Extension Progress and Quality Auditor.

Audits deepseek_annotations.jsonl for dataset completeness, duplicates,
score distributions, and confidence metrics across the 6 cognitive skills.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
ANNOTATIONS_FILE = BASE_DIR / "data" / "deepseek_annotations.jsonl"
FAILURES_FILE = BASE_DIR / "data" / "deepseek_failures.jsonl"
TOTAL_EXPECTED = 7652
REQUIRED_SKILLS = [
    "attention",
    "working_memory",
    "logical_reasoning",
    "language_processing",
    "critical_thinking",
    "metacognition",
]


def audit() -> None:
    print("=" * 65)
    print("  DeepSeek Annotations Audit & Progress Report")
    print("=" * 65)

    if not ANNOTATIONS_FILE.exists():
        print(f"\n[INFO] No annotations file found at: {ANNOTATIONS_FILE}")
        print(f"Progress: 0 / {TOTAL_EXPECTED} (0.0%)\n")
        return

    records = []
    question_ids = []
    confidences = []
    skill_scores = {s: [] for s in REQUIRED_SKILLS}

    with ANNOTATIONS_FILE.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
                qid = int(rec["question_id"])
                question_ids.append(qid)
                confidences.append(float(rec.get("confidence", 0.0)))
                for s in REQUIRED_SKILLS:
                    skill_scores[s].append(int(rec[s]))
            except Exception as e:
                print(f"[WARN] Failed parsing line {line_num}: {e}")

    total_records = len(records)
    unique_ids = set(question_ids)
    duplicates = total_records - len(unique_ids)
    missing_ids = set(range(TOTAL_EXPECTED)) - unique_ids
    progress_pct = (len(unique_ids) / TOTAL_EXPECTED) * 100

    failures_count = 0
    if FAILURES_FILE.exists():
        with FAILURES_FILE.open(encoding="utf-8") as f:
            failures_count = sum(1 for line in f if line.strip())

    print(f"Total Records Extracted : {total_records}")
    print(f"Unique Questions Done   : {len(unique_ids)} / {TOTAL_EXPECTED} ({progress_pct:.2f}%)")
    print(f"Duplicate Question IDs  : {duplicates}")
    print(f"Unannotated Questions   : {len(missing_ids)}")
    print(f"Recorded Failures       : {failures_count}")
    if confidences:
        print(f"Average Confidence      : {sum(confidences) / len(confidences):.3f}")

    print("\nCognitive Skills Score Distributions (0 - 3):")
    print("-" * 65)
    print(f"{'Skill':<22} {'Mean':<8} {'Score 0':<10} {'Score 1':<10} {'Score 2':<10} {'Score 3':<10}")
    print("-" * 65)

    for skill in REQUIRED_SKILLS:
        scores = skill_scores[skill]
        if scores:
            mean_val = sum(scores) / len(scores)
            counts = Counter(scores)
            print(
                f"{skill:<22} {mean_val:<8.2f} "
                f"{counts.get(0, 0):<10} {counts.get(1, 0):<10} "
                f"{counts.get(2, 0):<10} {counts.get(3, 0):<10}"
            )
        else:
            print(f"{skill:<22} N/A")

    print("=" * 65)

    if len(unique_ids) == TOTAL_EXPECTED:
        print("  STATUS: 100% COMPLETE! Ready for project export aggregation.")
    else:
        print(f"  STATUS: IN PROGRESS ({TOTAL_EXPECTED - len(unique_ids)} remaining).")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    audit()
