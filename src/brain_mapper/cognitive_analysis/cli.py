"""Command-line workflow for sampling and quality control."""

from __future__ import annotations

import argparse
import json

from .configuration import DEFAULT_CONFIG, load_config, resolve_path
from .quality import create_quality_outputs
from .sampling import sample_pilot


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
    parser.add_argument("command", choices=("sample", "quality"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "sample":
        _sample(config)
    elif args.command == "quality":
        _quality(config)


if __name__ == "__main__":
    main()
