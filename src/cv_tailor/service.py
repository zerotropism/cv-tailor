"""What the UI, the API and the MCP server share: the data directories and the two operations.

Documents are addressed by name, never by path: a name is looked up among the files actually
present, so no request can reach outside the data directories.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

from cv_tailor.config import CV_DIR, JOB_DIR, PRESELECT, PROMPT_RANK, PROMPT_REWRITE
from cv_tailor.domain.models import Ranking, RewrittenCV
from cv_tailor.domain.protocols import LLMClient
from cv_tailor.domain.ranking import DEFAULT_TOP_N, rank
from cv_tailor.domain.rewriting import rewrite

TIMEOUT_ENV_VAR = "CV_TAILOR_TIMEOUT"
# Ranking 15 preselected CVs takes about 1 minute with llama3.2:3b, 1.5 with qwen3.5:4b-mlx
DEFAULT_TIMEOUT_SECONDS = 600.0


async def run_bounded[T](operation: Callable[[], T], timeout: float) -> T:
    """Run a blocking operation in a worker thread and stop waiting after `timeout` seconds.

    Model calls block, and the Ollama client runs its own event loop for batches: off the
    caller's loop, they stall neither an MCP server nor an HTTP server. The thread itself
    cannot be interrupted; it finishes in the background. Raises TimeoutError.
    """
    return await asyncio.wait_for(asyncio.to_thread(operation), timeout)


class UnknownDocumentError(LookupError):
    """A CV or job name that matches no file."""


def _texts(directory: Path) -> dict[str, str]:
    return {path.stem: path for path in sorted(directory.glob("*.txt"))}


class CVTailor:
    def __init__(
        self,
        llm: LLMClient,
        cv_dir: Path = CV_DIR,
        job_dir: Path = JOB_DIR,
        rank_prompt: str = PROMPT_RANK,
        rewrite_prompt: str = PROMPT_REWRITE,
        preselect: int | None = PRESELECT,
    ) -> None:
        self.llm = llm
        self.cv_dir = cv_dir
        self.job_dir = job_dir
        self.rank_prompt = rank_prompt
        self.rewrite_prompt = rewrite_prompt
        self.preselect = preselect

    def cv_names(self) -> list[str]:
        return list(_texts(self.cv_dir))

    def job_names(self) -> list[str]:
        return list(_texts(self.job_dir))

    def cv(self, name: str) -> str:
        return self._read(_texts(self.cv_dir), "CV", name)

    def job(self, name: str) -> str:
        return self._read(_texts(self.job_dir), "job", name)

    def job_text(self, job_name: str = "", job_description: str = "") -> str:
        """Exactly one of a job name (from the job directory) or a job description."""
        if bool(job_name) == bool(job_description):
            raise ValueError("Give exactly one of job_name or job_description.")
        return self.job(job_name) if job_name else job_description

    def rank(self, job_description: str, top_n: int = DEFAULT_TOP_N) -> list[Ranking]:
        cvs = {name: self.cv(name) for name in self.cv_names()}
        return rank(job_description, cvs, self.llm, self.rank_prompt, top_n, self.preselect)

    def rewrite(self, job_description: str, cv_name: str) -> RewrittenCV:
        return rewrite(job_description, cv_name, self.cv(cv_name), self.llm, self.rewrite_prompt)

    @staticmethod
    def _read(files: dict[str, Path], kind: str, name: str) -> str:
        if name not in files:
            raise UnknownDocumentError(f"Unknown {kind} {name!r}; {len(files)} available.")
        return files[name].read_text(encoding="utf-8")
