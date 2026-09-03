from __future__ import annotations
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.evaluation.evaluator import Evaluator
from dashboard.app import Dashboard


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

    # Export all audit, decision, exception, and metrics artifacts
    os.makedirs("outputs/reports", exist_ok=True)
    os.makedirs("outputs/decisions", exist_ok=True)
    os.makedirs("outputs/audit", exist_ok=True)

    dashboard = Dashboard()
    dashboard.export_json(metrics, "outputs/reports/metrics.json")
    dashboard.export_exceptions(result.decisions, "outputs/reports/exceptions.json")
    dashboard.export_decisions(result.decisions, "outputs/decisions/decisions.json")
    dashboard.export_audit_trail(result.audit_trail, "outputs/audit/audit.json")
    dashboard.export_audit_trail(result.audit_trail, "outputs/audit/audit_trail.json")

    # Render dashboard with full decision, exception, and financial visibility
    dashboard.render(metrics, result.decisions, "Evaluation Report")


if __name__ == "__main__":
    main()
