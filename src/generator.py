"""LLM answer generation via Claude API with strict grounding."""
from __future__ import annotations

import logging
from typing import Any

import anthropic

from . import config
from .retriever import RetrievedChunk

logger = logging.getLogger(__name__)

# ── System prompt (grounding + citation instructions) ─────────────────────────

_SYSTEM_PROMPT = f"""\
You are a precise, document-grounded research assistant for the \
National Bank of Rwanda (BNR).

STRICT RULES:
1. Answer ONLY using information explicitly present in the document excerpts \
provided below the user question.
2. If the provided excerpts do not contain sufficient information to answer \
the question, you MUST respond with EXACTLY this sentence and nothing else:
   "{config.FALLBACK_MESSAGE}"
3. Do NOT add external knowledge, personal opinions, or inferences that go \
beyond what the documents state.
4. Be concise, factual, and professional.
5. After your answer, include a "Sources:" section listing every excerpt you \
drew upon, in the format:
   - <Document Name>, Page <N>   (use "—" for the page if the source is a dataset)

RESPONSE FORMAT:
<your answer>

Sources:
- <Document Name>, Page <N>
- …
"""


# ── Generator ─────────────────────────────────────────────────────────────────

class RAGGenerator:
    """Wraps the Anthropic API to produce grounded answers."""

    def __init__(
        self,
        api_key: str        = config.ANTHROPIC_API_KEY,
        model:   str        = config.LLM_MODEL,
    ) -> None:
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or set the environment variable."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def generate(
        self,
        question: str,
        chunks:   list[RetrievedChunk],
    ) -> dict[str, Any]:
        """
        Build a grounded answer from *chunks* for *question*.

        Returns a dict with keys:
          answer, sources, context_used, model,
          input_tokens, output_tokens
        """
        if not chunks:
            return {
                "answer":        config.FALLBACK_MESSAGE,
                "sources":       [],
                "context_used":  [],
                "model":         self.model,
                "input_tokens":  0,
                "output_tokens": 0,
            }

        # Build context block
        context_parts = []
        for i, chunk in enumerate(chunks, start=1):
            if chunk.doc_type == "csv":
                header = (
                    f"[Excerpt {i} | Source: {chunk.source_name} | "
                    f"Relevance: {chunk.similarity:.2f}]"
                )
            else:
                header = (
                    f"[Excerpt {i} | Source: {chunk.source_name}, "
                    f"Page {chunk.page} | Relevance: {chunk.similarity:.2f}]"
                )
            context_parts.append(f"{header}\n{chunk.text}")

        context = "\n\n" + ("\n\n" + "—" * 60 + "\n\n").join(context_parts)

        user_message = (
            f"Question: {question}\n\n"
            f"Document excerpts:{context}\n\n"
            "Please answer the question based strictly on the excerpts above."
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            logger.error(f"Anthropic API error: {exc}")
            raise

        answer_text = response.content[0].text

        # Deduplicated source list (preserving encounter order)
        seen: set[tuple] = set()
        sources = []
        for chunk in chunks:
            key = (chunk.source_name, chunk.page)
            if key not in seen:
                seen.add(key)
                sources.append({
                    "source_name": chunk.source_name,
                    "page":        chunk.page,
                    "doc_type":    chunk.doc_type,
                    "similarity":  chunk.similarity,
                })

        return {
            "answer":        answer_text,
            "sources":       sources,
            "context_used":  chunks,
            "model":         self.model,
            "input_tokens":  response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
