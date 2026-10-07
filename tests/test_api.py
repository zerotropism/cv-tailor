"""The HTTP adapter through FastAPI's TestClient, with a fake model."""

import time

import pytest
from fastapi.testclient import TestClient

from cv_tailor.adapters.fake import FakeLLM
from cv_tailor.api import create_app
from cv_tailor.domain.protocols import LLMUnavailable
from cv_tailor.domain.ranking import Match


def matches(*scores: float) -> list[Match]:
    return [Match(score=score, explanation="because") for score in scores]


@pytest.fixture
def client(make_service):
    def build(llm: FakeLLM | None = None, timeout: float = 5) -> TestClient:
        return TestClient(create_app(make_service(llm or FakeLLM()), timeout=timeout))

    return build


def test_health(client) -> None:
    assert client().get("/health").json() == {"status": "ok"}


def test_documents_are_listed_and_readable_by_name(client) -> None:
    api = client()
    assert api.get("/cvs").json() == ["CV_001_network", "CV_002_ml", "CV_003_cyber"]
    assert api.get("/jobs").json() == ["JD_Network_Engineer"]
    assert api.get("/cvs/CV_001_network").text == "routing, BGP"
    assert api.get("/jobs/JD_Network_Engineer").text.startswith("Network engineer")


@pytest.mark.parametrize("path", ["/cvs/CV_999", "/cvs/..%2Fsecret", "/jobs/..%2F..%2Fsecret"])
def test_unknown_or_escaping_names_are_not_found(client, path) -> None:
    assert client().get(path).status_code == 404


def test_rank_by_job_name(client) -> None:
    api = client(FakeLLM(structured=matches(0.2, 0.9, 0.5)))
    response = api.post("/rank", json={"job_name": "JD_Network_Engineer", "top_n": 2})
    assert response.status_code == 200
    assert [r["name"] for r in response.json()] == ["CV_002_ml", "CV_003_cyber"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"job_name": "JD_Network_Engineer", "job_description": "x"},
        {"job_name": "JD_Network_Engineer", "top_n": 0},
    ],
)
def test_invalid_rank_requests_are_rejected(client, body) -> None:
    assert client().post("/rank", json=body).status_code == 422


def test_unknown_job_is_not_found(client) -> None:
    assert client().post("/rank", json={"job_name": "JD_Unknown"}).status_code == 404


def test_rewrite_returns_the_markdown(client) -> None:
    body = {"cv_name": "CV_001_network", "job_description": "Network engineer"}
    response = client(FakeLLM(text="# Tailored")).post("/rewrite", json=body)
    assert response.json() == {"name": "CV_001_network", "content": "# Tailored"}


def test_an_unreachable_model_server_is_503(client) -> None:
    class DownLLM(FakeLLM):
        def complete(self, instructions, data):
            raise LLMUnavailable("connection refused")

    body = {"cv_name": "CV_001_network", "job_description": "x"}
    response = client(DownLLM()).post("/rewrite", json=body)
    assert response.status_code == 503
    assert "Ollama is unreachable" in response.json()["detail"]


def test_a_slow_model_is_504(client) -> None:
    class SlowLLM(FakeLLM):
        def complete(self, instructions, data):
            time.sleep(1)
            return "late"

    body = {"cv_name": "CV_001_network", "job_description": "x"}
    response = client(SlowLLM(), timeout=0.1).post("/rewrite", json=body)
    assert response.status_code == 504


def test_openapi_documents_every_route(client) -> None:
    paths = set(client().get("/openapi.json").json()["paths"])
    expected = {"/health", "/cvs", "/cvs/{name}", "/jobs", "/jobs/{name}", "/rank", "/rewrite"}
    assert paths == expected
