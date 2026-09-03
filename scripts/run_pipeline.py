from __future__ import annotations
import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.evaluation.evaluator import Evaluator


def main():
    print("Generating synthetic data...")
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=60)

    print("Running reconciliation pipeline...")
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)

    print("Evaluating results...")
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)

    # Write outputs
    os.makedirs("outputs/decisions", exist_ok=True)
    os.makedirs("outputs/audit", exist_ok=True)

    with open("outputs/decisions/decisions.json", "w", encoding="utf-8") as f:
        data = [d.model_dump() for d in result.decisions]
        json.dump(data, f, indent=2, default=str)

    with open("outputs/audit/audit.json", "w", encoding="utf-8") as f:
        # AuditTrail.entries are pydantic models — use model_dump
        data = [e.model_dump() for e in result.audit_trail.entries]
        json.dump(data, f, indent=2, default=str)

    print(f"\nPipeline finished in {result.processing_time_ms:.1f}ms")
    print(f"  Records processed: {metrics.total_records}")
    print(f"  Precision: {metrics.precision:.4f}")
    print(f"  Recall:    {metrics.recall:.4f}")
    print(f"  F1 Score:  {metrics.f1_score:.4f}")
    print(f"  Decisions written to outputs/decisions/decisions.json")
    print(f"  Audit trail written to outputs/audit/audit.json")


if __name__ == "__main__":
    main()
