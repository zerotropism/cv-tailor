"""MCP adapter: the service the UI uses, exposed as tools and resource templates.

Model calls run through run_bounded: a slow model can neither stall the event loop nor hold a
client indefinitely.
"""

import os
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

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

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}


def create_server(service: CVTailor, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> FastMCP:
    """Build a server around one service. Tests pass a service with a fake model."""
    mcp = FastMCP("cv-tailor")

    async def run[T](operation: Callable[[], T]) -> T:
        try:
            return await run_bounded(operation, timeout)
        except TimeoutError:
            raise ToolError(f"the model did not answer within {timeout:g}s") from None
        except LLMUnavailable as exc:
            raise ToolError(f"Ollama is unreachable ({exc}): start it, or set OLLAMA_HOST") from exc
        except (UnknownDocumentError, ValueError, LLMError) as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(annotations=READ_ONLY)
    def list_cvs() -> list[str]:
        """Names of the CVs that can be ranked or rewritten."""
        return service.cv_names()

    @mcp.tool(annotations=READ_ONLY)
    def list_jobs() -> list[str]:
        """Names of the sample job descriptions."""
        return service.job_names()

    @mcp.tool(annotations=READ_ONLY)
    async def rank_cvs(
        job_name: str = "", job_description: str = "", top_n: int = DEFAULT_TOP_N
    ) -> list[Ranking]:
        """The CVs that fit a job best, scored and explained. Give a job_name or a job_description.

        BM25 shortlists the closest CVs, then the model scores each one: about a minute locally.
        """
        return await run(lambda: service.rank(service.job_text(job_name, job_description), top_n))

    @mcp.tool(annotations=READ_ONLY)
    async def rewrite_cv(
        cv_name: str, job_name: str = "", job_description: str = ""
    ) -> RewrittenCV:
        """Reword one CV in Markdown to fit a job, without inventing anything.

        Give a job_name or a job_description.
        """
        return await run(
            lambda: service.rewrite(service.job_text(job_name, job_description), cv_name)
        )

    @mcp.resource("cv://{name}", mime_type="text/plain")
    def cv(name: str) -> str:
        """The text of one CV."""
        return service.cv(name)

    @mcp.resource("job://{name}", mime_type="text/plain")
    def job(name: str) -> str:
        """The text of one sample job description."""
        return service.job(name)

    return mcp


def main() -> None:
    """Console entry point: serve over stdio with the model from config.yaml or CV_TAILOR_MODEL."""
    timeout = float(os.environ.get(TIMEOUT_ENV_VAR, DEFAULT_TIMEOUT_SECONDS))
    create_server(CVTailor(OllamaClient(MODEL)), timeout).run(show_banner=False)


if __name__ == "__main__":
    main()
