"""The MCP adapter through the in-memory FastMCP client, with a fake model."""

import time

import pytest
from fastmcp import Client

from cv_tailor.adapters.fake import FakeLLM
from cv_tailor.domain.protocols import LLMUnavailable
from cv_tailor.domain.ranking import Match
from cv_tailor.server import create_server


def matches(*scores: float) -> list[Match]:
    return [Match(score=score, explanation="because") for score in scores]


TOOLS = {"list_cvs", "list_jobs", "rank_cvs", "rewrite_cv"}


async def test_tools_are_listed_and_read_only(make_service) -> None:
    async with Client(create_server(make_service(FakeLLM()))) as client:
        tools = await client.list_tools()
        templates = await client.list_resource_templates()
    assert {tool.name for tool in tools} == TOOLS
    assert all(tool.annotations.read_only_hint for tool in tools)
    assert {t.uri_template for t in templates} == {"cv://{name}", "job://{name}"}


async def test_rank_by_job_name_returns_structured_rankings(make_service) -> None:
    server = create_server(make_service(FakeLLM(structured=matches(0.2, 0.9, 0.5))))
    async with Client(server) as client:
        result = await client.call_tool("rank_cvs", {"job_name": "JD_Network_Engineer", "top_n": 2})
    rankings = result.structured_content["result"]
    assert [r["name"] for r in rankings] == ["CV_002_ml", "CV_003_cyber"]


async def test_rewrite_returns_the_markdown(make_service) -> None:
    server = create_server(make_service(FakeLLM(text="# Tailored")))
    arguments = {"cv_name": "CV_001_network", "job_description": "Network engineer"}
    async with Client(server) as client:
        result = await client.call_tool("rewrite_cv", arguments)
    assert result.structured_content == {"name": "CV_001_network", "content": "# Tailored"}


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("rewrite_cv", {"cv_name": "../secret", "job_description": "x"}, "Unknown CV"),
        ("rank_cvs", {}, "exactly one"),
        ("rank_cvs", {"job_name": "JD_Unknown"}, "Unknown job"),
    ],
)
async def test_bad_requests_come_back_as_tool_errors(make_service, tool, arguments, message):
    async with Client(create_server(make_service(FakeLLM()))) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error
    assert message in result.content[0].text


async def test_a_slow_model_is_cut_off(make_service) -> None:
    class SlowLLM(FakeLLM):
        def complete(self, instructions, data):
            time.sleep(1)
            return "late"

    server = create_server(make_service(SlowLLM()), timeout=0.1)
    arguments = {"cv_name": "CV_001_network", "job_description": "x"}
    async with Client(server) as client:
        result = await client.call_tool("rewrite_cv", arguments, raise_on_error=False)
    assert result.is_error
    assert "within 0.1s" in result.content[0].text


async def test_documents_are_readable_as_resources(make_service) -> None:
    async with Client(create_server(make_service(FakeLLM()))) as client:
        cv = await client.read_resource("cv://CV_001_network")
        job = await client.read_resource("job://JD_Network_Engineer")
    assert cv[0].text == "routing, BGP"
    assert job[0].text.startswith("Network engineer")


async def test_an_unreachable_model_server_is_named(make_service) -> None:
    class DownLLM(FakeLLM):
        def complete(self, instructions, data):
            raise LLMUnavailable("connection refused")

    arguments = {"cv_name": "CV_001_network", "job_description": "x"}
    async with Client(create_server(make_service(DownLLM()))) as client:
        result = await client.call_tool("rewrite_cv", arguments, raise_on_error=False)
    assert result.is_error
    assert "Ollama is unreachable" in result.content[0].text
