"""Rewriting one CV to match a job description."""

import html
import re

from cv_tailor.domain.models import RewrittenCV
from cv_tailor.domain.prompting import job_and_cv
from cv_tailor.domain.protocols import LLMClient

# Small models wrap their answer in a code fence despite being told not to
FENCE = re.compile(r"\A\s*```[a-zA-Z]*\n(?P<body>.*?)\n?```\s*\Z", re.DOTALL)


def clean_markdown(text: str) -> str:
    """Strip a wrapping code fence, decode HTML entities, neutralise raw HTML tags."""
    match = FENCE.match(text.strip())
    body = match.group("body") if match else text.strip()

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
