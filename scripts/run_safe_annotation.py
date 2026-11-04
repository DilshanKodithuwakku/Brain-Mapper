"""
Safe, Resumable Cognitive Annotation Runner for Google AI Studio Free Tier.

Features:
1. Resumable: Automatically skips already-annotated questions.
2. Graceful Shutdown: Safely captures Ctrl+C, saves current state, and exits without corruption.
3. Daily Safe Quota Guard: Enforces a daily limit (default: 1,200) to protect the 1,500 RPD free tier.
4. RPM Rate Limiting: 4.2s pacing to stay safely within the 15 RPM limit.
5. Multimodal: Automatically detects and attaches images for diagram questions.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.brain_mapper.cognitive_analysis.configuration import load_config, resolve_path
from src.brain_mapper.cognitive_analysis.gemini import GeminiAnnotator
from src.brain_mapper.cognitive_analysis.prompting import build_prompt, load_prompt_template
from src.brain_mapper.cognitive_analysis.schemas import AnnotationRecord, CognitiveScores

STOP_REQUESTED = False


def _signal_handler(sig, frame):
    global STOP_REQUESTED
    if not STOP_REQUESTED:
        print("\n\n[PAUSE REQUESTED] Finishing in-flight request and saving progress... Press Ctrl+C again to force exit.", flush=True)
        STOP_REQUESTED = True
    else:
        print("\n[FORCE EXIT] Exiting immediately.", flush=True)
        sys.exit(1)


def load_questions(config: dict[str, Any]) -> list[dict[str, Any]]:
    batch_config = config.get("full_batch", {})
    jsonl_path = resolve_path(batch_config.get("question_input", "data/annotations/xes3g5m/full_questions.jsonl"))
    
    if jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    # Fallback to questions.csv
    csv_path = resolve_path(batch_config.get("question_metadata", "data/processed/xes3g5m/questions.csv"))
    questions: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            questions.append({
                "question_id": int(row["question_id"]),
                "question": row["question_text"],
                "options": json.loads(row["options_json"]),
                "image_paths": json.loads(row["image_paths_json"]),
            })
    return questions


def load_completed_ids(output_path: Path) -> set[int]:
    if not output_path.exists():
        return set()
    completed = set()
    with output_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    completed.add(int(record["question_id"]))
                except Exception:
                    continue
    return completed


def run(
    daily_limit: int = 480,
    request_delay: float | None = None,
    config_path: str = "configs/cognitive_annotation.yaml",
) -> None:
    global STOP_REQUESTED
    signal.signal(signal.SIGINT, _signal_handler)

    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY is not set. Please add it to your .env file.", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    provider_config = config["provider"]
    model_name = os.getenv("GEMINI_MODEL", provider_config.get("model", "gemini-3.5-flash-lite"))
    max_tokens = int(provider_config.get("max_output_tokens", 400))
    max_attempts = int(provider_config.get("max_attempts", 5))
    initial_backoff = float(provider_config.get("initial_backoff_seconds", 4))
    
    delay = request_delay if request_delay is not None else float(provider_config.get("request_delay_seconds", 4.2))

    batch_cfg = config.get("full_batch", {})
    output_path = resolve_path(batch_cfg.get("annotation_output", "data/annotations/xes3g5m/full_annotations.jsonl"))
    failure_path = resolve_path(batch_cfg.get("failure_output", "data/annotations/xes3g5m/full_failures.jsonl"))
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.parent.mkdir(parents=True, exist_ok=True)

    questions = load_questions(config)
    total_questions = len(questions)
    completed_ids = load_completed_ids(output_path)
    prompt_template = load_prompt_template()

    print("=" * 65)
    print(" BRAIN MAPPER - SAFE DAILY COGNITIVE ANNOTATION")
    print("=" * 65)
    print(f" Model:            {model_name}")
    print(f" Daily Safe Limit: {daily_limit} questions/day (RPD guard)")
    print(f" Request Pacing:   {delay}s delay between requests (15 RPM guard)")
    print(f" Total Dataset:    {total_questions} questions")
    print(f" Previously Done:  {len(completed_ids)} / {total_questions} ({len(completed_ids)/total_questions*100:.1f}%)")
    print(f" Remaining Total:  {total_questions - len(completed_ids)} questions")
    print(f" Output File:      {output_path}")
    print("=" * 65)
    print(" Press Ctrl+C at any time to PAUSE and save progress safely.")
    print("=" * 65 + "\n")

    if len(completed_ids) >= total_questions:
        print("[ALL DONE] All questions in the dataset are already annotated!")
        return

    annotator = GeminiAnnotator(model=model_name, max_output_tokens=max_tokens)

    annotated_today = 0
    failed_today = 0
    session_start = time.time()

    with (
        output_path.open("a", encoding="utf-8", newline="\n") as success_file,
        failure_path.open("a", encoding="utf-8", newline="\n") as failure_file,
    ):
        for idx, question in enumerate(questions, start=1):
            if STOP_REQUESTED:
                break

            if annotated_today >= daily_limit:
                print("\n" + "=" * 65)
                print(f"[DAILY SAFE LIMIT REACHED] Hit quota cap of {daily_limit} questions for today.")
                print(f"Protection active: Saved your remaining free-tier daily quota.")
                print(f"Total Progress: {len(completed_ids)} / {total_questions} ({len(completed_ids)/total_questions*100:.1f}%)")
                print("Run this script again tomorrow to resume!")
                print("=" * 65)
                break

            qid = int(question["question_id"])
            if qid in completed_ids:
                continue

            has_image = bool(question.get("image_paths"))
            q_mode = "IMG" if has_image else "TXT"

            prompt, prompt_hash = build_prompt(question, prompt_template)
            scores: CognitiveScores | None = None
            last_err = ""

            t0 = time.time()
            for attempt in range(1, max_attempts + 1):
                try:
                    scores = annotator.annotate(prompt, question.get("image_paths"))
                    break
                except Exception as err:
                    last_err = str(err)
                    if "400 INVALID_ARGUMENT" in last_err:
                        break
                    if "GenerateRequestsPerDay" in last_err or "limit: 500" in last_err:
                        print("\n" + "=" * 65)
                        print(f"[DAILY MODEL QUOTA REACHED] Model '{model_name}' has reached its 500 req/day limit.")
                        print(f"✓ All {annotated_today} questions annotated in this session are safely saved!")
                        print("• Option 1: Wait for daily quota reset at 00:00 UTC (5:30 AM local time).")
                        print("• Option 2: Change GEMINI_MODEL=\"gemini-3.6-flash\" in .env for another 500 free requests today!")
                        print("=" * 65)
                        STOP_REQUESTED = True
                        break
                    if attempt < max_attempts:
                        wait_sec = initial_backoff * (2 ** (attempt - 1))
                        print(f"\n  [Retry {attempt}/{max_attempts}] Network/Quota wait {wait_sec:.1f}s (Error: {err})", flush=True)
                        time.sleep(wait_sec)

            duration = time.time() - t0

            if scores is not None:
                record = AnnotationRecord(
                    question_id=qid,
                    **scores.model_dump(),
                    provider="gemini",
                    model=model_name,
                    pipeline_version=str(config.get("pipeline_version", "1.0")),
                    taxonomy_version=str(config.get("taxonomy_version", "1.0")),
                    prompt_version=str(config.get("prompt_version", "1.0")),
                    prompt_sha256=prompt_hash,
                    input_mode="image" if has_image else "text",
                    image_paths=question.get("image_paths") or [],
                    usage=getattr(annotator, "last_usage", {}) or {},
                )
                success_file.write(record.model_dump_json() + "\n")
                success_file.flush()
                os.fsync(success_file.fileno())

                completed_ids.add(qid)
                annotated_today += 1

                # Live status line
                print(
                    f"[{qid:>4}] [{q_mode}] Done ({duration:.1f}s) | "
                    f"Attn:{scores.attention} Mem:{scores.working_memory} Log:{scores.logical_reasoning} "
                    f"Lang:{scores.language_processing} Crit:{scores.critical_thinking} Meta:{scores.metacognition} | "
                    f"Conf:{scores.confidence:.2f} | Today: {annotated_today}/{daily_limit} | "
                    f"Overall: {len(completed_ids)}/{total_questions} ({len(completed_ids)/total_questions*100:.1f}%)",
                    flush=True,
                )
            else:
                fail_record = {
                    "question_id": qid,
                    "error": last_err,
                    "failed_at_utc": datetime.now(UTC).isoformat(),
                }
                failure_file.write(json.dumps(fail_record, ensure_ascii=False) + "\n")
                failure_file.flush()
                os.fsync(failure_file.fileno())
                failed_today += 1
                print(f"[{qid:>4}] [{q_mode}] FAILED: {last_err[:80]}", flush=True)

            # Delay to enforce 15 RPM
            if not STOP_REQUESTED and annotated_today < daily_limit:
                time.sleep(delay)

    total_elapsed = time.time() - session_start
    print("\n" + "=" * 65)
    print(" SESSION SUMMARY")
    print("=" * 65)
    print(f" New Annotations Saved: {annotated_today}")
    print(f" Failed Items:          {failed_today}")
    print(f" Total Dataset Done:    {len(completed_ids)} / {total_questions} ({len(completed_ids)/total_questions*100:.1f}%)")
    print(f" Session Elapsed Time:  {total_elapsed/60:.1f} minutes")
    print(f" Output Location:       {output_path}")
    if STOP_REQUESTED:
        print(" [STATUS] Process paused cleanly by user. All progress is saved.")
        print(" To continue from this exact question, simply run the command again.")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Safe Daily Cognitive Annotation Runner")
    parser.add_argument(
        "--daily-limit",
        type=int,
        default=480,
        help="Maximum questions to annotate today (default: 480 for 500 RPD free-tier guard)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Seconds to wait between requests (default: 4.2s for 15 RPM guard)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/cognitive_annotation.yaml",
        help="Path to YAML configuration",
    )
    args = parser.parse_args()
    run(daily_limit=args.daily_limit, request_delay=args.delay, config_path=args.config)


if __name__ == "__main__":
    main()
