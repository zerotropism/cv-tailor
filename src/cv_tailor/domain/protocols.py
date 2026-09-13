"""The domain talks to a model through this contract only."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMClient(Protocol):
    """Instructions and data are passed separately so adapters can keep them apart."""

    def complete(self, instructions: str, data: str) -> str:
        """Free-form completion, returned as text."""
        ...

    def complete_structured(self, instructions: str, data: str, schema: type[ModelT]) -> ModelT:
        """Completion constrained by a JSON schema, returned as a validated model."""
        ...
