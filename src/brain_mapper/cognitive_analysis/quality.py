"""Quality checks, human-review template, and KT feature export."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from .sampling import load_jsonl
from .schemas import SKILL_NAMES, AnnotationRecord


def create_quality_outputs(
    sample_path: Path,
    annotation_path: Path,
    report_path: Path,
    review_path: Path,
    feature_path: Path,
    low_confidence_threshold: float = 0.60,
    dominant_score_fraction_threshold: float = 0.75,
    dominant_confidence_fraction_threshold: float = 0.80,
) -> dict[str, Any]:
    sample = load_jsonl(sample_path)
    raw_annotations = load_jsonl(annotation_path) if annotation_path.exists() else []
    annotations = [AnnotationRecord.model_validate(row) for row in raw_annotations]
    expected_ids = {int(row["question_id"]) for row in sample}
    observed_ids = [row.question_id for row in annotations]
    duplicate_ids = sorted(qid for qid, count in Counter(observed_ids).items() if count > 1)
    missing_ids = sorted(expected_ids - set(observed_ids))
    low_confidence = sorted(
        row.question_id for row in annotations if row.confidence < low_confidence_threshold
    )
    usage_totals: dict[str, int] = {}
    for row in annotations:
        for key, value in row.usage.items():
            if isinstance(value, int):
                usage_totals[key] = usage_totals.get(key, 0) + value

    warnings: list[str] = []
    distributions: dict[str, Any] = {}
    for skill in SKILL_NAMES:
        values = [getattr(row, skill) for row in annotations]
        counts = {str(score): values.count(score) for score in range(4)}
        dominant_fraction = max(counts.values()) / len(values) if values else 0
        if dominant_fraction > dominant_score_fraction_threshold:
            warnings.append(
                f"{skill} has {dominant_fraction:.1%} of scores in one category; "
                "review rubric calibration."
            )
        distributions[skill] = {
            "counts": counts,
            "mean": round(mean(values), 4) if values else None,
            "unused_scores": [score for score in range(4) if score not in values],
            "dominant_score_fraction": round(dominant_fraction, 4),
        }

    confidence_counts = Counter(row.confidence for row in annotations)
    dominant_confidence_fraction = (
        max(confidence_counts.values()) / len(annotations) if annotations else 0
    )
    if dominant_confidence_fraction > dominant_confidence_fraction_threshold:
        warnings.append(
            f"{dominant_confidence_fraction:.1%} of annotations use the same confidence value; "
            "LLM confidence is poorly calibrated and should not be treated as a probability."
        )

    report = {
        "expected": len(expected_ids),
        "annotated_records": len(annotations),
        "unique_annotated": len(set(observed_ids)),
        "coverage": round(len(set(observed_ids) & expected_ids) / len(expected_ids), 4)
        if expected_ids
        else 0,
        "missing_question_ids": missing_ids,
        "duplicate_question_ids": duplicate_ids,
        "low_confidence_threshold": low_confidence_threshold,
        "low_confidence_question_ids": low_confidence,
        "low_confidence_fraction": round(len(low_confidence) / len(annotations), 4)
        if annotations
        else 0,
        "confidence_counts": {
            str(value): count for value, count in sorted(confidence_counts.items())
        },
        "dominant_confidence_fraction": round(dominant_confidence_fraction, 4),
        "usage_totals": usage_totals,
        "skill_distributions": distributions,
        "ready_for_human_review": not missing_ids and not duplicate_ids,
        "calibration_warnings": warnings,
        "ready_for_full_annotation": False,
        "full_annotation_gate": "blocked_pending_human_review",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    question_lookup = {int(row["question_id"]): row["question"] for row in sample}
    review_columns = [
        "question_id",
        "question",
        *SKILL_NAMES,
        "confidence",
        "short_rationale",
        "human_decision",
        "human_notes",
    ]
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_columns)
        writer.writeheader()
        for row in annotations:
            writer.writerow(
                {
                    "question_id": row.question_id,
                    "question": question_lookup.get(row.question_id, ""),
                    **{skill: getattr(row, skill) for skill in SKILL_NAMES},
                    "confidence": row.confidence,
                    "short_rationale": row.short_rationale,
                    "human_decision": "",
                    "human_notes": "",
                }
            )

    feature_columns = [
        "question_id",
        *SKILL_NAMES,
        "annotation_confidence",
        "review_status",
        "taxonomy_version",
        "prompt_version",
        "annotation_model",
    ]
    with feature_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=feature_columns)
        writer.writeheader()
        for row in annotations:
            writer.writerow(
                {
                    "question_id": row.question_id,
                    **{skill: getattr(row, skill) for skill in SKILL_NAMES},
                    "annotation_confidence": row.confidence,
                    "review_status": row.review_status,
                    "taxonomy_version": row.taxonomy_version,
                    "prompt_version": row.prompt_version,
                    "annotation_model": row.model,
                }
            )
    return report
