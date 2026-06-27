"""Tree-narrow + graph-traversal retrieval with verifiable citations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from .config import Settings, get_settings
from .llm import chat, chat_json

log = logging.getLogger(__name__)

ENTITY_PICK_PROMPT = """You are picking the most relevant entities from a knowledge graph.

QUESTION: {question}

CANDIDATE ENTITIES (id :: name :: type):
{candidates}

Return JSON: {{"ids": [list of up to {k} most relevant entity ids]}}
"""

ANSWER_PROMPT = """Answer the QUESTION using ONLY the SUBGRAPH context.
For every claim, cite the source(s) it came from in square brackets like [doc#chunk=3].
If the subgraph does not contain the answer, say so plainly.

QUESTION: {question}

SUBGRAPH:
{subgraph}
"""


@dataclass
class Answer:
    """A grounded answer with its supporting subgraph and citations."""

    text: str
    citations: list[str]
    subgraph_nodes: list[str]


def _load_graph(settings: Settings) -> nx.MultiDiGraph:
    path = settings.output_dir / "graph.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Graph not built yet. Run `python -m veritasgraph_rag.ingest` first. "
            f"(expected {path})"
        )
    return nx.node_link_graph(json.loads(path.read_text()), multigraph=True, directed=True)


def _format_candidates(graph: nx.MultiDiGraph) -> str:
    return "\n".join(
        f"{nid} :: {data.get('name', nid)} :: {data.get('type', 'Entity')}"
        for nid, data in graph.nodes(data=True)
    )


def _format_subgraph(graph: nx.MultiDiGraph, nodes: list[str]) -> str:
    lines: list[str] = []
    for nid in nodes:
        if nid not in graph:
            continue
        data = graph.nodes[nid]
        lines.append(f"NODE {nid} ({data.get('type','Entity')}): {data.get('name', nid)}  "
                     f"[{data.get('source','?')}]")
    seen: set[tuple[str, str, str]] = set()
    for nid in nodes:
        if nid not in graph:
            continue
        for _, tgt, edata in graph.out_edges(nid, data=True):
            key = (nid, tgt, edata.get("type", ""))
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"EDGE {nid} -[{edata.get('type','RELATED_TO')}]-> {tgt}  "
                f"({edata.get('evidence','')}) [{edata.get('source','?')}]"
            )
    return "\n".join(lines)


def answer(question: str, *, k: int = 6, hops: int = 1,
           settings: Settings | None = None) -> Answer:
    """Retrieve a subgraph and produce a grounded answer with citations."""
    settings = settings or get_settings()
    graph = _load_graph(settings)

    # 1) Tree narrow — pick the most relevant seed entities.
    pick = chat_json(
        ENTITY_PICK_PROMPT.format(
            question=question,
            candidates=_format_candidates(graph),
            k=k,
        ),
        settings=settings,
    )
    seeds: list[str] = [nid for nid in pick.get("ids", []) if nid in graph]

    # 2) Graph traversal — expand by ``hops``.
    nodes: set[str] = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        next_frontier: set[str] = set()
        for nid in frontier:
            next_frontier.update(graph.successors(nid))
            next_frontier.update(graph.predecessors(nid))
        nodes |= next_frontier
        frontier = next_frontier

    subgraph_text = _format_subgraph(graph, list(nodes))

    # 3) Grounded generation.
    text = chat(
        ANSWER_PROMPT.format(question=question, subgraph=subgraph_text),
        settings=settings,
    )
    citations = sorted({
        c.strip("[]") for c in _extract_bracketed(text)
    })
    return Answer(text=text, citations=citations, subgraph_nodes=sorted(nodes))


def _extract_bracketed(text: str) -> list[str]:
    import re
    return re.findall(r"\[[^\[\]]+\]", text)
