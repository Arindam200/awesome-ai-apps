from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models import GeneratedGame


DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[1] / "generated-games"


class StoredGame(BaseModel):
    id: str
    title: str
    prompt: str
    genre: str
    created_at: str
    approved: bool
    repaired: bool = False
    issues: list[str] = Field(default_factory=list)

    @property
    def play_url(self) -> str:
        return f"/games/{self.id}"


def storage_dir() -> Path:
    return Path(os.environ.get("GENERATED_GAMES_DIR", DEFAULT_STORAGE_DIR))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "game"


def _game_id(title: str, now: datetime) -> str:
    stamp = now.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{_slugify(title)}-{uuid4().hex[:6]}"


def save_game(game: GeneratedGame, root: Path | None = None) -> StoredGame:
    if not game.review.approved or game.review.issues or game.safety_issues:
        raise ValueError("Only approved generated games can be saved.")

    base = root or storage_dir()
    now = datetime.now(timezone.utc)
    record = StoredGame(
        id=_game_id(game.spec.title, now),
        title=game.spec.title,
        prompt=game.prompt,
        genre=game.spec.genre,
        created_at=now.isoformat(),
        approved=game.review.approved and not game.review.issues and not game.safety_issues,
        repaired=game.repaired,
        issues=[*game.review.issues, *game.safety_issues],
    )

    game_dir = base / record.id
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "index.html").write_text(game.html, encoding="utf-8")
    (game_dir / "metadata.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record


def load_games(root: Path | None = None) -> list[StoredGame]:
    base = root or storage_dir()
    if not base.exists():
        return []

    records: list[StoredGame] = []
    for metadata_path in base.glob("*/metadata.json"):
        try:
            record = StoredGame.model_validate_json(metadata_path.read_text(encoding="utf-8"))
            if record.approved and not record.issues:
                records.append(record)
        except (OSError, ValueError, json.JSONDecodeError):
            continue

    return sorted(records, key=lambda item: item.created_at, reverse=True)


def get_game(record_id: str, root: Path | None = None) -> StoredGame | None:
    for record in load_games(root):
        if record.id == record_id:
            return record
    return None


def get_game_html(record_id: str, root: Path | None = None) -> str | None:
    base = root or storage_dir()
    html_path = base / record_id / "index.html"
    if not html_path.exists():
        return None
    return html_path.read_text(encoding="utf-8")
