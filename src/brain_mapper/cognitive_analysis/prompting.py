"""Versioned prompt construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .configuration import project_root

DEFAULT_PROMPT = project_root() / "prompts" / "cognitive_annotation_v1.txt"


def load_prompt_template(path: Path = DEFAULT_PROMPT) -> str:
    return path.read_text(encoding="utf-8")


def build_prompt(question: dict[str, Any], template: str) -> tuple[str, str]:
    options = question.get("options") or {}
    image_paths = question.get("image_paths") or []
    image_instruction = (
        "Use the attached question image(s) as part of the question."
        if image_paths
        else "No image is required for this question."
    )
    prompt = template.format(
        question_id=question["question_id"],
        question=str(question["question"]).strip(),
        options=json.dumps(options, ensure_ascii=False, sort_keys=True),
        image_instruction=image_instruction,
    )
    return prompt, hashlib.sha256(prompt.encode("utf-8")).hexdigest()
