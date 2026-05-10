from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(value: str, length: int = 24) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def infer_report_year(file_name: str) -> int | None:
    match = re.search(r"(20\d{2}|201\d)", file_name)
    return int(match.group(1)) if match else None


def infer_report_year_from_text(text: str) -> int | None:
    candidates = [int(match) for match in re.findall(r"\b(20\d{2}|201\d)\b", text)]
    reasonable = [year for year in candidates if 2010 <= year <= 2030]
    return reasonable[0] if reasonable else None


def infer_report_type(file_name: str) -> str:
    lower = file_name.lower()
    if "sustain" in lower or "environment" in lower or "socialimpact" in lower:
        return "sustainability_report"
    if "annual" in lower or "ar" in lower:
        return "annual_report"
    return "unknown"


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def split_text(text: str, target_chars: int, overlap_chars: int) -> list[str]:
    text = clean_text(text)
    if len(text) <= target_chars:
        return [text] if text else []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > target_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                end = start + target_chars
                chunks.append(paragraph[start:end].strip())
                start = max(end - overlap_chars, end)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= target_chars:
            current = candidate
            continue
        if current:
            chunks.append(current.strip())
        tail = current[-overlap_chars:] if overlap_chars and current else ""
        current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

    if current:
        chunks.append(current.strip())
    return chunks
