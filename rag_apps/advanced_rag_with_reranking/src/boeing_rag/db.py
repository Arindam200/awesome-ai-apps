from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from boeing_rag.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine():
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from boeing_rag import orm  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_chunk_columns()


def _ensure_chunk_columns() -> None:
    inspector = inspect(engine)
    if "chunks" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("chunks")}
    statements: list[str] = []
    if "raw_text" not in columns:
        statements.append("ALTER TABLE chunks ADD COLUMN raw_text TEXT")
    if "contextual_text" not in columns:
        statements.append("ALTER TABLE chunks ADD COLUMN contextual_text TEXT")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
