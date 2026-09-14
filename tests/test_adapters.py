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
