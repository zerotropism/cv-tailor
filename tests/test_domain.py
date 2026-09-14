"""Domain tests: no Ollama, no Streamlit, no network."""

import pytest
from pydantic import ValidationError

from cv_tailor.adapters.fake import FakeLLM
from cv_tailor.domain.models import Ranking
from cv_tailor.domain.prompting import job_and_cv
from cv_tailor.domain.ranking import Match, rank
from cv_tailor.domain.rewriting import rewrite

CVS = {"cv1": "python", "cv2": "network", "cv3": "cloud"}


def matches(*scores: float) -> list[Match]:
    return [Match(score=score, explanation="because") for score in scores]


def test_rank_returns_best_first() -> None:
    llm = FakeLLM(structured=matches(0.2, 0.9, 0.5))
    assert [r.name for r in rank("jd", CVS, llm, "instructions")] == [
        "cv2",
        "cv3",
        "cv1",
    ]


def test_rank_truncates_to_top_n() -> None:
    llm = FakeLLM(structured=matches(0.2, 0.9, 0.5))
    assert len(rank("jd", CVS, llm, "instructions", top_n=2)) == 2


def test_rank_calls_the_model_once_per_cv() -> None:
    llm = FakeLLM(structured=matches(0.1, 0.2, 0.3))
    rank("jd", CVS, llm, "instructions")
    assert len(llm.calls) == 3


def test_instructions_and_data_are_kept_apart() -> None:
    llm = FakeLLM(structured=matches(0.1, 0.2, 0.3))
    rank("jd text", CVS, llm, "INSTRUCTIONS")
    instructions, data = llm.calls[0]
    assert instructions == "INSTRUCTIONS"
    assert "INSTRUCTIONS" not in data


def test_cv_content_is_delimited() -> None:
    block = job_and_cv("jd text", "cv text")
    assert "<job_description>\njd text\n</job_description>" in block
    assert "<cv>\ncv text\n</cv>" in block


def test_score_outside_the_unit_interval_is_rejected() -> None:
    """A model answering 'Score: 85' must fail loudly, not rank first."""
    with pytest.raises(ValidationError):
        Ranking(name="cv1", score=85, explanation="x")


def test_rewrite_returns_markdown_for_the_named_cv() -> None:
    llm = FakeLLM(text="  # Tailored\n\n- one  ")
    result = rewrite("jd", "cv2", "content", llm, "instructions")
    assert result.name == "cv2"
    assert result.content == "# Tailored\n\n- one"


def test_code_fence_is_stripped() -> None:
    from cv_tailor.domain.rewriting import clean_markdown

    assert clean_markdown("```markdown\n# Title\n\n- item\n```") == "# Title\n\n- item"


def test_plain_markdown_is_left_alone() -> None:
    from cv_tailor.domain.rewriting import clean_markdown

    assert clean_markdown("# Title\n\n- item") == "# Title\n\n- item"


def test_inner_fences_are_preserved() -> None:
    """Only a fence wrapping the whole answer is a wrapper; inner ones are content."""
    from cv_tailor.domain.rewriting import clean_markdown

    text = "# Title\n\n```python\nprint(1)\n```\n\n- item"
    assert clean_markdown(text) == text


def test_html_entities_are_decoded() -> None:
    from cv_tailor.domain.rewriting import clean_markdown

    assert clean_markdown("d&#39;intrusion") == "d'intrusion"


def test_raw_html_cannot_reach_the_exporters() -> None:
    from cv_tailor.domain.rewriting import clean_markdown

    assert clean_markdown("&lt;style&gt;x&lt;/style&gt;") == "&lt;style&gt;x&lt;/style&gt;"
