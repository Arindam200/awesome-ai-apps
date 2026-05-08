"""Local LLM judge evaluation harness with Okahu/Monocle tracing."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from writing.evals.dataset import load_offline_eval_items, load_online_eval_items
from writing.evals.metric import BinaryLLMJudgeMetric, JudgeScore
from writing.utils.okahu_utils import trace_span

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvalResult:
    """A single local evaluation result."""

    slug: str
    expected_label: str | None
    score: JudgeScore


def _compute_f1(results: list[EvalResult]) -> float:
    """Compute F1 score between LLM judge predictions and true dataset labels."""

    labeled_results = [
        result for result in results if result.expected_label is not None
    ]
    if not labeled_results:
        logger.warning("No samples with true labels found — cannot compute F1.")
        return 0.0

    true_labels = [
        1 if result.expected_label == "pass" else 0 for result in labeled_results
    ]
    pred_labels = [int(result.score.value) for result in labeled_results]

    tp = sum(t == 1 and p == 1 for t, p in zip(true_labels, pred_labels))
    fp = sum(t == 0 and p == 1 for t, p in zip(true_labels, pred_labels))
    fn = sum(t == 1 and p == 0 for t, p in zip(true_labels, pred_labels))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    logger.info(
        "F1=%.3f (precision=%.3f, recall=%.3f) over %d samples",
        f1,
        precision,
        recall,
        len(labeled_results),
    )

    return f1


def _run_parallel(
    items: list[dict[str, Any]],
    workers: int,
    evaluator: Callable[[dict[str, Any]], EvalResult],
) -> list[EvalResult]:
    """Run evaluation work in a small thread pool."""

    if workers <= 1:
        return [evaluator(item) for item in items]

    results: list[EvalResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(evaluator, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())

    return results


def _record_score_trace(
    span_name: str,
    *,
    split: str,
    slug: str,
    model: str,
    expected_label: str | None,
    score: JudgeScore,
) -> None:
    """Emit a small trace span with judge score metadata."""

    with trace_span(
        span_name,
        {
            "split": split,
            "slug": slug,
            "model": model,
            "expected_label": expected_label,
            "actual_label": score.label,
            "score": score.value,
            "critique": score.critique,
            "reason": score.reason,
        },
    ):
        pass


def _record_f1_trace(
    span_name: str,
    *,
    split: str,
    model: str,
    f1: float | None,
    sample_count: int,
) -> None:
    """Emit run-level F1 metadata for Okahu/Monocle."""

    with trace_span(
        span_name,
        {
            "split": split,
            "model": model,
            "f_score": f1,
            "sample_count": sample_count,
        },
    ):
        pass


def run_evaluation(
    split: str = "test_evaluator",
    workers: int = 1,
    nb_samples: int | None = None,
) -> float:
    """Run the LLM judge on pre-generated posts from a dataset split."""

    logger.info("Running offline evaluation on split '%s'...", split)

    items = load_offline_eval_items(split)
    if nb_samples is not None:
        items = items[:nb_samples]

    metric = BinaryLLMJudgeMetric()

    def evaluate_item(sample: dict[str, Any]) -> EvalResult:
        with trace_span(
            "eval.offline.sample",
            {
                "split": split,
                "slug": sample["slug"],
                "model": metric._model,
                "expected_label": sample.get("label"),
            },
        ):
            score = metric.score(
                guideline=sample["guideline"],
                research=sample.get("research", ""),
                output=sample["generated_post"],
            )
            _record_score_trace(
                "eval.offline.score",
                split=split,
                slug=sample["slug"],
                model=metric._model,
                expected_label=sample.get("label"),
                score=score,
            )
            logger.info(
                "Evaluated %s: expected=%s actual=%s value=%.1f",
                sample["slug"],
                sample.get("label"),
                score.label,
                score.value,
            )
            return EvalResult(
                slug=sample["slug"],
                expected_label=sample.get("label"),
                score=score,
            )

    with trace_span(
        "eval.offline.run",
        {
            "split": split,
            "workers": workers,
            "nb_samples": nb_samples or len(items),
            "metric": metric.name,
            "model": metric._model,
        },
    ):
        results = _run_parallel(items, workers, evaluate_item)
        f1 = _compute_f1(results)
        _record_f1_trace(
            "eval.offline.summary",
            split=split,
            model=metric._model,
            f1=f1,
            sample_count=len(results),
        )

    logger.info("Offline evaluation complete. Check Okahu traces for details.")

    return f1


def run_online_evaluation(
    split: str = "online_test",
    workers: int = 1,
    nb_samples: int | None = None,
) -> float | None:
    """Generate posts on the fly and judge them with the LLM judge."""

    logger.info("Running online evaluation on split '%s'...", split)

    items = load_online_eval_items(split)
    if nb_samples is not None:
        items = items[:nb_samples]

    metric = BinaryLLMJudgeMetric()

    def evaluate_item(sample: dict[str, Any]) -> EvalResult:
        from writing.app.generate_post import generate_post

        with trace_span(
            "eval.online.sample",
            {
                "split": split,
                "slug": sample["slug"],
                "model": metric._model,
                "expected_label": sample.get("label"),
            },
        ):
            logger.info("Generating post for: %s...", sample.get("slug", "unknown"))
            generated = asyncio.run(
                generate_post(sample["guideline"], sample.get("research", ""))
            )
            generated_post = generated.post.content

            score = metric.score(
                guideline=sample["guideline"],
                research=sample.get("research", ""),
                output=generated_post,
            )
            _record_score_trace(
                "eval.online.score",
                split=split,
                slug=sample["slug"],
                model=metric._model,
                expected_label=sample.get("label"),
                score=score,
            )
            logger.info(
                "Generated + evaluated %s: expected=%s actual=%s value=%.1f",
                sample["slug"],
                sample.get("label"),
                score.label,
                score.value,
            )
            return EvalResult(
                slug=sample["slug"],
                expected_label=sample.get("label"),
                score=score,
            )

    with trace_span(
        "eval.online.run",
        {
            "split": split,
            "workers": workers,
            "nb_samples": nb_samples or len(items),
            "metric": metric.name,
            "model": metric._model,
        },
    ):
        results = _run_parallel(items, workers, evaluate_item)

        f1: float | None = None
        if any(result.expected_label is not None for result in results):
            f1 = _compute_f1(results)
        else:
            logger.info("Skipping F1 computation — no expert labels available.")
        _record_f1_trace(
            "eval.online.summary",
            split=split,
            model=metric._model,
            f1=f1,
            sample_count=len(results),
        )

    logger.info("Online evaluation complete. Check Okahu traces for details.")

    return f1
