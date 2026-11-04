"""Command-line workflow for sampling, annotation, and quality control."""

from __future__ import annotations

import argparse
import json

from .configuration import DEFAULT_CONFIG, load_config, resolve_path
from .pipeline import annotate_questions
from .quality import create_quality_outputs
from .sampling import load_jsonl, sample_pilot


def _sample(config: dict) -> None:
    pilot = config["pilot"]
    rows = sample_pilot(
        resolve_path(pilot["input"]),
        resolve_path(pilot["question_metadata"]),
        resolve_path(pilot["sample_output"]),
        int(pilot["size"]),
        int(pilot["seed"]),
    )
    print(f"Wrote {len(rows)} pilot questions to {resolve_path(pilot['sample_output'])}")


def _annotate_pilot(config: dict, limit: int | None) -> None:
    from .gemini import GeminiAnnotator

    pilot = config["pilot"]
    provider_config = config["provider"]
    questions = load_jsonl(resolve_path(pilot["sample_output"]))
    if limit is not None:
        questions = questions[:limit]
    provider = GeminiAnnotator(provider_config["model"], int(provider_config["max_output_tokens"]))
    manifest = annotate_questions(
        questions,
        resolve_path(pilot["annotation_output"]),
        resolve_path(pilot["failure_output"]),
        resolve_path(pilot["manifest_output"]),
        provider,
        config,
        max_attempts=int(provider_config["max_attempts"]),
        initial_backoff_seconds=float(provider_config["initial_backoff_seconds"]),
        request_delay_seconds=float(provider_config["request_delay_seconds"]),
    )
    print(json.dumps(manifest, indent=2))


def _quality(config: dict) -> None:
    pilot = config["pilot"]
    report = create_quality_outputs(
        resolve_path(pilot["sample_output"]),
        resolve_path(pilot["annotation_output"]),
        resolve_path(pilot["quality_report"]),
        resolve_path(pilot["review_template"]),
        resolve_path(pilot["feature_output"]),
        float(config["quality"]["low_confidence_threshold"]),
        float(config["quality"]["dominant_score_fraction_threshold"]),
        float(config["quality"]["dominant_confidence_fraction_threshold"]),
    )
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sample", "annotate-pilot", "quality", "run-pilot"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--limit", type=int, help="Annotate only the first N pilot items")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command in {"sample", "run-pilot"}:
        _sample(config)
    if args.command in {"annotate-pilot", "run-pilot"}:
        _annotate_pilot(config, args.limit)
    if args.command in {"quality", "run-pilot"}:
        _quality(config)


if __name__ == "__main__":
    main()
