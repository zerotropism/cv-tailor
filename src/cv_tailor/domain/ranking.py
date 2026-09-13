"""Ranking a batch of CVs against one job description."""

from collections.abc import Mapping

from pydantic import BaseModel, Field

from cv_tailor.domain.models import Ranking
from cv_tailor.domain.prompting import job_and_cv
from cv_tailor.domain.protocols import LLMClient

DEFAULT_TOP_N = 3


class Match(BaseModel):
    """What the model is asked to return for one CV. Its JSON schema constrains the output."""

    score: float = Field(ge=0.0, le=1.0)
    explanation: str


def rank(
    job_description: str,
    cvs: Mapping[str, str],
    llm: LLMClient,
    instructions: str,
    top_n: int = DEFAULT_TOP_N,
) -> list[Ranking]:
    """Score every CV, best first. Ties keep their input order."""
    rankings = []
    for name, content in cvs.items():
        match = llm.complete_structured(instructions, job_and_cv(job_description, content), Match)
        rankings.append(Ranking(name=name, score=match.score, explanation=match.explanation))

    rankings.sort(key=lambda ranking: ranking.score, reverse=True)
    return rankings[:top_n]
