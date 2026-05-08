"""Run LLM judge evaluation on a dataset split.

Usage:
    uv run python scripts/run_evaluation.py [--split SPLIT] [--workers N]
"""

import click

from writing.evals.evaluation import run_evaluation
from writing.utils.logging import setup_logging
from writing.utils.okahu_utils import configure_okahu


@click.command()
@click.option(
    "--split",
    default="dev_evaluator",
    type=click.Choice(["dev_evaluator", "test_evaluator"]),
    help="Which split to evaluate (default: dev_evaluator)",
)
@click.option(
    "--workers",
    default=1,
    type=int,
    help="Number of parallel evaluation threads (default: 1 for cleaner traces)",
)
@click.option(
    "--nb-samples",
    default=None,
    type=int,
    help="Limit number of samples to evaluate (default: all)",
)
def main(split: str, workers: int, nb_samples: int | None) -> None:
    """Run LLM judge evaluation with Okahu/Monocle tracing."""

    setup_logging()

    configure_okahu()
    f1 = run_evaluation(split=split, workers=workers, nb_samples=nb_samples)
    click.echo(f"F1 score (judge vs expert labels): {f1:.3f}")


if __name__ == "__main__":
    main()
