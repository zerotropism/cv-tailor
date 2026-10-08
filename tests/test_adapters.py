"""Adapter tests: message construction, schema wiring and error translation. No server needed."""

import httpx
import pytest

from cv_tailor.adapters.ollama_client import OllamaClient, translate_errors
from cv_tailor.domain.protocols import LLMTimeout, LLMUnavailable
from cv_tailor.domain.ranking import Match


def test_instructions_go_to_system_and_data_to_user() -> None:
    messages = OllamaClient("m")._messages("INSTRUCTIONS", "DATA")
    assert messages == [
        {"role": "system", "content": "INSTRUCTIONS"},
        {"role": "user", "content": "DATA"},
    ]


def test_match_schema_constrains_the_score() -> None:
    schema = Match.model_json_schema()
    assert schema["properties"]["score"]["minimum"] == 0.0
    assert schema["properties"]["score"]["maximum"] == 1.0
    assert set(schema["required"]) == {"score", "explanation"}


def test_transport_timeouts_become_domain_timeouts() -> None:
    @translate_errors
    def boom():
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(LLMTimeout):
        boom()


def test_connection_failures_become_domain_unavailability() -> None:
    @translate_errors
    def boom():
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMUnavailable):
        boom()


def test_an_empty_timeout_message_still_says_what_happened() -> None:
    """Async read timeouts carry no text: the error used to print as an empty line."""

    @translate_errors
    def boom():
        raise httpx.ReadTimeout("")

    with pytest.raises(LLMTimeout, match="ReadTimeout"):
        boom()


class Recorder:
    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": '{"score": 0.5, "explanation": "x"}'}}


class AsyncRecorder(Recorder):
    instances: list["AsyncRecorder"] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        AsyncRecorder.instances.append(self)

    async def chat(self, **kwargs):
        return super().chat(**kwargs)


@pytest.mark.parametrize("think", [False, True])
def test_every_call_says_whether_the_model_may_think(monkeypatch, think) -> None:
    client = OllamaClient("m", think=think)
    client._client = Recorder()
    monkeypatch.setattr("cv_tailor.adapters.ollama_client.ollama.AsyncClient", AsyncRecorder)
    AsyncRecorder.instances.clear()

    client.complete("i", "d")
    client.complete_structured("i", "d", Match)
    client.complete_structured_many("i", ["a", "b"], Match)

    batch = AsyncRecorder.instances[0].calls
    assert [call["think"] for call in client._client.calls + batch] == [think] * 4


def test_thinking_is_off_by_default() -> None:
    assert OllamaClient("m").think is False
