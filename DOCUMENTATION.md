# BNR Document Intelligence Assistant — Full Documentation

**Geredi Niyibigira | BNR Data Science Challenge #1 | February 2026**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Project Structure](#3-project-structure)
4. [Corpus Documents](#4-corpus-documents)
5. [Component Deep Dive](#5-component-deep-dive)
6. [Local Setup & Installation](#6-local-setup--installation)
7. [Running the System](#7-running-the-system)
8. [Evaluation](#8-evaluation)
9. [Deployment (Hugging Face Spaces)](#9-deployment-hugging-face-spaces)
10. [Making Changes & Redeployment](#10-making-changes--redeployment)
11. [Troubleshooting](#11-troubleshooting)
12. [Key Design Decisions](#12-key-design-decisions)
13. [Evaluation Results Summary](#13-evaluation-results-summary)
14. [Known Limitations & Future Improvements](#14-known-limitations--future-improvements)
15. [Security & API Key Management](#15-security--api-key-management)

---

## 1. Project Overview

A Retrieval-Augmented Generation (RAG) system that lets users ask natural language questions about
the BNR institutional document corpus. Answers are **strictly grounded** in the provided documents —
the system will never fabricate statistics or invent sources. When the answer cannot be determined
from the documents, a hardcoded fallback message is returned.

**Challenge requirement fulfilled:**
- Accepts a natural language question
- Retrieves relevant content from the 4 corpus documents
- Generates an answer grounded strictly in the retrieved text
- Cites the source document and page number for every claim
- Returns the exact fallback string when the answer is not in the corpus
- Logs every query to an audit trail

**Live demo:** https://huggingface.co/spaces/geredi/BNR-Document-Intelligence
**Source code:** https://github.com/GerediNIYIBIGIRA/BNR-DS-Challenge

---

## 2. System Architecture

```
User Question
     │
     ▼
[Embedding Model]          ← sentence-transformers/all-MiniLM-L6-v2 (local, CPU)
     │  384-dimensional vector
     ▼
[ChromaDB Vector Store]    ← cosine similarity search, top-5 chunks returned
     │  retrieved chunks + metadata
     ▼
[Prompt Builder]           ← concatenates chunks + strict grounding system prompt
     │  full prompt
     ▼
[Claude LLM]               ← claude-haiku-4-5-20251001 via Anthropic API
     │  answer text
     ▼
[Audit Logger]             ← appends JSON record to logs/audit.jsonl
     │
     ▼
Grounded Answer + Citations + Audit Entry
```

### Pipeline flow in code

```
app.py / main.py
    └── RAGPipeline.query()          # src/rag_pipeline.py
            ├── RAGRetriever.search()    # src/retriever.py  — embedding + ChromaDB
            └── RAGGenerator.generate() # src/generator.py  — Anthropic API call
                    └── AuditLogger.log()   # src/audit_logger.py
```

---

## 3. Project Structure

```
BNR-DS-Challenge-Geredi-Niyibigira/
│
├── corpus/                                      ← source documents (DO NOT delete)
│   ├── Finscope-Final-Report__10_07_2024-1.pdf
│   ├── Law_governing_the_Payment_system_2021.pdf
│   ├── The-State-of-the-Industry-Report-2025_English.pdf
│   └── dataset_...IMF.STA_FAS_4.0.0.csv
│
├── src/
│   ├── __init__.py
│   ├── config.py          ← all constants (chunk size, model, paths, etc.)
│   ├── ingestion.py       ← PDF/CSV loading, chunking, DocumentChunk dataclass
│   ├── retriever.py       ← ChromaDB setup, embedding, cosine search
│   ├── generator.py       ← Anthropic API call, grounding prompt, fallback
│   ├── rag_pipeline.py    ← end-to-end orchestration, format_response()
│   └── audit_logger.py    ← appends to logs/audit.jsonl
│
├── evaluation/
│   ├── __init__.py
│   ├── run_evaluation.py  ← runs 5 pre-defined questions, saves JSON report
│   └── eval_analysis.md   ← detailed analysis of all 5 live outputs
│
├── chroma_db/             ← persisted vector index (auto-created, gitignored)
├── logs/
│   └── audit.jsonl        ← query audit trail (auto-created, gitignored)
│
├── app.py                 ← Streamlit web UI
├── main.py                ← CLI entry point
├── create_presentation.py ← generates PPTX presentation
├── Dockerfile             ← Docker image for HF Spaces deployment
├── requirements.txt       ← Python dependencies
├── .env.example           ← template — copy to .env and fill in API key
├── .env                   ← your real API key (gitignored, never commit)
├── .gitignore
├── README.md
├── DOCUMENTATION.md       ← this file
└── DEPLOYMENT.md          ← step-by-step HF Spaces guide
```

---

## 4. Corpus Documents

All four files live in `corpus/`:

| File | Description | Format |
|------|-------------|--------|
| `Finscope-Final-Report__10_07_2024-1.pdf` | Rwanda FinScope 2024 — national financial inclusion survey | PDF |
| `Law_governing_the_Payment_system_2021.pdf` | Law No. 061/2021 governing the Payment System (NBR) | PDF |
| `The-State-of-the-Industry-Report-2025_English.pdf` | GSMA State of the Mobile Money Industry 2025 | PDF |
| `dataset_...IMF.STA_FAS_4.0.0.csv` | IMF Financial Access Survey — Rwanda indicators | CSV |

**Chunking strategy:**
- PDFs: 600-word sliding window, 100-word overlap between consecutive chunks
- CSV: one chunk per row (one row = one indicator with all its year values)
- Every chunk stores: source filename, human-readable name, page number, doc type, chunk ID (MD5)

**Total indexed:** ~368 chunks across the 4 documents

---

## 5. Component Deep Dive

### 5.1 `src/config.py` — Configuration

All tunable constants live here. Change these to adjust system behaviour:

| Constant | Default | Effect |
|----------|---------|--------|
| `CHUNK_SIZE` | 600 | Words per chunk during indexing |
| `CHUNK_OVERLAP` | 100 | Word overlap between consecutive chunks |
| `TOP_K` | 5 | Number of chunks retrieved per query |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for embeddings |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | Anthropic model for answer generation |
| `MAX_TOKENS` | 1024 | Maximum tokens in LLM response |
| `USE_EPHEMERAL_DB` | `False` (local) | Set via `CHROMADB_MODE=ephemeral` env var for cloud |
| `FALLBACK_MESSAGE` | `"The answer cannot be determined..."` | Exact fallback string |

### 5.2 `src/ingestion.py` — Document Loading & Chunking

- `load_all_documents(corpus_dir)` — scans the corpus directory and routes files to the correct loader
- `load_pdf(path)` — uses `pypdf` to extract text page by page, then applies the sliding window chunker
- `load_csv(path)` — reads with `pandas`; each row becomes one chunk with indicator name + all year values
- `_chunk_words(text, page, source, size, overlap)` — the core sliding window function
- `DocumentChunk` dataclass — holds `text`, `source_name`, `source_file`, `page`, `doc_type`, `chunk_id`

### 5.3 `src/retriever.py` — Vector Store & Retrieval

- Uses `SentenceTransformerEmbeddingFunction` (wraps the local model for ChromaDB)
- `RAGRetriever.__init__()` — creates `PersistentClient` (local) or `EphemeralClient` (cloud) based on `config.USE_EPHEMERAL_DB`
- `RAGRetriever.index_documents(chunks)` — embeds all chunks and upserts into ChromaDB collection `bnr_corpus`
- `RAGRetriever.search(query, top_k)` — embeds the query and returns top-k `RetrievedChunk` NamedTuples
- `RetrievedChunk` — NamedTuple with: `text`, `source_name`, `source_file`, `page`, `similarity`

### 5.4 `src/generator.py` — LLM Answer Generation

- `RAGGenerator.generate(question, chunks)` — builds the full prompt and calls the Anthropic API
- The **system prompt** strictly instructs the model to:
  - Answer ONLY from the provided excerpts
  - Cite every claim with `[Source Name, p.N]`
  - Return the exact `FALLBACK_MESSAGE` if the answer is not in the excerpts
  - Never use external knowledge
- Returns a dict with: `answer`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `is_fallback`

### 5.5 `src/rag_pipeline.py` — Orchestration

- `RAGPipeline.__init__(api_key, rebuild_index, top_k)` — initialises retriever + generator; optionally rebuilds the index
- `RAGPipeline.query(question)` — the main entry point; calls retriever then generator then audit logger
- `format_response(result)` — formats a result dict for terminal display
- Returns a full result dict consumed by both `app.py` (Streamlit) and `main.py` (CLI)

### 5.6 `src/audit_logger.py` — Audit Trail

Appends one JSON-lines record to `logs/audit.jsonl` per query:

```json
{
  "timestamp": "2026-02-27T10:00:00Z",
  "question": "...",
  "answer_preview": "first 200 chars of answer",
  "is_fallback": false,
  "sources_retrieved": [{"source": "...", "page": 5, "similarity": 0.82}],
  "num_chunks": 5,
  "model": "claude-haiku-4-5-20251001",
  "input_tokens": 1423,
  "output_tokens": 187,
  "latency_ms": 1340.2
}
```

---

## 6. Local Setup & Installation

### Prerequisites
- Python 3.9 or later
- An Anthropic API key (get one at https://console.anthropic.com)

### Step-by-step

```bash
# 1. Enter the project folder
cd BNR-DS-Challenge-Geredi-Niyibigira

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows CMD
# .venv\Scripts\Activate.ps1       # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt
# Note: first run downloads the embedding model (~90 MB) automatically

# 4. Set your API key
cp .env.example .env
# Open .env and set: ANTHROPIC_API_KEY=sk-ant-...
```

### `.env` file format

```
ANTHROPIC_API_KEY=sk-ant-api03-your-real-key-here
LLM_MODEL=claude-haiku-4-5-20251001        # optional override
```

---

## 7. Running the System

### Option A — Streamlit web UI (recommended)

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

First load builds the vector index (~20–30 s). Subsequent queries take 2–6 s.

### Option B — Command-line interface

```bash
# Interactive mode (prompts for questions)
python main.py

# Single question
python main.py --query "What are the NBR's powers in overseeing the payment system?"

# Adjust number of retrieved chunks
python main.py --query "..." --top-k 8

# Force re-index (run after adding new documents to corpus/)
python main.py --rebuild

# Hide retrieved context in output
python main.py --query "..." --no-context
```

### Option C — Evaluation suite

```bash
python evaluation/run_evaluation.py
# Runs all 5 challenge questions and saves a JSON report to evaluation/
```

---

## 8. Evaluation

### The 5 evaluation questions

| # | Question | Expected type |
|---|----------|--------------|
| Q1 | What are the main barriers to financial inclusion in rural Rwanda? | Grounded answer or refusal |
| Q2 | How does mobile money usage differ by gender? | Detailed answer from GSMA/FinScope |
| Q3 | Summarize the NBR's operational role in the payment system | Legal citation synthesis |
| Q4 | Has digital payment adoption increased? | Trend answer with data |
| Q5 | How does Rwanda compare to global mobile money trends? | Cross-document comparison |

### Live results summary

| Q | Similarity range | Answer type | Pass |
|---|-----------------|-------------|------|
| Q1 | 0.718 – 0.752 | Appropriate refusal | ✓ |
| Q2 | 0.717 – 0.770 | Detailed (global scope) | ✓ |
| Q3 | 0.672 – 0.760 | Multi-source synthesis | ✓ |
| Q4 | 0.508 – 0.579 | Confident answer (critical failure) | ✗ |
| Q5 | 0.699 – 0.775 | Honest partial answer | ✓ |

For full analysis see `evaluation/eval_analysis.md`.

---

## 9. Deployment (Hugging Face Spaces)

### Live URL
```
https://huggingface.co/spaces/geredi/BNR-Document-Intelligence
```

### How it works on HF Spaces

1. HF Spaces reads the `Dockerfile` at the repo root
2. Builds a Docker image: Python 3.11-slim + all dependencies from `requirements.txt`
3. Starts the container, Streamlit listens on port 7860 (HF's standard port)
4. `ANTHROPIC_API_KEY` and `CHROMADB_MODE=ephemeral` are injected from Space Secrets
5. On first visitor: vector index is rebuilt from corpus (~20–30 s, spinner shown)
6. Subsequent queries run against the in-memory ChromaDB

### Why Docker instead of native Streamlit SDK

HF Spaces offers a native Streamlit SDK option, but the project uses Docker for full control.
The `Dockerfile` is minimal — it simply installs requirements and runs Streamlit on port 7860.

### Why `CHROMADB_MODE=ephemeral`

- HF free-tier containers are ephemeral (no persistent disk writes)
- Setting this env var switches ChromaDB from `PersistentClient` to `EphemeralClient`
- The index is rebuilt in RAM on every cold start (~20–30 s)
- On a paid tier with persistent storage this would be changed to `persistent`

### Secrets set in HF Space Settings

| Name | Value | Visibility |
|------|-------|-----------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (real key) | Private (Secret) |
| `CHROMADB_MODE` | `ephemeral` | Private (Secret) |

**Important:** Only set these as **Secrets** (private), never as public Variables.

### Git remotes

```bash
git remote -v
# origin  https://github.com/GerediNIYIBIGIRA/BNR-DS-Challenge.git
# hf      https://huggingface.co/spaces/geredi/BNR-Document-Intelligence
```

---

## 10. Making Changes & Redeployment

### Workflow

```bash
# 1. Edit files locally
# 2. Test locally: streamlit run app.py

# 3. Commit changes
git add <files>
git commit -m "Describe your change"

# 4. Push to HF Spaces (triggers auto-rebuild, ~3-5 min)
git push hf main

# 5. Also keep GitHub in sync
git push origin main
```

### Adding new PDF documents to the corpus

```bash
# Copy the new PDF into corpus/
# Then:
git lfs track "*.pdf"    # only needed if not already tracked
git add corpus/new_file.pdf
git add .gitattributes   # if it changed
git commit -m "Add new corpus document: ..."
git push hf main
git push origin main
```

HF Spaces will rebuild and re-index on the next visitor after deployment.
Force re-index via the "Rebuild index" button in the Streamlit sidebar.

### Changing the LLM model

Edit `src/config.py`:
```python
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")   # upgrade example
```
Or set the `LLM_MODEL` secret in HF Space Settings (no code change needed).

---

## 11. Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `ANTHROPIC_API_KEY not set` | Missing `.env` or secrets | Add key to `.env` locally; add Secret in HF Settings |
| `ModuleNotFoundError: chromadb` | Install failed | `pip install chromadb` separately |
| `PermissionError` on `chroma_db/` | HF ephemeral filesystem | Set `CHROMADB_MODE=ephemeral` in Secrets |
| App crashes on HF startup | RAM exhausted | Check Logs tab; try CPU upgrade hardware |
| Push rejected (binary files) | PDFs not tracked by LFS | `git lfs install && git lfs migrate import --include="*.pdf" --everything` |
| `repository not found` | Wrong remote URL | Check `git remote -v` and fix with `git remote set-url` |
| API key blocked by GitHub | Real key in committed file | Replace with placeholder, wipe history, recommit |
| Slow first load | Cold start — index rebuild | Normal; shows spinner; ~20–30 s |
| Wrong model error | `.env` overrides config | Check `.env` for `LLM_MODEL=` line |

---

## 12. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embeddings | `all-MiniLM-L6-v2` (local) | No API cost; corpus text never leaves institution |
| Vector store | ChromaDB | Simple, reliable, metadata-rich, no server required |
| Chunking | 600 words / 100 overlap | Balances context completeness vs noise |
| LLM | Claude Haiku (Anthropic) | Fast, cost-effective, excellent instruction-following |
| Fallback | Hardcoded exact string | Prevents hallucination on out-of-corpus questions |
| Deployment | HF Spaces (Docker) | 16 GB RAM free; sentence-transformers needs ~600 MB |
| Cloud DB mode | EphemeralClient | HF free tier has no persistent disk; rebuilt on startup |
| Binary files | Git LFS | HF Hub rejects large binaries pushed via plain git |
| Audit trail | JSON-lines append | Simple, queryable, append-only — tamper-evident |

---

## 13. Evaluation Results Summary

### Scores at a glance

- **4/5 questions** produced correct or partially correct answers
- **0 hallucinations** — no fabricated statistics or invented sources
- **1 critical failure** (Q4): confident answer returned despite similarity scores < 0.58

### Root causes identified

1. **No similarity threshold gate** — Q4 answered confidently at sim=0.508; should refuse below 0.65
2. **Single-document bias** — Q2 and Q5 retrieved from only one document despite multi-source queries
3. **Semantic retrieval gap** — Q1 matched the topic (financial inclusion) but not the sub-topic (barriers)

---

## 14. Known Limitations & Future Improvements

### Immediate fixes (high impact)

| Fix | Addresses | Implementation |
|-----|-----------|---------------|
| Minimum similarity threshold (≥ 0.65) | Q4 over-confidence | Add check in `retriever.py` or `rag_pipeline.py` |
| Hybrid BM25 + dense retrieval | Q1 keyword recall | Add `rank_bm25` alongside ChromaDB |
| Diversified top-k (≥ 2 sources) | Q2/Q5 single-doc bias | Post-retrieval source diversity check |

### Medium-term improvements

- Cross-encoder reranking (e.g., `ms-marco-MiniLM-L-6-v2`) for chunk quality
- PDF table and figure extraction (current: text only)
- Metadata-filtered search (restrict query to one specific document)
- Faithfulness scoring (check answer is entailed by retrieved chunks before returning)

### Long-term

- Fine-tuned embedding model on Kinyarwanda–English financial/legal text
- Persistent vector store on HF paid tier (avoid cold-start rebuild)
- Centralised log aggregation (ELK/Splunk) with retention policy
- Golden test set for continuous evaluation on model upgrades

---

## 15. Security & API Key Management

### Rules

1. **Never commit `.env`** — it is in `.gitignore`; always use `.env.example` as the template
2. **Never put real keys in `.env.example`** — GitHub and HF will block the push (GH013 / HF secret scan)
3. **On HF Spaces** — always use **Secrets** (private), never public Variables
4. **Local dev** — key lives only in `.env` on your machine
5. **If a key is accidentally committed** — rotate it immediately at https://console.anthropic.com, then rewrite history

### Key rotation (if compromised)

```bash
# 1. Go to console.anthropic.com → API Keys → Delete the leaked key
# 2. Create a new key
# 3. Update .env locally
# 4. Update Secret in HF Space Settings
# 5. Rewrite local git history to remove the leaked key:
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' HEAD
git push origin main --force
git push hf main --force
```

---

*End of documentation. For questions contact Geredi Niyibigira.*
