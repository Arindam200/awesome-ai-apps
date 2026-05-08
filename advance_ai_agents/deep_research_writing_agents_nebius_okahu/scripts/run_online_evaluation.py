"""Run online LLM judge evaluation — generate posts on the fly and judge them.

This emulates a production evaluation pipeline where posts are generated
by the writing workflow and immediately evaluated by the LLM judge.

Usage:
    uv run python scripts/run_online_evaluation.py [--split SPLIT] [--workers N] [--nb-samples N]
"""

import click

from writing.evals.evaluation import run_online_evaluation
from writing.utils.logging import setup_logging
from writing.utils.okahu_utils import configure_okahu


@click.command()
@click.option(
    "--split",
    default="online_test",
    type=click.Choice(["dev_evaluator", "test_evaluator", "online_test"]),
    help="Which split to evaluate (default: online_test)",
)
@click.option(
    "--workers",
    default=1,
    type=int,
    help="Number of parallel threads (default: 1, generation is heavy)",
)
@click.option(
    "--nb-samples",
    default=None,
    type=int,
    help="Limit number of samples (default: all)",
)
def main(split: str, workers: int, nb_samples: int | None) -> None:
    """Run online evaluation: generate posts + judge them."""

    setup_logging()

    configure_okahu()
    f1 = run_online_evaluation(split=split, workers=workers, nb_samples=nb_samples)
    if f1 is not None:
        click.echo(f"F1 score (judge vs expert labels): {f1:.3f}")
    else:
        click.echo("Online evaluation complete (no F1 — simulating real-world usage).")


if __name__ == "__main__":
    main()
