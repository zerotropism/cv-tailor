# cv-tailor

Rank a batch of CVs against a job description with a local LLM, then tailor the best match to
that offer. Runs entirely on your machine through [Ollama](https://ollama.com/) — no CV ever
leaves it.

The rewriting is deliberately constrained: it rewords and reorders what the CV already contains,
and is instructed never to invent a skill, a responsibility or an experience.

## Installation

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and a running Ollama server.

```bash
uv sync
ollama pull llama3.2:3b
uv run cv-tailor
```

## Configuration

`config.yaml` holds the model name and the two prompts. The model can be overridden per run,
which is what makes comparing models practical:

```bash
CV_TAILOR_MODEL=qwen3:8b uv run cv-tailor
```

CVs are read from `data/cvs/` (one `.txt` per CV); `data/jobs/` holds sample job descriptions,
and is never scanned by the ranker.

## Architecture

```
src/cv_tailor/
├── domain/            no Streamlit, no Ollama, no I/O
│   ├── models.py      Ranking, RewrittenCV
│   ├── protocols.py   LLMClient, and the error types the UI catches
│   ├── prompting.py   delimited data blocks
│   ├── ranking.py     rank(jd, cvs, llm, instructions)
│   └── rewriting.py   rewrite(...) and Markdown cleanup
├── adapters/
│   ├── ollama_client.py   structured outputs, timeout, bounded concurrency
│   ├── fake.py            FakeLLM, used by the tests
│   ├── loader.py          reads CVs and .docx job descriptions
│   └── exporters.py       Markdown to DOCX, PDF, TXT
├── config.py
├── service.py         CVTailor: documents by name, rank and rewrite, shared by every adapter
├── server.py          MCP adapter: tools and resource templates, model calls under a timeout
└── ui/
    ├── main.py        Streamlit screens
    └── launch.py      `cv-tailor` console script
```

The domain depends on a `LLMClient` protocol, never on Ollama. That is what lets the whole test
suite run with no server: `FakeLLM` implements the same protocol and returns canned answers.

## MCP server

`cv-tailor-mcp` serves the same operations over stdio, through the shared `CVTailor` service.

| Kind | Name | Returns |
|---|---|---|
| Tool | `list_cvs()`, `list_jobs()` | document names |
| Tool | `rank_cvs(job_name or job_description, top_n=3)` | the best CVs, scored and explained |
| Tool | `rewrite_cv(cv_name, job_name or job_description)` | the CV reworded in Markdown |
| Resource template | `cv://{name}`, `job://{name}` | the text of one document |

Documents are addressed by name and looked up among the `.txt` files of `data/cvs/` and
`data/jobs/`: a name such as `../config` matches nothing and is refused. Every model call runs in
a worker thread and is cut off after `CV_TAILOR_TOOL_TIMEOUT` seconds (600 by default: ranking
calls the model once per CV). With [mcp-servers-cli](https://pypi.org/project/mcp-servers-cli/):

```bash
uvx mcp-servers-cli call rank_cvs '{"job_name": "JD_Network_Engineer"}' \
  --stdio "uv run --directory $PWD cv-tailor-mcp"
uvx mcp-servers-cli agent "Which three CVs fit JD_Network_Engineer best, and why?" \
  --model qwen3.5:4b-mlx --stdio "uv run --directory $PWD cv-tailor-mcp"
```

## Prompt handling

Instructions and data are sent as separate messages — instructions in the `system` role, the job
description and the CV in the `user` role, each wrapped in its own tag. Scores come back through
a JSON schema derived from a pydantic model rather than from a `Score:` line, so a CV cannot
forge one by containing that text.

This reduces prompt injection, it does not eliminate it: the model is still free to follow an
instruction it finds in a CV. Treat the ranking as advisory.

## Model requirements

The ranker asks for a JSON object constrained by a schema. `llama3.2:3b` handles it, but its
rewriting quality is modest and it wraps its answer in a code fence despite being told not to
(stripped automatically). A 7B or larger model produces noticeably better rewrites.

## Performance

Ranking makes one model call per CV, sequentially bounded by a semaphore. On a compute-bound
local machine the concurrency does not help much — measured 25.5s at concurrency 1 versus 22.1s
at concurrency 4 on 8 CVs with `llama3.2:3b`. The semaphore is there to cap queued requests, not
to speed them up. Expect roughly 3 minutes for 50 CVs on that setup.

## Tests

```bash
uv run pytest
```

No Ollama needed: the domain runs against `FakeLLM`, the adapter tests exercise message
construction and error translation without a server, the exporter tests check that DOCX, PDF
and TXT carry the same content, and the service and MCP tests run on small temporary data
directories through the in-memory FastMCP client.

## Dependencies

| Package        | Role                              |
|----------------|-----------------------------------|
| `streamlit`    | User interface                    |
| `ollama`       | Local model backend               |
| `pydantic`     | Domain models and output schemas  |
| `httpx`        | Transport errors, timeouts        |
| `python-docx`  | DOCX export and .docx reading     |
| `weasyprint`   | PDF export                        |
| `markdown`, `beautifulsoup4` | Markdown to HTML  |
| `pyyaml`       | Configuration                     |
| `fastmcp`      | MCP server                        |
