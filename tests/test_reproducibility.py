from __future__ import annotations
import pytest
from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.evaluation.evaluator import Evaluator


def test_end_to_end_reproducibility():
    """Verify that same seed produces identical data, decisions, and metrics."""
    seed = 42
    n = 30

    # Run 1
    ds1 = SyntheticDataGenerator(seed=seed).generate(n)
    p1 = ReconciliationPipeline()
    r1 = p1.run(ds1.ledger_records, ds1.bank_records, ds1.invoice_records)
    m1 = Evaluator(ds1.ground_truth_store).evaluate_pipeline_result(r1)

    # Run 2
    ds2 = SyntheticDataGenerator(seed=seed).generate(n)
    p2 = ReconciliationPipeline()
    r2 = p2.run(ds2.ledger_records, ds2.bank_records, ds2.invoice_records)
    m2 = Evaluator(ds2.ground_truth_store).evaluate_pipeline_result(r2)

    # 1. Identical source records
    assert ds1.ledger_records == ds2.ledger_records
    assert ds1.bank_records == ds2.bank_records
    assert ds1.invoice_records == ds2.invoice_records

    # 2. Identical ground truth transactions & pairs
    assert ds1.ground_truth_store.get_all_ground_truth_pairs() == ds2.ground_truth_store.get_all_ground_truth_pairs()

    # 3. Identical decisions
    d1_tuples = [(d.record_id, d.status.value, d.stage_resolved, d.confidence) for d in r1.decisions]
    d2_tuples = [(d.record_id, d.status.value, d.stage_resolved, d.confidence) for d in r2.decisions]
    assert d1_tuples == d2_tuples

    # 4. Identical metrics (excluding non-deterministic execution time)
    timing_keys = {"processing_time_ms", "throughput_records_per_sec"}
    d1 = m1.to_dict()
    d2 = m2.to_dict()
    for k in d1:
        if k in timing_keys:
            continue
        if isinstance(d1[k], float):
            assert abs(d1[k] - d2[k]) < 1e-9, f"Metric {k} differs: {d1[k]} vs {d2[k]}"
        else:
            assert d1[k] == d2[k], f"Metric {k} differs: {d1[k]} vs {d2[k]}"
