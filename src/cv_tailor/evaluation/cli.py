"""`cv-tailor-eval`: run the strategies, print a Markdown table, keep every outcome as JSON.

Outcomes are appended one JSON line at a time: a run that stops after an hour keeps what it
measured.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from cv_tailor.adapters.ollama_client import OllamaClient
from cv_tailor.config import MODEL
from cv_tailor.domain.protocols import LLMError
from cv_tailor.evaluation.harness import (
    DEFAULT_PRESELECT,
    STRATEGIES,
    Outcome,
    evaluate,
    markdown_table,
    summarise,
)
from cv_tailor.service import CVTailor


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cv-tailor-eval", description=__doc__)
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=list(STRATEGIES))
    parser.add_argument("--models", nargs="+", default=[MODEL], help="Ollama models")
    parser.add_argument("--runs", type=int, default=3, help="runs per model strategy")
    parser.add_argument("--preselect", type=int, default=DEFAULT_PRESELECT)
    parser.add_argument("--output", type=Path, default=Path("evaluation"))
    return parser.parse_args(argv)


def progress(outcome: Outcome) -> None:
    print(
        f"{outcome.strategy:8} {outcome.model:18} run {outcome.run} {outcome.job:30} "
        f"AP {outcome.average_precision:.2f}  {outcome.seconds:g}s",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse(argv)
    service = CVTailor(OllamaClient(MODEL))
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw = args.output / f"outcomes-{stamp}.jsonl"
    with raw.open("w") as sink:

        def record(outcome: Outcome) -> None:
            sink.write(json.dumps(outcome.to_dict()) + "\n")
            sink.flush()
            progress(outcome)

        try:
            outcomes = evaluate(
                service,
                args.strategies,
                args.models,
                args.runs,
                llm_for=OllamaClient,
                preselect=args.preselect,
                report=record,
            )
        except LLMError as exc:
            raise SystemExit(f"error: {exc} (outcomes so far: {raw})") from None
    table = markdown_table(summarise(outcomes))
    (args.output / f"summary-{stamp}.md").write_text(table + "\n")
    print(table)
    print(f"\noutcomes: {raw}", file=sys.stderr)
