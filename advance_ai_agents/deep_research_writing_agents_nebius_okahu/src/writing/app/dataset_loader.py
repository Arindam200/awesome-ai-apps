"""Dataset loader for LinkedIn posts with Pydantic models."""

import logging
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DATASET_DIR = (
    Path(__file__).parent.parent.parent.parent / "datasets" / "linkedin_paul_iusztin"
)


class Label(StrEnum):
    """Binary label for post evaluation."""

    PASS = "pass"
    FAIL = "fail"


class DatasetEntry(BaseModel):
    """A single entry in the LinkedIn posts dataset."""

    slug: str
    urn: str | None = None
    linkedin_url: str | None = None
    local_post: str
    local_media: list[str] | None = None
    reactions: int | None = None
    comments: int | None = None
    shares: int | None = None
    local_guideline: str | None = None
    local_seed: str | None = None
    local_research: str | None = None
    scope: list[str] | None = None
    local_generated_post: str | None = None
    label: Label | None = None
    critique: str | None = None

    def _read_file(self, field: str, base_dir: Path) -> str:
        """Read a file referenced by a field name."""

        value = getattr(self, field, None)
        if not value:
            return ""
        path = base_dir / value.lstrip("./")
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def post_content(self, base_dir: Path) -> str:
        """Read the ground truth post text."""

        return self._read_file("local_post", base_dir)

    def generated_content(self, base_dir: Path) -> str:
        """Read the generated post text."""

        return self._read_file("local_generated_post", base_dir)

    def guideline_content(self, base_dir: Path) -> str:
        """Read the guideline text."""

        return self._read_file("local_guideline", base_dir)

    def seed_content(self, base_dir: Path) -> str:
        """Read the seed text."""

        return self._read_file("local_seed", base_dir)

    def research_content(self, base_dir: Path) -> str:
        """Read the research text."""

        return self._read_file("local_research", base_dir)

    def media_paths(self, base_dir: Path) -> list[Path]:
        """Resolve media file paths."""

        if not self.local_media:
            return []
        return [
            base_dir / m.lstrip("./")
            for m in self.local_media
            if (base_dir / m.lstrip("./")).exists()
        ]


class PostExample(BaseModel):
    """A few-shot example post for the writer."""

    slug: str
    content: str


class MediaExample(BaseModel):
    """A few-shot example media for the image generator."""

    slug: str
    media_path: Path


class DatasetExamples(BaseModel):
    """Container for few-shot examples loaded from the dataset."""

    post_examples: list[PostExample] = Field(default_factory=list)
    media_examples: list[MediaExample] = Field(default_factory=list)

    def format_post_examples(self) -> str:
        """Format post examples as text for prompt injection."""

        if not self.post_examples:
            return "<none>"

        parts: list[str] = []
        for i, ex in enumerate(self.post_examples, 1):
            parts.append(f"--- Example {i} ---\n{ex.content}\n--- End Example {i} ---")

        return "\n\n".join(parts)


class LabeledSample(BaseModel):
    """A labeled sample for LLM judge evaluation."""

    slug: str
    ground_truth: str
    generated: str
    label: Label
    critique: str


def load_dataset() -> list[DatasetEntry]:
    """Load the full dataset index."""

    index_path = DATASET_DIR / "index.yaml"
    if not index_path.exists():
        logger.warning(f"Dataset index not found: {index_path}")
        return []

    raw = yaml.safe_load(index_path.read_text(encoding="utf-8"))

    return [DatasetEntry(**entry) for entry in raw]


def load_by_scope(scope: str) -> list[DatasetEntry]:
    """Load dataset entries filtered by a specific scope value."""

    return [e for e in load_dataset() if e.scope and scope in e.scope]


def load_labeled_samples(
    label_filter: Label | None = None,
) -> list[LabeledSample]:
    """Load all labeled samples with ground truth and generated text.

    Args:
        label_filter: If provided, only return samples with this label.

    Returns:
        List of LabeledSample objects.
    """

    entries = load_dataset()
    samples: list[LabeledSample] = []

    for entry in entries:
        if entry.label is None or entry.critique is None:
            continue
        if label_filter is not None and entry.label != label_filter:
            continue

        ground_truth = entry.post_content(DATASET_DIR)
        generated = entry.generated_content(DATASET_DIR)
        if not ground_truth or not generated:
            continue

        samples.append(
            LabeledSample(
                slug=entry.slug,
                ground_truth=ground_truth,
                generated=generated,
                label=entry.label,
                critique=entry.critique,
            )
        )

    return samples


def load_examples() -> DatasetExamples:
    """Load few-shot examples from the dataset based on the scope field.

    - scope contains 'train_generator' -> used as post text examples
    - scope contains 'train_image_generator' -> used as media examples

    Returns:
        DatasetExamples with deterministic, always-identical examples.
    """

    entries = load_dataset()

    post_examples: list[PostExample] = []
    media_examples: list[MediaExample] = []

    for entry in entries:
        if not entry.scope:
            continue

        if "train_generator" in entry.scope:
            content = entry.post_content(DATASET_DIR)
            if content:
                post_examples.append(PostExample(slug=entry.slug, content=content))

        if "train_image_generator" in entry.scope:
            paths = entry.media_paths(DATASET_DIR)
            if paths:
                media_examples.append(
                    MediaExample(slug=entry.slug, media_path=paths[0])
                )

    return DatasetExamples(
        post_examples=post_examples,
        media_examples=media_examples,
    )
