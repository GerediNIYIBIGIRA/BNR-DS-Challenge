"""Document ingestion: PDF and CSV loading with chunking."""
from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pypdf
import pandas as pd

from . import config

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class DocumentChunk:
    """A single retrievable chunk of a source document."""
    text:        str
    source_name: str          # Human-readable document name
    filename:    str          # Original filename
    page:        int          # Page number (1-based); 0 for CSV
    chunk_index: int          # Position within the page/document
    doc_type:    str          # "pdf" or "csv"
    metadata:    dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        """Stable, unique identifier derived from content."""
        key = f"{self.filename}|{self.page}|{self.chunk_index}"
        return hashlib.md5(key.encode()).hexdigest()

    def citation(self) -> str:
        if self.doc_type == "csv":
            return f"[Source: {self.source_name}]"
        return f"[Source: {self.source_name}, Page {self.page}]"


# ── Text utilities ─────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Normalise extracted PDF text."""
    text = re.sub(r"-\s*\n\s*", "", text)        # re-join hyphenated words
    text = re.sub(r"\s+", " ", text)              # collapse whitespace
    return text.strip()


def _chunk_words(text: str,
                 size: int = config.CHUNK_SIZE,
                 overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Split *text* into word-based sliding-window chunks."""
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        end   = min(start + size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk) > 80:          # discard very short fragments
            chunks.append(chunk)
        if end == len(words):
            break
        start += size - overlap
    return chunks


# ── PDF loader ────────────────────────────────────────────────────────────────

def load_pdf(filepath: Path) -> list[DocumentChunk]:
    """Extract and chunk text from a PDF file."""
    filename    = filepath.name
    source_name = config.DOCUMENT_NAMES.get(filename, filename)
    chunks: list[DocumentChunk] = []

    try:
        reader = pypdf.PdfReader(str(filepath))
        logger.info(f"  Loading '{source_name}' ({len(reader.pages)} pages)")

        for page_no, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text() or ""
                cleaned = _clean(raw)
                if not cleaned:
                    continue
                for ci, chunk_text in enumerate(_chunk_words(cleaned)):
                    chunks.append(DocumentChunk(
                        text=chunk_text,
                        source_name=source_name,
                        filename=filename,
                        page=page_no,
                        chunk_index=ci,
                        doc_type="pdf",
                    ))
            except Exception as exc:
                logger.warning(f"    Skip page {page_no}: {exc}")

    except Exception as exc:
        logger.error(f"  Failed to load {filename}: {exc}")

    logger.info(f"    → {len(chunks)} chunks")
    return chunks


# ── CSV loader ────────────────────────────────────────────────────────────────

def load_csv(filepath: Path) -> list[DocumentChunk]:
    """Convert IMF Financial Access Survey CSV into text chunks."""
    source_name = config.CSV_SOURCE_NAME
    chunks: list[DocumentChunk] = []

    try:
        df = pd.read_csv(str(filepath), encoding="utf-8-sig")
        logger.info(f"  Loading '{source_name}' ({len(df)} rows)")

        # Year columns are everything that looks like a 4-digit year
        year_cols = [c for c in df.columns if re.match(r"^\d{4}$", str(c))]
        id_cols   = [c for c in df.columns if c not in year_cols]

        # One chunk per indicator row (keeps context tight)
        for idx, row in df.iterrows():
            indicator = str(row.get("INDICATOR", row.get("Indicator Name", f"Row {idx}")))
            parts = [f"Indicator: {indicator}"]

            for col in id_cols:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    parts.append(f"  {col}: {val}")

            # Add year-value pairs only when non-empty
            year_data = {y: row[y] for y in year_cols if pd.notna(row[y]) and str(row[y]).strip()}
            if year_data:
                parts.append("  Annual values: " +
                             ", ".join(f"{y}={v}" for y, v in year_data.items()))

            text = "\n".join(parts)
            if len(text) > 40:
                chunks.append(DocumentChunk(
                    text=text,
                    source_name=source_name,
                    filename=filepath.name,
                    page=0,
                    chunk_index=int(str(idx)),
                    doc_type="csv",
                    metadata={"indicator": indicator},
                ))

    except Exception as exc:
        logger.error(f"  Failed to load CSV {filepath.name}: {exc}")

    logger.info(f"    → {len(chunks)} chunks")
    return chunks


# ── Corpus loader ─────────────────────────────────────────────────────────────

def load_corpus(corpus_dir: str | Path = config.CORPUS_DIR) -> list[DocumentChunk]:
    """Load all documents in *corpus_dir* and return a flat list of chunks."""
    corpus_dir = Path(corpus_dir)
    all_chunks: list[DocumentChunk] = []

    logger.info(f"Loading corpus from: {corpus_dir}")
    for path in sorted(corpus_dir.iterdir()):
        if path.suffix.lower() == ".pdf":
            all_chunks.extend(load_pdf(path))
        elif path.suffix.lower() == ".csv":
            all_chunks.extend(load_csv(path))

    logger.info(f"Total chunks in corpus: {len(all_chunks)}")
    return all_chunks
