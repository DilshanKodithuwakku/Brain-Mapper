import csv
import json
from pathlib import Path

from brain_mapper.data.prepare_xes3g5m import prepare_xes3g5m


def _write_sequences(path: Path, rows: list[dict[str, str]], include_masks: bool) -> None:
    columns = ["fold", "uid", "questions", "concepts", "responses", "timestamps"]
    if include_masks:
        columns.append("selectmasks")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_prepare_xes3g5m_separates_inputs_and_flattens_sequences(tmp_path):
    official = tmp_path / "official"
    images = official / "metadata" / "images"
    images.mkdir(parents=True)
    (images / "question_1-image_0.png").write_bytes(b"png")
    english_path = tmp_path / "questions_translated.json"
    english_path.write_text(
        json.dumps(
            {
                "0": {
                    "question": "What is 1 + 1?",
                    "content": "What is 1 + 1?",
                    "options": {},
                    "answer": ["2"],
                    "kc_routes": ["addition"],
                    "type": "填空",
                },
                "1": {
                    "question": "Which region is shaded?",
                    "content": "See question_1-image_0",
                    "options": {"A": "Left", "B": "Right"},
                    "answer": ["A"],
                    "kc_routes": ["geometry"],
                    "type": "单选",
                },
            }
        ),
        encoding="utf-8",
    )
    _write_sequences(
        official / "question_level" / "train_valid_sequences_quelevel.csv",
        [
            {
                "fold": "0",
                "uid": "10",
                "questions": "0,1,-1",
                "concepts": "2,3,-1",
                "responses": "1,0,-1",
                "timestamps": "1000,2000,-1",
                "selectmasks": "1,1,-1",
            }
        ],
        include_masks=True,
    )
    _write_sequences(
        official / "question_level" / "test_quelevel.csv",
        [
            {
                "fold": "-1",
                "uid": "20",
                "questions": "0",
                "concepts": "2",
                "responses": "0",
                "timestamps": "3000",
            }
        ],
        include_masks=False,
    )

    output = tmp_path / "output"
    summary = prepare_xes3g5m(official, english_path, output)

    with (output / "questions.csv").open(encoding="utf-8", newline="") as handle:
        questions = list(csv.DictReader(handle))
    with (output / "question_reference.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        references = list(csv.DictReader(handle))
    with (output / "interactions.csv").open(encoding="utf-8", newline="") as handle:
        interactions = list(csv.DictReader(handle))
    llm_inputs = [
        json.loads(line)
        for line in (output / "cognitive_annotation_input_text_only.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert len(questions) == 2
    assert "correct_answers_json" not in questions[0]
    assert references[0]["correct_answers_json"] == '["2"]'
    assert questions[1]["requires_image"] == "1"
    assert questions[1]["all_images_available"] == "1"
    assert [row["question_id"] for row in interactions] == ["0", "1", "0"]
    assert [row["student_interaction_index"] for row in interactions] == ["0", "1", "0"]
    assert llm_inputs == [{"question_id": 0, "question": "What is 1 + 1?", "options": {}}]
    assert summary["interaction_summary"]["interactions"] == 3
    assert summary["interaction_summary"]["train_test_student_overlap"] == 0
    assert summary["question_summary"]["text_only_questions"] == 1
