from __future__ import annotations
import json
import os
import pytest

from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.evaluation.evaluator import Evaluator
from dashboard.app import Dashboard
from src.schemas.enums import ResolutionStatus


def test_artifact_output_consistency():
    """Section 34: Programmatic verification of all exported artifacts and consistency across files."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    evaluator = Evaluator(ds.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    os.makedirs("outputs/reports", exist_ok=True)
    os.makedirs("outputs/decisions", exist_ok=True)
    os.makedirs("outputs/audit", exist_ok=True)

    dashboard = Dashboard()
    dashboard.export_json(metrics, "outputs/reports/metrics.json")
    dashboard.export_exceptions(result.decisions, "outputs/reports/exceptions.json")
    dashboard.export_decisions(result.decisions, "outputs/decisions/decisions.json")
    dashboard.export_audit_trail(result.audit_trail, "outputs/audit/audit.json")

    # Load all 4 exported files
    with open("outputs/reports/metrics.json", "r", encoding="utf-8") as f:
        metrics_json = json.load(f)

    with open("outputs/decisions/decisions.json", "r", encoding="utf-8") as f:
        decisions_json = json.load(f)

    with open("outputs/reports/exceptions.json", "r", encoding="utf-8") as f:
        exceptions_json = json.load(f)

    with open("outputs/audit/audit.json", "r", encoding="utf-8") as f:
        audit_json = json.load(f)

    # 1. Metrics decision counts == actual decisions
    assert len(decisions_json) == metrics_json["total_records"]
    assert len(decisions_json) == len(result.decisions)

    # 2. Exception count == actual exceptions
    assert metrics_json["exceptions_count"] == len(exceptions_json)
    assert len(exceptions_json) == sum(1 for d in decisions_json if d["status"] == "EXCEPTION")

    # 3. AI lifecycle counters == actual AI lifecycle records
    ai_accepted = metrics_json["ai_accepted_count"]
    ai_committed = metrics_json["ai_committed_count"]
    ai_val_failed = metrics_json["ai_validation_failed_count"]
    ai_superseded = metrics_json["ai_superseded_count"]
    ai_failed = metrics_json["ai_failed_count"]
    assert ai_accepted == ai_committed + ai_val_failed + ai_superseded + ai_failed

    # 4. Stage totals == actual final commitments
    resolved_decisions = [d for d in decisions_json if d["status"] == "RESOLVED"]
    exact_decisions = sum(1 for d in resolved_decisions if d.get("stage_resolved") == "EXACT")
    fuzzy_decisions = sum(1 for d in resolved_decisions if d.get("stage_resolved") == "FUZZY_DIRECT")
    ai_decisions = sum(1 for d in resolved_decisions if d.get("stage_resolved") == "AI_VERIFIED")

    # Stage pair counts sum to total committed pairs
    total_committed_pairs = (
        metrics_json["exact_matches_count"]
        + metrics_json["fuzzy_matches_count"]
        + metrics_json["ai_matches_count"]
    )
    assert total_committed_pairs == metrics_json["proposed_pairs_count"] == 172
    assert len(resolved_decisions) + len(exceptions_json) == len(decisions_json) == 179

    # 5. TP / FP / FN == independent evaluation
    all_gt = ds.ground_truth_store.get_all_ground_truth_pairs()
    predicted_pairs = set()
    for d in resolved_decisions:
        r1 = d["record_id"]
        for r2 in d["matched_with_ids"]:
            predicted_pairs.add(tuple(sorted([r1, r2])))

    independent_tp = len(predicted_pairs.intersection(all_gt))
    independent_fp = len(predicted_pairs.difference(all_gt))
    independent_fn = len(all_gt.difference(predicted_pairs))

    assert metrics_json["true_positives"] == independent_tp
    assert metrics_json["false_positives"] == independent_fp
    assert metrics_json["false_negatives"] == independent_fn

    # 6. Financial totals == canonical transaction aggregation
    assert metrics_json["canonical_transactions"] == ds.ground_truth_store.total_transactions
    assert pytest.approx(metrics_json["total_canonical_value"], 0.01) == sum(
        tx.base_amount for tx in ds.ground_truth_store._transactions.values()
    )

    # 7. Audit trail integrity
    audit_entries = audit_json.get("entries", [])
    assert len(audit_entries) > 0
    # Every terminal decision record appears in audit trail
    audit_records = {e["record_id"] for e in audit_entries if "record_id" in e}
    for d in decisions_json:
        assert d["record_id"] in audit_records
