"""Structured audit trail for every RAG query.

Each query is appended as a JSON-lines record to logs/audit.jsonl.
Fields logged:
  timestamp, question, answer, sources_retrieved,
  num_chunks, model, input_tokens, output_tokens, latency_ms
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

logger = logging.getLogger(__name__)
_AUDIT_FILE = config.LOG_DIR / "audit.jsonl"


def log_query(
    question:     str,
    result:       dict[str, Any],
    latency_ms:   float,
) -> None:
    """Append one audit record for *question* / *result* pair."""
    record: dict[str, Any] = {
        "timestamp":          datetime.now(timezone.utc).isoformat(),
        "question":           question,
        "answer_preview":     result.get("answer", "")[:300],
        "is_fallback":        result.get("answer", "").startswith(
                                  "The answer cannot be determined"
                              ),
        "sources_retrieved":  [
            {
                "source": c.get("source_name") if isinstance(c, dict)
                          else getattr(c, "source_name", ""),
                "page":   c.get("page") if isinstance(c, dict)
                          else getattr(c, "page", 0),
                "similarity": c.get("similarity") if isinstance(c, dict)
                              else getattr(c, "similarity", 0.0),
            }
            for c in result.get("sources", [])
        ],
        "num_chunks":         result.get("num_chunks_retrieved", 0),
        "model":              result.get("model", ""),
        "input_tokens":       result.get("input_tokens", 0),
        "output_tokens":      result.get("output_tokens", 0),
        "latency_ms":         round(latency_ms, 1),
    }

    try:
        with open(_AUDIT_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning(f"Audit log write failed: {exc}")
