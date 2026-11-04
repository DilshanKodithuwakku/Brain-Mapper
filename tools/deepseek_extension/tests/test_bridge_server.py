"""
Unit tests for the DeepSeek Extension Bridge Server and AnnotationManager.
"""

import json
import sys
import tempfile
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from tools.deepseek_extension.bridge_server import AnnotationManager, REQUIRED_SKILLS


@pytest.fixture
def mock_questions_csv(tmp_path: Path) -> Path:
    csv_file = tmp_path / "test_questions.csv"
    import csv
    with csv_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question_id", "question_text", "options_json", "image_paths_json", "has_images"])
        writer.writeheader()
        writer.writerow({
            "question_id": "0",
            "question_text": "What is 2 + 2?",
            "options_json": json.dumps(["3", "4", "5"]),
            "image_paths_json": json.dumps([]),
            "has_images": "False",
        })
        writer.writerow({
            "question_id": "1",
            "question_text": "Look at the shape and find the angle.",
            "options_json": json.dumps([]),
            "image_paths_json": json.dumps(["img1.png"]),
            "has_images": "True",
        })
        writer.writerow({
            "question_id": "2",
            "question_text": "Solve for x: 3x = 9",
            "options_json": json.dumps([]),
            "image_paths_json": json.dumps([]),
            "has_images": "False",
        })
    return csv_file


def test_annotation_manager_initialization(mock_questions_csv: Path, monkeypatch, tmp_path: Path):
    test_data_dir = tmp_path / "data"
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.DATA_DIR", test_data_dir)
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.ANNOTATIONS_FILE", test_data_dir / "deepseek_annotations.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.FAILURES_FILE", test_data_dir / "deepseek_failures.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.STATE_FILE", test_data_dir / "state.json")

    manager = AnnotationManager(questions_path=mock_questions_csv)
    status = manager.get_status()

    assert status["total_questions"] == 3
    assert status["completed_count"] == 0
    assert status["remaining_count"] == 3
    assert status["next_question_id"] == 0
    assert not status["done"]


def test_get_next_question_prompt(mock_questions_csv: Path, monkeypatch, tmp_path: Path):
    test_data_dir = tmp_path / "data"
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.DATA_DIR", test_data_dir)
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.ANNOTATIONS_FILE", test_data_dir / "deepseek_annotations.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.FAILURES_FILE", test_data_dir / "deepseek_failures.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.STATE_FILE", test_data_dir / "state.json")

    manager = AnnotationManager(questions_path=mock_questions_csv)
    next_q = manager.get_next_question()

    assert next_q is not None
    assert next_q["question_id"] == 0
    assert "What is 2 + 2?" in next_q["prompt"]
    assert "attention" in next_q["prompt"]
    assert "Options:" in next_q["prompt"]
    assert not next_q["has_images"]
    assert len(next_q["image_urls"]) == 0


def test_get_next_question_multimodal(mock_questions_csv: Path, monkeypatch, tmp_path: Path):
    test_data_dir = tmp_path / "data"
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.DATA_DIR", test_data_dir)
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.ANNOTATIONS_FILE", test_data_dir / "deepseek_annotations.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.FAILURES_FILE", test_data_dir / "deepseek_failures.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.STATE_FILE", test_data_dir / "state.json")

    manager = AnnotationManager(questions_path=mock_questions_csv)
    # Skip Q0
    manager.completed_ids.add(0)
    next_q = manager.get_next_question()

    assert next_q is not None
    assert next_q["question_id"] == 1
    assert next_q["has_images"] is True
    assert len(next_q["image_urls"]) == 1
    assert "/api/image?path=" in next_q["image_urls"][0]
    assert "diagram(s) for this question are attached" in next_q["prompt"]


def test_validate_and_save_annotation(mock_questions_csv: Path, monkeypatch, tmp_path: Path):
    test_data_dir = tmp_path / "data"
    ann_file = test_data_dir / "deepseek_annotations.jsonl"
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.DATA_DIR", test_data_dir)
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.ANNOTATIONS_FILE", ann_file)
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.FAILURES_FILE", test_data_dir / "deepseek_failures.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.STATE_FILE", test_data_dir / "state.json")

    manager = AnnotationManager(questions_path=mock_questions_csv)

    valid_payload = {
        "question_id": 0,
        "scores": {
            "attention": 1,
            "working_memory": 1,
            "logical_reasoning": 2,
            "language_processing": 1,
            "critical_thinking": 0,
            "metacognition": 0,
        },
        "confidence": 0.95,
        "short_rationale": "Simple addition arithmetic.",
    }

    result = manager.validate_and_save_annotation(valid_payload)
    assert result["success"] is True
    assert result["completed_total"] == 1

    status = manager.get_status()
    assert status["completed_count"] == 1
    assert status["next_question_id"] == 1

    # Verify written file
    assert ann_file.exists()
    lines = [json.loads(line) for line in ann_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["question_id"] == 0
    assert lines[0]["logical_reasoning"] == 2


def test_validation_errors(mock_questions_csv: Path, monkeypatch, tmp_path: Path):
    test_data_dir = tmp_path / "data"
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.DATA_DIR", test_data_dir)
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.ANNOTATIONS_FILE", test_data_dir / "deepseek_annotations.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.FAILURES_FILE", test_data_dir / "deepseek_failures.jsonl")
    monkeypatch.setattr("tools.deepseek_extension.bridge_server.STATE_FILE", test_data_dir / "state.json")

    manager = AnnotationManager(questions_path=mock_questions_csv)

    # 1. Unknown question_id
    with pytest.raises(ValueError, match="Unknown question_id"):
        manager.validate_and_save_annotation({"question_id": 9999})

    # 2. Missing skill
    with pytest.raises(ValueError, match="Missing required cognitive skill"):
        manager.validate_and_save_annotation({
            "question_id": 0,
            "scores": {"attention": 1},
        })

    # 3. Out of bounds score (>3)
    with pytest.raises(ValueError, match="score must be integer between 0 and 3"):
        manager.validate_and_save_annotation({
            "question_id": 0,
            "scores": {
                "attention": 4,  # invalid
                "working_memory": 1,
                "logical_reasoning": 2,
                "language_processing": 1,
                "critical_thinking": 0,
                "metacognition": 0,
            },
        })
