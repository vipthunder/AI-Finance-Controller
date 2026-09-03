from __future__ import annotations
import pytest
from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.evaluation.evaluator import Evaluator


def test_financial_value_metrics():
    """Verify canonical business transaction value de-duplication and accounting."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(40)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    evaluator = Evaluator(ds.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # 1. Total business value matches sum of ground truth transaction base amounts
    expected_business_value = sum(tx.base_amount for tx in ds.ground_truth_store._transactions.values())
    assert abs(metrics.total_business_value - expected_business_value) < 1e-4

    # 2. Reconciled business value + exception business value == total business value
    assert abs((metrics.reconciled_business_value + metrics.exception_business_value) - metrics.total_business_value) < 1e-4

    # 3. Canonical business value is strictly less than raw triple-counted source value
    assert metrics.total_business_value < metrics.total_value

    # 4. Value reconciliation rate is bounded between 0 and 1
    assert 0.0 <= metrics.business_value_reconciliation_rate <= 1.0
    assert 0.0 <= metrics.value_reconciliation_rate <= 1.0

    # 5. Incorrectly matched value is 0.0 under strict validation
    assert metrics.incorrectly_matched_value == 0.0
