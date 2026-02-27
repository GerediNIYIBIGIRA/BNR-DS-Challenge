"""Central configuration for the BNR RAG System."""
from __future__ import annotations

import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
CORPUS_DIR  = BASE_DIR / "corpus"
CHROMA_DIR  = BASE_DIR / "chroma_db"
LOG_DIR     = BASE_DIR / "logs"

# ── Deployment mode ──────────────────────────────────────────────────────────
# Set CHROMADB_MODE=ephemeral in cloud environments (HF Spaces, Streamlit Cloud)
# to use an in-memory vector store (no disk writes, rebuilt on each startup).
USE_EPHEMERAL_DB = os.getenv("CHROMADB_MODE", "persistent") == "ephemeral"

# Create directories only when using persistent storage
if not USE_EPHEMERAL_DB:
    CHROMA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ── Human-readable document names ────────────────────────────────────────────
DOCUMENT_NAMES: dict[str, str] = {
    "Finscope-Final-Report__10_07_2024-1.pdf":
        "Rwanda FinScope 2024 Report",
    "Law_governing_the_Payment_system_2021.pdf":
        "Payment System Law No. 061/2021 (NBR)",
    "The-State-of-the-Industry-Report-2025_English.pdf":
        "GSMA State of the Industry Report 2025",
}
# CSV is matched by extension – name assigned at load time
CSV_SOURCE_NAME = "IMF Financial Access Survey – Rwanda"

# ── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 600   # words per chunk
CHUNK_OVERLAP = 100   # word overlap between consecutive chunks

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K            = 5
COLLECTION_NAME  = "bnr_corpus"
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"   # local, 384-dim, no API key

# ── LLM ──────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL         = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS        = 1024

# ── Fallback message (required by the spec) ───────────────────────────────────
FALLBACK_MESSAGE = "The answer cannot be determined from the provided documents."