# BNR Document Intelligence — RAG Prototype

A Retrieval-Augmented Generation (RAG) system for querying the BNR institutional
corpus. Answers are grounded strictly in the provided documents and cite the
source document and page number.

Submitted by **Geredi Niyibigira** — BNR Data Science Challenge #1

---

## System Architecture

```
User Question
     │
     ▼
[Embedding Model]        ← sentence-transformers/all-MiniLM-L6-v2 (local)
     │
     ▼
[ChromaDB Vector Store]  ← cosine similarity, persistent on disk
     │  top-k chunks
     ▼
[Claude LLM]             ← Anthropic API, strict grounding system prompt
     │
     ▼
Grounded Answer + Citations + Audit Log
```

### Key design choices

| Component | Choice | Reason |
|-----------|--------|--------|
| Embeddings | `all-MiniLM-L6-v2` (local) | No API cost; data stays on-premises |
| Vector store | ChromaDB (persistent) | Simple, reliable, stores metadata |
| Chunking | 600-word windows, 100-word overlap | Balances context completeness vs noise |
| LLM | Claude 3.5 Haiku | Fast, cost-effective, instruction-following |
| Fallback | Hardcoded exact string | Prevents hallucination on out-of-corpus questions |

---

## Corpus

Place these four files in the `corpus/` directory:

| File | Description |
|------|-------------|
| `Finscope-Final-Report__10_07_2024-1.pdf` | Rwanda FinScope 2024 Report |
| `Law_governing_the_Payment_system_2021.pdf` | Payment System Law No. 061/2021 (NBR) |
| `The-State-of-the-Industry-Report-2025_English.pdf` | GSMA State of the Industry 2025 |
| `dataset_...IMF.STA_FAS_4.0.0.csv` | IMF Financial Access Survey — Rwanda |

---

## Setup

### Prerequisites

- Python 3.9 or later
- An [Anthropic API key](https://console.anthropic.com)

### 1 — Clone / unzip and enter the project folder

```bash
cd BNR-DS-Challenge-Geredi-Niyibigira
```

### 2 — Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> First run downloads the embedding model (~90 MB).

### 4 — Configure API key

```bash
cp .env.example .env
# Open .env and set: ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running the System

### Option A — Streamlit web UI (recommended for demo)

```bash
streamlit run app.py
```

Open <http://localhost:8501> in your browser.

### Option B — Command-line interface

```bash
# Interactive mode
python main.py

# Single question
python main.py --query "What are the barriers to financial inclusion in Rwanda?"

# Force re-index (after adding new documents)
python main.py --rebuild
```

### Option C — Run the evaluation suite

```bash
python evaluation/run_evaluation.py
```

This runs 5 pre-defined questions (including one out-of-corpus control)
and saves a JSON report to `evaluation/`.

---

## Project Structure

```
BNR-DS-Challenge-Geredi-Niyibigira/
├── corpus/                      ← source documents (PDF + CSV)
├── src/
│   ├── config.py                ← all configuration constants
│   ├── ingestion.py             ← PDF/CSV loading and chunking
│   ├── retriever.py             ← ChromaDB vector store + retrieval
│   ├── generator.py             ← Claude API answer generation
│   ├── rag_pipeline.py          ← end-to-end orchestration
│   └── audit_logger.py          ← JSON-lines query audit trail
├── evaluation/
│   └── run_evaluation.py        ← evaluation harness (5 questions)
├── chroma_db/                   ← persisted vector index (auto-created)
├── logs/
│   └── audit.jsonl              ← query audit trail (auto-created)
├── main.py                      ← CLI entry point
├── app.py                       ← Streamlit web UI
├── requirements.txt
├── .env.example
└── README.md
```

---

## Audit Trail

Every query is logged to `logs/audit.jsonl` with:

```json
{
  "timestamp": "2026-02-27T10:00:00Z",
  "question": "...",
  "answer_preview": "...",
  "is_fallback": false,
  "sources_retrieved": [{"source": "...", "page": 5, "similarity": 0.82}],
  "num_chunks": 5,
  "model": "claude-3-5-haiku-20241022",
  "input_tokens": 1423,
  "output_tokens": 187,
  "latency_ms": 1340.2
}
```

---

## Reflection

**1. Risks in a central bank setting**
- Model may misquote or subtly misrepresent regulatory text.
- Outdated corpus if documents are not re-indexed after updates.
- Data leakage: queries sent to external API (mitigated by local embeddings).

**2. Reducing hallucinations**
- Strict system prompt: answer only from excerpts.
- Hardcoded fallback string for out-of-corpus questions.
- Top-k similarity threshold — discard low-confidence chunks.

**3. Logging and audit trail**
- `logs/audit.jsonl` records every query (see above).
- In production: centralised log aggregation (ELK / Splunk), retention policy.

**4. Testing model updates**
- Maintain a golden Q&A test set; compare answers before/after model swap.
- Track faithfulness (answer contained in retrieved context) and source-hit rate.

**5. Future improvements**
- Hybrid retrieval (BM25 + dense) for better keyword recall on legal text.
- Cross-encoder reranking to improve chunk quality.
- Metadata-filtered search (restrict to a specific document).
- Fine-tuned embedding model on financial/legal Kinyarwanda–English text.
