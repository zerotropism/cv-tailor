"""In-memory LLM for tests: deterministic, no service, no network."""

from pydantic import BaseModel

from cv_tailor.domain.protocols import ModelT


class FakeLLM:
    """Records every call and replays canned answers."""

    def __init__(self, text: str = "# Rewritten CV", structured: list[BaseModel] | None = None):
        self.text = text
        self.structured = list(structured or [])
        self.calls: list[tuple[str, str]] = []

    def complete(self, instructions: str, data: str) -> str:
        self.calls.append((instructions, data))
        return self.text

    def complete_structured(self, instructions: str, data: str, schema: type[ModelT]) -> ModelT:
        self.calls.append((instructions, data))
        if not self.structured:
            raise AssertionError("FakeLLM ran out of structured answers")
        return schema.model_validate(self.structured.pop(0).model_dump())

    def complete_structured_many(
        self, instructions: str, data: list[str], schema: type[ModelT]
    ) -> list[ModelT]:
        return [self.complete_structured(instructions, block, schema) for block in data]
