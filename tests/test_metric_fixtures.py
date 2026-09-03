from __future__ import annotations
import datetime as dt
import pytest

from src.schemas.records import Record
from src.schemas.candidates import CandidatePair
from src.schemas.decisions import Decision
from src.schemas.enums import SourceType, TransactionDirection, ResolutionStatus, ExceptionReason, MatchStage
from src.schemas.validation import ValidationResult
from src.schemas.ground_truth import GroundTruthStore, GroundTruthTransaction
from src.schemas.audit import AuditTrail
from src.evaluation.evaluator import Evaluator
from src.evaluation.metric_definitions import METRIC_DEFINITIONS


def test_metric_definitions_registry_completeness():
    """Verify that all 5 metric levels have complete and well-formed definitions."""
    required_levels = {"RECORD", "TRANSACTION", "RELATIONSHIP", "AI_PROPOSAL", "FINANCIAL"}
    levels_found = {m.level for m in METRIC_DEFINITIONS.values()}
    assert required_levels.issubset(levels_found)
    for name, m in METRIC_DEFINITIONS.items():
        assert m.name == name
        assert m.description
        assert m.numerator
        assert m.unit in ("count", "ratio", "percentage", "currency_usd", "ms")
        assert m.formula


def test_fixture_relationship_precision_recall_f1():
    """Deterministic fixture test with known TP=8, FP=2, FN=2.
    Expected: Precision = 8/10 = 0.8, Recall = 8/10 = 0.8, F1 = 0.8.
    """
    gt_store = GroundTruthStore()

    # Create 10 ground truth transactions (GT-01 to GT-10), each with 1 relationship: L <-> B
    for i in range(1, 11):
        gt_id = f"GT-{i:02d}"
        tx = GroundTruthTransaction(
            gt_id=gt_id,
            date=dt.date(2024, 1, 1),
            base_amount=100.0,
            base_currency="USD",
            canonical_counterparty="TEST_CORP",
            category="TEST",
            description="Fixture tx",
            source_record_ids={"LEDGER": [f"L-{i:02d}"], "BANK": [f"B-{i:02d}"]},
        )
        gt_store.add_transaction(tx)

    evaluator = Evaluator(gt_store)

    # Decisions:
    # 8 True Positives: L-01 to L-08 correctly matched with B-01 to B-08
    # 2 False Positives: L-11 matched with B-11, L-12 matched with B-12 (not in GT)
    # 2 False Negatives: L-09 and B-09, L-10 and B-10 unmatched (left in exceptions)
    decisions = []
    records = []

    # 8 TPs
    for i in range(1, 9):
        lid = f"LEDGER:L-{i:02d}"
        bid = f"BANK:B-{i:02d}"
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(
            record_id=lid,
            status=ResolutionStatus.RESOLVED,
            stage_resolved="EXACT",
            matched_with_ids=[bid],
            confidence=1.0,
            rationale="TP match",
        ))
        decisions.append(Decision(
            record_id=bid,
            status=ResolutionStatus.RESOLVED,
            stage_resolved="EXACT",
            matched_with_ids=[lid],
            confidence=1.0,
            rationale="TP match",
        ))

    # 2 FPs (incorrect matches not in GT)
    for i in (11, 12):
        lid = f"LEDGER:L-{i:02d}"
        bid = f"BANK:B-{i:02d}"
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(
            record_id=lid,
            status=ResolutionStatus.RESOLVED,
            stage_resolved="EXACT",
            matched_with_ids=[bid],
            confidence=1.0,
            rationale="FP match",
        ))
        decisions.append(Decision(
            record_id=bid,
            status=ResolutionStatus.RESOLVED,
            stage_resolved="EXACT",
            matched_with_ids=[lid],
            confidence=1.0,
            rationale="FP match",
        ))

    # 2 FNs (records in GT 09 and 10 left as exceptions)
    for i in (9, 10):
        lid = f"LEDGER:L-{i:02d}"
        bid = f"BANK:B-{i:02d}"
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(
            record_id=lid,
            status=ResolutionStatus.EXCEPTION,
            exception_reason=ExceptionReason.NO_CANDIDATE,
            confidence=0.0,
            rationale="Unmatched FN",
        ))
        decisions.append(Decision(
            record_id=bid,
            status=ResolutionStatus.EXCEPTION,
            exception_reason=ExceptionReason.NO_CANDIDATE,
            confidence=0.0,
            rationale="Unmatched FN",
        ))

    metrics = evaluator.evaluate(
        decisions=decisions,
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=len(records),
        records=records,
    )

    assert metrics.true_positives == 8
    assert metrics.false_positives == 2
    assert metrics.false_negatives == 2
    assert metrics.proposed_pairs_count == 10
    assert metrics.total_ground_truth_pairs == 10

    assert pytest.approx(metrics.precision, 0.0001) == 0.8
    assert pytest.approx(metrics.recall, 0.0001) == 0.8
    assert pytest.approx(metrics.f1_score, 0.0001) == 0.8


def test_fixture_financial_level_separation():
    """Fixture verifying exact financial level separation:
    - 3 transactions with known values ($1,000, $2,000, $3,000) = $6,000 total canonical value.
    - Tx 1 ($1,000): fully reconciled.
    - Tx 2 ($2,000): partially reconciled (2 of 3 records resolved).
    - Tx 3 ($3,000): unresolved (all records in exception).
    """
    gt_store = GroundTruthStore()
    
    # Tx 1: $1,000 fully reconciled (L-01, B-01, I-01)
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-01", date=dt.date(2024, 1, 1), base_amount=1000.0, base_currency="USD",
        canonical_counterparty="C1", category="TEST", description="",
        source_record_ids={"LEDGER": ["L-01"], "BANK": ["B-01"], "INVOICE": ["I-01"]},
    ))
    # Tx 2: $2,000 partially reconciled (L-02, B-02 resolved, I-02 exception)
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-02", date=dt.date(2024, 1, 1), base_amount=2000.0, base_currency="USD",
        canonical_counterparty="C2", category="TEST", description="",
        source_record_ids={"LEDGER": ["L-02"], "BANK": ["B-02"], "INVOICE": ["I-02"]},
    ))
    # Tx 3: $3,000 unresolved (L-03, B-03, I-03 all exceptions)
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-03", date=dt.date(2024, 1, 1), base_amount=3000.0, base_currency="USD",
        canonical_counterparty="C3", category="TEST", description="",
        source_record_ids={"LEDGER": ["L-03"], "BANK": ["B-03"], "INVOICE": ["I-03"]},
    ))

    records = [
        # Tx 1
        Record(id="L-01", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=1000.0, currency="USD", counterparty="C1"),
        Record(id="B-01", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=1000.0, currency="USD", counterparty="C1"),
        Record(id="I-01", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=1000.0, currency="USD", counterparty="C1"),
        # Tx 2
        Record(id="L-02", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=2000.0, currency="USD", counterparty="C2"),
        Record(id="B-02", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=2000.0, currency="USD", counterparty="C2"),
        Record(id="I-02", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=2000.0, currency="USD", counterparty="C2"),
        # Tx 3
        Record(id="L-03", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=3000.0, currency="USD", counterparty="C3"),
        Record(id="B-03", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=3000.0, currency="USD", counterparty="C3"),
        Record(id="I-03", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=3000.0, currency="USD", counterparty="C3"),
    ]

    decisions = [
        # Tx 1: All 3 resolved
        Decision(record_id="LEDGER:L-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-01", "INVOICE:I-01"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01", "INVOICE:I-01"], confidence=1.0, rationale=""),
        Decision(record_id="INVOICE:I-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01", "BANK:B-01"], confidence=1.0, rationale=""),
        # Tx 2: 2 resolved, 1 exception
        Decision(record_id="LEDGER:L-02", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-02"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-02", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-02"], confidence=1.0, rationale=""),
        Decision(record_id="INVOICE:I-02", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
        # Tx 3: All 3 exceptions
        Decision(record_id="LEDGER:L-03", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
        Decision(record_id="BANK:B-03", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
        Decision(record_id="INVOICE:I-03", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(
        decisions=decisions,
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=len(records),
        records=records,
    )

    assert metrics.canonical_transactions == 3
    assert metrics.fully_reconciled_transactions == 1
    assert metrics.partially_reconciled_transactions == 1
    assert metrics.unresolved_transactions == 1
    assert pytest.approx(metrics.fully_reconciled_tx_rate, 0.001) == 1 / 3
    assert pytest.approx(metrics.partial_transaction_coverage, 0.001) == 2 / 3

    assert metrics.total_canonical_value == 6000.0
    assert metrics.fully_reconciled_value == 1000.0
    assert metrics.partially_reconciled_value == 2000.0
    assert pytest.approx(metrics.full_value_reconciliation_rate, 0.001) == 1000.0 / 6000.0


def test_adversarial_fixture_1_tp8_fp1_fn2():
    """Adversarial Fixture 1:
    Ground truth: 10 relationships
    Prediction: 8 correct, 1 incorrect
    Expected: TP = 8, FP = 1, FN = 2
    """
    gt_store = GroundTruthStore()
    for i in range(1, 11):
        gt_store.add_transaction(GroundTruthTransaction(
            gt_id=f"GT-{i:02d}", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
            canonical_counterparty="TEST", category="TEST", description="",
            source_record_ids={"LEDGER": [f"L-{i:02d}"], "BANK": [f"B-{i:02d}"]},
        ))

    evaluator = Evaluator(gt_store)
    records = []
    decisions = []

    # 8 correct predictions
    for i in range(1, 9):
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(record_id=f"LEDGER:L-{i:02d}", status=ResolutionStatus.RESOLVED, stage_resolved="EXACT", matched_with_ids=[f"BANK:B-{i:02d}"], confidence=1.0, rationale=""))
        decisions.append(Decision(record_id=f"BANK:B-{i:02d}", status=ResolutionStatus.RESOLVED, stage_resolved="EXACT", matched_with_ids=[f"LEDGER:L-{i:02d}"], confidence=1.0, rationale=""))

    # 1 incorrect prediction (L-99 with B-99, not in GT)
    records.append(Record(id="L-99", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
    records.append(Record(id="B-99", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
    decisions.append(Decision(record_id="LEDGER:L-99", status=ResolutionStatus.RESOLVED, stage_resolved="EXACT", matched_with_ids=["BANK:B-99"], confidence=1.0, rationale=""))
    decisions.append(Decision(record_id="BANK:B-99", status=ResolutionStatus.RESOLVED, stage_resolved="EXACT", matched_with_ids=["LEDGER:L-99"], confidence=1.0, rationale=""))

    # 2 remaining GT records left unresolved (FN)
    for i in (9, 10):
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(record_id=f"LEDGER:L-{i:02d}", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""))
        decisions.append(Decision(record_id=f"BANK:B-{i:02d}", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""))

    metrics = evaluator.evaluate(decisions=decisions, audit_trail=AuditTrail(), processing_time_ms=10.0, total_records=len(records), records=records)

    assert metrics.total_ground_truth_pairs == 10
    assert metrics.proposed_pairs_count == 9
    assert metrics.true_positives == 8
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 2
    assert pytest.approx(metrics.precision, 0.001) == 8 / 9
    assert pytest.approx(metrics.recall, 0.001) == 8 / 10


def test_adversarial_fixture_2_tp5_fp0_fn0():
    """Adversarial Fixture 2:
    Ground truth: 5
    Prediction: 5 (all correct)
    Expected: TP = 5, FP = 0, FN = 0
    """
    gt_store = GroundTruthStore()
    records = []
    decisions = []
    for i in range(1, 6):
        gt_store.add_transaction(GroundTruthTransaction(
            gt_id=f"GT-{i:02d}", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
            canonical_counterparty="TEST", category="TEST", description="",
            source_record_ids={"LEDGER": [f"L-{i:02d}"], "BANK": [f"B-{i:02d}"]},
        ))
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(record_id=f"LEDGER:L-{i:02d}", status=ResolutionStatus.RESOLVED, stage_resolved="EXACT", matched_with_ids=[f"BANK:B-{i:02d}"], confidence=1.0, rationale=""))
        decisions.append(Decision(record_id=f"BANK:B-{i:02d}", status=ResolutionStatus.RESOLVED, stage_resolved="EXACT", matched_with_ids=[f"LEDGER:L-{i:02d}"], confidence=1.0, rationale=""))

    metrics = Evaluator(gt_store).evaluate(decisions=decisions, audit_trail=AuditTrail(), processing_time_ms=10.0, total_records=len(records), records=records)

    assert metrics.total_ground_truth_pairs == 5
    assert metrics.proposed_pairs_count == 5
    assert metrics.true_positives == 5
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1_score == 1.0


def test_adversarial_fixture_3_tp0_fp0_fn5():
    """Adversarial Fixture 3:
    Ground truth: 5
    Prediction: 0
    Expected: TP = 0, FP = 0, FN = 5, Recall = 0
    """
    gt_store = GroundTruthStore()
    records = []
    decisions = []
    for i in range(1, 6):
        gt_store.add_transaction(GroundTruthTransaction(
            gt_id=f"GT-{i:02d}", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
            canonical_counterparty="TEST", category="TEST", description="",
            source_record_ids={"LEDGER": [f"L-{i:02d}"], "BANK": [f"B-{i:02d}"]},
        ))
        records.append(Record(id=f"L-{i:02d}", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        records.append(Record(id=f"B-{i:02d}", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"))
        decisions.append(Decision(record_id=f"LEDGER:L-{i:02d}", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""))
        decisions.append(Decision(record_id=f"BANK:B-{i:02d}", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""))

    metrics = Evaluator(gt_store).evaluate(decisions=decisions, audit_trail=AuditTrail(), processing_time_ms=10.0, total_records=len(records), records=records)

    assert metrics.total_ground_truth_pairs == 5
    assert metrics.proposed_pairs_count == 0
    assert metrics.true_positives == 0
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 5
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1_score == 0.0


def test_adversarial_fixture_4_equal_counts_wrong_relationships():
    """Adversarial Fixture 4 — Equal Counts But Wrong Relationships (Mandatory):
    Ground truth: A-B, B-C (2 relationships)
    Prediction: A-C, B-D (2 relationships)
    Expected: TP = 0, FP = 2, FN = 2
    Proves the evaluator does not confuse equal counts with correct reconciliation.
    """
    gt_store = GroundTruthStore()
    # Transaction 1 has A (LEDGER:A), B (BANK:B), and C (INVOICE:C)
    # Ground truth relationships are (A-B) and (B-C)
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-01", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
        canonical_counterparty="TEST", category="TEST", description="",
        source_record_ids={"LEDGER": ["A"], "BANK": ["B"], "INVOICE": ["C"]},
    ))
    # We only consider the pairs A-B and B-C as ground truth for this test
    # By default, GroundTruthStore generates 3 pairs for 3 records: (A-B), (B-C), (A-C).
    # To test strictly 2 ground truth relationships:
    # Let GT have: Tx 1: (L-A, B-B), Tx 2: (B-B2, I-C)
    gt_store_strict = GroundTruthStore()
    gt_store_strict.add_transaction(GroundTruthTransaction(
        gt_id="GT-A_B", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
        canonical_counterparty="TEST", category="TEST", description="",
        source_record_ids={"LEDGER": ["A"], "BANK": ["B"]},
    ))
    gt_store_strict.add_transaction(GroundTruthTransaction(
        gt_id="GT-B_C", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
        canonical_counterparty="TEST", category="TEST", description="",
        source_record_ids={"BANK": ["B_SRC"], "INVOICE": ["C"]},
    ))

    # Ground truth pairs in gt_store_strict are exactly 2:
    # ('BANK:B', 'LEDGER:A') and ('BANK:B_SRC', 'INVOICE:C')
    assert len(gt_store_strict.get_all_ground_truth_pairs()) == 2

    # Prediction proposes 2 completely different relationships:
    # 1. ('INVOICE:C', 'LEDGER:A')  [A-C]
    # 2. ('BANK:B', 'INVOICE:D')     [B-D]
    records = [
        Record(id="A", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"),
        Record(id="B", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"),
        Record(id="B_SRC", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"),
        Record(id="C", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"),
        Record(id="D", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=100.0, currency="USD", counterparty="TEST"),
    ]

    decisions = [
        Decision(record_id="LEDGER:A", status=ResolutionStatus.RESOLVED, stage_resolved="FUZZY_DIRECT", matched_with_ids=["INVOICE:C"], confidence=0.9, rationale="A-C"),
        Decision(record_id="INVOICE:C", status=ResolutionStatus.RESOLVED, stage_resolved="FUZZY_DIRECT", matched_with_ids=["LEDGER:A"], confidence=0.9, rationale="A-C"),
        Decision(record_id="BANK:B", status=ResolutionStatus.RESOLVED, stage_resolved="FUZZY_DIRECT", matched_with_ids=["INVOICE:D"], confidence=0.9, rationale="B-D"),
        Decision(record_id="INVOICE:D", status=ResolutionStatus.RESOLVED, stage_resolved="FUZZY_DIRECT", matched_with_ids=["BANK:B"], confidence=0.9, rationale="B-D"),
        Decision(record_id="BANK:B_SRC", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
    ]

    metrics = Evaluator(gt_store_strict).evaluate(
        decisions=decisions, audit_trail=AuditTrail(), processing_time_ms=10.0, total_records=len(records), records=records
    )

    assert metrics.total_ground_truth_pairs == 2
    assert metrics.proposed_pairs_count == 2
    assert metrics.true_positives == 0, "No relationships match ground truth"
    assert metrics.false_positives == 2, "Both proposed relationships are incorrect"
    assert metrics.false_negatives == 2, "Both ground truth relationships were missed"
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1_score == 0.0


def test_adversarial_candidate_recall_fixture():
    """Section 6 Candidate Recall Fixture:
    10 eligible GT relationships
    8 receive at least one candidate
    Expected: Candidate Recall = 80% (0.80)
    """
    gt_store = GroundTruthStore()
    for i in range(1, 11):
        gt_store.add_transaction(GroundTruthTransaction(
            gt_id=f"GT-{i:02d}", date=dt.date(2024, 1, 1), base_amount=100.0, base_currency="USD",
            canonical_counterparty="TEST", category="TEST", description="",
            source_record_ids={"LEDGER": [f"L-{i:02d}"], "BANK": [f"B-{i:02d}"]},
        ))

    # 8 of 10 ground truth pairs received candidate generation
    raw_candidate_pair_keys = [
        tuple(sorted([f"LEDGER:L-{i:02d}", f"BANK:B-{i:02d}"]))
        for i in range(1, 9)
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(
        decisions=[],
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=20,
        raw_candidate_pair_keys=raw_candidate_pair_keys,
    )

    assert metrics.total_ground_truth_pairs == 10
    assert pytest.approx(metrics.candidate_recall, 0.001) == 0.80
    assert pytest.approx(metrics.raw_candidate_recall, 0.001) == 0.80


def test_cross_metric_invariants_live_benchmark():
    """Section 35: Cross-metric invariants automated verification on benchmark execution."""
    from src.data_generation.generator import SyntheticDataGenerator
    from src.pipeline.reconciliation_pipeline import ReconciliationPipeline

    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)
    evaluator = Evaluator(ds.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # 1. TP + FN = eligible ground-truth relationships
    assert metrics.true_positives + metrics.false_negatives == metrics.total_ground_truth_pairs

    # 2. TP + FP = predicted relationships
    assert metrics.true_positives + metrics.false_positives == metrics.proposed_pairs_count

    # 3. AI Accepted = AI Committed + AI Validation Failed + AI Superseded + AI Failed
    assert metrics.ai_accepted_count == (
        metrics.ai_committed_count
        + metrics.ai_validation_failed_count
        + metrics.ai_superseded_count
        + metrics.ai_failed_count
    )

    # 4. Fully Reconciled + Partial + Unresolved = Canonical Transactions
    assert (
        metrics.fully_reconciled_transactions
        + metrics.partially_reconciled_transactions
        + metrics.unresolved_transactions
    ) == metrics.canonical_transactions

    # 5. Exception Count = Exception List Length
    exception_decisions = [d for d in result.decisions if d.status == ResolutionStatus.EXCEPTION]
    assert metrics.exceptions_count == len(exception_decisions)

    # 6. Silent Drops = 0 and Decision Count = Input Records
    assert metrics.silent_drop_count == 0
    assert len(result.decisions) == len(result.records)


def test_adversarial_transaction_case_a_fully_reconciled():
    """Issue 2 - Case A:
    GT: A-B, B-C. Predicted: A-B, B-C, A-C.
    Expected: FULLY_RECONCILED.
    """
    gt_store = GroundTruthStore()
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-01",
        date=dt.date(2024, 1, 1),
        base_amount=500.0,
        base_currency="USD",
        canonical_counterparty="Vendor",
        category="STANDARD",
        description="",
        source_record_ids={"LEDGER": ["L-01"], "BANK": ["B-01"], "INVOICE": ["I-01"]},
    ))

    records = [
        Record(id="L-01", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="B-01", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="I-01", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
    ]

    decisions = [
        Decision(record_id="LEDGER:L-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-01", "INVOICE:I-01"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01", "INVOICE:I-01"], confidence=1.0, rationale=""),
        Decision(record_id="INVOICE:I-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01", "BANK:B-01"], confidence=1.0, rationale=""),
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(
        decisions=decisions,
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=len(records),
        records=records,
    )

    assert metrics.canonical_transactions == 1
    assert metrics.fully_reconciled_transactions == 1
    assert metrics.partially_reconciled_transactions == 0
    assert metrics.unresolved_transactions == 0
    assert metrics.fully_reconciled_value == 500.0


def test_adversarial_transaction_case_b_partially_reconciled():
    """Issue 2 - Case B:
    GT: A-B, B-C. Predicted: A-B, B-D.
    Expected: PARTIALLY_RECONCILED.
    """
    gt_store = GroundTruthStore()
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-01",
        date=dt.date(2024, 1, 1),
        base_amount=500.0,
        base_currency="USD",
        canonical_counterparty="Vendor",
        category="STANDARD",
        description="",
        source_record_ids={"LEDGER": ["L-01"], "BANK": ["B-01"], "INVOICE": ["I-01"]},
    ))

    records = [
        Record(id="L-01", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="B-01", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="I-01", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="B-D", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Other"),
    ]

    decisions = [
        # L-01 matched with B-01 (correct pair)
        Decision(record_id="LEDGER:L-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-01"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01"], confidence=1.0, rationale=""),
        # I-01 matched with B-D (wrong pair)
        Decision(record_id="INVOICE:I-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-D"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-D", status=ResolutionStatus.RESOLVED, matched_with_ids=["INVOICE:I-01"], confidence=1.0, rationale=""),
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(
        decisions=decisions,
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=len(records),
        records=records,
    )

    assert metrics.canonical_transactions == 1
    assert metrics.fully_reconciled_transactions == 0
    assert metrics.partially_reconciled_transactions == 1
    assert metrics.unresolved_transactions == 0
    assert metrics.partially_reconciled_value == 500.0


def test_adversarial_transaction_case_c_unresolved():
    """Issue 2 - Case C:
    GT: A-B, B-C. Predicted: A-D, B-D.
    Expected: UNRESOLVED.
    """
    gt_store = GroundTruthStore()
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-01",
        date=dt.date(2024, 1, 1),
        base_amount=500.0,
        base_currency="USD",
        canonical_counterparty="Vendor",
        category="STANDARD",
        description="",
        source_record_ids={"LEDGER": ["L-01"], "BANK": ["B-01"], "INVOICE": ["I-01"]},
    ))

    records = [
        Record(id="L-01", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="B-01", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="I-01", source=SourceType.INVOICE, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Vendor"),
        Record(id="B-D", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=500.0, currency="USD", counterparty="Other"),
    ]

    decisions = [
        Decision(record_id="LEDGER:L-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-D"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-D"], confidence=1.0, rationale=""),
        Decision(record_id="INVOICE:I-01", status=ResolutionStatus.EXCEPTION, exception_reason=ExceptionReason.NO_CANDIDATE, confidence=0.0, rationale=""),
        Decision(record_id="BANK:B-D", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01", "BANK:B-01"], confidence=1.0, rationale=""),
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(
        decisions=decisions,
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=len(records),
        records=records,
    )

    assert metrics.canonical_transactions == 1
    assert metrics.fully_reconciled_transactions == 0
    assert metrics.partially_reconciled_transactions == 0
    assert metrics.unresolved_transactions == 1
    assert metrics.unresolved_canonical_value == 500.0


def test_adversarial_transaction_case_d_records_resolved_wrong_relationship():
    """Issue 2 - Case D (MANDATORY):
    Create a transaction where two source records are marked RESOLVED,
    but the relationship between them is wrong.
    The evaluator MUST NOT classify that transaction as fully reconciled.
    """
    gt_store = GroundTruthStore()
    # Canonical transaction GT-01 consists of LEDGER:L-01 and BANK:B-01
    gt_store.add_transaction(GroundTruthTransaction(
        gt_id="GT-01",
        date=dt.date(2024, 1, 1),
        base_amount=1200.0,
        base_currency="USD",
        canonical_counterparty="VendorA",
        category="STANDARD",
        description="",
        source_record_ids={"LEDGER": ["L-01"], "BANK": ["B-01"]},
    ))

    records = [
        Record(id="L-01", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=1200.0, currency="USD", counterparty="VendorA"),
        Record(id="B-01", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=1200.0, currency="USD", counterparty="VendorA"),
        Record(id="L-99", source=SourceType.LEDGER, date=dt.date(2024, 1, 1), amount=1200.0, currency="USD", counterparty="VendorWrong"),
        Record(id="B-99", source=SourceType.BANK, date=dt.date(2024, 1, 1), amount=1200.0, currency="USD", counterparty="VendorWrong"),
    ]

    # BOTH L-01 and B-01 reach RESOLVED status, but they are matched to wrong external records!
    decisions = [
        Decision(record_id="LEDGER:L-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-99"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-99", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-01"], confidence=1.0, rationale=""),
        Decision(record_id="BANK:B-01", status=ResolutionStatus.RESOLVED, matched_with_ids=["LEDGER:L-99"], confidence=1.0, rationale=""),
        Decision(record_id="LEDGER:L-99", status=ResolutionStatus.RESOLVED, matched_with_ids=["BANK:B-01"], confidence=1.0, rationale=""),
    ]

    evaluator = Evaluator(gt_store)
    metrics = evaluator.evaluate(
        decisions=decisions,
        audit_trail=AuditTrail(),
        processing_time_ms=10.0,
        total_records=len(records),
        records=records,
    )

    # CRITICAL: Evaluator MUST NOT classify this transaction as fully reconciled!
    assert metrics.fully_reconciled_transactions == 0
    assert metrics.partially_reconciled_transactions == 0
    assert metrics.unresolved_transactions == 1
    assert metrics.fully_reconciled_value == 0.0
    assert metrics.unresolved_canonical_value == 1200.0


def test_ai_recommendation_and_contribution_recall_definitions():
    """Issue 3: Verify AI Recommendation Recall and Contribution Recall definitions and formulas."""
    from src.data_generation.generator import SyntheticDataGenerator
    from src.pipeline.reconciliation_pipeline import ReconciliationPipeline

    ds = SyntheticDataGenerator(seed=42).generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)
    evaluator = Evaluator(ds.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # In benchmark on Seed 42:
    # Mid-band evaluated: 144 candidate pairs
    # True GT pairs among those 144: 21 (ai_eligible_gt_relationships)
    # Correct AI accepted & committed: 21
    # Total GT pairs in benchmark: 172
    assert metrics.ai_eligible_gt_relationships == 21
    assert metrics.ai_accepted_count == 23
    assert metrics.ai_committed_count == 21
    assert metrics.total_ground_truth_pairs == 172

    # AI Recommendation Recall = 21 / 21 = 100.00%
    assert pytest.approx(metrics.ai_recommendation_recall, 0.001) == 1.0000

    # AI Contribution Recall = 21 / 172 = 12.21%
    assert pytest.approx(metrics.ai_contribution_recall, 0.001) == 21.0 / 172.0

    # AI Recommendation Precision = 21 / 23 = 91.30%
    assert pytest.approx(metrics.ai_recommendation_precision, 0.001) == 21.0 / 23.0


def test_audit_trail_correspondence_invariant():
    """Issue 6: Audit Correspondence Invariant.
    1. For every terminal decision, there must be a matching audit event with same record_id and same status.
    2. For every exception, there must be an audit event with same record_id and exception reason.
    3. For every AI lifecycle outcome (accepted, committed, validation failed, superseded), audit evidence exists.
    """
    from src.data_generation.generator import SyntheticDataGenerator
    from src.pipeline.reconciliation_pipeline import ReconciliationPipeline

    ds = SyntheticDataGenerator(seed=42).generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    audit_entries = result.audit_trail.entries
    record_ids_in_audit = {e.record_id for e in audit_entries}

    # 1. Every terminal decision has matching audit event with same record_id and same terminal status
    for d in result.decisions:
        assert d.record_id in record_ids_in_audit, f"Record {d.record_id} missing from audit trail!"
        matching_events = [e for e in audit_entries if e.record_id == d.record_id and e.decision == d.status.value]
        assert len(matching_events) >= 1, f"No matching audit event found for decision {d.record_id} with status {d.status.value}"

    # 2. Every exception has matching audit event with exception reason
    for d in result.decisions:
        if d.status == ResolutionStatus.EXCEPTION:
            matching_exc_events = [
                e for e in audit_entries
                if e.record_id == d.record_id
                and e.decision == "EXCEPTION"
                and e.metadata.get("reason") == d.exception_reason.value
            ]
            assert len(matching_exc_events) >= 1, f"No audit event with matching reason {d.exception_reason} for {d.record_id}"

    # 3. AI lifecycle outcomes have corresponding audit evidence
    ai_validation_failed_events = [e for e in audit_entries if e.event == "validation_failed" and e.decision == "VALIDATION_FAILED"]
    assert len(ai_validation_failed_events) >= 2

    ai_committed_events = [e for e in audit_entries if e.stage == "AI_VERIFIED" and e.decision == "RESOLVED"]
    assert len(ai_committed_events) >= 21

