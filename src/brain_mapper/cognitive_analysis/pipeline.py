"""Resumable cognitive annotation pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .configuration import DEFAULT_CONFIG, load_config, resolve_path
from .prompting import build_prompt, load_prompt_template
from .schemas import AnnotationRecord, CognitiveScores


class AnnotationProvider(Protocol):
    provider_name: str
    model: str
    last_usage: dict[str, Any]

    def annotate(self, prompt: str, image_paths: list[str] | None = None) -> CognitiveScores: ...


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _completed_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {int(row["question_id"]) for row in _load_jsonl(path)}


def load_image_questions(metadata_path: Path) -> list[dict[str, Any]]:
    """Convert image-dependent question metadata into annotation inputs."""
    rows: list[dict[str, Any]] = []
    with metadata_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["requires_image"] != "1":
                continue
            paths = json.loads(row["image_paths_json"])
            rows.append(
                {
                    "question_id": int(row["question_id"]),
                    "question": row["question_text"],
                    "options": json.loads(row["options_json"]),
                    "image_paths": paths,
                }
            )
    return rows


def annotate_questions(
    questions: list[dict[str, Any]],
    output_path: Path,
    failure_path: Path,
    manifest_path: Path,
    provider: AnnotationProvider,
    config: dict[str, Any],
    *,
    max_attempts: int,
    initial_backoff_seconds: float,
    request_delay_seconds: float,
) -> dict[str, Any]:
    """Annotate incrementally; existing successful question IDs are skipped."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _completed_ids(output_path)
    prompt_template = load_prompt_template()
    started = datetime.now(UTC)
    counts = {"requested": len(questions), "annotated": 0, "skipped": 0, "failed": 0}
    usage_totals: dict[str, int] = {}

    with (
        output_path.open("a", encoding="utf-8", newline="\n") as success_handle,
        failure_path.open("a", encoding="utf-8", newline="\n") as failure_handle,
    ):
        for position, question in enumerate(questions, start=1):
            question_id = int(question["question_id"])
            if question_id in completed:
                counts["skipped"] += 1
                continue

            prompt, prompt_hash = build_prompt(question, prompt_template)
            last_error = ""
            scores: CognitiveScores | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    scores = provider.annotate(prompt, question.get("image_paths"))
                    break
                # Provider libraries expose several transport and response exceptions;
                # all must be persisted so a long batch remains resumable.
                except Exception as error:  # noqa: BLE001
                    last_error = f"{type(error).__name__}: {error}"
                    if "400 INVALID_ARGUMENT" in last_error:
                        break
                    if attempt < max_attempts:
                        time.sleep(initial_backoff_seconds * (2 ** (attempt - 1)))

            if scores is None:
                failure = {
                    "question_id": question_id,
                    "attempts": max_attempts,
                    "error": last_error,
                    "failed_at_utc": datetime.now(UTC).isoformat(),
                }
                failure_handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
                failure_handle.flush()
                counts["failed"] += 1
            else:
                usage = getattr(provider, "last_usage", {}) or {}
                for key, value in usage.items():
                    if isinstance(value, int):
                        usage_totals[key] = usage_totals.get(key, 0) + value
                record = AnnotationRecord(
                    question_id=question_id,
                    **scores.model_dump(),
                    provider=provider.provider_name,
                    model=provider.model,
                    pipeline_version=str(config["pipeline_version"]),
                    taxonomy_version=str(config["taxonomy_version"]),
                    prompt_version=str(config["prompt_version"]),
                    prompt_sha256=prompt_hash,
                    input_mode="image" if question.get("image_paths") else "text",
                    image_paths=question.get("image_paths") or [],
                    usage=usage,
                )
                success_handle.write(record.model_dump_json() + "\n")
                success_handle.flush()
                completed.add(question_id)
                counts["annotated"] += 1

            if position % 10 == 0 or position == len(questions):
                print(
                    f"Processed {position}/{len(questions)} "
                    f"(new={counts['annotated']}, skipped={counts['skipped']}, "
                    f"failed={counts['failed']})",
                    flush=True,
                )
            if request_delay_seconds and position < len(questions):
                time.sleep(request_delay_seconds)

    manifest = {
        **counts,
        "total_successful_records": len(completed),
        "unresolved_question_ids": sorted(
            int(question["question_id"])
            for question in questions
            if int(question["question_id"]) not in completed
        ),
        "provider": provider.provider_name,
        "model": provider.model,
        "pipeline_version": str(config["pipeline_version"]),
        "taxonomy_version": str(config["taxonomy_version"]),
        "prompt_version": str(config["prompt_version"]),
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "output": str(output_path),
        "failures": str(failure_path),
        "usage_totals_this_run": usage_totals,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def run_annotation(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    provider_config = config["provider"]
    from .gemini import GeminiAnnotator

    provider = GeminiAnnotator(
        model=args.model or provider_config["model"],
        max_output_tokens=int(provider_config["max_output_tokens"]),
    )
    if args.input_mode == "image":
        questions = load_image_questions(resolve_path(args.input))
    else:
        questions = _load_jsonl(resolve_path(args.input))
    if args.limit is not None:
        questions = questions[: args.limit]
    return annotate_questions(
        questions,
        resolve_path(args.output),
        resolve_path(args.failures),
        resolve_path(args.manifest),
        provider,
        config,
        max_attempts=int(provider_config["max_attempts"]),
        initial_backoff_seconds=float(provider_config["initial_backoff_seconds"]),
        request_delay_seconds=float(provider_config["request_delay_seconds"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--failures", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--input-mode", choices=("text", "image"), default="text")
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int)
    return parser


def main() -> None:
    manifest = run_annotation(build_parser().parse_args())
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
