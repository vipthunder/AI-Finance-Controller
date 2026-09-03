from __future__ import annotations
import datetime as dt
import pytest

from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.decisions import Decision
from src.schemas.enums import SourceType, MatchStage, ResolutionStatus, ExceptionReason
from src.schemas.validation import ValidationResult
from src.schemas.ground_truth import GroundTruthStore, GroundTruthTransaction
from src.schemas.audit import AuditTrail
from src.matching.candidate_generator import CandidateGenerator
from src.matching.exact_matcher import ExactMatcher
from src.matching.fuzzy_matcher import FuzzyScorer
from src.verification.ai_verifier import AIVerifier
from src.validation.deterministic_validator import DeterministicValidator
from src.controller.decision_controller import DecisionController
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.data_generation.generator import SyntheticDataGenerator
from src.evaluation.evaluator import Evaluator


def make_candidate_pair(
    r1: Record,
    r2: Record,
    score: float = 1.0,
    stage: MatchStage = MatchStage.EXACT,
) -> CandidatePair:
    amt_diff = abs(r1.amount - r2.amount)
    date_diff = abs((r1.date - r2.date).days)
    fs = FeatureScores(
        name_similarity=score,
        amount_proximity=1.0,
        date_proximity=1.0,
        composite_score=score,
        amount_diff=amt_diff,
        date_diff_days=date_diff,
    )
    return CandidatePair(
        record_a=r1,
        record_b=r2,
        score=score,
        feature_scores=fs,
        matched_on=["RULE"],
        stage=stage,
    )


def test_scenario_01_exact_match():
    """Scenario 1: Exact match with matching reference and exact attributes."""
    r1 = Record(id="L-101", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="ACME CORP", reference_id="REF-101")
    r2 = Record(id="B-101", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="ACME CORP", reference_id="REF-101")

    matcher = ExactMatcher()
    candidates, _ = matcher.match([r1, r2])
    assert len(candidates) == 1
    assert candidates[0].stage == MatchStage.EXACT

    validator = DeterministicValidator()
    val_res = validator.validate(candidates[0], set())
    assert val_res.is_valid

    controller = DecisionController()
    d1, d2 = controller.commit_match(candidates[0], val_res)
    assert d1.status == ResolutionStatus.RESOLVED
    assert d1.stage_resolved == "EXACT"


def test_scenario_02_fuzzy_match():
    """Scenario 2: Fuzzy match with slight name variation scoring >= 0.85."""
    r1 = Record(id="L-102", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=750.0, currency="USD", counterparty="AMAZON WEB SERVICES")
    r2 = Record(id="B-102", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=750.0, currency="USD", counterparty="AMAZON WEB SERVICES INC")

    gen = CandidateGenerator()
    pairs = gen.generate([r1, r2])
    assert len(pairs) == 1

    scorer = FuzzyScorer()
    scored = scorer.score_candidates(pairs)
    assert scored[0].score >= 0.85
    scored[0].stage = MatchStage.FUZZY_DIRECT

    val_res = DeterministicValidator().validate(scored[0], set())
    assert val_res.is_valid

    d1, d2 = DecisionController().commit_match(scored[0], val_res)
    assert d1.status == ResolutionStatus.RESOLVED
    assert d1.stage_resolved == "FUZZY_DIRECT"


def test_scenario_03_ai_match():
    """Scenario 3: AI match with significant vendor alias in mid-band [0.50, 0.85)."""
    r1 = Record(id="L-103", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=1200.0, currency="USD", counterparty="GOOGLE CLOUD")
    r2 = Record(id="B-103", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=1200.0, currency="USD", counterparty="GCP")

    gen = CandidateGenerator()
    pairs = gen.generate([r1, r2])
    assert len(pairs) == 1

    scored = FuzzyScorer().score_candidates(pairs)
    assert 0.50 <= scored[0].score < 0.85

    verified, rejected = AIVerifier().verify_candidates(scored)
    assert len(verified) == 1
    assert verified[0].stage == MatchStage.AI_VERIFIED

    val_res = DeterministicValidator().validate(verified[0], set())
    assert val_res.is_valid


def test_scenario_04_ai_accepted_validator_rejected():
    """Scenario 4: AI accepted match where amount exceeds tolerance -> rejected by validator."""
    r1 = Record(id="L-104", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="GOOGLE CLOUD")
    r2 = Record(id="B-104", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=150.0, currency="USD", counterparty="GCP")

    pair = make_candidate_pair(r1, r2, score=0.75, stage=MatchStage.AI_VERIFIED)
    validator = DeterministicValidator()
    val_res = validator.validate(pair, set())

    assert not val_res.is_valid
    assert any("exceeds abs tolerance" in c or "exceeds pct tolerance" in c for c in val_res.failed_checks)

    controller = DecisionController()
    d1, d2 = controller.record_validation_failed(pair, val_res)
    assert d1.status == ResolutionStatus.EXCEPTION
    assert d1.exception_reason == ExceptionReason.VALIDATION_FAILED


def test_scenario_05_ai_accepted_superseded():
    """Scenario 5: AI accepts candidate, but higher-ranking proposal already claimed the source slot."""
    r_l = Record(id="L-105", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=200.0, currency="USD", counterparty="STRIPE")
    r_b_exact = Record(id="B-105", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=200.0, currency="USD", counterparty="STRIPE", reference_id="REF-105")
    r_b_alt = Record(id="B-105-ALT", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=200.0, currency="USD", counterparty="STRIPE PAYMENTS")

    pair_exact = make_candidate_pair(r_l, r_b_exact, score=1.0, stage=MatchStage.EXACT)
    pair_ai = make_candidate_pair(r_l, r_b_alt, score=0.80, stage=MatchStage.AI_VERIFIED)

    controller = DecisionController()
    controller.commit_match(pair_exact, ValidationResult(is_valid=True))

    d1, d2 = controller.record_superseded(
        pair_ai,
        r_b_exact.summary_key(),
        "Slot for BANK already committed to higher-ranking exact match",
        winning_pair=pair_exact,
    )
    assert d1.status == ResolutionStatus.SUPERSEDED
    assert d1.metadata["winning_candidate"] == pair_exact.pair_key


def test_scenario_06_ai_accepted_committed():
    """Scenario 6: Legitimate AI verified candidate wins competition and commits as final match."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    assert result.ai_committed_count > 0, "Pipeline must commit legitimate AI-verified matches"
    ai_decisions = [d for d in result.decisions if d.stage_resolved == "AI_VERIFIED" and d.status == ResolutionStatus.RESOLVED]
    assert len(ai_decisions) > 0


def test_scenario_07_duplicate_conflict():
    """Scenario 7: Duplicate clone is blocked by validator and routed to LIKELY_DUPLICATE exception."""
    r_orig = Record(id="B-107", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=300.0, currency="USD", counterparty="TEST")
    r_clone = Record(id="B-107-DUP1", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=300.0, currency="USD", counterparty="TEST")
    r_ledger = Record(id="L-107", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=300.0, currency="USD", counterparty="TEST")

    dup_map = {r_clone.summary_key(): r_orig.summary_key()}
    pair = make_candidate_pair(r_ledger, r_clone, score=0.90, stage=MatchStage.FUZZY_DIRECT)

    validator = DeterministicValidator()
    val_res = validator.validate(pair, set(), duplicate_map=dup_map)
    assert not val_res.is_valid
    assert any("Intra-source duplicate" in c for c in val_res.failed_checks)


def test_scenario_08_unresolved_exception():
    """Scenario 8: Record with zero viable candidates is routed to exception queue with actionable reason."""
    raw_ledger = [{"ledger_id": "L-108", "posting_date": "2024-01-01", "amount": "9999.99", "currency": "USD", "vendor_account": "UNIQUE VENDOR"}]
    raw_bank = [{"transaction_id": "B-108", "value_date": "2024-06-01", "settled_amount": "10.00", "currency_code": "USD", "statement_narrative": "DIFFERENT VENDOR"}]

    pipeline = ReconciliationPipeline()
    result = pipeline.run(raw_ledger, raw_bank, [])

    orphan_dec = next(d for d in result.decisions if "L-108" in d.record_id)
    assert orphan_dec.status == ResolutionStatus.EXCEPTION
    assert orphan_dec.exception_reason in (ExceptionReason.NO_CANDIDATE, ExceptionReason.LOW_CONFIDENCE, ExceptionReason.AMBIGUOUS)


def test_scenario_09_currency_mismatch():
    """Scenario 9: Currency mismatch fails deterministic validator with critical error."""
    r1 = Record(id="L-109", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="VENDOR")
    r2 = Record(id="B-109", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="EUR", counterparty="VENDOR")

    pair = make_candidate_pair(r1, r2, score=1.0, stage=MatchStage.EXACT)
    val_res = DeterministicValidator().validate(pair, set())
    assert not val_res.is_valid
    assert any("Currency mismatch" in c for c in val_res.failed_checks)


def test_scenario_10_candidate_generation_failure():
    """Scenario 10: Candidate generator records miss reasons when blocking predicates reject pairs."""
    gen = CandidateGenerator()
    r1 = Record(id="L-110", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="ALPHA")
    r2 = Record(id="B-110", source=SourceType.BANK, date=dt.date(2024, 5, 1), amount=100.0, currency="USD", counterparty="BETA")  # 120 days apart

    pairs = gen.generate([r1, r2])
    assert len(pairs) == 0
    miss_reasons = gen.get_miss_reasons(r1.summary_key())
    assert len(miss_reasons) > 0
    assert any("Date lag" in m or "Amount diff" in m for m in miss_reasons)


def test_scenario_11_competing_proposals_ranking():
    """Scenario 11: Multiple valid competing proposals for the same source slot are resolved by global rank."""
    r_l = Record(id="L-111", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="ACME")
    r_b1 = Record(id="B-111A", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="ACME HIGH")
    r_b2 = Record(id="B-111B", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="ACME MID")

    p1 = make_candidate_pair(r_l, r_b1, score=0.92, stage=MatchStage.FUZZY_DIRECT)
    p2 = make_candidate_pair(r_l, r_b2, score=0.88, stage=MatchStage.FUZZY_DIRECT)

    proposals = [p2, p1]
    proposals.sort(key=lambda p: (1 if p.stage == MatchStage.EXACT else 0, p.score), reverse=True)

    committed = {}
    superseded = []
    controller = DecisionController()

    for p in proposals:
        ka = p.record_a.summary_key()
        kb = p.record_b.summary_key()
        sa = p.record_a.source.value
        sb = p.record_b.source.value

        slots_a = committed.setdefault(ka, {})
        slots_b = committed.setdefault(kb, {})

        if sb in slots_a or sa in slots_b:
            win_k, win_p = slots_a.get(sb) or slots_b.get(sa)
            d1, d2 = controller.record_superseded(p, win_k, "Slot collision", winning_pair=win_p)
            superseded.append((p, win_k))
        else:
            slots_a[sb] = (kb, p)
            slots_b[sa] = (ka, p)
            controller.commit_match(p, ValidationResult(is_valid=True))

    assert len(superseded) == 1
    assert superseded[0][0].record_b.summary_key() == r_b2.summary_key()
    assert superseded[0][1] == r_b1.summary_key()


def test_scenario_12_partial_reconciliation():
    """Scenario 12: Transaction with 2 of 3 sources resolved is reported as partially reconciled, NOT fully reconciled."""
    gt_store = GroundTruthStore()
    tx = GroundTruthTransaction(
        gt_id="GT-112",
        date=dt.date(2024, 1, 1),
        base_amount=400.0,
        base_currency="USD",
        canonical_counterparty="ACME",
        category="STANDARD",
        description="",
        source_record_ids={"LEDGER": ["L-112"], "BANK": ["B-112"], "INVOICE": ["I-112"]},
    )
    gt_store.add_transaction(tx)

    records = [
        Record(id="L-112", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=400.0, currency="USD", counterparty="ACME"),
        Record(id="B-112", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=400.0, currency="USD", counterparty="ACME"),
        Record(id="I-112", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=400.0, currency="USD", counterparty="ACME"),
    ]

    # Only L-112 and B-112 are resolved; I-112 is in exception
    decisions = [
        Decision(record_id="LEDGER:L-112", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-112"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-112", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-112"], confidence=1.0, rationale=""),
        Decision(record_id="INVOICE:I-112", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(decisions=decisions, audit_trail=AuditTrail(), processing_time_ms=10.0, total_records=3, records=records)

    assert metrics.canonical_transactions == 1
    assert metrics.fully_reconciled_transactions == 0
    assert metrics.partially_reconciled_transactions == 1
    assert metrics.unresolved_transactions == 0
    assert metrics.fully_reconciled_tx_rate == 0.0
    assert metrics.partial_transaction_coverage == 1.0
    assert metrics.fully_reconciled_value == 0.0
    assert metrics.partially_reconciled_value == 400.0
