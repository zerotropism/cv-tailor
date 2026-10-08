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
├── api.py             HTTP adapter: FastAPI routes over the same service
├── evaluation/        metrics, BM25, strategies, and the cv-tailor-eval CLI
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
a worker thread and is cut off after `CV_TAILOR_TIMEOUT` seconds (600 by default: ranking
calls the model once per CV). With [mcp-servers-cli](https://pypi.org/project/mcp-servers-cli/):

```bash
uvx mcp-servers-cli call rank_cvs '{"job_name": "JD_Network_Engineer"}' \
  --stdio "uv run --directory $PWD cv-tailor-mcp"
uvx mcp-servers-cli agent "Which three CVs fit JD_Network_Engineer best, and why?" \
  --model qwen3.5:4b-mlx --stdio "uv run --directory $PWD cv-tailor-mcp"
```

## HTTP API

`cv-tailor-api` serves the same service with FastAPI on `127.0.0.1:8000`
(`CV_TAILOR_API_HOST`, `CV_TAILOR_API_PORT`). It has no authentication: keep it local.

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/health` | | `{"status": "ok"}` |
| `GET` | `/cvs`, `/jobs` | | document names |
| `GET` | `/cvs/{name}`, `/jobs/{name}` | | the document as text, 404 if unknown |
| `POST` | `/rank` | `job_name` or `job_description`, `top_n` | rankings, best first |
| `POST` | `/rewrite` | `cv_name`, `job_name` or `job_description` | the rewritten CV |

A request with both or neither job field is rejected with 422. Model failures map to 503 when
Ollama is unreachable, 504 after `CV_TAILOR_TIMEOUT` seconds and 502 for any other model error.
The interactive documentation is at `/docs`.

```bash
uv run cv-tailor-api &
curl -s localhost:8000/jobs
curl -s -X POST localhost:8000/rank -H "Content-Type: application/json" \
  -d '{"job_name": "JD_Network_Engineer", "top_n": 3}'
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

Reasoning is switched off (`think=False` on every Ollama call). With it, `qwen3.5:4b-mlx` spent
about 95 seconds thinking before each two-sentence score, against 11 seconds without; models
without reasoning, such as `llama3.2:3b`, accept the setting.

## Performance

Ranking makes one model call per CV, sequentially bounded by a semaphore. On a compute-bound
local machine the concurrency does not help much — measured 25.5s at concurrency 1 versus 22.1s
at concurrency 4 on 8 CVs with `llama3.2:3b`. The semaphore is there to cap queued requests, not
to speed them up. Expect roughly 3 minutes for 50 CVs on that setup.

## Evaluation

`cv-tailor-eval` measures how well a ranking strategy puts the right CVs first.

Reference. Each CV name ends with its category (`CV_021_network`) and each sample job targets
one category, so a CV is relevant to a job when the categories match: 12 or 13 relevant CVs out
of 50 per job, with no manual labelling. The category is a proxy: a network profile may be
partly relevant to an infrastructure job.

Metrics. Relevance is binary, so the harness reports ranking metrics rather than a rank
correlation, which is ill-defined when almost every pair is tied: mean average precision (MAP),
precision in the first 5 (P@5) and NDCG@10, averaged over the four jobs; the spread is the
standard deviation of MAP across runs. It also counts model calls, seconds per job, and how
many CVs share the best score, since tied CVs keep their file order.

Strategies.

| Strategy | Model calls per job | What it does |
|---|---|---|
| `lexical` | 0 | BM25 between the job description and each CV, accents and case ignored |
| `llm` | 50 | the model scores every CV, as the UI, the MCP server and the API do |
| `hybrid` | `--preselect`, 15 by default | BM25 shortlist, then the model reorders it |

```bash
uv run cv-tailor-eval --strategies lexical
uv run cv-tailor-eval --models llama3.2:3b qwen3.5:4b-mlx --runs 3
```

Each model is measured completely, run after run, before the next one starts: a model that
fails leaves the previous ones fully measured. `--think` lets reasoning models think, at the
cost of minutes per call; `--timeout` sets the seconds allowed per model call (120 by
default). Both are recorded under the summary table.

Each outcome (strategy, model, run, job, full ranking, metrics, timing) is appended to
`evaluation/outcomes-<time>.jsonl` as it is measured, so an interrupted run keeps its data; the
table is printed and written to `evaluation/summary-<time>.md`.

Measured on the bundled data:

| Strategy | Model | Runs | MAP | P@5 | NDCG@10 | Model calls / job |
|---|---|---|---|---|---|---|
| lexical | - | 1 | 0.907 | 0.900 | 0.918 | 0 |

The sample CVs and jobs were generated with a shared vocabulary, which favours a lexical
method; real CVs, with synonyms and mixed languages, would narrow the gap. The harness measures
ranking only: whether a rewrite stays faithful to the CV is not evaluated.

## Tests

```bash
uv run pytest
```

No Ollama needed: the domain runs against `FakeLLM`, the adapter tests exercise message
construction and error translation without a server, the exporter tests check that DOCX, PDF
and TXT carry the same content, and the service and MCP tests run on small temporary data
directories through the in-memory FastMCP client and FastAPI's `TestClient`.

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
| `fastapi`, `uvicorn` | HTTP API                    |
