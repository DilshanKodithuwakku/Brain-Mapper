"""Gemini implementation of the cognitive annotation provider."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .configuration import resolve_path
from .schemas import CognitiveScores


class GeminiAnnotator:
    """Call Gemini with structured output and no automatic function calling."""

    provider_name = "gemini"

    def __init__(self, model: str, max_output_tokens: int = 400) -> None:
        load_dotenv()
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to the local .env file.")
        self.model = os.getenv("GEMINI_MODEL", model)
        self.max_output_tokens = max_output_tokens
        self.client = genai.Client()
        self.last_usage: dict[str, Any] = {}

    def annotate(self, prompt: str, image_paths: list[str] | None = None) -> CognitiveScores:
        contents: list[Any] = [prompt]
        for raw_path in image_paths or []:
            path = resolve_path(Path(raw_path))
            mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
            contents.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type))

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CognitiveScores,
                max_output_tokens=self.max_output_tokens,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0,
            ),
        )
        if not response.text:
            raise ValueError("Gemini returned no text response")
        self.last_usage = (
            response.usage_metadata.model_dump(exclude_none=True)
            if response.usage_metadata is not None
            else {}
        )
        return CognitiveScores.model_validate_json(response.text)
