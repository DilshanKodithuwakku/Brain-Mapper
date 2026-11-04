"""Prepare, submit, monitor, and collect a full Gemini Batch annotation job."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from .configuration import DEFAULT_CONFIG, load_config, resolve_path
from .prompting import build_prompt, load_prompt_template
from .quality import create_quality_outputs
from .sampling import write_jsonl
from .schemas import AnnotationRecord, CognitiveScores

TERMINAL_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}


def load_all_questions(metadata_path: Path) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with metadata_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            questions.append(
                {
                    "question_id": int(row["question_id"]),
                    "question": row["question_text"],
                    "options": json.loads(row["options_json"]),
                    "image_paths": json.loads(row["image_paths_json"]),
                }
            )
    return questions


def _image_part(raw_path: str) -> dict[str, Any]:
    path = resolve_path(raw_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }


def build_batch_request(question: dict[str, Any], max_output_tokens: int) -> dict[str, Any]:
    prompt, _ = build_prompt(question, load_prompt_template())
    parts: list[dict[str, Any]] = [{"text": prompt}]
    parts.extend(_image_part(path) for path in question.get("image_paths") or [])
    return {
        "key": f"question-{question['question_id']}",
        "request": {
            "contents": [{"parts": parts, "role": "user"}],
            "generation_config": {
                "response_mime_type": "application/json",
                "response_json_schema": CognitiveScores.model_json_schema(),
                "max_output_tokens": max_output_tokens,
                "temperature": 0,
            },
        },
    }


def prepare(config: dict[str, Any], limit: int | None = None) -> dict[str, Any]:
    batch = config["full_batch"]
    questions = load_all_questions(resolve_path(batch["question_metadata"]))
    if limit is not None:
        questions = questions[:limit]
    question_input = resolve_path(batch["question_input"])
    write_jsonl(question_input, questions)
    request_file = resolve_path(batch["request_file"])
    request_file.parent.mkdir(parents=True, exist_ok=True)
    max_tokens = int(config["provider"]["max_output_tokens"])
    with request_file.open("w", encoding="utf-8", newline="\n") as handle:
        for index, question in enumerate(questions, start=1):
            handle.write(
                json.dumps(
                    build_batch_request(question, max_tokens),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
            if index % 500 == 0:
                print(f"Prepared {index}/{len(questions)} requests", flush=True)
    summary = {
        "questions": len(questions),
        "text_questions": sum(not row["image_paths"] for row in questions),
        "image_questions": sum(bool(row["image_paths"]) for row in questions),
        "request_file": str(request_file),
        "request_file_bytes": request_file.stat().st_size,
    }
    print(json.dumps(summary, indent=2))
    return summary


def _client() -> genai.Client:
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is missing from .env")
    return genai.Client()


def submit(config: dict[str, Any]) -> dict[str, Any]:
    batch = config["full_batch"]
    request_file = resolve_path(batch["request_file"])
    if not request_file.exists():
        raise FileNotFoundError("Prepare the batch request file before submitting it.")
    client = _client()
    uploaded = client.files.upload(
        file=request_file,
        config=types.UploadFileConfig(
            display_name="brain-mapper-full-cognitive-requests",
            mime_type="application/jsonl",
        ),
    )
    model = os.getenv("GEMINI_MODEL", config["provider"]["model"])
    manifest: dict[str, Any] = {
        "uploaded_file_name": uploaded.name,
        "model": model,
        "submitted_at_utc": datetime.now(UTC).isoformat(),
        "request_file": str(request_file),
    }
    manifest_path = resolve_path(batch["job_manifest"])
    try:
        job = client.batches.create(
            model=model,
            src={"file_name": uploaded.name},
            config={"display_name": "brain-mapper-xes3g5m-cognitive-v1"},
        )
        manifest["job_name"] = job.name
        manifest["state"] = job.state.name if job.state else None
    except ClientError as error:
        manifest["state"] = "BATCH_SUBMISSION_FAILED"
        manifest["error"] = str(error)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if "FAILED_PRECONDITION" in str(error):
            raise RuntimeError(
                "Gemini Batch submission requires a paid API project. Google AI Pro does not "
                "enable API billing; activate billing for this key's project in AI Studio."
            ) from error
        raise
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


def _load_manifest(config: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = resolve_path(config["full_batch"]["job_manifest"])
    if not path.exists():
        raise FileNotFoundError("No batch job manifest exists. Submit the batch first.")
    return path, json.loads(path.read_text(encoding="utf-8"))


def status(config: dict[str, Any]) -> dict[str, Any]:
    path, manifest = _load_manifest(config)
    job = _client().batches.get(name=manifest["job_name"])
    manifest["state"] = job.state.name if job.state else None
    manifest["last_checked_at_utc"] = datetime.now(UTC).isoformat()
    if job.error:
        manifest["error"] = job.error.model_dump(exclude_none=True)
    if job.dest and job.dest.file_name:
        manifest["result_file_name"] = job.dest.file_name
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


def _response_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise ValueError("Batch response has no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part["text"] for part in parts if part.get("text")]
    if not texts:
        raise ValueError("Batch response contains no text")
    return "".join(texts)


def collect(config: dict[str, Any]) -> dict[str, Any]:
    batch = config["full_batch"]
    manifest = status(config)
    if manifest["state"] != "JOB_STATE_SUCCEEDED":
        raise RuntimeError(f"Batch is not ready: {manifest['state']}")
    client = _client()
    content = client.files.download(file=manifest["result_file_name"])
    questions = {
        int(row["question_id"]): row
        for row in load_all_questions(resolve_path(batch["question_metadata"]))
    }
    template = load_prompt_template()
    annotations: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for raw_line in content.decode("utf-8").splitlines():
        if not raw_line.strip():
            continue
        result = json.loads(raw_line)
        key = result.get("key", "")
        question_id = int(key.removeprefix("question-"))
        if result.get("error"):
            failures.append({"question_id": question_id, "error": result["error"]})
            continue
        try:
            response = result["response"]
            scores = CognitiveScores.model_validate_json(_response_text(response))
            question = questions[question_id]
            _, prompt_hash = build_prompt(question, template)
            usage = response.get("usageMetadata") or response.get("usage_metadata") or {}
            record = AnnotationRecord(
                question_id=question_id,
                **scores.model_dump(),
                provider="gemini-batch",
                model=manifest["model"],
                pipeline_version=str(config["pipeline_version"]),
                taxonomy_version=str(config["taxonomy_version"]),
                prompt_version=str(config["prompt_version"]),
                prompt_sha256=prompt_hash,
                input_mode="image" if question["image_paths"] else "text",
                image_paths=question["image_paths"],
                usage=usage,
            )
            annotations.append(record.model_dump(mode="json"))
        except (KeyError, ValueError) as error:
            failures.append(
                {"question_id": question_id, "error": f"{type(error).__name__}: {error}"}
            )
    annotations.sort(key=lambda row: row["question_id"])
    failures.sort(key=lambda row: row["question_id"])
    write_jsonl(resolve_path(batch["annotation_output"]), annotations)
    write_jsonl(resolve_path(batch["failure_output"]), failures)
    summary = {
        "annotations": len(annotations),
        "failures": len(failures),
        "expected": len(questions),
    }
    print(json.dumps(summary, indent=2))
    return summary


def quality(config: dict[str, Any]) -> dict[str, Any]:
    batch = config["full_batch"]
    quality_config = config["quality"]
    report = create_quality_outputs(
        resolve_path(batch["question_input"]),
        resolve_path(batch["annotation_output"]),
        resolve_path(batch["quality_report"]),
        resolve_path(batch["review_template"]),
        resolve_path(batch["feature_output"]),
        float(quality_config["low_confidence_threshold"]),
        float(quality_config["dominant_score_fraction_threshold"]),
        float(quality_config["dominant_confidence_fraction_threshold"]),
    )
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "submit", "status", "collect", "quality"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--limit", type=int, help="Prepare only the first N questions for testing")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "prepare":
        prepare(config, args.limit)
    elif args.command == "submit":
        submit(config)
    elif args.command == "status":
        status(config)
    elif args.command == "collect":
        collect(config)
    else:
        quality(config)


if __name__ == "__main__":
    main()
