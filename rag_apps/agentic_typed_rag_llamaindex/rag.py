"""Document ingestion and a LlamaIndex in-memory knowledge base."""

from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from llama_index.core import VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode


DEFAULT_NEBIUS_API_BASE = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
MAX_URL_BYTES = 2_000_000


def nebius_api_base() -> str:
    """Return the Token Factory endpoint, honoring the NEBIUS_API_BASE override."""
    return os.getenv("NEBIUS_API_BASE", "").strip() or DEFAULT_NEBIUS_API_BASE


def build_embed_model(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    api_key: str | None = None,
) -> BaseEmbedding:
    """Create a Nebius embedding model for the knowledge base."""
    from llama_index.embeddings.nebius import NebiusEmbedding

    api_key = api_key or os.getenv("NEBIUS_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set NEBIUS_API_KEY before building the knowledge base")
    return NebiusEmbedding(
        model_name=model_name,
        api_key=api_key,
        api_base=nebius_api_base(),
    )


@dataclass(frozen=True)
class DocumentChunk:
    """A source span stored in the vector index."""

    source: str
    chunk_id: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    """A chunk paired with its retrieval similarity."""

    chunk: DocumentChunk
    score: float


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into sentence-aware word windows with deterministic overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    if not text.split():
        return []
    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        tokenizer=str.split,
    )
    return splitter.split_text(text)


def document_chunks(
    source: str,
    text: str,
    *,
    locator: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Build chunks with stable, human-readable identifiers."""
    texts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    prefix = f"{source}:{locator}" if locator else source
    return [
        DocumentChunk(source=source, chunk_id=f"{prefix}:c{index}", text=value)
        for index, value in enumerate(texts, start=1)
    ]


class KnowledgeBase:
    """A session-scoped LlamaIndex vector index with chunk-level lookups."""

    def __init__(self, embed_model: BaseEmbedding):
        self.embed_model = embed_model
        self._index = VectorStoreIndex(nodes=[], embed_model=embed_model)
        self._chunks: dict[tuple[str, str], DocumentChunk] = {}
        self._order: list[DocumentChunk] = []

    @property
    def chunks(self) -> tuple[DocumentChunk, ...]:
        return tuple(self._order)

    @property
    def count(self) -> int:
        return len(self._order)

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(chunk.source for chunk in self._order))

    @property
    def embedding_name(self) -> str:
        return getattr(self.embed_model, "model_name", type(self.embed_model).__name__)

    def add_document(
        self,
        source: str,
        text: str,
        *,
        locator: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> int:
        """Chunk, embed, and append one document to the index."""
        source = source.strip()
        if not source:
            raise ValueError("source must not be empty")
        chunks = document_chunks(
            source,
            text,
            locator=locator,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        return self.add_chunks(chunks)

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Embed and insert prepared chunks as LlamaIndex nodes."""
        new_chunks = [
            chunk for chunk in chunks if (chunk.source, chunk.chunk_id) not in self._chunks
        ]
        if not new_chunks:
            return 0

        nodes = [
            TextNode(
                id_=chunk.chunk_id,
                text=chunk.text,
                metadata={"source": chunk.source},
                excluded_embed_metadata_keys=["source"],
                excluded_llm_metadata_keys=["source"],
            )
            for chunk in new_chunks
        ]
        self._index.insert_nodes(nodes)
        for chunk in new_chunks:
            self._chunks[(chunk.source, chunk.chunk_id)] = chunk
            self._order.append(chunk)
        return len(new_chunks)

    def search(self, query: str, limit: int = 4) -> list[SearchResult]:
        """Return the nearest chunks ordered by cosine similarity."""
        if not query.strip() or limit <= 0 or not self._order:
            return []

        retriever = self._index.as_retriever(similarity_top_k=limit)
        results = []
        for node_with_score in retriever.retrieve(query):
            source = str(node_with_score.node.metadata.get("source", ""))
            chunk = self._chunks.get((source, node_with_score.node.node_id))
            if chunk is None:
                continue
            score = float(node_with_score.score or 0.0)
            results.append(
                SearchResult(chunk=chunk, score=round(min(max(score, 0.0), 1.0), 4))
            )
        return results

    def find_chunk(self, source: str, chunk_id: str) -> DocumentChunk | None:
        return self._chunks.get((source, chunk_id))


def extract_document_pages(data: bytes) -> list[str]:
    """Extract Markdown text page by page with LiteParse, fully locally."""
    from liteparse import LiteParse

    parser = LiteParse(output_format="markdown", quiet=True)
    result = parser.parse(data)
    return [
        (page.markdown or page.text or "").strip()
        for page in sorted(result.pages, key=lambda page: page.page_num)
    ]


def ingest_document(kb: KnowledgeBase, source: str, data: bytes) -> int:
    """Extract and index all text-bearing pages from an uploaded document."""
    pages = extract_document_pages(data)
    chunks = []
    for page_number, text in enumerate(pages, start=1):
        if text:
            chunks.extend(document_chunks(source, text, locator=f"p{page_number}"))
    if not chunks:
        raise ValueError(f"No extractable text found in {source}")
    return kb.add_chunks(chunks)


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        elif tag in {"br", "p", "div", "article", "section", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "article", "section", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Reduce HTML to readable text without third-party parsers."""
    parser = _ReadableHTMLParser()
    parser.feed(html)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def validate_public_url(url: str) -> None:
    """Reject malformed URLs and hosts that resolve outside the public internet."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not supported")

    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost":
        raise ValueError("Private or local URLs are not supported")

    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            answers = socket.getaddrinfo(hostname, parsed.port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"Could not resolve URL host: {hostname}") from exc
        addresses = {
            ipaddress.ip_address(str(answer[4][0]).split("%", 1)[0])
            for answer in answers
        }

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private or local URLs are not supported")


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url_text(url: str) -> str:
    """Fetch a bounded HTTP document and return readable text."""
    validate_public_url(url)
    request = Request(url, headers={"User-Agent": "typed-rag-demo/1.0"})
    opener = build_opener(_PublicRedirectHandler())
    with opener.open(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "text/plain"}:
            raise ValueError(f"Unsupported URL content type: {content_type}")
        body = response.read(MAX_URL_BYTES + 1)
        if len(body) > MAX_URL_BYTES:
            raise ValueError("URL content is larger than 2 MB")
        charset = response.headers.get_content_charset() or "utf-8"

    decoded = body.decode(charset, errors="replace")
    text = html_to_text(decoded) if content_type == "text/html" else decoded.strip()
    if not text:
        raise ValueError("No readable text found at URL")
    return text
