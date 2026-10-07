"""Rewriting one CV to match a job description."""

import html
import re

from cv_tailor.domain.models import RewrittenCV
from cv_tailor.domain.prompting import job_and_cv
from cv_tailor.domain.protocols import LLMClient

# Small models wrap their answer in a code fence despite being told not to, sometimes leave it
# open, and sometimes add a note after it
OPENING_FENCE = re.compile(r"\A```[a-zA-Z]*[ \t]*\n")
CLOSING_FENCE = re.compile(r"^```[ \t]*$", re.MULTILINE)


def strip_wrapping_fence(text: str) -> str:
    """The answer without the fence around it, nor anything the model wrote after that fence.

    Only an answer that starts with a fence is wrapped. Its body ends at the last closing fence,
    so fenced blocks inside it are kept; an unclosed wrapper loses its opening line only.
    """
    text = text.strip()
    opening = OPENING_FENCE.match(text)
    if opening is None:
        return text
    body = text[opening.end() :]
    closings = list(CLOSING_FENCE.finditer(body))
    if closings:
        body = body[: closings[-1].start()]
    return body.strip()


def clean_markdown(text: str) -> str:
    """Strip a wrapping code fence, decode HTML entities, neutralise raw HTML tags."""
    body = strip_wrapping_fence(text)

    # Models emit entities such as &#39; in otherwise plain text
    body = html.unescape(body)

    # Re-escape angle brackets: the rewritten CV is data, it must not inject markup
    # into the HTML we hand to the DOCX and PDF exporters
    return body.replace("<", "&lt;").replace(">", "&gt;")


def rewrite(
    job_description: str, name: str, cv_content: str, llm: LLMClient, instructions: str
) -> RewrittenCV:
    """Return the CV rewritten in Markdown. Content is never invented, only reworded."""
    content = llm.complete(instructions, job_and_cv(job_description, cv_content))
    return RewrittenCV(name=name, content=clean_markdown(content))
