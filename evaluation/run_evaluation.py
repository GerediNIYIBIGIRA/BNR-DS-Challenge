"""
BNR RAG System — Evaluation Script
===================================
Runs 5 predefined questions (including one out-of-corpus control),
prints detailed results to stdout, and saves a JSON report.

Usage:
    python evaluation/run_evaluation.py
    python evaluation/run_evaluation.py --rebuild   # re-index first
"""
from __future__ import annotations

import json
import logging
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)   # suppress noisy info during eval

# ── Evaluation questions ──────────────────────────────────────────────────────

QUESTIONS = [
    {
        "id": "Q1",
        "question": "What are the main barriers to financial inclusion in rural Rwanda?",
        "expected_sources": ["Rwanda FinScope 2024 Report"],
        "commentary": (
            "FinScope 2024 documents demand-side barriers such as distance to "
            "financial access points, low income, lack of documentation, and "
            "limited financial literacy. The system should retrieve these passages."
        ),
        "out_of_corpus": False,
    },
    {
        "id": "Q2",
        "question": "How does mobile money usage differ by gender in Rwanda and globally?",
        "expected_sources": [
            "Rwanda FinScope 2024 Report",
            "GSMA State of the Industry Report 2025",
        ],
        "commentary": (
            "This cross-document question requires merging Rwanda-specific gender "
            "data from FinScope with global GSMA gender-gap figures. Tests multi-source "
            "retrieval. A limitation: the system may not always retrieve both documents."
        ),
        "out_of_corpus": False,
    },
    {
        "id": "Q3",
        "question": "What are the National Bank of Rwanda's supervisory powers over payment systems?",
        "expected_sources": ["Payment System Law No. 061/2021 (NBR)"],
        "commentary": (
            "Tests retrieval of specific legal text. The law explicitly defines NBR's "
            "oversight powers. The system should cite specific articles."
        ),
        "out_of_corpus": False,
    },
    {
        "id": "Q4",
        "question": "What was the number of mobile money accounts in Rwanda in 2022 according to the IMF survey?",
        "expected_sources": ["IMF Financial Access Survey – Rwanda"],
        "commentary": (
            "Tests retrieval from structured CSV data. The system must parse and "
            "cite numeric data from the IMF dataset."
        ),
        "out_of_corpus": False,
    },
    {
        "id": "Q5",
        "question": "What is the current inflation rate in the United States?",
        "expected_sources": [],
        "commentary": (
            "CONTROL — out-of-corpus question. "
            "The system must respond with the fallback message. "
            "Failure here (hallucinating an answer) is a critical safety failure."
        ),
        "out_of_corpus": True,
    },
]

# ── Runner ────────────────────────────────────────────────────────────────────

def run_evaluation(pipeline) -> list[dict]:
    from src.config import FALLBACK_MESSAGE

    records = []
    print("\n" + "=" * 72)
    print("  BNR RAG SYSTEM — EVALUATION RUN")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    for q in QUESTIONS:
        print(f"\n{'-'*72}")
        print(f"[{q['id']}] {q['question']}")
        print(f"{'-'*72}")

        result = pipeline.query(q["question"])

        print(f"\nANSWER:\n{result['answer']}\n")

        print("RETRIEVED CONTEXT:")
        for chunk in result["context_used"]:
            print(
                f"  - {chunk.source_name:45s} | "
                f"Page {str(chunk.page):4s} | "
                f"sim={chunk.similarity:.3f}"
            )

        print(f"\nCOMMENTARY:\n{q['commentary']}\n")

        # ── Pass/fail assessment ───────────────────────────────────────────
        gave_fallback = FALLBACK_MESSAGE in result["answer"]

        if q["out_of_corpus"]:
            passed = gave_fallback
            verdict = "PASS" if passed else "FAIL  (should have given fallback)"
        else:
            # Check at least one expected source is among top-retrieved
            retrieved_names = {c.source_name for c in result["context_used"]}
            source_hit = any(s in retrieved_names for s in q["expected_sources"])
            passed = source_hit and not gave_fallback
            verdict = (
                "PASS" if passed
                else "PARTIAL/FAIL - check commentary above"
            )

        print(f"VERDICT: {verdict}")
        print(f"Latency: {result['latency_ms']:.0f} ms | "
              f"Tokens: {result['input_tokens']} in / {result['output_tokens']} out")

        records.append({
            "id":                q["id"],
            "question":          q["question"],
            "answer":            result["answer"],
            "retrieved_sources": [
                {
                    "source": c.source_name,
                    "page":   c.page,
                    "sim":    c.similarity,
                }
                for c in result["context_used"]
            ],
            "expected_sources":  q["expected_sources"],
            "out_of_corpus":     q["out_of_corpus"],
            "gave_fallback":     gave_fallback,
            "passed":            passed,
            "verdict":           verdict,
            "latency_ms":        result["latency_ms"],
            "input_tokens":      result["input_tokens"],
            "output_tokens":     result["output_tokens"],
            "commentary":        q["commentary"],
        })

    # ── Summary ────────────────────────────────────────────────────────────────
    n_pass = sum(1 for r in records if r["passed"])
    print(f"\n{'='*72}")
    print(f"SUMMARY: {n_pass}/{len(records)} questions passed")
    for r in records:
        icon = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"  {icon} [{r['id']}] {r['question'][:60]}")
    print("=" * 72)

    return records


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run BNR RAG evaluation")
    parser.add_argument("--rebuild", action="store_true",
                        help="Force corpus re-index before evaluation")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    from src.rag_pipeline import RAGPipeline
    print("Initialising pipeline …")
    pipeline = RAGPipeline(api_key=api_key, rebuild_index=args.rebuild)

    records = run_evaluation(pipeline)

    # Save JSON report
    out_dir  = Path(__file__).parent
    out_file = out_dir / f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    print(f"\nReport saved -> {out_file}")


if __name__ == "__main__":
    main()
