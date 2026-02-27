"""Vector-store retrieval using ChromaDB + sentence-transformers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from . import config
from .ingestion import DocumentChunk

logger = logging.getLogger(__name__)


# ── Result type ───────────────────────────────────────────────────────────────

class RetrievedChunk(NamedTuple):
    text:        str
    source_name: str
    filename:    str
    page:        int
    doc_type:    str
    similarity:  float          # cosine similarity 0-1 (higher = more relevant)

    def citation(self) -> str:
        if self.doc_type == "csv":
            return f"[Source: {self.source_name}]"
        return f"[Source: {self.source_name}, Page {self.page}]"


# ── Retriever ─────────────────────────────────────────────────────────────────

class RAGRetriever:
    """Persistent ChromaDB-backed semantic retriever."""

    def __init__(
        self,
        db_path:         str | Path = config.CHROMA_DIR,
        collection_name: str        = config.COLLECTION_NAME,
        embedding_model: str        = config.EMBEDDING_MODEL,
    ) -> None:
        self.db_path         = Path(db_path)
        self.collection_name = collection_name

        logger.info(f"Loading embedding model '{embedding_model}' ...")
        self._embed_fn = SentenceTransformerEmbeddingFunction(
            model_name=embedding_model,
            device="cpu",
        )

        # Use ephemeral (in-memory) client for cloud deployments where the
        # filesystem is not persistent (HF Spaces, Streamlit Cloud, etc.).
        if config.USE_EPHEMERAL_DB:
            self._client = chromadb.EphemeralClient()
            logger.info("ChromaDB: ephemeral (in-memory) mode")
        else:
            self._client = chromadb.PersistentClient(path=str(self.db_path))

        self._col = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Collection '{collection_name}' — {self._col.count()} chunks indexed.")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        return self._col.count() == 0

    @property
    def chunk_count(self) -> int:
        return self._col.count()

    # ── Indexing ──────────────────────────────────────────────────────────────

    def index_documents(self, chunks: list[DocumentChunk], batch_size: int = 128) -> None:
        """(Re)index *chunks* into ChromaDB."""
        logger.info(f"Indexing {len(chunks)} chunks …")

        # Drop and recreate collection for a clean rebuild
        self._client.delete_collection(self.collection_name)
        self._col = self._client.create_collection(
            name=self.collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            self._col.add(
                ids       = [c.chunk_id for c in batch],
                documents = [c.text for c in batch],
                metadatas = [
                    {
                        "source_name": c.source_name,
                        "filename":    c.filename,
                        "page":        c.page,
                        "doc_type":    c.doc_type,
                    }
                    for c in batch
                ],
            )
            logger.info(
                f"  Indexed {min(start + batch_size, len(chunks))}/{len(chunks)} chunks"
            )

        logger.info(f"Indexing complete — {self._col.count()} total chunks.")

    # ── Querying ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = config.TOP_K) -> list[RetrievedChunk]:
        """Return the *k* most semantically similar chunks for *query*."""
        n = min(k, self._col.count())
        if n == 0:
            return []

        results = self._col.query(
            query_texts=[query],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(RetrievedChunk(
                text        = text,
                source_name = meta.get("source_name", "Unknown"),
                filename    = meta.get("filename", ""),
                page        = meta.get("page", 0),
                doc_type    = meta.get("doc_type", "pdf"),
                similarity  = round(1.0 - float(dist), 4),  # distance → similarity
            ))

        return chunks
