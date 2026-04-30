from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://rag:rag@localhost:5432/boeing_rag"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "boeing_reports"

    boeing_pdf_dir: Path = Path("data/sample_pdfs")
    parsed_dir: Path = Path("data/parsed")
    page_image_dir: Path = Path("data/pages")
    context_cache_dir: Path = Path("data/context_cache")
    upload_dir: Path = Path("data/uploads")

    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.studio.nebius.com/v1"
    nebius_embed_model: str | None = None
    nebius_chat_model: str | None = None
    nebius_vision_model: str | None = None

    local_embed_dim: int = 1024
    reranker_provider: str = "lexical"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    sparse_model: str = "Qdrant/bm25"
    dense_vector_name: str = "dense"
    sparse_vector_name: str = "sparse"
    contextual_retrieval: bool = True
    contextual_prompt_version: str = "contextual-v1"
    contextual_context_chars: int = 12000
    contextual_chunk_chars: int = 2200
    contextual_max_tokens: int = 140

    vector_top_k: int = 40
    lexical_top_k: int = 40
    rerank_top_k: int = 12
    answer_context_chunks: int = 8
    answer_max_tokens: int = 1400

    chunk_target_chars: int = 1400
    chunk_overlap_chars: int = 200
    min_page_text_chars_for_ocr: int = 80
    docling_do_ocr: bool = False
    auto_ocr: bool = True
    visual_parse: bool = False
    visual_parse_max_pages: int = 4
    visual_parse_timeout_seconds: float = 90.0
    visual_parse_include_all_image_pages: bool = False

    @property
    def use_nebius_embeddings(self) -> bool:
        return bool(self.nebius_api_key and self.nebius_embed_model)

    @property
    def use_nebius_chat(self) -> bool:
        return bool(self.nebius_api_key and self.nebius_chat_model)

    @property
    def use_nebius_vision(self) -> bool:
        return bool(self.nebius_api_key and self.nebius_vision_model)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.parsed_dir.mkdir(parents=True, exist_ok=True)
    settings.page_image_dir.mkdir(parents=True, exist_ok=True)
    settings.context_cache_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
