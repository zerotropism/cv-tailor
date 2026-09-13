"""Rewriting one CV to match a job description."""

from cv_tailor.domain.models import RewrittenCV
from cv_tailor.domain.prompting import job_and_cv
from cv_tailor.domain.protocols import LLMClient


def rewrite(
    job_description: str, name: str, cv_content: str, llm: LLMClient, instructions: str
) -> RewrittenCV:
    """Return the CV rewritten in Markdown. Content is never invented, only reworded."""
    content = llm.complete(instructions, job_and_cv(job_description, cv_content))
    return RewrittenCV(name=name, content=content.strip())
