"""Shared fixtures: small data directories, so tests never depend on the bundled samples."""

from pathlib import Path

import pytest

from cv_tailor.adapters.fake import FakeLLM
from cv_tailor.service import CVTailor

CVS = {"CV_001_network": "routing, BGP", "CV_002_ml": "pytorch", "CV_003_cyber": "SIEM"}


@pytest.fixture
def data_dirs(tmp_path) -> tuple[Path, Path]:
    cv_dir, job_dir = tmp_path / "cvs", tmp_path / "jobs"
    cv_dir.mkdir()
    job_dir.mkdir()
    for name, text in CVS.items():
        (cv_dir / f"{name}.txt").write_text(text)
    (job_dir / "JD_Network_Engineer.txt").write_text("Network engineer: BGP, routing")
    (job_dir / "JD_Network_Engineer.docx").write_bytes(b"ignored: only .txt is read")
    (tmp_path / "secret.txt").write_text("outside the data directories")
    return cv_dir, job_dir


@pytest.fixture
def make_service(data_dirs):
    def build(llm: FakeLLM) -> CVTailor:
        cv_dir, job_dir = data_dirs
        return CVTailor(llm, cv_dir, job_dir, rank_prompt="rank", rewrite_prompt="rewrite")

    return build
