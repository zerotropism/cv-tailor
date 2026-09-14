"""Smoke tests: modules import, config loads, PDF backend is available."""

import pytest

MODULES = ["config", "llm_client", "adapters.loader", "adapters.exporters", "ui.main"]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    __import__(f"cv_tailor.{name}")


def test_config_loads_from_any_cwd() -> None:
    from cv_tailor.config import load_config

    cfg = load_config()
    assert isinstance(cfg, dict)
    assert cfg


def test_resumes_load_from_explicit_path() -> None:
    from cv_tailor.adapters.loader import load_resumes
    from cv_tailor.config import CV_DIR

    resumes = load_resumes(str(CV_DIR))
    assert resumes
    assert all(content.strip() for content in resumes.values())
    assert all(name.startswith("CV") for name in resumes)
