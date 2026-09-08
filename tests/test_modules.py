"""Smoke tests: modules import, config loads, PDF backend is available."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

MODULES = ["config", "cv_loader", "exporters", "llm_client", "main"]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    __import__(name)


def test_config_loads_from_any_cwd() -> None:
    from config import load_config

    cfg = load_config()
    assert isinstance(cfg, dict)
    assert cfg


def test_pdf_export_backend_available() -> None:
    from weasyprint import HTML

    assert HTML is not None


def test_resumes_load_from_explicit_path() -> None:
    """load_resumes defaults to a relative '../data', so pass an explicit path.

    Fixing that default belongs to the layering refactor (step 3.3).
    """
    from cv_loader import load_resumes

    resumes = load_resumes(str(ROOT / "data"))
    assert len(resumes) == 50
