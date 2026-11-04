import base64
import csv
import json

from brain_mapper.cognitive_analysis.batch import build_batch_request, load_all_questions


def test_batch_request_contains_structured_schema_and_image(tmp_path, monkeypatch):
    image = tmp_path / "question.png"
    image.write_bytes(b"fake-image")
    monkeypatch.setattr("brain_mapper.cognitive_analysis.batch.resolve_path", lambda path: image)
    request = build_batch_request(
        {
            "question_id": 7,
            "question": "Which region is shaded?",
            "options": {"A": "Left", "B": "Right"},
            "image_paths": ["question.png"],
        },
        400,
    )

    assert request["key"] == "question-7"
    generation = request["request"]["generation_config"]
    assert generation["response_mime_type"] == "application/json"
    assert "attention" in generation["response_json_schema"]["properties"]
    image_data = request["request"]["contents"][0]["parts"][1]["inline_data"]
    assert base64.b64decode(image_data["data"]) == b"fake-image"


def test_load_all_questions_preserves_image_paths(tmp_path):
    path = tmp_path / "questions.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["question_id", "question_text", "options_json", "image_paths_json"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "question_id": 2,
                "question_text": "Use the diagram.",
                "options_json": json.dumps({}),
                "image_paths_json": json.dumps(["images/question.png"]),
            }
        )

    assert load_all_questions(path) == [
        {
            "question_id": 2,
            "question": "Use the diagram.",
            "options": {},
            "image_paths": ["images/question.png"],
        }
    ]
