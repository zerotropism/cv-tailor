"""The service shared by the adapters: documents by name only, the two operations."""

import pytest

from cv_tailor.adapters.fake import FakeLLM
from cv_tailor.domain.ranking import Match
from cv_tailor.service import UnknownDocumentError


def matches(*scores: float) -> list[Match]:
    return [Match(score=score, explanation="because") for score in scores]


def test_names_come_from_the_text_files(make_service) -> None:
    service = make_service(FakeLLM())
    assert service.cv_names() == ["CV_001_network", "CV_002_ml", "CV_003_cyber"]
    assert service.job_names() == ["JD_Network_Engineer"]


@pytest.mark.parametrize("name", ["CV_999", "../secret", "../../etc/passwd"])
def test_only_listed_names_can_be_read(make_service, name) -> None:
    with pytest.raises(UnknownDocumentError):
        make_service(FakeLLM()).cv(name)


def test_job_is_given_by_name_or_text_but_not_both(make_service) -> None:
    service = make_service(FakeLLM())
    assert service.job_text(job_name="JD_Network_Engineer").startswith("Network engineer")
    assert service.job_text(job_description="free text") == "free text"
    for arguments in ({}, {"job_name": "JD_Network_Engineer", "job_description": "x"}):
        with pytest.raises(ValueError, match="exactly one"):
            service.job_text(**arguments)


def test_rank_scores_every_cv_best_first(make_service) -> None:
    llm = FakeLLM(structured=matches(0.9, 0.1, 0.4))
    rankings = make_service(llm).rank("Network engineer", top_n=2)
    assert [r.name for r in rankings] == ["CV_001_network", "CV_003_cyber"]
    assert len(llm.calls) == 3
    assert all(instructions == "rank" for instructions, _ in llm.calls)


def test_rewrite_uses_the_named_cv(make_service) -> None:
    llm = FakeLLM(text="# Network CV")
    result = make_service(llm).rewrite("Network engineer", "CV_001_network")
    assert (result.name, result.content) == ("CV_001_network", "# Network CV")
    assert "routing, BGP" in llm.calls[0][1]
