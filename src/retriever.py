"""Vector-store retrieval using FAISS + sentence-transformers."""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import NamedTuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

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
    """FAISS-backed semantic retriever (exact cosine similarity)."""

    def __init__(
        self,
        db_path:         str | Path = config.CHROMA_DIR,
        collection_name: str        = config.COLLECTION_NAME,
        embedding_model: str        = config.EMBEDDING_MODEL,
    ) -> None:
        self.db_path         = Path(db_path)
        self.collection_name = collection_name
        self._persistent     = not config.USE_EPHEMERAL_DB

        self._index_path = self.db_path / f"{collection_name}.faiss"
        self._meta_path  = self.db_path / f"{collection_name}.pkl"

        logger.info(f"Loading embedding model '{embedding_model}' ...")
        self._model = SentenceTransformer(embedding_model, device="cpu")

        self._index:    faiss.Index | None = None
        self._texts:    list[str]          = []
        self._metadata: list[dict]         = []

        # Load persisted index if available
        if self._persistent and self._index_path.exists() and self._meta_path.exists():
            self._load()
            logger.info(f"Loaded existing index: {self.chunk_count} chunks.")
        else:
            logger.info("No existing index found — will build on first use.")

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._index = faiss.read_index(str(self._index_path))
        with open(self._meta_path, "rb") as f:
            data = pickle.load(f)
        self._texts    = data["texts"]
        self._metadata = data["metadata"]

    def _save(self) -> None:
        if not self._persistent or self._index is None:
            return
        self.db_path.mkdir(exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        with open(self._meta_path, "wb") as f:
            pickle.dump({"texts": self._texts, "metadata": self._metadata}, f)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        return self._index is None or self._index.ntotal == 0

    @property
    def chunk_count(self) -> int:
        return 0 if self._index is None else self._index.ntotal

    # ── Indexing ──────────────────────────────────────────────────────────────

    def index_documents(self, chunks: list[DocumentChunk], batch_size: int = 64) -> None:
        """Encode *chunks* and build a cosine-similarity FAISS index."""
        logger.info(f"Indexing {len(chunks)} chunks …")

        texts = [c.text for c in chunks]

        all_emb: list[np.ndarray] = []
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start : start + batch_size]
            emb = self._model.encode(batch_texts, show_progress_bar=False)
            all_emb.append(emb)
            logger.info(
                f"  Encoded {min(start + batch_size, len(texts))}/{len(texts)} chunks"
            )

        embeddings = np.vstack(all_emb).astype("float32")
        faiss.normalize_L2(embeddings)          # cosine ≡ inner product after normalising

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)    # exact cosine search
        self._index.add(embeddings)

        self._texts = texts
        self._metadata = [
            {
                "source_name": c.source_name,
                "filename":    c.filename,
                "page":        c.page,
                "doc_type":    c.doc_type,
            }
            for c in chunks
        ]

        self._save()
        logger.info(f"Indexing complete — {self.chunk_count} total chunks.")

    # ── Querying ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, k: int = config.TOP_K) -> list[RetrievedChunk]:
        """Return the *k* most semantically similar chunks for *query*."""
        if self.is_empty:
            return []

        n = min(k, self.chunk_count)

        q_emb = self._model.encode([query]).astype("float32")
        faiss.normalize_L2(q_emb)

        scores, indices = self._index.search(q_emb, n)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self._metadata[idx]
            results.append(RetrievedChunk(
                text        = self._texts[idx],
                source_name = meta.get("source_name", "Unknown"),
                filename    = meta.get("filename", ""),
                page        = meta.get("page", 0),
                doc_type    = meta.get("doc_type", "pdf"),
                similarity  = round(float(score), 4),   # cosine similarity
            ))

        return results
