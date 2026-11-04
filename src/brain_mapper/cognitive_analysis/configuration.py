"""Configuration loading with paths resolved from the project root."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path("configs/cognitive_annotation.yaml")


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = project_root() / config_path
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    config["_config_path"] = str(config_path)
    return config


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root() / path
