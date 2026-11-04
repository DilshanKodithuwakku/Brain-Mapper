"""Deterministic, stratified pilot sampling."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def _length_band(text: str) -> str:
    length = len(text)
    if length <= 120:
        return "short"
    if length <= 300:
        return "medium"
    return "long"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sample_pilot(
    input_path: Path,
    metadata_path: Path,
    output_path: Path,
    sample_size: int = 200,
    seed: int = 42,
) -> list[dict[str, Any]]:
    candidates = load_jsonl(input_path)
    if sample_size <= 0 or sample_size > len(candidates):
        raise ValueError(f"sample_size must be between 1 and {len(candidates)}")

    with metadata_path.open(encoding="utf-8", newline="") as handle:
        metadata = {int(row["question_id"]): row for row in csv.DictReader(handle)}

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        question_id = int(item["question_id"])
        question_type = metadata.get(question_id, {}).get("question_type", "unknown")
        enriched = dict(item)
        enriched["sampling_stratum"] = f"{question_type}:{_length_band(item['question'])}"
        groups[(question_type, _length_band(item["question"]))].append(enriched)

    rng = random.Random(seed)
    for rows in groups.values():
        rng.shuffle(rows)

    selected: list[dict[str, Any]] = []
    allocations: dict[tuple[str, str], int] = {}
    for key, rows in groups.items():
        allocations[key] = min(len(rows), int(sample_size * len(rows) / len(candidates)))

    # Ensure every populated stratum appears when the requested sample allows it.
    if sample_size >= len(groups):
        for key in groups:
            allocations[key] = max(1, allocations[key])

    while sum(allocations.values()) > sample_size:
        eligible = [key for key, count in allocations.items() if count > 1]
        key = max(eligible, key=lambda item: allocations[item] / len(groups[item]))
        allocations[key] -= 1
    while sum(allocations.values()) < sample_size:
        eligible = [key for key, rows in groups.items() if allocations[key] < len(rows)]
        key = max(
            eligible,
            key=lambda item: len(groups[item]) * sample_size / len(candidates) - allocations[item],
        )
        allocations[key] += 1

    for key, rows in groups.items():
        selected.extend(rows[: allocations[key]])
    selected.sort(key=lambda item: int(item["question_id"]))
    write_jsonl(output_path, selected)
    return selected
