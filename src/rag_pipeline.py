"""End-to-end RAG pipeline: ingest → index → retrieve → generate → audit."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from . import config
from .ingestion import load_corpus
from .retriever import RAGRetriever
from .generator import RAGGenerator
from .audit_logger import log_query

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Orchestrates the full RAG pipeline for the BNR corpus.

    Usage:
        pipeline = RAGPipeline()
        result   = pipeline.query("What are barriers to financial inclusion?")
        print(result["answer"])
    """

    def __init__(
        self,
        corpus_dir:    str | Path = config.CORPUS_DIR,
        db_path:       str | Path = config.CHROMA_DIR,
        api_key:       str        = config.ANTHROPIC_API_KEY,
        model:         str        = config.LLM_MODEL,
        rebuild_index: bool       = False,
        top_k:         int        = config.TOP_K,
    ) -> None:
        self.corpus_dir = Path(corpus_dir)
        self.top_k      = top_k

        self.retriever = RAGRetriever(
            db_path         = db_path,
            collection_name = config.COLLECTION_NAME,
            embedding_model = config.EMBEDDING_MODEL,
        )
        self.generator = RAGGenerator(api_key=api_key, model=model)

        if rebuild_index or self.retriever.is_empty:
            self.build_index()

    # ── Index management ──────────────────────────────────────────────────────

    def build_index(self) -> None:
        """(Re)load all corpus documents and rebuild the vector index."""
        logger.info("Building vector index …")
        chunks = load_corpus(self.corpus_dir)
        if not chunks:
            raise ValueError(
                f"No documents found in corpus directory: {self.corpus_dir}"
            )
        self.retriever.index_documents(chunks)
        logger.info(f"Index ready — {self.retriever.chunk_count} chunks.")

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(self, question: str) -> dict[str, Any]:
        """
        Answer *question* using the RAG pipeline.

        Returns:
            {
              "question":            str,
              "answer":              str,
              "sources":             list[dict],
              "context_used":        list[RetrievedChunk],
              "num_chunks_retrieved":int,
              "model":               str,
              "input_tokens":        int,
              "output_tokens":       int,
              "latency_ms":          float,
            }
        """
        t0 = time.monotonic()

        # 1. Retrieve
        chunks = self.retriever.retrieve(question, k=self.top_k)

        # 2. Generate
        result = self.generator.generate(question, chunks)

        latency_ms = (time.monotonic() - t0) * 1000
        result["question"]            = question
        result["num_chunks_retrieved"] = len(chunks)
        result["latency_ms"]           = round(latency_ms, 1)

        # 3. Audit
        log_query(question, result, latency_ms)

        return result

    # ── Display helpers ───────────────────────────────────────────────────────

    def format_response(self, result: dict[str, Any], show_context: bool = True) -> str:
        """Return a human-readable string for the terminal."""
        lines = [
            f"\n{'='*70}",
            f"QUESTION: {result['question']}",
            f"{'='*70}",
            "",
            "ANSWER:",
            result["answer"],
            "",
            f"[{result['latency_ms']:.0f} ms | "
            f"{result['input_tokens']} in / {result['output_tokens']} out tokens]",
        ]

        if show_context and result.get("context_used"):
            lines += ["", "─── RETRIEVED CONTEXT ───"]
            for i, chunk in enumerate(result["context_used"], start=1):
                lines.append(
                    f"\n  [{i}] {chunk.source_name} | "
                    f"Page {chunk.page} | sim={chunk.similarity:.3f}"
                )
                lines.append(f"  {chunk.text[:220].replace(chr(10), ' ')} …")

        return "\n".join(lines)
