"""HTTP adapter: the service the UI and the MCP server use, as a FastAPI application.

Local by default: it listens on 127.0.0.1 and has no authentication, so it is not meant to be
exposed on a network as it stands.
"""

import os
from collections.abc import Callable
from importlib import metadata
from typing import Self

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, model_validator

from cv_tailor.adapters.ollama_client import OllamaClient
from cv_tailor.config import MODEL
from cv_tailor.domain.models import Ranking, RewrittenCV
from cv_tailor.domain.protocols import LLMError, LLMUnavailable
from cv_tailor.domain.ranking import DEFAULT_TOP_N
from cv_tailor.service import (
    DEFAULT_TIMEOUT_SECONDS,
    TIMEOUT_ENV_VAR,
    CVTailor,
    UnknownDocumentError,
    run_bounded,
)

HOST_ENV_VAR = "CV_TAILOR_API_HOST"
PORT_ENV_VAR = "CV_TAILOR_API_PORT"


class JobRequest(BaseModel):
    """A job given by name, from data/jobs/, or as a full description: exactly one of the two."""

    job_name: str = ""
    job_description: str = ""

    @model_validator(mode="after")
    def exactly_one_job(self) -> Self:
        if bool(self.job_name) == bool(self.job_description):
            raise ValueError("Give exactly one of job_name or job_description.")
        return self


class RankRequest(JobRequest):
    top_n: int = Field(DEFAULT_TOP_N, ge=1, le=100)


class RewriteRequest(JobRequest):
    cv_name: str


def create_app(service: CVTailor, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> FastAPI:
    """Build the application around one service. Tests pass a service with a fake model."""
    app = FastAPI(title="cv-tailor", version=metadata.version("cv-tailor"))

    def read(load: Callable[[str], str], name: str) -> str:
        try:
            return load(name)
        except UnknownDocumentError as exc:
            raise HTTPException(404, str(exc)) from exc

    async def run[T](operation: Callable[[], T]) -> T:
        try:
            return await run_bounded(operation, timeout)
        except TimeoutError:
            raise HTTPException(504, f"the model did not answer within {timeout:g}s") from None
        except UnknownDocumentError as exc:
            raise HTTPException(404, str(exc)) from exc
        except LLMUnavailable as exc:
            raise HTTPException(503, f"Ollama is unreachable ({exc})") from exc
        except LLMError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/cvs")
    def cvs() -> list[str]:
        """Names of the CVs that can be ranked or rewritten."""
        return service.cv_names()

    @app.get("/cvs/{name}", response_class=PlainTextResponse)
    def cv(name: str) -> str:
        return read(service.cv, name)

    @app.get("/jobs")
    def jobs() -> list[str]:
        """Names of the sample job descriptions."""
        return service.job_names()

    @app.get("/jobs/{name}", response_class=PlainTextResponse)
    def job(name: str) -> str:
        return read(service.job, name)

    @app.post("/rank")
    async def rank(request: RankRequest) -> list[Ranking]:
        """Score every CV against the job, best first: one model call per CV."""
        return await run(
            lambda: service.rank(
                service.job_text(request.job_name, request.job_description), request.top_n
            )
        )

    @app.post("/rewrite")
    async def rewrite(request: RewriteRequest) -> RewrittenCV:
        """Reword one CV in Markdown to fit the job, without inventing anything."""
        return await run(
            lambda: service.rewrite(
                service.job_text(request.job_name, request.job_description), request.cv_name
            )
        )

    return app


def build_app() -> FastAPI:
    """Factory for uvicorn: the Ollama-backed service, model from config.yaml or CV_TAILOR_MODEL."""
    timeout = float(os.environ.get(TIMEOUT_ENV_VAR, DEFAULT_TIMEOUT_SECONDS))
    return create_app(CVTailor(OllamaClient(MODEL)), timeout)


def main() -> None:
    """Console entry point: serve on CV_TAILOR_API_HOST:CV_TAILOR_API_PORT, 127.0.0.1:8000."""
    host = os.environ.get(HOST_ENV_VAR, "127.0.0.1")
    port = int(os.environ.get(PORT_ENV_VAR, "8000"))
    uvicorn.run("cv_tailor.api:build_app", factory=True, host=host, port=port)
