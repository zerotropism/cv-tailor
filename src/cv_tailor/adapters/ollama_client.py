"""Ollama adapter: structured outputs, explicit timeout, bounded concurrency."""

import asyncio
import functools

import httpx
import ollama

from cv_tailor.domain.protocols import LLMError, LLMTimeout, LLMUnavailable, ModelT

DEFAULT_TIMEOUT_SECONDS = 120.0
# Ollama is compute-bound on a local machine: this caps queued requests, it does not speed them up
DEFAULT_CONCURRENCY = 4


def translate_errors(func):
    """Keep httpx out of the domain and out of the UI."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(str(exc)) from exc
        except (httpx.ConnectError, ConnectionError) as exc:
            raise LLMUnavailable(str(exc)) from exc
        except (ollama.ResponseError, ollama.RequestError) as exc:
            raise LLMError(str(exc)) from exc

    return wrapper


class OllamaClient:
    """Talks to a local Ollama server. Instructions go to the system role, data to the user role."""

    def __init__(
        self,
        model: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.concurrency = concurrency
        # timeout is an httpx keyword forwarded by the client, not an Ollama option
        self._client = ollama.Client(timeout=timeout)

    def _messages(self, instructions: str, data: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": instructions},
            {"role": "user", "content": data},
        ]

    @translate_errors
    def complete(self, instructions: str, data: str) -> str:
        response = self._client.chat(model=self.model, messages=self._messages(instructions, data))
        return response["message"]["content"]

    @translate_errors
    def complete_structured(self, instructions: str, data: str, schema: type[ModelT]) -> ModelT:
        response = self._client.chat(
            model=self.model,
            messages=self._messages(instructions, data),
            format=schema.model_json_schema(),
        )
        return schema.model_validate_json(response["message"]["content"])

    @translate_errors
    def complete_structured_many(
        self, instructions: str, data: list[str], schema: type[ModelT]
    ) -> list[ModelT]:
        """Run the batch with bounded concurrency. Results keep the input order."""
        return asyncio.run(self._gather(instructions, data, schema))

    async def _gather(
        self, instructions: str, data: list[str], schema: type[ModelT]
    ) -> list[ModelT]:
        client = ollama.AsyncClient(timeout=self.timeout)
        limit = asyncio.Semaphore(self.concurrency)

        async def one(block: str) -> ModelT:
            async with limit:
                response = await client.chat(
                    model=self.model,
                    messages=self._messages(instructions, block),
                    format=schema.model_json_schema(),
                )
                return schema.model_validate_json(response["message"]["content"])

        return await asyncio.gather(*(one(block) for block in data))
