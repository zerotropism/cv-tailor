"""Run ranking strategies against the reference and summarise the metrics.

The reference comes from the data itself: each CV name ends with its category
(CV_021_network) and each sample job targets one category. A CV is relevant to a job when the
categories match. This is a proxy: a network profile may be partly relevant to an
infrastructure job.
"""

import statistics
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

from cv_tailor.domain.protocols import LLMClient
from cv_tailor.domain.ranking import rank
from cv_tailor.evaluation.lexical import bm25_scores, lexical_ranking
from cv_tailor.evaluation.metrics import average_precision, ndcg_at, precision_at, tied_with_top
from cv_tailor.service import CVTailor

JOB_CATEGORIES = {
    "JD_Cybersecurity_Analyst": "cyber",
    "JD_Infrastructure_Engineer": "infrastructure",
    "JD_Machine_Learning_Engineer": "ml",
    "JD_Network_Engineer": "network",
}
STRATEGIES = ("lexical", "llm", "hybrid")
DEFAULT_PRESELECT = 15


def relevant_cvs(cv_names: list[str], job_name: str) -> set[str]:
    category = JOB_CATEGORIES[job_name]
    relevant = {name for name in cv_names if name.endswith(f"_{category}")}
    if not relevant:
        raise ValueError(f"no CV of category {category!r} for {job_name}")
    return relevant


@dataclass(frozen=True)
class Outcome:
    """One strategy, one model, one run, one job."""

    strategy: str
    model: str
    run: int
    job: str
    ranked: list[str]
    model_calls: int
    seconds: float
    tied_with_top: int
    average_precision: float
    precision_at_5: float
    ndcg_at_10: float

    def to_dict(self) -> dict:
        return asdict(self)


def ranked_by_model(
    job: str, cvs: Mapping[str, str], llm: LLMClient, instructions: str
) -> tuple[list[str], list[float]]:
    rankings = rank(job, cvs, llm, instructions, top_n=len(cvs))
    return [r.name for r in rankings], [r.score for r in rankings]


def run_strategy(
    strategy: str,
    job: str,
    cvs: Mapping[str, str],
    llm: LLMClient | None,
    instructions: str,
    preselect: int = DEFAULT_PRESELECT,
) -> tuple[list[str], int, int]:
    """The full ranking, the number of model calls, and how many CVs tie for first place."""
    lexical = lexical_ranking(job, cvs)
    if strategy == "lexical":
        return lexical, 0, tied_with_top(list(bm25_scores(job, cvs).values()))
    if llm is None:
        raise ValueError(f"strategy {strategy!r} needs a model")
    if strategy == "llm":
        ranked, scores = ranked_by_model(job, cvs, llm, instructions)
        return ranked, len(cvs), tied_with_top(scores)
    if strategy == "hybrid":
        shortlist = {name: cvs[name] for name in lexical[:preselect]}
        ranked, scores = ranked_by_model(job, shortlist, llm, instructions)
        # the CVs the preselection left out keep their lexical order, after the shortlist
        return ranked + lexical[preselect:], len(shortlist), tied_with_top(scores)
    raise ValueError(f"unknown strategy {strategy!r}; choose from {', '.join(STRATEGIES)}")


def evaluate(
    service: CVTailor,
    strategies: list[str],
    models: list[str],
    runs: int,
    llm_for: Callable[[str], LLMClient],
    preselect: int = DEFAULT_PRESELECT,
    report: Callable[[Outcome], None] = lambda outcome: None,
) -> list[Outcome]:
    """Every strategy for every job; model strategies once per model and run, lexical once."""
    cvs = {name: service.cv(name) for name in service.cv_names()}
    outcomes = []
    # model first, then run: a model that fails leaves the previous models fully measured
    plan = [("lexical", "-", 1)] if "lexical" in strategies else []
    model_strategies = [s for s in strategies if s != "lexical"]
    plan += [(s, m, r) for m in models for r in range(1, runs + 1) for s in model_strategies]
    for strategy, model, run in plan:
        llm = None if strategy == "lexical" else llm_for(model)
        for job_name in JOB_CATEGORIES:
            job = service.job(job_name)
            relevant = relevant_cvs(list(cvs), job_name)
            started = time.perf_counter()
            ranked, calls, tied = run_strategy(
                strategy, job, cvs, llm, service.rank_prompt, preselect
            )
            outcome = Outcome(
                strategy=strategy,
                model=model,
                run=run,
                job=job_name,
                ranked=ranked,
                model_calls=calls,
                seconds=round(time.perf_counter() - started, 2),
                tied_with_top=tied,
                average_precision=round(average_precision(ranked, relevant), 4),
                precision_at_5=round(precision_at(ranked, relevant, 5), 4),
                ndcg_at_10=round(ndcg_at(ranked, relevant, 10), 4),
            )
            report(outcome)
            outcomes.append(outcome)
    return outcomes


@dataclass(frozen=True)
class Summary:
    """Means over jobs and runs; the spread is the standard deviation of the per-run MAP."""

    strategy: str
    model: str
    runs: int
    mean_average_precision: float
    map_spread: float
    precision_at_5: float
    ndcg_at_10: float
    model_calls_per_job: float
    seconds_per_job: float
    tied_with_top: float


def summarise(outcomes: list[Outcome]) -> list[Summary]:
    groups: dict[tuple[str, str], list[Outcome]] = {}
    for outcome in outcomes:
        groups.setdefault((outcome.strategy, outcome.model), []).append(outcome)
    summaries = []
    for (strategy, model), group in groups.items():
        per_run = [
            statistics.mean(o.average_precision for o in group if o.run == run)
            for run in sorted({o.run for o in group})
        ]
        summaries.append(
            Summary(
                strategy=strategy,
                model=model,
                runs=len(per_run),
                mean_average_precision=round(statistics.mean(per_run), 3),
                map_spread=round(statistics.pstdev(per_run), 3),
                precision_at_5=round(statistics.mean(o.precision_at_5 for o in group), 3),
                ndcg_at_10=round(statistics.mean(o.ndcg_at_10 for o in group), 3),
                model_calls_per_job=statistics.mean(o.model_calls for o in group),
                seconds_per_job=round(statistics.mean(o.seconds for o in group), 1),
                tied_with_top=round(statistics.mean(o.tied_with_top for o in group), 1),
            )
        )
    return summaries


def markdown_table(summaries: list[Summary]) -> str:
    lines = [
        "| Strategy | Model | Runs | MAP | ± | P@5 | NDCG@10 | Model calls / job | s / job "
        "| Tied for first |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s.strategy} | {s.model} | {s.runs} | {s.mean_average_precision:.3f} "
            f"| {s.map_spread:.3f} | {s.precision_at_5:.3f} | {s.ndcg_at_10:.3f} "
            f"| {s.model_calls_per_job:g} | {s.seconds_per_job:g} | {s.tied_with_top:g} |"
        )
    return "\n".join(lines)
