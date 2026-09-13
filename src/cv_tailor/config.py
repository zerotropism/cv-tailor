import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
CV_DIR = DATA_DIR / "cvs"
JOB_DIR = DATA_DIR / "jobs"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration from a YAML file."""
    config_file = Path(config_path) if config_path else ROOT / "config.yaml"
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file '{config_file}' not found.")

    with config_file.open() as f:
        return yaml.safe_load(f)


_config = load_config()

# CVBOOSTER_MODEL wins over config.yaml: comparing models should not need a commit
MODEL: str = os.getenv("CV_TAILOR_MODEL", _config.get("model", "llama3.2:3b"))
PROMPT_RANK: str = _config.get("prompts", {}).get("rank", {}).get("custom", "")
PROMPT_REWRITE: str = _config.get("prompts", {}).get("rewrite", {}).get("custom", "")
