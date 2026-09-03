from __future__ import annotations
from src.evaluation.evaluator import Evaluator
from src.schemas.ground_truth import GroundTruthStore
from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline


def test_evaluation_init():
    gt = GroundTruthStore()
    evaluator = Evaluator(gt)
    assert evaluator is not None


def test_evaluation_end_to_end():
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    assert metrics.total_records > 0
    assert metrics.precision >= 0.0
    assert metrics.recall >= 0.0
    assert metrics.processing_time_ms > 0.0
    assert metrics.throughput_records_per_sec > 0.0
    # Should have some matches
    assert metrics.exact_matches_count + metrics.fuzzy_matches_count + metrics.ai_matches_count > 0


def test_reconciliation_metrics():
    """Verify the core reconciliation category metrics are computed."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # Precision should be high (deterministic validator catches most errors)
    assert metrics.precision >= 0.9
    # F1 is the harmonic mean of precision and recall
    if metrics.precision + metrics.recall > 0:
        expected_f1 = 2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall)
        assert abs(metrics.f1_score - expected_f1) < 1e-6
    # Candidate recall >= overall recall (candidate set is a superset of committed matches)
    assert metrics.candidate_recall >= metrics.recall or metrics.candidate_recall == 0.0


def test_automation_metrics():
    """Verify auto-resolution metrics (exact + fuzzy, no AI)."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # Auto-resolution rate is between 0 and 1
    assert 0.0 <= metrics.auto_resolution_rate <= 1.0
    # Auto-resolution precision is between 0 and 1
    assert 0.0 <= metrics.auto_resolution_precision <= 1.0
    # Auto-resolution recall is between 0 and 1
    assert 0.0 <= metrics.auto_resolution_recall <= 1.0
    # Auto-resolution recall <= overall recall
    assert metrics.auto_resolution_recall <= metrics.recall + 1e-6


def test_ai_metrics():
    """Verify AI category metrics."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # AI committed count <= AI accepted count
    assert metrics.ai_committed_count <= metrics.ai_accepted_count
    # AI invocations count tracks mid-band candidates
    assert metrics.ai_invocations_count >= 0
    # AI precision and recall are in [0, 1]
    assert 0.0 <= metrics.ai_precision <= 1.0
    assert 0.0 <= metrics.ai_recall <= 1.0


def test_exception_metrics():
    """Verify exception category metrics."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # Exception count + resolved count should account for all records
    assert metrics.exceptions_count >= 0
    # Exception precision and recall in [0, 1]
    assert 0.0 <= metrics.exception_precision <= 1.0
    assert 0.0 <= metrics.exception_recall <= 1.0
    # Reasons breakdown sums to exception count
    assert sum(metrics.exceptions_by_reason.values()) == metrics.exceptions_count


def test_financial_metrics():
    """Verify financial category metrics."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # Total value must be positive (we have real transactions)
    assert metrics.total_value > 0.0
    # Matched value <= total value
    assert metrics.matched_value <= metrics.total_value + 1e-2
    # Exception value >= 0
    assert metrics.exception_value >= 0.0
    # Value reconciliation rate in [0, 1]
    assert 0.0 <= metrics.value_reconciliation_rate <= 1.0
    # Incorrectly matched value >= 0
    assert metrics.incorrectly_matched_value >= 0.0


def test_safety_metrics():
    """Verify safety category metrics."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=20)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # Duplicate escape rate should be 0 (validator blocks duplicates)
    assert metrics.duplicate_escape_rate == 0.0
    # Critical error rate in [0, 1]
    assert 0.0 <= metrics.critical_error_rate <= 1.0
    # Silent drop count should be 0 (all records get a decision)
    assert metrics.silent_drop_count == 0


def test_metrics_to_dict_has_all_fields():
    """Verify the metrics dict export contains all 6 categories."""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=10)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)
    d = metrics.to_dict()

    # Reconciliation
    assert "precision" in d
    assert "recall" in d
    assert "f1_score" in d
    assert "candidate_recall" in d

    # Automation
    assert "auto_resolution_rate" in d
    assert "auto_resolution_precision" in d
    assert "auto_resolution_recall" in d

    # AI
    assert "ai_invocations_count" in d
    assert "ai_accepted_count" in d
    assert "ai_committed_count" in d
    assert "ai_precision" in d
    assert "ai_recall" in d

    # Exceptions
    assert "exceptions_count" in d
    assert "exception_precision" in d
    assert "exception_recall" in d
    assert "exceptions_by_reason" in d

    # Financial
    assert "total_value" in d
    assert "matched_value" in d
    assert "exception_value" in d
    assert "incorrectly_matched_value" in d
    assert "value_reconciliation_rate" in d

    # Safety
    assert "duplicate_escape_rate" in d
    assert "critical_error_rate" in d
    assert "silent_drop_count" in d


def test_empty_pipeline():
    """Edge case: empty ground truth, no records."""
    gt = GroundTruthStore()
    evaluator = Evaluator(gt)
    from src.schemas.audit import AuditTrail
    metrics = evaluator.evaluate(
        decisions=[],
        audit_trail=AuditTrail(entries=[]),
        processing_time_ms=1.0,
        total_records=0,
    )
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1_score == 0.0
    assert metrics.candidate_recall == 0.0
    assert metrics.auto_resolution_rate == 0.0
    assert metrics.total_value == 0.0
    assert metrics.silent_drop_count == 0
    assert metrics.duplicate_escape_rate == 0.0
