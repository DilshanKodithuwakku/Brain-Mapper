"""Validated records used by the cognitive annotation pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

SKILL_NAMES = (
    "attention",
    "working_memory",
    "logical_reasoning",
    "language_processing",
    "critical_thinking",
    "metacognition",
)


class CognitiveScores(BaseModel):
    """The strictly validated JSON object requested from the LLM."""

    attention: int = Field(ge=0, le=3)
    working_memory: int = Field(ge=0, le=3)
    logical_reasoning: int = Field(ge=0, le=3)
    language_processing: int = Field(ge=0, le=3)
    critical_thinking: int = Field(ge=0, le=3)
    metacognition: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0.0, le=1.0)
    short_rationale: str = Field(min_length=5, max_length=500)


class AnnotationRecord(CognitiveScores):
    """Scores plus reproducibility and review metadata stored for each item."""

    question_id: int
    provider: str
    model: str
    pipeline_version: str
    taxonomy_version: str
    prompt_version: str
    prompt_sha256: str
    input_mode: str = "text"
    image_paths: list[str] = Field(default_factory=list)
    review_status: str = "unreviewed"
    created_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    usage: dict[str, Any] = Field(default_factory=dict)
