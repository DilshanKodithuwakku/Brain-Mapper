"""
Isolated Local Bridge Server for DeepSeek Browser Extension Annotation.

Coordinates question serving, schema validation, and atomic writing to disk
without modifying or corrupting project datasets.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

# Define paths relative to this script
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
DATA_DIR = BASE_DIR / "data"
QUESTIONS_CSV = PROJECT_ROOT / "data" / "processed" / "xes3g5m" / "questions.csv"
ANNOTATIONS_FILE = DATA_DIR / "deepseek_annotations.jsonl"
FAILURES_FILE = DATA_DIR / "deepseek_failures.jsonl"
STATE_FILE = DATA_DIR / "state.json"

REQUIRED_SKILLS = [
    "attention",
    "working_memory",
    "logical_reasoning",
    "language_processing",
    "critical_thinking",
    "metacognition",
]

PROMPT_TEMPLATE = """You are annotating the cognitive requirements of an educational question for a cognitive-aware knowledge-tracing research dataset.

Evaluate what a typical Grade 3 student must do to solve the question. Do not judge how difficult the wording feels to an adult. Do not infer requirements from a correct answer, knowledge-component label, student response, or other information that is not included below.

Use this scale for every skill:
0 = not required or negligible
1 = low: one simple, direct use
2 = moderate: sustained or multi-step use
3 = high: central, complex, or sustained use

Skill definitions:
- attention: Select and maintain focus on relevant details, constraints, symbols, options, or visual elements while ignoring distractions.
- working_memory: Hold and manipulate multiple pieces of information or intermediate results. Simple recall alone is not working memory.
- logical_reasoning: Apply rules, relations, deductions, sequencing, or multi-step mathematical reasoning to reach a conclusion.
- language_processing: Understand vocabulary, grammar, references, or a linguistically complex problem statement. Reading one short direct sentence is at most low.
- critical_thinking: Compare plausible approaches, evaluate evidence or assumptions, detect ambiguity, or select and justify a strategy. Routine application of a known procedure is not automatically critical thinking.
- metacognition: Explicitly plan, monitor, check, or reflect on one's own approach. Most routine questions should receive 0 unless self-monitoring is genuinely required by the task.

Score requirements independently. Use the full 0-3 range, but do not inflate scores simply because the question is mathematical. Confidence is confidence in the annotation (0.0-1.0), not confidence that a student answers correctly. Give one concise rationale grounded only in the supplied question.

Question ID: {question_id}
Question:
{question_text}

Options:
{options_formatted}

{image_note}

CRITICAL: Return ONLY a single valid JSON object. Do not include markdown code blocks, think tags, or introductory text. The response must parse directly into this structure:
{{
  "question_id": {question_id},
  "attention": <integer 0-3>,
  "working_memory": <integer 0-3>,
  "logical_reasoning": <integer 0-3>,
  "language_processing": <integer 0-3>,
  "critical_thinking": <integer 0-3>,
  "metacognition": <integer 0-3>,
  "confidence": <float 0.0-1.0>,
  "short_rationale": "<concise explanation>"
}}"""


class AnnotationManager:
    """Manages question queue, atomic disk writes, and completion state."""

    def __init__(self, questions_path: Path = QUESTIONS_CSV) -> None:
        self.questions_path = questions_path
        self.questions: list[dict[str, Any]] = []
        self.questions_by_id: dict[int, dict[str, Any]] = {}
        self.completed_ids: set[int] = set()
        self.failed_ids: set[int] = set()
        self.skipped_ids: set[int] = set()
        self.failure_counts: dict[int, int] = {}
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.load_questions()
        self.load_completed()
        self.load_failures()

    def load_questions(self) -> None:
        if not self.questions_path.exists():
            raise FileNotFoundError(f"Questions CSV not found at: {self.questions_path}")

        self.questions.clear()
        self.questions_by_id.clear()
        with self.questions_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q_id = int(row["question_id"])
                options = json.loads(row["options_json"]) if row.get("options_json") else []
                image_paths = json.loads(row["image_paths_json"]) if row.get("image_paths_json") else []
                has_images = len(image_paths) > 0 or row.get("requires_image", "") in ("1", "True", "true") or row.get("has_images", "").lower() == "true"
                record = {
                    "question_id": q_id,
                    "question_text": row.get("question_text", ""),
                    "options": options,
                    "image_paths": image_paths,
                    "has_images": has_images,
                }
                self.questions.append(record)
                self.questions_by_id[q_id] = record

        # Sort by question_id
        self.questions.sort(key=lambda x: x["question_id"])

    def load_completed(self) -> None:
        self.completed_ids.clear()
        if not ANNOTATIONS_FILE.exists():
            return

        with ANNOTATIONS_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self.completed_ids.add(int(record["question_id"]))
                except Exception:
                    continue

    def load_failures(self) -> None:
        self.failed_ids.clear()
        if not FAILURES_FILE.exists():
            return

        with FAILURES_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self.failed_ids.add(int(record["question_id"]))
                except Exception:
                    continue

    def get_status(self) -> dict[str, Any]:
        total = len(self.questions)
        completed = len(self.completed_ids)
        failed = len(self.failed_ids)
        remaining = total - completed
        percent = round((completed / total * 100), 2) if total > 0 else 0.0

        next_id = None
        for q in self.questions:
            qid = q["question_id"]
            if qid not in self.completed_ids and qid not in self.skipped_ids:
                next_id = qid
                break

        return {
            "total_questions": total,
            "completed_count": completed,
            "failed_count": failed,
            "remaining_count": remaining,
            "progress_percent": percent,
            "next_question_id": next_id,
            "done": remaining == 0,
        }

    def get_next_question(self) -> dict[str, Any] | None:
        for q in self.questions:
            qid = q["question_id"]
            if qid not in self.completed_ids and qid not in self.skipped_ids:
                # Format options
                options_str = "\n".join(f"- {opt}" for opt in q["options"]) if q["options"] else "None (open/fill-in-the-blank question)"
                
                # Image handling
                image_urls: list[str] = []
                image_filenames: list[str] = []
                if q["has_images"] and q["image_paths"]:
                    image_note = "Note: The diagram(s) for this question are attached as images. Evaluate the visual perception, spatial/geometric, and cognitive demands required to interpret the diagram and solve the question."
                    for img_rel in q["image_paths"]:
                        image_urls.append(f"/api/image?path={quote(img_rel)}")
                        image_filenames.append(Path(img_rel).name)
                else:
                    image_note = "Note: This is a text-only mathematics problem."

                prompt = PROMPT_TEMPLATE.format(
                    question_id=qid,
                    question_text=q["question_text"],
                    options_formatted=options_str,
                    image_note=image_note,
                )

                return {
                    "question_id": qid,
                    "prompt": prompt,
                    "has_images": q["has_images"],
                    "image_paths": q["image_paths"],
                    "image_urls": image_urls,
                    "image_filenames": image_filenames,
                    "completed_count": len(self.completed_ids),
                    "total_questions": len(self.questions),
                }
        return None

    def validate_and_save_annotation(self, payload: dict[str, Any]) -> dict[str, Any]:
        question_id = int(payload.get("question_id", -1))
        if question_id not in self.questions_by_id:
            raise ValueError(f"Unknown question_id: {question_id}")

        scores = payload.get("scores", {})
        for skill in REQUIRED_SKILLS:
            if skill not in scores:
                raise ValueError(f"Missing required cognitive skill: {skill}")
            val = scores[skill]
            if not isinstance(val, int) or val < 0 or val > 3:
                raise ValueError(f"Skill '{skill}' score must be integer between 0 and 3, got: {val}")

        confidence = float(payload.get("confidence", 0.9))
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got: {confidence}")

        short_rationale = str(payload.get("short_rationale", "")).strip()
        if not short_rationale:
            short_rationale = "Annotated via DeepSeek Web Automation"

        record = {
            "attention": scores["attention"],
            "working_memory": scores["working_memory"],
            "logical_reasoning": scores["logical_reasoning"],
            "language_processing": scores["language_processing"],
            "critical_thinking": scores["critical_thinking"],
            "metacognition": scores["metacognition"],
            "confidence": confidence,
            "short_rationale": short_rationale,
            "question_id": question_id,
            "provider": "deepseek",
            "model": payload.get("model", "deepseek-chat-web"),
            "pipeline_version": "1.0",
            "taxonomy_version": "1.0",
            "input_mode": "text" if not self.questions_by_id[question_id]["has_images"] else "multimodal_context",
            "has_images": self.questions_by_id[question_id]["has_images"],
            "review_status": "unreviewed",
            "created_at_utc": datetime.now(UTC).isoformat(),
        }

        # Atomic append to deepseek_annotations.jsonl
        with ANNOTATIONS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        self.completed_ids.add(question_id)
        if question_id in self.failed_ids:
            self.failed_ids.remove(question_id)
        if question_id in self.failure_counts:
            del self.failure_counts[question_id]

        # Update state file
        self._save_state(question_id)

        return {"success": True, "question_id": question_id, "completed_total": len(self.completed_ids)}

    def record_failure(self, payload: dict[str, Any]) -> None:
        question_id = int(payload.get("question_id", -1))
        error_msg = str(payload.get("error", "Unknown error"))
        raw_text = str(payload.get("raw_response", ""))[:500]

        fail_record = {
            "question_id": question_id,
            "error": error_msg,
            "raw_response_snippet": raw_text,
            "failed_at_utc": datetime.now(UTC).isoformat(),
        }

        with FAILURES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fail_record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        if question_id != -1:
            self.failed_ids.add(question_id)
            self.failure_counts[question_id] = self.failure_counts.get(question_id, 0) + 1
            if self.failure_counts[question_id] >= 2:
                print(f"\n[AUTO-SKIP] Question #{question_id} failed {self.failure_counts[question_id]} times. Skipping to prevent queue stall.\n", flush=True)
                self.skipped_ids.add(question_id)

    def skip_question(self, question_id: int) -> None:
        self.skipped_ids.add(question_id)

    def reset_skipped(self) -> None:
        self.skipped_ids.clear()

    def _save_state(self, last_qid: int) -> None:
        state = {
            "last_processed_id": last_qid,
            "completed_count": len(self.completed_ids),
            "failed_count": len(self.failed_ids),
            "updated_at_utc": datetime.now(UTC).isoformat(),
        }
        temp_file = STATE_FILE.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(STATE_FILE)


class BridgeHandler(BaseHTTPRequestHandler):
    manager: AnnotationManager

    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/api/status":
            self._send_json(HTTPStatus.OK, self.manager.get_status())
        elif path == "/api/next_question":
            next_q = self.manager.get_next_question()
            if next_q:
                self._send_json(HTTPStatus.OK, {"done": False, **next_q})
            else:
                self._send_json(HTTPStatus.OK, {"done": True, "message": "All questions annotated!"})
        elif path == "/api/image":
            query = parse_qs(parsed_url.query)
            img_rel = query.get("path", [""])[0]
            if not img_rel:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing path parameter"})
                return

            # Resolve path safely relative to PROJECT_ROOT
            safe_path = (PROJECT_ROOT / img_rel).resolve()
            root_resolved = PROJECT_ROOT.resolve()
            if not str(safe_path).lower().startswith(str(root_resolved).lower()) or not safe_path.exists() or not safe_path.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Image file not found"})
                return

            ext = safe_path.suffix.lower()
            content_type = "image/png" if ext == ".png" else "image/jpeg" if ext in (".jpg", ".jpeg") else "application/octet-stream"

            data = safe_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self._set_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Endpoint not found: {path}"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
            return

        if path == "/api/submit":
            try:
                res = self.manager.validate_and_save_annotation(payload)
                self._send_json(HTTPStatus.OK, res)
            except Exception as e:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        elif path == "/api/fail":
            self.manager.record_failure(payload)
            self._send_json(HTTPStatus.OK, {"recorded": True})
        elif path == "/api/skip":
            qid = payload.get("question_id")
            if qid is not None:
                self.manager.skip_question(int(qid))
                self._send_json(HTTPStatus.OK, {"skipped": qid})
            else:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing question_id"})
        elif path == "/api/reset_skipped":
            self.manager.reset_skipped()
            self._send_json(HTTPStatus.OK, {"reset": True})
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Endpoint not found: {path}"})

    def log_message(self, format: str, *args: Any) -> None:
        # Clean logging for stdout
        sys.stdout.write(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    manager = AnnotationManager()
    BridgeHandler.manager = manager
    server = ThreadingHTTPServer((host, port), BridgeHandler)
    status = manager.get_status()

    print("=" * 65)
    print("  DeepSeek Isolated Annotation Bridge Server")
    print("=" * 65)
    print(f"  Server URL      : http://{host}:{port}")
    print(f"  Total Questions : {status['total_questions']}")
    print(f"  Completed       : {status['completed_count']} ({status['progress_percent']}%)")
    print(f"  Remaining       : {status['remaining_count']}")
    print(f"  Failed Logged   : {status['failed_count']}")
    print(f"  Next Question ID: {status['next_question_id']}")
    print(f"  Annotations Path: {ANNOTATIONS_FILE.resolve()}")
    print("=" * 65)
    print("  Ready for DeepSeek Chrome Extension connection. Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down bridge server cleanly...")
        server.shutdown()
        server.server_close()
        print("[STOP] Server closed.")


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8765
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(host, port)
