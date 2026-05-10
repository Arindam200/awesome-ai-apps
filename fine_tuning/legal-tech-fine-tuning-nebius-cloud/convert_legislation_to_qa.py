#!/usr/bin/env python3
"""
Convert legislation.jsonl (flat statutory text) into chat JSONL for RAG-style fine-tuning.

Each output line is one training example:
  {"messages":[{"role":"user","content":...},{"role":"assistant","content":...}]}

User turns embed a *simulated retrieved chunk* (context) plus a question; assistant
answers using only extractive material from that chunk (summaries = first sentences),
so supervised targets stay grounded without a second LLM.

Usage:
  python convert_legislation_to_qa.py \\
      --input legislation.jsonl \\
      --output legislation_qa.jsonl

  python convert_legislation_to_qa.py --input legislation.jsonl --output /tmp/sample.jsonl --max-records 2

"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Iterator


def clean_legislation_text(text: str, title: str = "") -> str:
    """Drop URL, repeated head metadata, and normalise whitespace."""
    t = text.strip()
    if t.startswith("http://") or t.startswith("https://"):
        t = re.sub(r"^https?://\S+\s*", "", t, count=1)

    # Trim boilerplate before the operative enactment wording where possible
    for anchor in (r"An Act to make provision", r"BE IT ENACTED", r"as follows:—"):
        m = re.search(anchor, t, flags=re.I)
        if m and m.start() < 2500:
            t = t[m.start() :]
            break
    else:
        # Fall back: jump to first occurrence of known title phrase
        if title:
            key = title.strip()[:40]
            pos = t.find(key)
            if 0 < pos < 1200:
                t = t[pos:]

    t = re.sub(r"\s+", " ", t)
    return t.strip()


def split_sentences(text: str, max_sentences: int = 6) -> list[str]:
    """Lightweight sentence split for statute prose."""
    # Avoid splitting on decimals in "s. 1" / "1.2"
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(0-9\"])", text)
    out: list[str] = []
    buf = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if buf and len(buf) + 1 + len(p) < 12:
            buf += " " + p
            continue
        if buf:
            out.append(buf)
            buf = p
        else:
            buf = p
        if len(out) >= max_sentences - 1 and buf:
            break
    if buf and len(out) < max_sentences:
        out.append(buf)
    return out if out else [text[:800]]


def summarising_answer(chunk: str, max_chars: int = 1200) -> str:
    """Short extractive 'summary' — first sentences only."""
    sents = split_sentences(chunk, max_sentences=5)
    text = " ".join(sents)
    if len(text) > max_chars:
        text = text[: max_chars - 3].rsplit(" ", 1)[0] + "..."
    return text


def bullet_points_answer(chunk: str, max_items: int = 6) -> str:
    sents = split_sentences(chunk, max_sentences=max_items)
    return "\n".join(f"- {s.strip()}" for s in sents if len(s.strip()) > 20)


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Sliding-window chunks with overlap."""
    t = text
    if len(t) <= max_chars:
        return [t]
    chunks: list[str] = []
    start = 0
    step = max(256, max_chars - overlap)
    while start < len(t):
        end = min(start + max_chars, len(t))
        piece = t[start:end]
        # try to break at last space before end
        if end < len(t):
            last_sp = piece.rfind(" ")
            if last_sp > max_chars * 0.6:
                piece = piece[:last_sp]
                end = start + last_sp
        chunks.append(piece.strip())
        if end >= len(t):
            break
        start = start + step
        if start >= len(t):
            break
    return [c for c in chunks if c]


def rag_user_message(context: str, question: str, title: str | None = None) -> str:
    header = (
        "You are a UK legislation assistant. Use ONLY the Context below. "
        "If the context is insufficient, say what is missing. Do not invent citations or dates.\n\n"
    )
    meta = f"Legislation: {title}\n\n" if title else ""
    return (
        header
        + meta
        + "Context:\n"
        + context
        + "\n\nQuestion:\n"
        + question
    )


def iter_qa_rows(
    record: dict[str, Any],
    max_chunk_chars: int,
    overlap: int,
    doc_index: int,
) -> Iterator[dict[str, Any]]:
    title = (record.get("title") or "Unknown Act").strip()
    text = clean_legislation_text(record.get("text") or "", title=title)
    rid = str(record.get("id") or f"doc_{doc_index}")

    if not text:
        return

    # 1) Metadata-style turn (short; helps citation behaviour)
    meta_bits = [title]
    if record.get("year_number"):
        meta_bits.append(f"Year/chapter reference in data: {record['year_number']}")
    if record.get("leg_type"):
        meta_bits.append(f"Type: {record['leg_type']}")

    yield {
        "messages": [
            {
                "role": "user",
                "content": (
                    "What legislation record is described below? Give the short title "
                    "and any identifier you can infer.\n\n"
                    + "\n".join(meta_bits[:3])
                ),
            },
            {
                "role": "assistant",
                "content": (
                    f"The short title appears to be «{title}». "
                    f"Use the official text on legislation.gov.uk for authoritative citation."
                ),
            },
        ],
        "meta": {"source_id": rid, "kind": "metadata"},
    }

    chunks = chunk_text(text, max_chunk_chars, overlap)

    for ci, chunk in enumerate(chunks):
        if len(chunk) < 80:
            continue
        base_meta = {"source_id": rid, "chunk_index": ci, "title": title}

        # RAG-style turns: questions + extractive targets
        pairs: list[tuple[str, str, str]] = [
            (
                "summarise_plain",
                "Summarise the main provisions in this excerpt in plain English (2–5 sentences). Use only the context.",
                summarising_answer(chunk),
            ),
            (
                "bullets",
                "List the main points from this excerpt as bullet points. Use only what appears in the context.",
                bullet_points_answer(chunk),
            ),
            (
                "topic",
                "In one or two sentences, what subject matter does this excerpt address? Base your answer solely on the context.",
                summarising_answer(chunk, max_chars=600),
            ),
            (
                "quote_key",
                "Identify the core obligation or rule expressed in this passage and quote the shortest phrase from the context that supports it.",
                chunk[: min(900, len(chunk))] + ("..." if len(chunk) > 900 else ""),
            ),
        ]

        for qi, (kind, question, answer) in enumerate(pairs):
            yield {
                "messages": [
                    {
                        "role": "user",
                        "content": rag_user_message(chunk, question, title),
                    },
                    {"role": "assistant", "content": answer.strip()},
                ],
                "meta": {**base_meta, "kind": kind, "qa_index": qi},
            }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="legislation.jsonl", help="Input JSONL path")
    ap.add_argument(
        "--output",
        default="legislation_qa.jsonl",
        help="Output JSONL path (messages + optional meta)",
    )
    ap.add_argument("--max-chunk-chars", type=int, default=3500)
    ap.add_argument("--overlap", type=int, default=400)
    ap.add_argument("--max-records", type=int, default=0, help="0 = all lines")
    ap.add_argument(
        "--include-meta",
        action="store_true",
        help="Keep meta (source_id, chunk_index) per line; default is messages-only for trainers",
    )
    args = ap.parse_args()

    written = 0
    with open(args.input, encoding="utf-8") as fin, open(
        args.output, "w", encoding="utf-8"
    ) as fout:
        for di, line in enumerate(fin):
            if args.max_records and di >= args.max_records:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Skip line {di+1}: {e}")
                continue
            for row in iter_qa_rows(rec, args.max_chunk_chars, args.overlap, di):
                if args.include_meta:
                    out = row
                else:
                    out = {"messages": row["messages"]}
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                written += 1

    print(f"Wrote {written} examples to {args.output}")


if __name__ == "__main__":
    main()
