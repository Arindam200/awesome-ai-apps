import json
import os
from typing import Any

from dotenv import load_dotenv
from memori import Memori
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover - optional dependency
    MongoClient = None  # type: ignore[misc]


load_dotenv()


class MemoriManager:
    """
    Thin wrapper around Memori + OpenAI client + SQLAlchemy engine.
    Reuses the pattern from ai_consultant_agent but tailored to a single learner.
    """

    def __init__(
        self,
        openai_api_key: str | None = None,
        db_url: str | None = None,
        sqlite_path: str = "./memori_study.sqlite",
        entity_id: str = "study-coach-user",
        process_id: str = "study-coach",
    ) -> None:
        """
        If `db_url` is not provided, falls back to local SQLite at `sqlite_path`.
        Supports:
        - Any SQLAlchemy URL (SQLite, Postgres, MySQL, CockroachDB, etc.).
        - MongoDB URLs starting with mongodb:// or mongodb+srv://.
        """
        self.sqlite_path = sqlite_path
        self.entity_id = entity_id
        self.process_id = process_id
        self.db_url = db_url or ""

        openai_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY is not set – cannot initialize Memori.")

        self.SessionLocal: sessionmaker | None = None

        # Decide connection strategy based on db_url scheme
        conn_arg: Any
        db_url_effective = self.db_url.strip()

        if db_url_effective.startswith("mongodb://") or db_url_effective.startswith(
            "mongodb+srv://"
        ):
            if MongoClient is None:
                raise RuntimeError(
                    "pymongo is required for MongoDB connections. "
                    "Install it or use a SQLAlchemy database URL."
                )
            mongo_client = MongoClient(db_url_effective)

            # Derive DB name from path; fallback to 'memori'
            from urllib.parse import urlparse

            parsed = urlparse(db_url_effective)
            db_name = parsed.path.lstrip("/") or "memori"

            def get_db():
                return mongo_client[db_name]

            conn_arg = get_db
        else:
            # SQLAlchemy path (SQLite / Postgres / MySQL / CockroachDB / etc.)
            if db_url_effective:
                database_url = db_url_effective
            else:
                database_url = f"sqlite:///{self.sqlite_path}"

            engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
            if database_url.startswith("sqlite"):
                engine_kwargs["connect_args"] = {"check_same_thread": False}

            engine = create_engine(database_url, **engine_kwargs)

            # Optional connectivity check
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=engine
            )
            conn_arg = self.SessionLocal

        client = OpenAI(api_key=openai_key)
        mem = Memori(conn=conn_arg).openai.register(client)
        mem.attribution(entity_id=self.entity_id, process_id=self.process_id)
        mem.config.storage.build()

        self.memori: Memori = mem
        self.openai_client = client

    def get_db(self) -> Session | None:
        if self.SessionLocal is None:
            return None
        return self.SessionLocal()

    # --- High-level “semantic” helpers for the Study Coach demo ---

    def log_learner_profile(self, profile_data: dict[str, Any]) -> None:
        """
        Store a structured learner profile in Memori via a dedicated document.
        We wrap the profile in a small JSON payload tagged as a study profile so
        it can be retrieved deterministically later via Memori.search().
        """
        payload = {
            "type": "study_profile",
            "version": 1,
            "profile": profile_data,
        }
        tagged_text = "STUDY_COACH_PROFILE " + json.dumps(payload, ensure_ascii=False)

        self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Store the following study coach learner profile document "
                        "in long-term memory so it can be recalled later:\n\n"
                        f"{tagged_text}"
                    ),
                },
            ],
        )

        # Best-effort explicit commit, mirroring other agents' patterns
        try:
            adapter = getattr(self.memori.config.storage, "adapter", None)
            if adapter is not None and hasattr(adapter, "commit"):
                adapter.commit()
        except Exception:
            # Non-fatal; Memori should still persist in most configurations.
            pass

    def log_study_session(self, session_summary: str) -> None:
        """
        Store a single study session summary (topic, duration, score, mood, etc.).
        """
        prompt = (
            "The following text summarizes one study session for this learner. "
            "Extract and remember: topic, difficulty, performance, misconceptions, "
            "and any motivation signals:\n\n"
            f"{session_summary}"
        )
        self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": "Confirm that you have updated the learner's memory.",
                },
            ],
        )

        # Best-effort explicit commit so sessions are durably stored
        try:
            adapter = getattr(self.memori.config.storage, "adapter", None)
            if adapter is not None and hasattr(adapter, "commit"):
                adapter.commit()
        except Exception:
            pass

    def summarize_progress(self, question: str) -> str:
        """
        Ask Memori/LLM to summarize progress, weak/strong topics, or patterns.
        `question` is phrased from the user's point of view (e.g. 'What are my weak topics?').
        """
        system_prompt = (
            "You are an AI study coach with long-term memory about the learner's "
            "past study sessions, topics, scores, and motivation. Answer the user's "
            "question using those memories. Be concrete about weak/strong topics "
            "and any patterns across time (time of day, resource type, etc.)."
        )
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
        return response.choices[0].message.content

    def get_latest_learner_profile(self) -> dict[str, Any] | None:
        """
        Attempt to retrieve the most recently stored learner profile from Memori
        using a semantic search for our tagged study profile documents.

        Returns:
            Dict representing the profile (compatible with LearnerProfile model),
            or None if nothing can be found/parsed.
        """
        search_fn = getattr(self.memori, "search", None)
        if search_fn is None:
            return None

        try:
            # Search for our tag; Memori returns stored documents/snippets, not
            # hallucinated content.
            results: list[Any] = search_fn("STUDY_COACH_PROFILE", limit=5) or []
        except Exception:
            return None

        for r in results:
            text = str(r)
            idx = text.find("{")
            jdx = text.rfind("}")
            if idx == -1 or jdx == -1:
                continue
            try:
                obj = json.loads(text[idx : jdx + 1])
            except Exception:
                continue

            if not isinstance(obj, dict):
                continue
            if obj.get("type") != "study_profile":
                continue
            profile = obj.get("profile")
            if isinstance(profile, dict):
                return profile

        return None
