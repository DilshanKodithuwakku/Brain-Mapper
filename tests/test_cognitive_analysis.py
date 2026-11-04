import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from brain_mapper.cognitive_analysis.pipeline import annotate_questions
from brain_mapper.cognitive_analysis.quality import create_quality_outputs
from brain_mapper.cognitive_analysis.sampling import sample_pilot
from brain_mapper.cognitive_analysis.schemas import CognitiveScores


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_scores_reject_values_outside_taxonomy_scale():
    with pytest.raises(ValidationError):
        CognitiveScores(
            attention=4,
            working_memory=1,
            logical_reasoning=1,
            language_processing=1,
            critical_thinking=1,
            metacognition=0,
            confidence=0.9,
            short_rationale="Invalid attention score.",
        )


def test_pilot_sampling_is_exact_and_deterministic(tmp_path):
    inputs = [
        {"question_id": index, "question": "word " * (index + 1), "options": {}}
        for index in range(20)
    ]
    input_path = tmp_path / "input.jsonl"
    metadata_path = tmp_path / "questions.csv"
    first_output = tmp_path / "first.jsonl"
    second_output = tmp_path / "second.jsonl"
    _write_jsonl(input_path, inputs)
    with metadata_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question_id", "question_type"])
        writer.writeheader()
        for index in range(20):
            writer.writerow(
                {"question_id": index, "question_type": "fill_blank" if index < 10 else "choice"}
            )

    first = sample_pilot(input_path, metadata_path, first_output, sample_size=8, seed=42)
    second = sample_pilot(input_path, metadata_path, second_output, sample_size=8, seed=42)

    assert len(first) == 8
    assert first == second
    assert {row["sampling_stratum"].split(":")[0] for row in first} == {
        "fill_blank",
        "choice",
    }


class _FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self):
        self.last_usage = {"prompt_token_count": 10}

    def annotate(self, prompt, image_paths=None):
        return CognitiveScores(
            attention=1,
            working_memory=2,
            logical_reasoning=2,
            language_processing=1,
            critical_thinking=0,
            metacognition=0,
            confidence=0.9,
            short_rationale="A concise test rationale.",
        )


def test_pipeline_resumes_and_quality_exports_features(tmp_path):
    questions = [
        {"question_id": 1, "question": "What is 2 + 2?", "options": {}},
        {"question_id": 2, "question": "What is 3 + 3?", "options": {}},
    ]
    sample_path = tmp_path / "sample.jsonl"
    output_path = tmp_path / "annotations.jsonl"
    failure_path = tmp_path / "failures.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(sample_path, questions)
    config = {"pipeline_version": "1", "taxonomy_version": "1", "prompt_version": "1"}

    first = annotate_questions(
        questions,
        output_path,
        failure_path,
        manifest_path,
        _FakeProvider(),
        config,
        max_attempts=1,
        initial_backoff_seconds=0,
        request_delay_seconds=0,
    )
    second = annotate_questions(
        questions,
        output_path,
        failure_path,
        manifest_path,
        _FakeProvider(),
        config,
        max_attempts=1,
        initial_backoff_seconds=0,
        request_delay_seconds=0,
    )

    assert first["annotated"] == 2
    assert second["skipped"] == 2
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 2

    report = create_quality_outputs(
        sample_path,
        output_path,
        tmp_path / "report.json",
        tmp_path / "review.csv",
        tmp_path / "features.csv",
    )
    assert report["coverage"] == 1.0
    assert report["ready_for_human_review"] is True
    assert report["ready_for_full_annotation"] is False
    assert report["full_annotation_gate"] == "blocked_pending_human_review"
    assert len((tmp_path / "features.csv").read_text(encoding="utf-8").splitlines()) == 3
