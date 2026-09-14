"""Domain models. No Streamlit, no Ollama, no I/O."""

from pydantic import BaseModel, Field


class Ranking(BaseModel):
    """How well one CV matches a job description."""

    name: str
    score: float = Field(ge=0.0, le=1.0)
    explanation: str


class RewrittenCV(BaseModel):
    """A CV rewritten to match a job description, in Markdown."""

    name: str
    content: str
