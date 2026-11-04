"""
Unit tests for the DeepSeek Response Parser logic.
Validates extraction of cognitive scores from raw DeepSeek outputs,
including DeepSeek-R1 <think> tags, markdown code blocks, and edge cases.
"""

import json
import re
import pytest

REQUIRED_SKILLS = [
    "attention",
    "working_memory",
    "logical_reasoning",
    "language_processing",
    "critical_thinking",
    "metacognition",
]


def strip_think_blocks(text: str) -> str:
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_json_string(raw_text: str) -> str:
    text = strip_think_blocks(raw_text)
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block:
        return code_block.group(1).strip()
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()
    return text


def parse_and_validate(raw_text: str, expected_question_id: int | None = None) -> dict:
    json_str = extract_json_string(raw_text)
    data = json.loads(json_str)

    if expected_question_id is not None and "question_id" in data:
        assert int(data["question_id"]) == expected_question_id, (
            f"Stale output: got QID {data['question_id']} but expected {expected_question_id}"
        )

    scores = {}
    for skill in REQUIRED_SKILLS:
        assert skill in data, f"Missing skill: {skill}"
        val = round(float(data[skill]))
        assert 0 <= val <= 3, f"Score out of range: {val}"
        scores[skill] = val

    conf = float(data.get("confidence", 0.95))
    assert 0.0 <= conf <= 1.0, f"Confidence out of range: {conf}"

    return {
        "question_id": data.get("question_id"),
        "scores": scores,
        "confidence": conf,
        "short_rationale": str(data.get("short_rationale", "")).strip(),
    }


def test_reject_stale_question_id():
    raw = """{
      "question_id": 7,
      "attention": 2,
      "working_memory": 2,
      "logical_reasoning": 3,
      "language_processing": 1,
      "critical_thinking": 1,
      "metacognition": 0,
      "confidence": 0.95,
      "short_rationale": "Previous question rationale."
    }"""
    # Should succeed for Q7
    res = parse_and_validate(raw, expected_question_id=7)
    assert res["question_id"] == 7

    # Should raise AssertionError for Q8
    with pytest.raises(AssertionError, match="Stale output"):
        parse_and_validate(raw, expected_question_id=8)


def test_clean_json_parsing():
    raw = """{
      "attention": 2,
      "working_memory": 2,
      "logical_reasoning": 3,
      "language_processing": 1,
      "critical_thinking": 1,
      "metacognition": 0,
      "confidence": 0.95,
      "short_rationale": "Requires multi-step deductive reasoning."
    }"""
    res = parse_and_validate(raw)
    assert res["scores"]["logical_reasoning"] == 3
    assert res["scores"]["metacognition"] == 0
    assert res["confidence"] == 0.95


def test_markdown_code_block_parsing():
    raw = """Here is the cognitive evaluation:
```json
{
  "attention": 1,
  "working_memory": 1,
  "logical_reasoning": 2,
  "language_processing": 1,
  "critical_thinking": 0,
  "metacognition": 0,
  "confidence": 0.90,
  "short_rationale": "Basic arithmetic calculation."
}
```
Hope this helps!"""
    res = parse_and_validate(raw)
    assert res["scores"]["logical_reasoning"] == 2
    assert res["confidence"] == 0.90


def test_deepseek_r1_think_tag_stripping():
    raw = """<think>
The student is in Grade 3.
The question involves counting elements in a set.
Attention: 2 because visual tracking is needed.
Logical reasoning: 1.
Metacognition: 0.
Let's format the response in strict JSON.
</think>
```json
{
  "attention": 2,
  "working_memory": 1,
  "logical_reasoning": 1,
  "language_processing": 1,
  "critical_thinking": 0,
  "metacognition": 0,
  "confidence": 0.95,
  "short_rationale": "Counting items requires focused visual attention."
}
```"""
    res = parse_and_validate(raw)
    assert res["scores"]["attention"] == 2
    assert res["scores"]["working_memory"] == 1
    assert "visual attention" in res["short_rationale"]
