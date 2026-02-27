# BNR RAG System — Evaluation Analysis
**Geredi Niyibigira | Data Science Challenge #1**

All five questions were run against the live system. Results below.

---

## Q1 — What are the main barriers to financial inclusion in rural Rwanda?

**Retrieved chunks:**
| Source | Page | Similarity |
|--------|------|-----------|
| Rwanda FinScope 2024 Report | 75 | 0.752 |
| Rwanda FinScope 2024 Report | 32 | 0.735 |
| Rwanda FinScope 2024 Report | 33 | 0.727 |
| Rwanda FinScope 2024 Report | 5  | 0.720 |
| Rwanda FinScope 2024 Report | 15 | 0.718 |

**Final answer (summary):**
> "The answer cannot be determined from the provided documents. While the excerpts discuss financial inclusion achievements and recommendations, they do not explicitly identify the main barriers to financial inclusion in rural Rwanda."

**Commentary on correctness:**
Technically correct — the system retrieved summary/recommendation pages (pp. 75, 15), which discuss what Rwanda should prioritise going forward, not what blocks rural access today. The refusal is honest and reflects good grounding discipline. No hallucination.

**Identified limitation:**
*Retrieval gap due to semantic mismatch.* The query phrase "barriers to financial inclusion" semantically matched high-level inclusion pages rather than the demand-side constraint chapters likely buried in pages 45–65. The embedding model found pages about "financial inclusion" (the topic) but missed pages specifically discussing obstacles. A hybrid BM25 + dense search on keywords like "challenge," "obstacle," "barrier," "constraint" would likely surface the relevant pages. This is the most impactful improvement available.

---

## Q2 — How does mobile money usage differ by gender?

**Retrieved chunks:**
| Source | Page | Similarity |
|--------|------|-----------|
| GSMA State of the Industry Report 2025 | 75 | 0.770 |
| GSMA State of the Industry Report 2025 | 71 | 0.741 |
| GSMA State of the Industry Report 2025 | 76 | 0.735 |
| GSMA State of the Industry Report 2025 | 77 | 0.727 |
| GSMA State of the Industry Report 2025 | 70 | 0.717 |

**Final answer (summary):**
Detailed, structured answer covering: account ownership gaps (Pakistan: women 70% less likely), frequency of use (7-day gap wider than 30-day), and specific transaction types (salaries, merchant payments, bill payments) where women lag. Sources: GSMA pp. 70–77.

**Commentary on correctness:**
Strong retrieval — the system correctly located GSMA's entire "Chapter 4: The mobile money gender gap" section. Statistics are specific and verifiable. However, the answer focuses on global/South Asia data and includes no Rwanda-specific gender data, even though FinScope 2024 contains Rwanda gender breakdown statistics.

**Identified limitation:**
*Geographic scope mismatch without flagging.* The system retrieved the GSMA chapter on gender (correct conceptually) but never cross-referenced FinScope for Rwanda-specific gender data. A single-document bias occurred — once high-similarity GSMA chunks were found, retrieval did not diversify to FinScope. A multi-source retrieval strategy or metadata-filtered post-query would have enriched the answer with both global and Rwanda-specific data.

---

## Q3 — Summarize the National Bank of Rwanda's operational role in the payment system

**Retrieved chunks:**
| Source | Page | Similarity |
|--------|------|-----------|
| Payment System Law No. 061/2021 (NBR) | 1  | 0.760 |
| Rwanda FinScope 2024 Report           | 60 | 0.754 |
| Rwanda FinScope 2024 Report           | 25 | 0.682 |
| Payment System Law No. 061/2021 (NBR) | 40 | 0.681 |
| Rwanda FinScope 2024 Report           | 61 | 0.672 |

**Final answer (summary):**
Four roles identified: (1) General Powers (Art. 4), (2) Investigative Powers (Art. 5), (3) Interoperability Management (Art. on interoperability), (4) Strategic Leadership with MINECOFIN on the RNPS Strategy 2018–2024. Sources: Law pp. 1, 40; FinScope p. 60.

**Commentary on correctness:**
Good multi-source synthesis. Article-level citations are precise and verifiable. FinScope p. 60 added useful strategic context. The answer correctly distinguished NBR's legal mandate (from the Law) from its policy strategy (from FinScope's reference to MINECOFIN collaboration).

**Identified limitation:**
*Secondary source used in place of primary for strategic role.* FinScope p. 60 is a survey report referencing the RNPS Strategy — not the strategy itself. Citing a survey's mention of a strategy is one step removed from the authoritative source. Additionally, the "Interoperability" role lacks a specific article number, which reduces verifiability. In a central bank setting, all legal citations must be precise.

---

## Q4 — Has digital payment adoption increased?

**Retrieved chunks:**
| Source | Page | Similarity |
|--------|------|-----------|
| GSMA State of the Industry Report 2025 | 61 | 0.579 |
| GSMA State of the Industry Report 2025 | 44 | 0.536 |
| GSMA State of the Industry Report 2025 | 60 | 0.517 |
| GSMA State of the Industry Report 2025 | 50 | 0.510 |
| GSMA State of the Industry Report 2025 | 57 | 0.508 |

**Final answer (summary):**
Yes, with stats: ASEAN region 25% utility digital payments, 80% of account holders use digital payments, mobile money loan customers grew 50% (Sep 2023–Jun 2024), credit-offering providers grew from 24% to 44%.

**Commentary on correctness:**
This is the most problematic output. All five similarity scores are below 0.58 — the weakest retrieval of the entire evaluation. Despite this, the system returned a confident detailed answer rather than a refusal. Compare with Q1 (scores 0.718–0.752) where a refusal was correctly issued. The inconsistency is a significant safety concern.

**Identified limitation (critical failure case):**
*Inconsistent uncertainty thresholds — low-confidence retrieval produces confident output.* Q4 demonstrates that the system lacks a similarity score threshold gate. Below a minimum confidence floor (e.g., 0.65), the system should refuse or warn the user rather than answering confidently. The ASEAN statistics returned are geographically misaligned with the Rwanda context and may mislead a user who does not inspect raw retrieval scores. **This is the primary failure case to address.**

---

## Q5 — How does Rwanda compare to global mobile money trends?

**Retrieved chunks:**
| Source | Page | Similarity |
|--------|------|-----------|
| Rwanda FinScope 2024 Report | 40 | 0.775 |
| Rwanda FinScope 2024 Report | 41 | 0.723 |
| Rwanda FinScope 2024 Report | 34 | 0.700 |
| Rwanda FinScope 2024 Report | 36 | 0.699 |
| Rwanda FinScope 2024 Report | 73 | 0.699 |

**Final answer (summary):**
Rwanda data provided: 98% mobile money awareness, 77% registered wallets (6.3M), 86% used mobile money, 56% mobile wallets only. System correctly states it cannot compare to global trends because no global benchmark data was retrieved.

**Commentary on correctness:**
Honest and technically correct. The Rwanda figures are accurate and well-sourced. The self-limitation statement ("I cannot make a direct comparison without global data") is appropriate given the retrieved context.

**Identified limitation:**
*Cross-document retrieval failure for comparative queries.* The GSMA document (already indexed) contains global mobile money benchmarks that would have enabled the comparison. However, the query's Rwanda-heavy language anchored retrieval entirely to FinScope. GSMA was never surfaced. A decomposed two-stage retrieval ("retrieve Rwanda data" + "retrieve global benchmarks") or diversified retrieval that enforces representation from multiple documents would enable this comparison.

---

## Summary Table

| # | Question | Answer Type | Correct? | Primary Failure |
|---|----------|-------------|----------|-----------------|
| Q1 | Barriers to inclusion in rural Rwanda | Appropriate refusal | ✓ | Retrieval gap — semantic mismatch on "barriers" |
| Q2 | Gender gap in mobile money | Detailed, structured | ✓ (global only) | Geographic mismatch, Rwanda not retrieved |
| Q3 | NBR payment system role | Multi-source synthesis | ✓ Mostly | Secondary source citation; imprecise article ref |
| Q4 | Digital payment adoption | Confident answer | ✗ | Low-confidence retrieval, no threshold gate |
| Q5 | Rwanda vs global trends | Honest partial answer | ✓ | Cross-document failure — GSMA not retrieved |

## Key Findings

1. **Grounding works** — the system never fabricated statistics or invented sources.
2. **Fallback triggers correctly** for clearly insufficient context (Q1) but inconsistently for low-confidence retrieval (Q4). A minimum similarity threshold (~0.65) would fix this.
3. **Single-document bias** — comparative or multi-source questions tend to retrieve from one document. Diversified top-k retrieval (e.g., at least 2 chunks from different sources) would improve Q2 and Q5.
4. **Citation precision** — article-number citations from the payment law are a strength. Citations to survey documents citing other strategies are a weakness.
