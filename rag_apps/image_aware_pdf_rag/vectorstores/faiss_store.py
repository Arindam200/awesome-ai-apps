
"""Local FAISS vector store with chunk metadata and persistence."""

from __future__ import annotations

from contextlib import contextmanager
import copy
import errno
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Iterable, Iterator
from uuid import uuid4

import faiss
import numpy as np

from interfaces.vector_store import SearchResult, VectorDocument


class _PersistenceLockUnavailable(PermissionError):
    """The persistence lock cannot be acquired due to filesystem access."""


@contextmanager
def _persistence_lock(directory: Path) -> Iterator[None]:
    """Serialize persistence within this process and across processes."""
    key = str(directory.resolve())
    with _directory_locks_guard:
        process_lock = _directory_locks.setdefault(key, threading.RLock())
    with process_lock:
        with _file_persistence_lock(directory):
            yield


_directory_locks_guard = threading.Lock()
_directory_locks: dict[str, threading.RLock] = {}


@contextmanager
def _file_persistence_lock(directory: Path) -> Iterator[None]:
    """Serialize version activation, cleanup, and snapshot loading."""
    lock_path = directory / ".persistence.lock"
    try:
        lock_file = lock_path.open("a+b")
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
            raise _PersistenceLockUnavailable(
                exc.errno, exc.strerror, exc.filename
            ) from exc
        raise

    with lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            while True:
                lock_file.seek(0)
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if getattr(exc, "winerror", None) == 5:
                        raise _PersistenceLockUnavailable(
                            exc.errno, exc.strerror, exc.filename
                        ) from exc
                    if exc.errno not in (errno.EACCES, errno.EDEADLK):
                        if exc.errno in (errno.EPERM, errno.EROFS):
                            raise _PersistenceLockUnavailable(
                                exc.errno, exc.strerror, exc.filename
                            ) from exc
                        raise
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
                    raise _PersistenceLockUnavailable(
                        exc.errno, exc.strerror, exc.filename
                    ) from exc
                raise
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class FAISSVectorStore:
    """FAISS-backed implementation of the VectorStore contract.

    Vectors use inner-product similarity. For cosine similarity,
    supply L2-normalized document and query embeddings.
    """

    INDEX_FILENAME = "index.faiss"
    METADATA_FILENAME = "metadata.json"
    VERSIONS_DIRNAME = "versions"
    CURRENT_FILENAME = "CURRENT"
    RETAINED_VERSIONS = 2

    def __init__(
        self,
        dimension: int | None = None,
        persist_dir: str | Path | None = None,
    ) -> None:
        if dimension is not None and (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 1
        ):
            raise ValueError("dimension must be a positive integer")

        self.persist_dir = Path(persist_dir) if persist_dir else None
        self.dimension = dimension

        self.index: Any = None
        self._next_faiss_id = 1

        # Stable application chunk ID -> FAISS integer ID.
        self._chunk_to_faiss: dict[str, int] = {}

        # FAISS integer ID -> stored document fields.
        self._documents: dict[int, dict[str, Any]] = {}
        self._mutation_lock = threading.RLock()

        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _write_transaction(self) -> Iterator[None]:
        """Reload the latest snapshot and atomically persist one mutation."""
        with self._mutation_lock:
            if self.persist_dir is None:
                snapshot = self._snapshot_state()
                try:
                    yield
                except BaseException:
                    self._restore_state(snapshot)
                    raise
                return

            with _persistence_lock(self.persist_dir):
                current_path = self.persist_dir / self.CURRENT_FILENAME
                legacy_metadata = self.persist_dir / self.METADATA_FILENAME
                if current_path.exists() or legacy_metadata.exists():
                    configured_dimension = self.dimension
                    latest = self._load_unlocked(self.persist_dir)
                    if (
                        configured_dimension is not None
                        and latest.dimension != configured_dimension
                    ):
                        raise ValueError(
                            "Persisted vector dimension does not match this store"
                        )
                    self._restore_state(latest._snapshot_state())

                snapshot = self._snapshot_state()
                try:
                    yield
                    self._save_unlocked()
                except BaseException:
                    self._restore_state(snapshot)
                    raise

    def _snapshot_state(self) -> tuple[Any, ...]:
        """Copy mutable index state for rollback after a failed write."""
        return (
            self.dimension,
            faiss.clone_index(self.index) if self.index is not None else None,
            self._next_faiss_id,
            self._chunk_to_faiss.copy(),
            copy.deepcopy(self._documents),
        )

    def _restore_state(self, snapshot: tuple[Any, ...]) -> None:
        """Restore mutable index state from a transaction snapshot."""
        (
            self.dimension,
            self.index,
            self._next_faiss_id,
            self._chunk_to_faiss,
            self._documents,
        ) = snapshot

    def _create_index(self, dimension: int) -> None:
        """Create an index that supports explicit integer IDs."""

        self.dimension = dimension
        base_index = faiss.IndexFlatIP(dimension)
        self.index = faiss.IndexIDMap2(base_index)

    @staticmethod
    def _validate_embedding(
        embedding: Iterable[float],
        expected_dimension: int | None = None,
    ) -> np.ndarray:
        """Validate numeric type, 1D shape, and dimension conformance of an embedding."""
        try:
            vector = np.asarray(list(embedding), dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding must contain numeric values") from exc

        if vector.ndim != 1 or vector.size == 0:
            raise ValueError("Embedding must be a non-empty one-dimensional vector")

        if not np.isfinite(vector).all():
            raise ValueError("Embedding must contain only finite values")

        if expected_dimension is not None and vector.size != expected_dimension:
            raise ValueError(
                f"Embedding dimension is {vector.size}; "
                f"expected {expected_dimension}"
            )

        return vector

    def add_documents(self, documents: list[VectorDocument]) -> None:
        """Add documents, replacing any existing documents with the same IDs."""

        if not documents:
            return

        with self._write_transaction():
            prepared: list[tuple[VectorDocument, np.ndarray]] = []
            seen_ids: set[str] = set()
            expected_dimension = self.dimension

            for document in documents:
                if not isinstance(document.id, str) or not document.id.strip():
                    raise ValueError("Document ID must be a non-empty string")

                if document.id in seen_ids:
                    raise ValueError(f"Duplicate document ID: {document.id}")

                seen_ids.add(document.id)

                if not isinstance(document.text, str) or not document.text.strip():
                    raise ValueError(f"Document {document.id} has empty text")

                if not isinstance(document.metadata, dict):
                    raise ValueError("Document metadata must be a dictionary")

                vector = self._validate_embedding(
                    document.embedding,
                    expected_dimension,
                )

                if expected_dimension is None:
                    expected_dimension = int(vector.size)

                prepared.append((document, vector))

            # Validate the entire batch before modifying the existing index.
            if self.dimension is None:
                self._create_index(expected_dimension)
            elif self.index is None:
                self._create_index(self.dimension)

            existing_ids = [
                document.id
                for document, _ in prepared
                if document.id in self._chunk_to_faiss
            ]
            self._delete_unlocked(existing_ids)

            vectors = np.vstack([vector for _, vector in prepared]).astype(
                np.float32,
                copy=False,
            )
            faiss_ids = np.arange(
                self._next_faiss_id,
                self._next_faiss_id + len(prepared),
                dtype=np.int64,
            )
            self.index.add_with_ids(vectors, faiss_ids)

            for (document, _), faiss_id in zip(prepared, faiss_ids):
                integer_id = int(faiss_id)
                self._chunk_to_faiss[document.id] = integer_id
                self._documents[integer_id] = {
                    "id": document.id,
                    "text": document.text,
                    "metadata": dict(document.metadata),
                }

            self._next_faiss_id += len(prepared)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return the most similar matching documents."""

        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")

        if filters is not None and not isinstance(filters, dict):
            raise ValueError("filters must be a dictionary or None")

        if self.index is None or self.index.ntotal == 0:
            return []

        query = self._validate_embedding(
            query_embedding,
            self.dimension,
        ).reshape(1, -1)

        # Apply metadata filters in the application layer. Fetch all current
        # candidates so filtering does not unnecessarily hide valid matches.
        candidate_count = int(self.index.ntotal)
        scores, ids = self.index.search(query, candidate_count)

        results: list[SearchResult] = []

        for score, faiss_id in zip(scores[0], ids[0]):
            integer_id = int(faiss_id)

            if integer_id == -1:
                continue

            record = self._documents.get(integer_id)
            if record is None:
                continue

            metadata = record["metadata"]

            if filters and any(
                metadata.get(key) != value
                for key, value in filters.items()
            ):
                continue

            results.append(
                SearchResult(
                    id=record["id"],
                    text=record["text"],
                    metadata=dict(metadata),
                    score=float(score),
                )
            )

            if len(results) >= top_k:
                break

        return results

    def delete(
        self,
        ids: list[str],
        *,
        save: bool = True,
    ) -> None:
        """Delete chunks by their stable application IDs."""

        if not ids:
            return

        if not save:
            with self._mutation_lock:
                self._delete_unlocked(ids)
            return

        with self._write_transaction():
            self._delete_unlocked(ids)

    def _delete_unlocked(self, ids: list[str]) -> None:
        """Delete chunks by stable IDs while a write transaction is held."""
        integer_ids = [
            self._chunk_to_faiss[chunk_id]
            for chunk_id in set(ids)
            if chunk_id in self._chunk_to_faiss
        ]

        if not integer_ids:
            return

        self.index.remove_ids(np.asarray(integer_ids, dtype=np.int64))

        for integer_id in integer_ids:
            record = self._documents.pop(integer_id, None)

            if record:
                self._chunk_to_faiss.pop(record["id"], None)

    def delete_source(self, source_id: str) -> int:
        """Delete every chunk belonging to one PDF; return count removed."""

        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id must be a non-empty string")

        with self._write_transaction():
            chunk_ids = [
                record["id"]
                for record in self._documents.values()
                if record["metadata"].get("source_id") == source_id
            ]
            self._delete_unlocked(chunk_ids)
        return len(chunk_ids)

    def save(self) -> None:
        """Persist the FAISS index and its associated metadata."""

        if self.persist_dir is None:
            return

        with self._write_transaction():
            pass

    def _save_unlocked(self) -> None:
        """Persist the current state while the persistence lock is held."""
        if self.persist_dir is None:
            return

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "dimension": self.dimension,
            "next_faiss_id": self._next_faiss_id,
            "documents": {
                str(faiss_id): record
                for faiss_id, record in self._documents.items()
            },
        }

        version = uuid4().hex
        versions_dir = self.persist_dir / self.VERSIONS_DIRNAME
        versions_dir.mkdir(parents=True, exist_ok=True)
        for stale_staging in versions_dir.glob(".tmp-*"):
            if stale_staging.is_dir():
                shutil.rmtree(stale_staging)
        for stale_pointer in self.persist_dir.glob(
            f".{self.CURRENT_FILENAME}.*.tmp"
        ):
            if stale_pointer.is_file():
                stale_pointer.unlink()

        staging_dir = versions_dir / f".tmp-{version}"
        version_dir = versions_dir / version
        current_path = self.persist_dir / self.CURRENT_FILENAME
        temporary_current = (
            self.persist_dir / f".{self.CURRENT_FILENAME}.{version}.tmp"
        )
        activated = False
        staging_dir.mkdir()

        try:
            if self.index is not None:
                faiss.write_index(
                    self.index,
                    str(staging_dir / self.INDEX_FILENAME),
                )

            (staging_dir / self.METADATA_FILENAME).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            staging_dir.replace(version_dir)

            temporary_current.write_text(version, encoding="ascii")
            temporary_current.replace(current_path)
            activated = True

            committed_versions = sorted(
                (
                    path
                    for path in versions_dir.iterdir()
                    if path.is_dir()
                    and len(path.name) == 32
                    and all(
                        character in "0123456789abcdef"
                        for character in path.name
                    )
                ),
                key=lambda path: path.stat().st_mtime_ns,
                reverse=True,
            )
            retained = {version}
            for path in committed_versions:
                if len(retained) >= self.RETAINED_VERSIONS:
                    break
                retained.add(path.name)

            for path in committed_versions:
                if path.name not in retained:
                    try:
                        shutil.rmtree(path)
                    except OSError:
                        pass
        except BaseException:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            if temporary_current.exists():
                temporary_current.unlink()
            if not activated and version_dir.exists():
                shutil.rmtree(version_dir)
            raise

    @classmethod
    def load(cls, persist_dir: str | Path) -> "FAISSVectorStore":
        """Load a previously saved store."""

        directory = Path(persist_dir)
        if not directory.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {directory / cls.METADATA_FILENAME}"
            )

        try:
            with _persistence_lock(directory):
                return cls._load_unlocked(directory)
        except _PersistenceLockUnavailable:
            current_path = directory / cls.CURRENT_FILENAME

            def read_current_version() -> str | None:
                """Read the active snapshot version hash from current_path."""
                try:
                    return current_path.read_text(encoding="ascii").strip()
                except FileNotFoundError:
                    return None

            for attempt in range(3):
                version_before = read_current_version()
                try:
                    return cls._load_unlocked(directory)
                except (FileNotFoundError, RuntimeError, ValueError) as exc:
                    if (
                        isinstance(exc, ValueError)
                        and str(exc)
                        != "Saved FAISS index and metadata are inconsistent"
                    ):
                        raise

                    version_after = read_current_version()
                    if version_after == version_before or attempt == 2:
                        raise

            raise RuntimeError("Unable to load a stable FAISS snapshot")

    @classmethod
    def _load_unlocked(cls, directory: Path) -> "FAISSVectorStore":
        """Load index and metadata from disk without acquiring a file lock."""
        current_path = directory / cls.CURRENT_FILENAME
        if current_path.exists():
            version = current_path.read_text(encoding="ascii").strip()
            if len(version) != 32 or any(
                character not in "0123456789abcdef" for character in version
            ):
                raise ValueError("Saved FAISS version pointer is invalid")

            version_dir = directory / cls.VERSIONS_DIRNAME / version
            metadata_path = version_dir / cls.METADATA_FILENAME
            index_path = version_dir / cls.INDEX_FILENAME
        else:
            # Support stores written before versioned persistence was introduced.
            metadata_path = directory / cls.METADATA_FILENAME
            index_path = directory / cls.INDEX_FILENAME

        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        store = cls(
            dimension=payload.get("dimension"),
            persist_dir=directory,
        )

        if index_path.exists():
            store.index = faiss.read_index(str(index_path))

            if store.dimension != store.index.d:
                raise ValueError("Saved index and metadata dimensions do not match")

        store._next_faiss_id = int(payload.get("next_faiss_id", 1))
        store._documents = {
            int(faiss_id): record
            for faiss_id, record in payload.get("documents", {}).items()
        }
        store._chunk_to_faiss = {
            record["id"]: faiss_id
            for faiss_id, record in store._documents.items()
        }

        indexed_count = store.index.ntotal if store.index is not None else 0
        if indexed_count != len(store._documents):
            raise ValueError("Saved FAISS index and metadata are inconsistent")

        return store
