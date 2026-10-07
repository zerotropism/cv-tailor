"""The evaluation harness: metrics checked by hand, strategies run against a scripted model."""

import re

import pytest

from cv_tailor.adapters.fake import FakeLLM
from cv_tailor.evaluation.harness import (
    JOB_CATEGORIES,
    evaluate,
    markdown_table,
    relevant_cvs,
    run_strategy,
    summarise,
)
from cv_tailor.evaluation.lexical import lexical_ranking, tokens
from cv_tailor.evaluation.metrics import average_precision, ndcg_at, precision_at, tied_with_top
from cv_tailor.service import CVTailor


def test_average_precision_by_hand() -> None:
    # relevant at ranks 1 and 3: (1/1 + 2/3) / 2
    assert average_precision(["a", "b", "c", "d"], {"a", "c"}) == pytest.approx(5 / 6)
    assert average_precision(["a", "c", "b"], {"a", "c"}) == 1.0


def test_average_precision_needs_a_relevant_cv() -> None:
    with pytest.raises(ValueError):
        average_precision(["a"], set())


def test_precision_and_ndcg() -> None:
    assert precision_at(["a", "b", "c", "d", "e"], {"a", "c"}, 5) == 0.4
    assert ndcg_at(["a", "c", "b"], {"a", "c"}, 10) == 1.0
    assert ndcg_at(["b", "a", "c"], {"a", "c"}, 10) < 1.0


def test_ties_with_the_best_score_are_counted() -> None:
    assert tied_with_top([0.8, 0.8, 0.5, 0.8]) == 3
    assert tied_with_top([0.9, 0.8]) == 1


def test_tokens_ignore_case_and_accents() -> None:
    assert tokens("Ingénieur Réseau, BGP/OSPF") == ["ingenieur", "reseau", "bgp", "ospf"]


def test_lexical_ranking_puts_the_matching_document_first() -> None:
    documents = {"a": "kubernetes terraform", "b": "bgp ospf routing", "c": "pytorch"}
    assert lexical_ranking("network engineer: BGP and OSPF routing", documents)[0] == "b"


def test_relevance_comes_from_the_category_in_the_name() -> None:
    names = ["CV_001_network", "CV_002_ml", "CV_003_network"]
    assert relevant_cvs(names, "JD_Network_Engineer") == {"CV_001_network", "CV_003_network"}
    with pytest.raises(ValueError, match="no CV"):
        relevant_cvs(names, "JD_Cybersecurity_Analyst")


class CategoryLLM(FakeLLM):
    """Scores 0.9 when the CV mentions the job's category word, 0.1 otherwise."""

    def complete_structured(self, instructions, data, schema):
        self.calls.append((instructions, data))
        category = re.search(r"category (\w+)", data).group(1)
        score = 0.9 if data.count(category) >= 2 else 0.1
        return schema.model_validate({"score": score, "explanation": "scripted"})


CATEGORY_WORDS = {"cyber": "cyber", "infrastructure": "infra", "ml": "learning", "network": "net"}


@pytest.fixture
def service(tmp_path) -> CVTailor:
    """Two CVs per category, and the four sample job names, each naming its category word."""
    cv_dir, job_dir = tmp_path / "cvs", tmp_path / "jobs"
    cv_dir.mkdir()
    job_dir.mkdir()
    number = 0
    for category, word in CATEGORY_WORDS.items():
        for _ in range(2):
            number += 1
            (cv_dir / f"CV_{number:03}_{category}.txt").write_text(f"skills {word} {word}")
    for job, category in JOB_CATEGORIES.items():
        (job_dir / f"{job}.txt").write_text(f"category {CATEGORY_WORDS[category]}")
    return CVTailor(CategoryLLM(), cv_dir, job_dir, rank_prompt="rank", rewrite_prompt="x")


def test_hybrid_calls_the_model_on_the_shortlist_only(service) -> None:
    cvs = {name: service.cv(name) for name in service.cv_names()}
    llm = CategoryLLM()
    job = service.job("JD_Network_Engineer")
    ranked, calls, _ = run_strategy("hybrid", job, cvs, llm, "rank", preselect=3)
    assert calls == len(llm.calls) == 3
    assert sorted(ranked) == sorted(cvs)


def test_model_strategies_need_a_model(service) -> None:
    with pytest.raises(ValueError, match="needs a model"):
        run_strategy("llm", "job", {"a": "x"}, None, "rank")


def test_every_strategy_is_evaluated_and_summarised(service) -> None:
    outcomes = evaluate(
        service, ["lexical", "llm", "hybrid"], ["fake"], 2, llm_for=lambda m: CategoryLLM()
    )
    # lexical once, the two model strategies twice, for each of the four jobs
    assert len(outcomes) == 4 * (1 + 2 * 2)
    llm = [o for o in outcomes if o.strategy == "llm"]
    assert all(o.average_precision == 1.0 and o.model_calls == 8 for o in llm)
    summaries = {s.strategy: s for s in summarise(outcomes)}
    assert summaries["llm"].runs == 2
    assert summaries["llm"].mean_average_precision == 1.0
    assert "| llm | fake | 2 | 1.000 |" in markdown_table(list(summaries.values()))


def test_the_cli_writes_outcomes_and_a_summary(tmp_path, capsys) -> None:
    """The lexical strategy needs no model: the CLI runs it on the bundled data."""
    import json

    from cv_tailor.evaluation.cli import main

    main(["--strategies", "lexical", "--output", str(tmp_path)])
    lines = next(tmp_path.glob("outcomes-*.jsonl")).read_text().splitlines()
    outcomes = [json.loads(line) for line in lines]
    assert [o["job"] for o in outcomes] == list(JOB_CATEGORIES)
    assert next(tmp_path.glob("summary-*.md")).read_text().startswith("| Strategy |")
    assert "| lexical | - | 1 |" in capsys.readouterr().out
