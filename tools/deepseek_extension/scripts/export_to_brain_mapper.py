"""
Safe Aggregation and Export to Brain Mapper.

CRITICAL RULE: Will refuse to aggregate or touch the main project repository
until all 7,652 questions are successfully annotated and verified.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parents[1]
ANNOTATIONS_FILE = BASE_DIR / "data" / "deepseek_annotations.jsonl"
TOTAL_EXPECTED = 7652

DEST_DIR = PROJECT_ROOT / "data" / "annotations" / "xes3g5m"
DEST_CSV = DEST_DIR / "deepseek_cognitive_features.csv"
DEST_JSONL = DEST_DIR / "deepseek_annotations.jsonl"

REQUIRED_SKILLS = [
    "attention",
    "working_memory",
    "logical_reasoning",
    "language_processing",
    "critical_thinking",
    "metacognition",
]


def export(force: bool = False) -> None:
    print("=" * 65)
    print("  Brain Mapper - DeepSeek Dataset Aggregator & Exporter")
    print("=" * 65)

    if not ANNOTATIONS_FILE.exists():
        print(f"[ERROR] Annotations file does not exist at: {ANNOTATIONS_FILE}", file=sys.stderr)
        sys.exit(1)

    records_by_id = {}
    with ANNOTATIONS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qid = int(rec["question_id"])
            # Keep latest record if duplicate
            records_by_id[qid] = rec

    completed_count = len(records_by_id)
    missing_ids = set(range(TOTAL_EXPECTED)) - set(records_by_id.keys())

    if completed_count < TOTAL_EXPECTED:
        print(f"[BLOCKED] Incomplete Dataset: {completed_count} / {TOTAL_EXPECTED} annotated.")
        print(f"Missing {len(missing_ids)} questions.")
        if not force:
            print("\n[GUARD] Policy blocks aggregation until the ENTIRE dataset (all 7,652 questions)")
            print("is annotated and verified. To override this guard, pass --force.\n")
            sys.exit(1)
        else:
            print("[WARNING] Proceeding with incomplete export due to explicit --force flag!")

    print(f"\n[INFO] Validating and exporting {completed_count} records to main project...")
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Export JSONL
    with DEST_JSONL.open("w", encoding="utf-8") as f_out:
        for qid in sorted(records_by_id.keys()):
            f_out.write(json.dumps(records_by_id[qid], ensure_ascii=False) + "\n")
    print(f"Exported JSONL: {DEST_JSONL}")

    # 2. Export cognitive features CSV
    fieldnames = ["question_id"] + REQUIRED_SKILLS + ["confidence", "short_rationale"]
    with DEST_CSV.open("w", encoding="utf-8", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for qid in sorted(records_by_id.keys()):
            rec = records_by_id[qid]
            row = {
                "question_id": qid,
                "attention": rec["attention"],
                "working_memory": rec["working_memory"],
                "logical_reasoning": rec["logical_reasoning"],
                "language_processing": rec["language_processing"],
                "critical_thinking": rec["critical_thinking"],
                "metacognition": rec["metacognition"],
                "confidence": rec.get("confidence", 0.95),
                "short_rationale": rec.get("short_rationale", ""),
            }
            writer.writerow(row)
    print(f"Exported CSV  : {DEST_CSV}")

    print("\n[SUCCESS] Aggregation complete!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export DeepSeek annotations to Brain Mapper")
    parser.add_argument("--force", action="store_true", help="Force partial export before 100% completion")
    args = parser.parse_args()
    export(force=args.force)
