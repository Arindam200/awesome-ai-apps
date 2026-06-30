"""Document ingestion → chunks → entity/relationship extraction → graph build.

This is a minimal showcase that demonstrates the VeritasGraph pipeline end-to-end
in a single file. The production pipeline lives in the upstream repo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

import networkx as nx
from pypdf import PdfReader

from .config import Settings, get_settings
from .llm import chat_json

log = logging.getLogger(__name__)

EXTRACTION_PROMPT_TEMPLATE = """You are an information-extraction engine.

Given the TEXT below, return a JSON object with two keys:
  - "entities":      list of {{"id": snake_case_id, "name": str, "type": str}}
  - "relationships": list of {{"source": id, "target": id, "type": str, "evidence": str}}

Use snake_case ids consistent across chunks for the same real-world entity.
Return ONLY valid JSON.

TEXT:
\"\"\"{chunk}\"\"\"
"""


def _read_documents(input_dir: Path) -> Iterable[tuple[str, str]]:
    """Yield ``(doc_id, text)`` pairs for every supported file under ``input_dir``."""
    for path in sorted(input_dir.iterdir()):
        if path.is_dir():
            continue
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        elif suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
        else:
            log.debug("Skipping unsupported file %s", path.name)
            continue
        yield path.stem, text


def _chunk(text: str, size: int = 1500, overlap: int = 200) -> list[str]:
    """Naive character chunker — fine for a showcase, swap for a token-aware one in prod."""
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def build_graph(settings: Settings | None = None) -> nx.MultiDiGraph:
    """Build the property graph from documents in ``settings.input_dir``."""
    settings = settings or get_settings()
    graph: nx.MultiDiGraph = nx.MultiDiGraph()

    for doc_id, text in _read_documents(settings.input_dir):
        for chunk_idx, chunk in enumerate(_chunk(text)):
            try:
                payload = chat_json(
                    EXTRACTION_PROMPT_TEMPLATE.format(chunk=chunk),
                    settings=settings,
                )
            except Exception:  # noqa: BLE001 - best-effort showcase
                log.exception("Extraction failed for %s chunk %d", doc_id, chunk_idx)
                continue

            for ent in payload.get("entities", []):
                node_id = ent["id"]
                graph.add_node(
                    node_id,
                    name=ent.get("name", node_id),
                    type=ent.get("type", "Entity"),
                    source=f"{doc_id}#chunk={chunk_idx}",
                )
            for rel in payload.get("relationships", []):
                graph.add_edge(
                    rel["source"],
                    rel["target"],
                    type=rel.get("type", "RELATED_TO"),
                    evidence=rel.get("evidence", ""),
                    source=f"{doc_id}#chunk={chunk_idx}",
                )

    out_path = settings.output_dir / "graph.json"
    nx.write_graphml(graph, settings.output_dir / "graph.graphml")
    out_path.write_text(json.dumps(nx.node_link_data(graph), indent=2))
    log.info("Wrote graph: %d nodes, %d edges → %s", graph.number_of_nodes(),
             graph.number_of_edges(), out_path)
    return graph


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_graph()


if __name__ == "__main__":
    main()
