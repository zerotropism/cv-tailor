"""Ranking a batch of CVs against one job description."""

from collections.abc import Mapping

from pydantic import BaseModel, Field

from cv_tailor.domain.lexical import lexical_ranking
from cv_tailor.domain.models import Ranking
from cv_tailor.domain.prompting import job_and_cv
from cv_tailor.domain.protocols import LLMClient

DEFAULT_TOP_N = 3
# Measured with cv-tailor-eval (README, Evaluation): a BM25 shortlist of 15 out of 50 CVs, then
# the model, beats the model on all 50 for both models tried, with a third of the calls
DEFAULT_PRESELECT = 15


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
    preselect: int | None = DEFAULT_PRESELECT,
) -> list[Ranking]:
    """The best CVs, best first.

    With `preselect`, the model scores only the CVs BM25 finds closest to the job, at least
    `top_n` of them, in BM25 order, so tied scores fall back on lexical similarity. With None,
    the model scores every CV and ties keep their input order.
    """
    if preselect is not None and len(cvs) > max(preselect, top_n):
        shortlist = lexical_ranking(job_description, cvs)[: max(preselect, top_n)]
        cvs = {name: cvs[name] for name in shortlist}
    names = list(cvs)
    blocks = [job_and_cv(job_description, cvs[name]) for name in names]
    matches = llm.complete_structured_many(instructions, blocks, Match)

    rankings = [
        Ranking(name=name, score=match.score, explanation=match.explanation)
        for name, match in zip(names, matches, strict=True)
    ]
    rankings.sort(key=lambda ranking: ranking.score, reverse=True)
    return rankings[:top_n]
