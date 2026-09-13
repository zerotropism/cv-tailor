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

    def complete_structured_many(
        self, instructions: str, data: list[str], schema: type[ModelT]
    ) -> list[ModelT]:
        """Same as complete_structured over a batch. Order of results matches the input."""
        ...


class LLMError(RuntimeError):
    """Any failure while talking to the model backend."""


class LLMTimeout(LLMError):
    """The backend took longer than the configured timeout."""


class LLMUnavailable(LLMError):
    """The backend could not be reached."""
