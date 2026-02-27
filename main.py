#!/usr/bin/env python3
"""BNR RAG System — Command-Line Interface

Usage:
  python main.py                        # interactive mode
  python main.py --query "..."          # single query
  python main.py --rebuild              # force re-index then interactive
  python main.py --query "..." --top-k 7
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def _build_pipeline(rebuild: bool, top_k: int):
    from src.rag_pipeline import RAGPipeline

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(
            "\nERROR: ANTHROPIC_API_KEY is not set.\n"
            "Copy .env.example → .env and add your key.\n"
        )
        sys.exit(1)

    print("Initialising BNR RAG System …\n")
    return RAGPipeline(api_key=api_key, rebuild_index=rebuild, top_k=top_k)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BNR RAG System – query BNR institutional documents"
    )
    parser.add_argument("--query",   type=str,  help="Single question (non-interactive)")
    parser.add_argument("--rebuild", action="store_true", help="Force re-index the corpus")
    parser.add_argument("--top-k",  type=int, default=5,  help="Chunks to retrieve (default 5)")
    parser.add_argument("--no-context", action="store_true",
                        help="Hide retrieved context in output")
    args = parser.parse_args()

    pipeline = _build_pipeline(args.rebuild, args.top_k)
    show_ctx = not args.no_context

    # ── Single-query mode ─────────────────────────────────────────────────────
    if args.query:
        result = pipeline.query(args.query.strip())
        print(pipeline.format_response(result, show_context=show_ctx))
        return

    # ── Interactive mode ──────────────────────────────────────────────────────
    print("BNR RAG System ready.  Commands: 'quit' to exit | 'rebuild' to re-index\n")
    print("─" * 70)

    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break
        if question.lower() == "rebuild":
            pipeline.build_index()
            continue

        result = pipeline.query(question)
        print(pipeline.format_response(result, show_context=show_ctx))


if __name__ == "__main__":
    main()
