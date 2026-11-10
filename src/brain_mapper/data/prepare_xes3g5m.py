"""Prepare XES3G5M question metadata and question-level interactions.

The official XES3G5M release supplies student sequences and Chinese metadata.
ExRec supplies an English translation keyed by the same question identifiers.
This module combines those sources without copying answer or KC labels into the
model-safe question table used for cognitive annotation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


IMAGE_REFERENCE_PATTERN = re.compile(r"question_\d+-image_\d+")
QUESTION_OUTPUT_COLUMNS = [
    "question_id",
    "question_text",
    "source_content_english",
    "options_json",
    "question_type",
    "requires_image",
    "image_refs_json",
    "image_paths_json",
    "all_images_available",
]
REFERENCE_OUTPUT_COLUMNS = [
    "question_id",
    "correct_answers_json",
    "kc_routes_json",
    "source_type",
]
INTERACTION_OUTPUT_COLUMNS = [
    "split",
    "fold",
    "student_id",
    "student_interaction_index",
    "source_row",
    "source_position",
    "question_id",
    "concept_ids",
    "is_correct",
    "timestamp_ms",
    "requires_image",
]
REQUIRED_SEQUENCE_COLUMNS = {
    "fold",
    "uid",
    "questions",
    "concepts",
    "responses",
    "timestamps",
}


def _set_csv_field_limit() -> None:
    """Allow the long comma-separated sequence fields in test_quelevel.csv."""
    limit = 2**31 - 1
    while limit > 0:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _split_sequence(value: str) -> list[str]:
    return value.split(",") if value else []


def _atomic_csv_writer(path: Path, fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    handle = temporary.open("w", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    return temporary, handle, writer


def _write_question_tables(
    english_questions_path: Path,
    image_directory: Path,
    output_directory: Path,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    questions = json.loads(english_questions_path.read_text(encoding="utf-8"))
    if not isinstance(questions, dict):
        raise ValueError(f"{english_questions_path} must contain a JSON object")

    images_by_stem = {
        path.stem: path
        for path in image_directory.iterdir()
        if path.is_file()
    }
    model_safe_path = output_directory / "questions.csv"
    reference_path = output_directory / "question_reference.csv"
    llm_input_path = output_directory / "cognitive_annotation_input_text_only.jsonl"
    model_tmp, model_handle, model_writer = _atomic_csv_writer(
        model_safe_path, QUESTION_OUTPUT_COLUMNS
    )
    reference_tmp, reference_handle, reference_writer = _atomic_csv_writer(
        reference_path, REFERENCE_OUTPUT_COLUMNS
    )
    llm_tmp = llm_input_path.with_suffix(llm_input_path.suffix + ".tmp")
    llm_handle = llm_tmp.open("w", encoding="utf-8", newline="\n")

    metadata_by_id: dict[int, dict[str, Any]] = {}
    missing_image_refs: set[str] = set()
    type_counts: Counter[str] = Counter()
    image_question_count = 0
    text_only_count = 0
    try:
        for raw_id, record in sorted(questions.items(), key=lambda item: int(item[0])):
            if not isinstance(record, dict):
                raise ValueError(f"Question {raw_id} must be a JSON object")
            question_id = int(raw_id)
            question_text = str(record.get("question") or record.get("content") or "").strip()
            if not question_text:
                raise ValueError(f"Question {question_id} has no English text")
            options = record.get("options") or {}
            searchable = " ".join(
                [
                    question_text,
                    str(record.get("content") or ""),
                    _json_cell(options),
                ]
            )
            image_refs = sorted(set(IMAGE_REFERENCE_PATTERN.findall(searchable)))
            image_paths = [str(images_by_stem[ref]) for ref in image_refs if ref in images_by_stem]
            unavailable = set(image_refs) - images_by_stem.keys()
            missing_image_refs.update(unavailable)
            requires_image = bool(image_refs)
            all_images_available = not unavailable
            source_type = str(record.get("type") or "")
            question_type = {
                "填空": "fill_blank",
                "单选": "single_choice",
                "0": "fill_blank",
                "1": "single_choice",
            }.get(source_type, "unknown")
            type_counts[question_type] += 1
            image_question_count += int(requires_image)
            text_only_count += int(not requires_image)

            model_writer.writerow(
                {
                    "question_id": question_id,
                    "question_text": question_text,
                    "source_content_english": str(record.get("content") or ""),
                    "options_json": _json_cell(options),
                    "question_type": question_type,
                    "requires_image": int(requires_image),
                    "image_refs_json": _json_cell(image_refs),
                    "image_paths_json": _json_cell(image_paths),
                    "all_images_available": int(all_images_available),
                }
            )
            reference_writer.writerow(
                {
                    "question_id": question_id,
                    "correct_answers_json": _json_cell(record.get("answer") or []),
                    "kc_routes_json": _json_cell(record.get("kc_routes") or []),
                    "source_type": source_type,
                }
            )
            if not requires_image:
                llm_handle.write(
                    _json_cell(
                        {
                            "question_id": question_id,
                            "question": question_text,
                            "options": options,
                        }
                    )
                    + "\n"
                )
            metadata_by_id[question_id] = {
                "requires_image": requires_image,
                "all_images_available": all_images_available,
            }
    finally:
        model_handle.close()
        reference_handle.close()
        llm_handle.close()

    model_tmp.replace(model_safe_path)
    reference_tmp.replace(reference_path)
    llm_tmp.replace(llm_input_path)
    summary = {
        "questions": len(metadata_by_id),
        "text_only_questions": text_only_count,
        "image_dependent_questions": image_question_count,
        "question_type_counts": dict(type_counts),
        "available_image_files": len(images_by_stem),
        "missing_referenced_images": len(missing_image_refs),
        "missing_image_refs": sorted(missing_image_refs),
    }
    return metadata_by_id, summary


def _sequence_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    _set_csv_field_limit()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_SEQUENCE_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        for source_row, row in enumerate(reader, start=2):
            yield source_row, row


def _iter_interactions(
    path: Path,
    split: str,
    question_metadata: dict[int, dict[str, Any]],
    student_positions: defaultdict[str, int],
) -> Iterator[dict[str, Any]]:
    for source_row, row in _sequence_rows(path):
        vectors = {
            key: _split_sequence(row[key])
            for key in ("questions", "concepts", "responses", "timestamps")
        }
        lengths = {key: len(value) for key, value in vectors.items()}
        if len(set(lengths.values())) != 1:
            raise ValueError(f"{path}:{source_row} has unequal sequence lengths: {lengths}")
        masks = _split_sequence(row.get("selectmasks", ""))
        if masks and len(masks) != lengths["questions"]:
            raise ValueError(
                f"{path}:{source_row} has {len(masks)} masks for "
                f"{lengths['questions']} interactions"
            )

        student_id = row["uid"]
        for position, (qid, concepts, response, timestamp) in enumerate(
            zip(
                vectors["questions"],
                vectors["concepts"],
                vectors["responses"],
                vectors["timestamps"],
                strict=True,
            )
        ):
            mask = masks[position] if masks else "1"
            if mask == "-1" or qid == "-1":
                continue
            question_id = int(qid)
            if question_id not in question_metadata:
                raise ValueError(
                    f"{path}:{source_row} references unknown question_id {question_id}"
                )
            if response not in {"0", "1"}:
                raise ValueError(f"{path}:{source_row} has invalid response {response!r}")
            timestamp_ms = int(timestamp)
            if timestamp_ms < 0:
                raise ValueError(f"{path}:{source_row} has invalid timestamp {timestamp!r}")
            interaction_index = student_positions[student_id]
            student_positions[student_id] += 1
            yield {
                "split": split,
                "fold": int(row["fold"]),
                "student_id": student_id,
                "student_interaction_index": interaction_index,
                "source_row": source_row,
                "source_position": position,
                "question_id": question_id,
                "concept_ids": concepts,
                "is_correct": int(response),
                "timestamp_ms": timestamp_ms,
                "requires_image": int(question_metadata[question_id]["requires_image"]),
            }


def _write_interactions(
    sources: Iterable[tuple[str, Path]],
    question_metadata: dict[int, dict[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    temporary, handle, writer = _atomic_csv_writer(output_path, INTERACTION_OUTPUT_COLUMNS)
    student_positions: defaultdict[str, int] = defaultdict(int)
    last_timestamp: dict[str, int] = {}
    split_rows: Counter[str] = Counter()
    split_students: defaultdict[str, set[str]] = defaultdict(set)
    folds: Counter[str] = Counter()
    questions_seen: set[int] = set()
    correct = 0
    image_dependent = 0
    timestamp_order_violations = 0
    try:
        for split, source in sources:
            for record in _iter_interactions(
                source, split, question_metadata, student_positions
            ):
                student_id = str(record["student_id"])
                timestamp = int(record["timestamp_ms"])
                previous = last_timestamp.get(student_id)
                if previous is not None and timestamp < previous:
                    timestamp_order_violations += 1
                last_timestamp[student_id] = timestamp
                writer.writerow(record)
                split_rows[split] += 1
                split_students[split].add(student_id)
                folds[f"{split}:{record['fold']}"] += 1
                questions_seen.add(int(record["question_id"]))
                correct += int(record["is_correct"])
                image_dependent += int(record["requires_image"])
    finally:
        handle.close()
    temporary.replace(output_path)

    total_rows = sum(split_rows.values())
    sequence_lengths = list(student_positions.values())
    train_students = split_students.get("train_valid", set())
    test_students = split_students.get("test", set())
    questions_without_interactions = sorted(set(question_metadata) - questions_seen)
    return {
        "interactions": total_rows,
        "split_interactions": dict(split_rows),
        "unique_students": len(student_positions),
        "split_unique_students": {
            split: len(students) for split, students in split_students.items()
        },
        "train_test_student_overlap": len(train_students & test_students),
        "unique_questions_in_interactions": len(questions_seen),
        "questions_without_interactions": len(questions_without_interactions),
        "question_ids_without_interactions": questions_without_interactions,
        "correct_rate": correct / total_rows if total_rows else None,
        "image_dependent_interactions": image_dependent,
        "text_only_interactions": total_rows - image_dependent,
        "fold_interactions": dict(folds),
        "minimum_student_sequence_length": min(sequence_lengths, default=0),
        "maximum_student_sequence_length": max(sequence_lengths, default=0),
        "timestamp_order_violations": timestamp_order_violations,
    }


def prepare_xes3g5m(
    official_root: Path,
    english_questions_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Create model-safe questions, reference labels, and flat interactions."""
    train_path = official_root / "question_level" / "train_valid_sequences_quelevel.csv"
    test_path = official_root / "question_level" / "test_quelevel.csv"
    image_directory = official_root / "metadata" / "images"
    required_paths = [train_path, test_path, image_directory, english_questions_path]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing XES3G5M inputs: " + ", ".join(missing))

    output_directory.mkdir(parents=True, exist_ok=True)
    question_metadata, question_summary = _write_question_tables(
        english_questions_path, image_directory, output_directory
    )
    interaction_summary = _write_interactions(
        [("train_valid", train_path), ("test", test_path)],
        question_metadata,
        output_directory / "interactions.csv",
    )
    summary: dict[str, Any] = {
        "dataset": "XES3G5M with ExRec English questions",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "official_root": str(official_root.resolve()),
        "english_questions_source": str(english_questions_path.resolve()),
        "outputs": {
            "questions": str((output_directory / "questions.csv").resolve()),
            "question_reference": str(
                (output_directory / "question_reference.csv").resolve()
            ),
            "cognitive_annotation_input_text_only": str(
                (output_directory / "cognitive_annotation_input_text_only.jsonl").resolve()
            ),
            "interactions": str((output_directory / "interactions.csv").resolve()),
        },
        "excluded_source": str(
            (official_root / "question_level" / "test_window_sequences_quelevel.csv").resolve()
        ),
        "excluded_source_reason": (
            "Overlapping evaluation windows repeat student history and would duplicate "
            "interactions in a canonical event table."
        ),
        "question_summary": question_summary,
        "interaction_summary": interaction_summary,
        "limitations": [
            "The released sequences contain binary correctness, not each student's raw answer.",
            "Training sequences were truncated by the dataset authors, so the original complete "
            "interaction history cannot be reconstructed.",
            "Question answers and KC routes are isolated in question_reference.csv to avoid "
            "leakage into cognitive-skill annotation.",
        ],
    }
    summary_path = output_directory / "processing_summary.json"
    temporary_summary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    temporary_summary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary_summary.replace(summary_path)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--official-root",
        type=Path,
        default=Path("data/raw/xes3g5m"),
        help="Extracted official XES3G5M directory",
    )
    parser.add_argument(
        "--english-questions",
        type=Path,
        default=Path("data/raw/xes3g5m/metadata/questions_translated.json"),
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/processed/xes3g5m"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = prepare_xes3g5m(
        official_root=args.official_root,
        english_questions_path=args.english_questions,
        output_directory=args.output_directory,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
