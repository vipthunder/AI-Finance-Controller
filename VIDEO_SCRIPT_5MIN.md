# 🎬 5-Minute Video Pitch & Demonstration Script
**Project:** AI Finance Controller — Multi-Source Financial Reconciliation Engine  
**Track:** Track 04 (Razorpay Buildathon)  
**Target Duration:** Exactly 5:00 (300 seconds)  
**Recommended Pacing:** 130–140 words per minute (~670 words total spoken text)

---

## ⏱️ Timeline & Storyboard Matrix

| Timestamp | Visual Source | On-Screen Action | Spoken Topic / Key Focus |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:45** (45s) | Slide 1 / Title Card | Title + 3 disparate feeds graphic (ERP, Bank, Invoice) | The Enterprise Crisis: Messy statements, wire fees, duplicate clones, and why unconstrained LLMs fail |
| **0:45 – 1:45** (60s) | Slide 2 / Architecture | System Architecture Flowchart | Core Innovation: Multi-signal blocking, tiered matching, and *"AI proposes, deterministic controls decide"* |
| **1:45 – 3:00** (75s) | Terminal (Wide) | Run `python scripts/run_demo.py` (Steps 1–4) | Live Pipeline Demo: 100% precision, 60/60 transactions, $182,008.84 canonical volume reconciled |
| **3:00 – 4:00** (60s) | Terminal (Wide) | Scroll to Step 7 (Red table) & Step 5 (Exception Queue) | The "Hero Moment": Deterministic validator blocks AI-approved duplicate clone; zero silent drops |
| **4:00 – 4:45** (45s) | Terminal (Wide) | Run `python -m pytest tests/ -q` | 171-Test Verification Pyramid: AST boundary isolation, invariant tests, reproducibility |
| **4:45 – 5:00** (15s) | Slide 3 / Camera | Final takeaway & GitHub link | Closing Summary & Business Impact |

---

## 🎙️ Word-for-Word Teleprompter Script

### [0:00 – 0:45] Block 1: Hook & The Problem
> **[VISUAL: Slide 1 — Project Title & Problem Graphic]**
>
> *"Every day, high-growth fintech platforms and enterprises process millions of transactions across general ledgers, external bank feeds, and accounts payable invoices.*
>
> *In the real world, this financial data is notoriously corrupted.*
> *Counterparty narratives are noisy—like `'AWS*US-EAST-1'` versus `'AMAZON WEB SERVICES INC'`. Intermediary wire fees silently deduct twenty dollars off a ten-thousand-dollar settlement. Multi-day banking settlement lags break temporal alignment, and duplicate bank retry debits create phantom records.*
>
> *Legacy heuristic rulebooks are too rigid, generating mountains of false rejections. But letting unconstrained AI or LLMs match ledgers is legally indefensible—LLMs hallucinate, and financial accounting demands absolute mathematical certainty.*
>
> *This is the **AI Finance Controller**: an auditable multi-source reconciliation engine built on a non-negotiable principle: **AI proposes, but deterministic financial controls decide.**"*

---

### [0:45 – 1:45] Block 2: Architecture & Core Philosophy
> **[VISUAL: Slide 2 — System Architecture Flowchart]**
>
> *"Here is how our architecture guarantees both semantic intelligence and bank-grade safety:*
>
> *First, raw records enter our **Canonical Normalizer**, which strips corporate legal suffixes and maps vendor aliases.*
>
> *Next, our **Multi-Signal Candidate Generator** prunes the search space using reference keys, canonical entities, and temporal proximity.*
>
> *Then, candidates pass through a tiered resolution funnel:*
> *One: Exact matches resolve instantly in O(1) hash time.*
> *Two: High-confidence fuzzy matches above 0.85 resolve automatically.*
> *Three: The ambiguous mid-band—composite scores between 0.50 and 0.85—is routed to our **AI Verifier** for structured counterparty reasoning.*
>
> *Crucially: **No AI proposal is ever committed directly.** Every candidate must independently pass our **Authoritative Deterministic Validator**, strictly verifying currency parity, date windows, duplicate locks, and wire fee tolerances. If matches collide, a global competition policy supersedes the losing match. Nothing is ever silently dropped."*

---

### [1:45 – 3:00] Block 3: Live Pipeline Execution & Benchmark Scorecard
> **[VISUAL: Switch to Terminal (Full Screen, Wide, Font Size 15px)]**  
> **[ACTION: Type `python scripts/run_demo.py` and hit Enter]**
>
> *"Let's see the engine in action.*
> *Here we run `python scripts/run_demo.py` on a multi-source financial benchmark of sixty canonical business transactions and 179 records across Ledger, Bank, and Invoice.*
>
> *In under one hundred milliseconds, the entire pipeline executes.*
>
> **[ACTION: Scroll to the colored Rich scorecard table; point cursor at Precision & Recall]**
>
> *Let's look at the authoritative scorecard evaluated against ground truth:*
> *• **Relationship Precision: 100.00%** with zero false positives.*
> *• **Relationship Recall: 100.00%**—all 172 ground-truth relationships resolved.*
> *• **Transaction Level:** 60 out of 60 canonical business transactions are fully reconciled.*
> *• **Financial Accounting:** Exactly $182,008.84 of underlying transaction volume is reconciled with zero multi-counting across sources and zero dollars of capital misallocated.*
> *• **Active AI Contribution:** Structured AI verification rescued twenty-one ambiguous transactions that heuristics alone could never have solved."*

---

### [3:00 – 4:00] Block 4: The Hero Moment — Deterministic Guardrail Overrides AI
> **[VISUAL: Scroll down to Step 7 (Red table: Live Failure Demonstration)]**
>
> *"Now, here is the most technically defensible feature of our system: **watch what happens when AI is wrong.***
>
> **[ACTION: Zoom in or highlight the red table: `AI Proposed MATCH → Deterministic Validator Overrode & Blocked`]**
>
> *In this scenario, a bank record contained a duplicate retry clone. Because the counterparty names matched semantically, the AI verifier approved the pairing with high confidence.*
>
> *In an unconstrained AI system, this would cause a catastrophic double-reconciliation. But here, our **Deterministic Safety Validator intercepted the AI match and blocked it**, identifying it as an intra-source duplicate.*
>
> **[ACTION: Scroll up slightly to Step 5: Human Escalation Queue]**
>
> *The blocked candidate was deterministically routed into our **Human Escalation Queue** with an explicit reason code, financial exposure, and suggested remediation.*
>
> *Every single input record reaches an explicit terminal state. There are **zero silent drops**, and every single decision is logged to an immutable append-only audit trail."*

---

### [4:00 – 4:45] Block 5: The 171-Test Verification Pyramid
> **[VISUAL: Terminal]**  
> **[ACTION: Type `python -m pytest tests/ -q` and hit Enter]**
>
> *"To prove production readiness, we built an exhaustive **171-test automated suite** that runs in just ten seconds:*
>
> **[ACTION: Let the test progress bar run to 100% and show `171 passed`]**
>
> *• **AST Import Boundary Isolation:** Verifies production code never touches or leaks test fixtures.*
> *• **Adversarial Set-Theory Fixtures:** Mathematically tests TP, FP, and FN edge cases.*
> *• **Decision Invariant Tests:** Guarantees every AI proposal is fully accounted for.*
> *• **Byte-for-Byte Reproducibility:** Guarantees deterministic metrics across benchmark seeds."*

---

### [4:45 – 5:00] Block 6: Conclusion & Takeaway
> **[VISUAL: Slide 3 / Webcam / GitHub Repo]**
>
> *"With sub-hundred-millisecond batch throughput, zero financial capital at risk, and full support for live Gemini or OpenAI models, the AI Finance Controller bridges modern generative intelligence with the uncompromising rigor of enterprise financial accounting.*
>
> *Thank you!"*

---

## ⌨️ Terminal Commands Cheat Sheet

Copy-paste these directly during your demo:

```powershell
# 1. Clear terminal
cls

# 2. Run Live Demo (Tables, Scorecard, and Live Failure Demo)
python scripts/run_demo.py

# 3. Run Full Automated Test Suite (171 Tests)
python -m pytest tests/ -q

# 4. View Generated Output Files
Get-ChildItem outputs/reports/
```

---

## 🎯 Key Numbers to Emphasize on Screen

| Metric | Target Value | Why It Matters |
| :--- | :---: | :--- |
| **Relationship Precision** | `100.00%` | Zero false matches committed to the general ledger |
| **Relationship Recall** | `100.00%` | All 172 eligible relationships discovered |
| **Fully Reconciled Tx** | `60 / 60 (100%)` | Every single multi-source transaction resolved |
| **Canonical Volume** | `$182,008.84` | Canonical deduplication prevents 3x triple-counting |
| **Capital at Risk** | `$0.00` | Zero incorrect financial allocations |
| **Silent Drops** | `0` | Every record maps to a verified terminal decision |
| **Active AI Matches** | `21` | Ambiguous transactions successfully rescued by AI |
| **Test Suite** | `171 passed` | Exhaustive AST, invariant, and regression tests |

---

## 🎥 Recording & Audio Setup Guide

1. **Terminal Appearance:**
   * Window Width: At least **130 columns** (prevents Rich table borders from wrapping).
   * Font: **Cascadia Code**, **JetBrains Mono**, or **Fira Code** at **15px–16px**.
   * Color Scheme: Dark theme (*Dracula*, *One Half Dark*, or *Campbell*).
2. **Screen Recording:**
   * Resolution: 1920x1080 (1080p), 60 FPS.
   * Tool: **OBS Studio** (Free) or **Screen Studio** / **CapCut**.
3. **Voiceover Polish:**
   * Record in a quiet room with your microphone 6 inches from your mouth.
   * Run the audio through **Adobe Podcast AI Enhance** (free web tool at `podcast.adobe.com/enhance`) to eliminate background noise and add broadcast warmth.
