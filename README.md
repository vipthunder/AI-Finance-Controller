# AI Finance Controller — Track 04: Multi-Source Financial Reconciliation Engine

A production-grade, technically defensible, auditable financial reconciliation engine built for the **Razorpay Buildathon**. Reconciles complex multi-source transactions across **General Ledger (Internal ERP)**, **Bank Statements (External Settlements)**, and **Invoices (Accounts Payable)** with authoritative deterministic controls, genuine AI verification, and 100% decision traceability.

---

##  System Architecture

```
                       [ Ingestion & Normalizer ] 
                       (Canonical Vendor Catalog & Legal Suffix Stripping)
                                   │
                                   ▼
[ Multi-Signal Candidate Generator (Blocking) ] ──(Reference, Entity, Proximity Blocking)
                                   │
                                   ▼
                          [ Exact Matcher ] ──────────(Exact Pairs)─────────────┐
                                   │                                            │
                          (Unmatched Candidates)                                │
                                   │                                            │
                                   ▼                                            │
                      [ Fuzzy Scorer (Rapidfuzz) ]                              │
                                   │                                            │
               ┌───────────────────┴───────────────────┐                        │
               │ Score >= 0.85        0.50 <= Score < 0.85                     │
               ▼                                       ▼                        │
       (Direct Fuzzy Match)                    [ AI Verifier ]                  │
               │                            (LLMProvider Abstraction:          │
               │                             Gemini/OpenAI or Mock)             │
               │                                       │                        │
               │                                (Score >= 0.75)                 │
               │                                       │                        │
               └───────────────────────┬───────────────┘                        │
                                       ▼                                        │
                      [ Collision & Competition Policy ]                        │
                        (Losing matches → SUPERSEDED)                           │
                                       │                                        │
                                       ▼                                        │
                      [ Authoritative Deterministic Validator ] <───────────────┘
                        (Amounts, Dates, Currencies, Duplicate Clones)
                                       │
                         ┌─────────────┴─────────────┐
                       PASS                         FAIL
                         │                            │
                         ▼                            ▼
               [ Decision Controller ]      [ Exception Investigator ]
                         │                            │
                         ▼                            ▼
                 (Resolved Match)           (Human Escalation Queue)
                         │                            │
                         └─────────────┬──────────────┘
                                       ▼
                         [ Immutable Audit Trail ]
                 (outputs/audit/audit.json & decisions.json)
```

---

##  5-Minute Razorpay Pitch

### 1. The Core Problem in Modern B2B Reconciliation
Fintech platforms and high-growth enterprises process millions of transactions daily across legacy ERPs, payment gateways, and diverse banking rails. Real-world financial feeds are notoriously messy:
* **Statement narrative noise:** `"AWS*US-EAST-1"`, `"AMZN WEB SERVICES"`, `"AMAZON WEB SERVICES INC"`
* **Deducted intermediary wire fees:** A $10,000 disbursement arriving as $9,980 after a $20 processing fee.
* **Settlement timing lag:** Invoices issued on Friday settling via ACH or RTGS on Tuesday.
* **Intra-source cloned duplicates:** Double-debits or retry attempts in bank feeds that naive matchers link to pending invoices.

### 2. Why Conventional Heuristics & Unconstrained AI Both Fail
* **Pure heuristic rules** either suffer high false positives or artificially deflate recall when fees, timing lags, or name variations appear.
* **Unconstrained AI / LLMs** are non-deterministic, hallucinatory, and legally indefensible. Financial reconciliations demand deterministic guarantees.

### 3. The Antigravity Solution: Targeted AI within Authoritative Guardrails
* **Authoritative Deterministic Controls:** No AI or fuzzy match can ever commit directly. The shared `DeterministicValidator` strictly enforces currency consistency, amount tolerances ($28 absolute / 5% relative), date windows, and intra-source duplicate locks.
* **Genuine AI Provider Abstraction:** Mid-band ambiguous candidates are inspected by `AIVerifier` via `BaseLLMProvider` (`LiveLLMProvider` with structured JSON schema or deterministic `MockLLMProvider`), recording token latency and estimated cost.
* **Zero Silent Drops:** Every record reaches an explicit terminal state. If an AI-accepted pair collides with an earlier match, the losing candidate is deterministically flagged as `SUPERSEDED` with cross-references and audit entries.
* **Actionable Human Escalation Queue:** Exceptions are never dead ends. Every exception contains an ID, source IDs, root-cause reason code (`AMBIGUOUS`, `LIKELY_DUPLICATE`, `VALIDATION_FAILED`), financial amounts, and suggested human remediation actions.

---

##  Authoritative Benchmark Scorecard (Clean Benchmark: Seed 42, 60 Tx, 179 Records)

All figures below are extracted directly from `outputs/reports/metrics.json` produced by `python scripts/evaluate.py`:

| Level / Category | Metric | Value | Technical Defense & Definition |
| :--- | :--- | :---: | :--- |
| **RELATIONSHIP LEVEL** | **Candidate Recall** | **100.00%** | Multi-signal blocking (reference, canonical entity, proximity) captures all 172 eligible GT relationships. |
| | **Relationship Precision** | **100.00%** | Zero false positives (`FP = 0`). Every committed relationship verified by deterministic controls. |
| | **Relationship Recall** | **100.00%** | All 172 ground-truth relationships committed across Ledger, Bank, and Invoice (`TP = 172`). |
| | **Relationship F1 Score** | **100.00%** | Harmonic mean: $2 \times P \times R / (P + R) = 1.0000$. |
| **TRANSACTION LEVEL** | **Canonical Transactions** | **60** | Distinct economic business transactions in ground-truth store. |
| | **Fully Reconciled Tx** | **60 (100.00%)** | All source records and relationships belonging to each transaction are completely resolved. |
| | **Partially Reconciled Tx** | **0 (0.00%)** | Zero transactions left with incomplete source matching. |
| | **Unresolved Tx** | **0 (0.00%)** | Zero transactions abandoned. |
| **AI PROPOSAL LEVEL** | **AI Invocations** | **144** | Mid-band ambiguous candidate pairs routed to LLM provider. |
| | **AI Accepted** | **23** | Structured LLM verification approved 23 ambiguous candidate pairs with confidence $\ge 0.75$. |
| | **AI Committed** | **21** | **Active AI Contribution:** 21 AI-verified proposals won global slot competition and committed as final matches. |
| | **AI Validation Failed** | **2** | Deterministic safety validator caught 2 candidates violating financial tolerances. |
| | **AI Superseded** | **0** | Zero AI proposals lost to invalid collisions. |
| | **AI Invariant Accounting** | **100.00%** | `AI_ACCEPTED (23) == AI_COMMITTED (21) + AI_VAL_FAILED (2) + AI_SUPERSEDED (0) + AI_FAILED (0)`. |
| | **AI Recommendation Precision** | **91.30%** | Correct AI recommendations / all AI accepted proposals ($21 / 23$). |
| | **AI Recommendation Recall** | **100.00%** | Correct AI recommendations / AI-eligible GT relationships ($21 / 21$). |
| | **AI Contribution Recall** | **12.21%** | Global GT relationships resolved by AI / all GT relationships ($21 / 172$). |
| **FINANCIAL LEVEL** | **Total Canonical Value** | **$182,008.84** | De-duplicated true business transaction value across 3 systems (prevents triple counting). |
| | **Fully Reconciled Value** | **$182,008.84** | **100.00%** of underlying business transaction volume fully resolved. |
| | **Unresolved Canonical Value** | **$0.00** | Canonical transactions left unreconciled. |
| | **Incorrectly Matched Value** | **$0.00** | **Zero financial capital at risk** from misallocated settlements. |
| | **Exception Source-Record Exposure** | **$18,666.10** | Exposure held in exception queue (strictly duplicate clones and missing records). |
| **SAFETY & AUDIT** | **Duplicate Escape Rate** | **0.0000** | Cloned bank records blocked by intra-source duplicate detection. |
| | **Critical Error Rate** | **0.0000** | Zero currency mismatches or same-source pairs committed. |
| | **Silent-Drop Count** | **0** | Invariant verified: every input record maps to exactly one terminal state (`decisions == records`). |
| | **Audit Trail Integrity** | **100%** | Every decision, exception, and proposal logged to `outputs/audit/audit.json`. |
| **PERFORMANCE** | **Throughput** | **~2,700 rec/sec** | Sub-100ms pipeline execution across 179 records (excludes dataset generation). |

> **Core Financial Design Principle:**  
> *AI proposes. Deterministic financial controls decide. Global competition resolves conflicts. Exceptions capture uncertainty. Audit records everything. Independent evaluation measures truth.*

---

##  Genuine AI Judgment Architecture

Financial reconciliation demands absolute mathematical correctness. A system that allows an LLM to hallucinate debit/credit pairings or bypass financial tolerances is fundamentally indefensible in production.

### Where AI IS Used
* **Mid-Band Ambiguity (0.50 ≤ Composite Score < 0.85):** When names possess substantial variation (e.g. `"L&W Legal"` vs `"LATHAM & WATKINS LLP"`, or `"SFDC"` vs `"SALESFORCE INC"`), AI provides semantic reasoning, entity grounding, and risk-flag detection.
* **Structured Decision Outputs:** The LLM produces a strict JSON payload with boolean approval, confidence, structured decision rationale, and identified discrepancy vectors.

### Where AI IS NOT Used
* **Exact Matching:** Handled purely by deterministic O(1) hash lookups on reference identifiers and exact attributes.
* **Deterministic Financial Validation:** The LLM *never* commits a transaction. Every match proposed by AI must independently pass the `DeterministicValidator` (currency consistency, amount tolerance, date window, duplicate checks).
* **Policy Enforcement:** Financial controls and regulatory constraints remain deterministic, auditable, and code-enforced.

---

##  Failure Recovery & Real Engineering Bugs Solved

Every failure documented below was an actual defect uncovered and resolved during the hardening pass:

### 1. Silent Drop of AI Recommendations
* **Symptom:** AI evaluated 23 mid-band candidate pairs, accepted them, but reported `AI committed = 0` and records appeared to vanish.
* **Root Cause:** A collision check noticed that the counterparty record had already been committed in an earlier high-confidence stage and called `continue`, silently discarding the candidate pair without a terminal decision.
* **Engineering Fix:** Implemented explicit `SUPERSEDED` state in `DecisionController` and `ReconciliationPipeline`. The losing match is recorded with conflicting transaction pointers, rationale, and audit events.
* **Regression Guard:** `tests/test_stopping_conditions.py::test_sc01_ai_accepted_not_silently_lost`.

### 2. Candidate Recall Conflation
* **Symptom:** Candidate recall was reported as a unified number that masked candidate generation bottlenecks by combining candidate generation with exact matching.
* **Root Cause:** Exact matches were being injected into the evaluation candidate pool, inflating candidate recall.
* **Engineering Fix:** Disentangled metrics into `raw_candidate_recall` (pure candidate generator performance), `exact_match_coverage`, and `final_reconciliation_recall`.
* **Regression Guard:** `tests/test_full_pyramid.py::test_sc07_candidate_recall_is_measured`.

### 3. Financial Metric Multi-Counting Across Data Sources
* **Symptom:** Total value reported exceeded $559k for transactions representing ~$182k in actual business volume.
* **Root Cause:** Naive sum of all records in Ledger + Bank + Invoice summed each underlying economic transaction 2 to 3 times.
* **Engineering Fix:** Implemented transaction-level canonical accounting via `GroundTruthStore` mapping canonical business values (`$182,008.84`) separately from raw source sums.
* **Regression Guard:** `tests/test_full_pyramid.py::test_sc09_financial_value_reconciliation_is_measured` and `tests/test_financial_value.py`.

### 4. Silent Live → Mock Fallback
* **Symptom:** When live LLM API keys failed or timed out, the provider silently defaulted to mock heuristic values, giving false confidence in live AI.
* **Root Cause:** Broad `try...except` block in `LiveLLMProvider` caught API errors and substituted mock responses.
* **Engineering Fix:** Removed silent fallbacks. API errors now set `is_error=True`, flag `ai_failed_count`, and explicitly report provider mode as `ERROR` or `LIVE`.
* **Regression Guard:** `src/verification/llm_provider.py` and `tests/test_ai_verification.py`.

---

##  Unified Configuration (`configs/thresholds.yaml` & `src/config.py`)

All tolerances and thresholds are centrally defined and loaded via Pydantic models:

```yaml
router:
  high_confidence: 0.85
  mid_band_min: 0.50

ai_verification:
  acceptance_threshold: 0.75
  provider: "mock" # "live" for OpenAI/Gemini

validator:
  max_amount_abs_tolerance: 28.00  # Absorbs intermediary wire fees ($15-$25)
  max_amount_pct_tolerance: 0.05   # 5% relative variance
  max_date_tolerance_days: 10      # Settlement timing window

candidate_generation:
  max_date_diff_days: 14
  max_amount_pct_diff: 0.20
  max_amount_abs_diff: 30.00
  enable_reference_blocking: true
  enable_entity_blocking: true
  enable_proximity_blocking: true
```

---

##  Comprehensive Automated Test Suite (171 Tests)

Run the full automated test suite verifying all buildathon requirements:

```bash
python -m pytest tests/ -v
```

### Key Test Categories
* `tests/test_isolation.py`: AST-based import-boundary test enforcing that production modules never import `ground_truth`, `SyntheticDataGenerator`, or `evaluator`.
* `tests/test_integration_scenarios.py`: 12 end-to-end integration tests covering exact, fuzzy, AI, validator rejection, superseded proposals, duplicate conflicts, unresolved exceptions, currency mismatches, blocking failures, competing proposals, and partial reconciliation.
* `tests/test_metric_fixtures.py`: 15 fixture tests including all 4 mandatory adversarial evaluation fixtures (TP/FP/FN set theory, equal counts with wrong relationships, candidate recall, and cross-metric invariants), 4 adversarial transaction-level fixtures (A, B, C, and Case D wrong relationships with resolved records), AI recall definitions, and audit correspondence invariants.
* `tests/test_output_consistency.py`: Programmatic verification ensuring metrics, decisions, exceptions, and audit logs are 100% mutually consistent.
* `tests/test_decision_accounting.py`: Invariant test proving `AI accepted == AI committed + AI superseded + AI validation failures + AI failed` with zero silent drops.
* `tests/test_financial_value.py`: Proves canonical business transaction value de-duplication.
* `tests/test_reproducibility.py`: Verifies byte-for-byte reproducibility across identical seeds for datasets, decisions, and metrics.
* `tests/test_configuration.py`: Proves that modifying thresholds in configuration changes system behavior dynamically without modifying code.
* `tests/test_normalization.py`: Validates legal suffix stripping, whitespace/punctuation cleanup, canonical alias mapping, and null safety.
* `tests/test_full_pyramid.py`: 75-test test pyramid covering regressions, invariants, stopping conditions, and end-to-end execution.

---

##  System Limitations & Honest Scope

1. **Batch Scaling:** The current pipeline operates in-memory with sub-100ms execution on batches of hundreds of multi-source records (~2,700 rec/sec). High-volume enterprise environments processing tens of millions of records daily would distribute candidate generation and blocking across Apache Spark or distributed streaming queues (e.g. Kafka).
2. **Wire Fee Tolerance Bounds:** Financial tolerances are bounded at $28.00 absolute and 5.0% relative in `configs/thresholds.yaml` to prevent fraud. Edge-case cross-border wires incurring exotic correspondent fees (> $28) are safely routed to the human exception queue for manual approval.
3. **AI Provider Mode:** For 100% byte-for-byte offline reproducibility in buildathon evaluation, the benchmark runs with `MockLLMProvider`. Production live AI verification can be activated at any time by supplying a `GEMINI_API_KEY` or `OPENAI_API_KEY` in `.env` and configuring `provider: "live"` in `configs/thresholds.yaml`.

---

##  Execution & Verification Commands

### 1. Run Clean Evaluation & Generate Output Artifacts
```bash
python scripts/evaluate.py
```
Generated artifacts:
* `outputs/reports/metrics.json`: Full 78-key reconciliation scorecard and discrepancy breakdown.
* `outputs/reports/exceptions.json`: Actionable per-record exception queue with evidence and suggested actions.
* `outputs/decisions/decisions.json`: Complete audit of all resolved and superseded decisions.
* `outputs/audit/audit.json`: Complete append-only audit trail with timestamps and inputs.

### 2. Run Interactive Demo
```bash
python scripts/run_demo.py
```

### 3. Generate New Synthetic Dataset
```bash
python scripts/generate_data.py
```
Deterministic zero-padded IDs (`GT-0001`, `L-0001`, `B-0001`, `I-0001`, `B-0001-DUP1`).
