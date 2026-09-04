# AI Finance Controller — Track 04

### Multi-Source Financial Reconciliation Engine

An automated system for matching transactions across ledgers, bank statements, and invoices.

Financial records from different systems rarely look identical. Vendor names change, references differ, settlement dates move, and duplicate records can appear.

This project combines **exact matching, fuzzy matching, AI verification, deterministic validation, exception handling, and audit logging** to reconcile those records safely.

> **AI proposes. Deterministic controls decide.**

---

## Objective

> Automatically match transactions from the ledger, bank statements, and invoices accurately and safely.

---

## The Problem

The same business transaction can look different across financial systems.

For example:

```text
Ledger
Vendor:    AMAZON WEB SERVICES INC
Amount:    $10,000
Reference: REF-1042

Bank
Vendor:    AWS US-EAST-1
Amount:    $9,980
Reference: ACH-7781

Invoice
Vendor:    AMZN WEB SERVICES
Amount:    $10,000
Reference: INV-4821
```

These records can represent the same underlying transaction.

A simple exact matcher may fail to connect them.

Amounts can also differ because of fees.

Dates can differ because of settlement delays.

Duplicates can appear in individual source systems.

The system needs to handle these cases without creating incorrect financial matches.

---

# Architecture

```text
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
                  ┌────────────────┴────────────────────┐                       │
                  │ Score >= 0.85       0.50 <= Score < 0.85                    │
                  ▼                              ▼                              │
          (Direct Fuzzy Match)            [ AI Verifier ]                       │
                  │                        (LLMProvider Abstraction:            │
                  │                          Gemini)                            │
                  │                              │                              │
                  │                       (Score >= 0.75)                       │
                  │                              │                              │
                  └──────────────────┬───────────┘                              │
                                     ▼                                          │
                       [ Collision & Competition Policy ]                       │
                         (Losing matches → SUPERSEDED)                          │
                                     │                                          │
                                     ▼                                          │
                       [ Authoritative Deterministic Validator ]  ◄─────────────┘
                         (Amounts, Dates, Currencies, Duplicate Clones)
                                     │
                            ┌────────┴─────────┐
                            │                  │
                          PASS               FAIL
                            │                  │
                            ▼                  ▼
                  [ Decision Controller ]  [ Exception Investigator ]
                            │                  │
                            ▼                  ▼
                    (Resolved Match)      (Human Escalation Queue)
                            │                  │
                            └────────┬─────────┘
                                     ▼
                       [ Immutable Audit Trail ]
                (outputs/audit/audit.json & decisions.json)
```

---

# How It Works

## 1. Ingestion and Normalization

The project works with three source systems:

```text
data/raw/
├── ledger.csv
├── bank.csv
└── invoices.csv
```

Each source uses different field names and formats.

The normalizer converts them into a common internal representation.

It handles:

* Date normalization
* Amount normalization
* Currency normalization
* Vendor normalization
* Whitespace and punctuation cleanup
* Legal suffix handling
* Canonical entity mapping

### Example

```text
"AMAZON WEB SERVICES INC."
            ↓
"AMAZON WEB SERVICES"
```

Known aliases can also map to the same canonical entity.

```text
"AWS"
"AWS*US-EAST-1"
"AMZN WEB SERVICES"
            ↓
AMAZON WEB SERVICES
```

This gives the matching stages a consistent view of the data.

---

# 2. Candidate Generation

The system does not compare every record with every other record.

Instead, it generates a smaller set of plausible candidates.

Three blocking strategies are used.

### Reference Blocking

Records sharing useful reference evidence become candidates.

```text
REF-1042
   │
   ├── Ledger L-1042
   └── Bank B-1042
```

### Entity Blocking

Records mapped to the same canonical entity can become candidates.

```text
MICROSOFT AZURE
MS AZURE COMPUTING
AZURE
```

### Proximity Blocking

Candidates can also be generated using amount and date proximity.

Current candidate-generation limits include:

```text
Maximum date difference:        14 days
Maximum percentage difference:  20%
Maximum absolute difference:    $30
```

This reduces the search space before fuzzy scoring.

---

# 3. Exact Matching

Exact matching handles the strongest cases first.

Example:

```text
Ledger
Date:       2024-05-20
Amount:     $147.52
Currency:   USD
Vendor:     STRIPE
```

```text
Bank
Date:       2024-05-20
Amount:     $147.52
Currency:   USD
Vendor:     STRIPE
```

When the relevant attributes agree, the relationship can be resolved deterministically.

There is no need to involve AI.

---

# 4. Fuzzy Matching

Some valid matches are not exact.

The fuzzy matcher uses RapidFuzz.

The composite score uses:

```text
Vendor similarity   → 40%
Amount similarity   → 40%
Date similarity     → 20%
```

### Example

```text
Ledger
Vendor: LATHAM & WATKINS LLP
Amount: $4,850
Date:   2024-08-12
```

```text
Bank
Vendor: L&W LEGAL
Amount: $4,850
Date:   2024-08-13
```

The vendor names differ.

The amount matches exactly.

The dates are close.

This is the type of case where fuzzy matching can identify a likely relationship.

---

# 5. Confidence Routing

The fuzzy score determines what happens next.

```text
Score ≥ 0.85
      ↓
Direct fuzzy match
```

Ambiguous candidates enter AI verification:

```text
0.50 ≤ Score < 0.85
      ↓
AI verification
```

This prevents straightforward transactions from unnecessarily going through an LLM.

---

# 6. AI Verification

AI is used only for ambiguous candidate pairs.

The project uses a provider abstraction:

```text
BaseLLMProvider
      │
      ├── MockLLMProvider
      │
      └── LiveLLMProvider
```

The AI verifier produces a structured recommendation.

Conceptually:

```json
{
  "match": true,
  "confidence": 0.91,
  "reason": "Entity aliases and financial attributes are consistent.",
  "discrepancies": [
    "Settlement date differs by one day"
  ]
}
```

The recommendation is only a proposal.

AI does not directly commit the transaction.

---

# 7. Deterministic Financial Validation

Every proposed match passes through deterministic validation.

The validator checks:

* Currency consistency
* Absolute amount difference
* Relative amount difference
* Date difference
* Duplicate conflicts
* Same-source restrictions

Current validation limits are:

```text
Maximum absolute amount difference: $28
Maximum relative difference:        5%
Maximum date difference:             10 days
```

### Example

```text
Ledger → $10,000
Bank   → $10,900
```

The AI might consider them related.

However:

```text
Absolute difference = $900
Relative difference = 9%
```

The validator rejects the proposal.

```text
AI             → MATCH
Validator      → FAIL
Final decision → EXCEPTION
```

This keeps financial authority outside the LLM.

---

# 8. Collision Handling

A collision occurs when multiple proposals compete for the same record.

For example:

```text
Ledger L-101
     │
     ├── Bank B-201
     │
     └── Bank B-202
```

Both candidates may look plausible.

Only one relationship can become the final match.

Suppose B-201 wins:

```text
L-101 ─────► B-201
             WINNER

L-101 ─────► B-202
             SUPERSEDED
```

The losing proposal is not silently discarded.

It is recorded as `SUPERSEDED`.

This preserves complete decision accounting.

---

# 9. Exception Handling

Some records cannot be safely reconciled automatically.

These cases move into an exception queue.

Current reason codes include:

```text
AMBIGUOUS
LIKELY_DUPLICATE
VALIDATION_FAILED
NO_CANDIDATE
```

### Example

```text
Record: B-1042
Amount: $5,000

Reason:
LIKELY_DUPLICATE

Suggested action:
Review against the original settlement.
```

The exception investigator also provides suggested remediation actions.

---

# 10. Canonical Financial Accounting

A source record is not the same thing as a business transaction.

Suppose the same transaction appears in three systems:

```text
Ledger   → $1,000
Bank     → $1,000
Invoice  → $1,000
```

There are three source records.

There is only one underlying business transaction.

A naive sum gives:

```text
$3,000
```

The actual business value is:

```text
$1,000
```

The project therefore separates source-level records from canonical transactions.

```text
Source Records
      ↓
Matched Relationships
      ↓
Canonical Transaction
      ↓
Business Value
```

This prevents double counting.

---

# End-to-End Example

Consider:

```text
Ledger
Vendor:    Latham & Watkins LLP
Amount:    $8,500
Date:      2024-06-30
Reference: REF-9012
```

```text
Bank
Vendor:    L&W Legal
Amount:    $8,480
Date:      2024-07-02
Reference: ACH-7712
```

The system processes them as follows:

```text
1. Normalize vendor names
            ↓
2. Map entities to canonical representations
            ↓
3. Generate a candidate pair
            ↓
4. Calculate fuzzy similarity
            ↓
5. Route the ambiguous case to AI
            ↓
6. AI proposes a match
            ↓
7. Validator checks amount, date, currency, and duplicates
            ↓
8. Proposal passes
            ↓
9. Transaction is resolved
```

This shows where each stage contributes.

---

# Benchmark Results

The included benchmark contains:

```text
Canonical transactions:     60
Source records:             179
Ground-truth relationships: 172
```

Current results:

| Metric                        |                 Result |
| ----------------------------- | ---------------------: |
| Candidate Recall              |               **100%** |
| Relationship Precision        |               **100%** |
| Relationship Recall           |               **100%** |
| Relationship F1               |               **100%** |
| Fully Reconciled Transactions |            **60 / 60** |
| Unresolved Transactions       |                  **0** |
| Incorrectly Matched Value     |                 **$0** |
| Duplicate Escape Rate         |                  **0** |
| Critical Error Rate           |                  **0** |
| Silent Drop Count             |                  **0** |
| Audit Trail Integrity         |               **100%** |
| Throughput                    | **~2,700 records/sec** |

The benchmark results are generated from the project's evaluation pipeline.

---

# AI Contribution

The benchmark routed ambiguous candidates through AI verification.

```text
AI Invocations        144
AI Accepted            23
AI Committed            21
AI Validation Failed    2
```

The two validation failures are important.

They show that an AI recommendation does not automatically become a financial match.

---

# Financial Results

The benchmark reports:

```text
Total canonical business value:
$182,008.84
```

Fully reconciled value:

```text
$182,008.84
```

Unresolved canonical value:

```text
$0.00
```

Incorrectly matched value:

```text
$0.00
```

Source-level values can be higher because the same transaction appears across multiple systems.

---

# Engineering Challenges

## 1. Silent AI Decisions

An accepted AI proposal could collide with an earlier match.

The proposal could previously disappear without a terminal state.

The project now records the losing proposal as:

```text
SUPERSEDED
```

This makes decision accounting explicit.

---

## 2. Candidate Recall Measurement

Candidate recall should measure candidate generation itself.

Exact matches should not inflate that metric.

The evaluation separates:

```text
Raw candidate recall
Exact match coverage
Final reconciliation recall
```

This provides a clearer measurement of the matching pipeline.

---

## 3. Financial Double Counting

Summing all Ledger, Bank, and Invoice values can count the same transaction multiple times.

Canonical transaction accounting prevents this.

---

## 4. Live AI Failures

A failed live LLM call should not silently become mock output.

The live provider reports failures explicitly.

This prevents a provider outage from appearing as successful AI verification.

---

# Audit Trail

The pipeline records reconciliation decisions and processing events.

Generated outputs include:

```text
outputs/
├── audit/
│   ├── audit.json
│   └── audit_trail.json
│
├── decisions/
│   └── decisions.json
│
└── reports/
    ├── metrics.json
    └── exceptions.json
```

These outputs allow inspection of:

* Matching decisions
* AI proposals
* Validation results
* Superseded proposals
* Exceptions
* Evaluation metrics

---

# Testing

The project contains **171 automated tests**.

Run them with:

```bash
python -m pytest tests/ -v
```

The tests cover:

```text
Normalization
Candidate Generation
Exact Matching
Fuzzy Matching
AI Verification
Deterministic Validation
Decision Accounting
Exception Handling
Financial Value Reconciliation
Audit Consistency
Reproducibility
Configuration
Integration Scenarios
```

Failure scenarios are also tested.

Examples include:

```text
Duplicate conflicts
Currency mismatches
Validation failures
Competing proposals
Silent drops
Candidate recall
Financial value reconciliation
```

---

# Reproducibility

The synthetic dataset uses:

```text
Seed = 42
```

The default benchmark uses:

```text
MockLLMProvider
```

This makes benchmark execution reproducible without external API calls.

Live AI verification can be enabled separately.

---

# Configuration

Important thresholds are centralized in:

```text
configs/thresholds.yaml
```

Example:

```yaml
router:
  high_confidence: 0.85
  mid_band_min: 0.50

ai_verification:
  acceptance_threshold: 0.75
  provider: "mock"

validator:
  max_amount_abs_tolerance: 28.0
  max_amount_pct_tolerance: 0.05
  max_date_tolerance_days: 10

candidate_generation:
  max_date_diff_days: 14
  max_amount_pct_diff: 0.20
  max_amount_abs_diff: 30.0

scoring:
  weight_name: 0.40
  weight_amount: 0.40
  weight_date: 0.20
```

This keeps important behavior configurable.

---

# Project Structure

```text
AI Finance Controller/
│
├── configs/
│   ├── settings.yaml
│   └── thresholds.yaml
│
├── data/
│   ├── raw/
│   │   ├── bank.csv
│   │   ├── invoices.csv
│   │   └── ledger.csv
│   │
│   └── ground_truth/
│       └── ground_truth.json
│
├── dashboard/
│   └── app.py
│
├── outputs/
│   ├── audit/
│   ├── decisions/
│   └── reports/
│
├── scripts/
│   ├── evaluate.py
│   ├── generate_data.py
│   ├── run_demo.py
│   └── run_pipeline.py
│
├── src/
│   ├── audit/
│   ├── config.py
│   ├── controller/
│   ├── data_generation/
│   ├── evaluation/
│   ├── ingestion/
│   ├── investigation/
│   ├── matching/
│   ├── pipeline/
│   ├── schemas/
│   ├── validation/
│   └── verification/
│
├── tests/
│
├── pyproject.toml
└── README.md
```

---

# Installation

Install the project with:

```bash
pip install -e .
```

For development and testing:

```bash
pip install -e ".[dev]"
```

---

# Running the Project

## Run the reconciliation pipeline

```bash
python scripts/run_pipeline.py
```

## Run the full evaluation

```bash
python scripts/evaluate.py
```

This generates:

```text
outputs/reports/metrics.json
outputs/reports/exceptions.json
outputs/decisions/decisions.json
outputs/audit/audit.json
```

## Run the demo

```bash
python scripts/run_demo.py
```

## Generate synthetic data

```bash
python scripts/generate_data.py
```

## Run all tests

```bash
python -m pytest tests/ -v
```

---

# Technology Stack

| Technology      | Purpose                    |
| --------------- | -------------------------- |
| Python          | Core implementation        |
| Pydantic        | Data models and validation |
| RapidFuzz       | Fuzzy matching             |
| PyYAML          | Configuration              |
| Python-dateutil | Date handling              |
| Rich            | Terminal reporting         |
| Streamlit       | Dashboard                  |
| Pytest          | Automated testing          |
| OpenAI / Gemini | Live AI verification       |

---

# Limitations

The current pipeline processes records in memory.

It is designed around the included buildathon-scale workload.

For larger datasets, candidate generation could be distributed.

Possible future infrastructure includes:

```text
Apache Spark
Kafka
Distributed processing
Partitioned pipelines
```

Financial tolerances are intentionally conservative.

Cases outside those limits are routed for human review.

The benchmark uses a mock AI provider for reproducibility.

Live AI mode depends on external API availability.

---

# Final Principle

The system separates matching, AI reasoning, and financial control.

> **AI proposes. Deterministic controls decide.**
