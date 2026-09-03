from __future__ import annotations
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table

from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.evaluation.evaluator import Evaluator
from src.investigation.exception_investigator import ExceptionInvestigator
from src.schemas.enums import ResolutionStatus
from dashboard.app import Dashboard

console = Console()


def main():
    console.rule("[bold bright_cyan]AI Finance Controller — Live Demo[/bold bright_cyan]")
    console.print()

    # ── Step 1: Generate Data ──
    console.print("[bold]Step 1:[/bold] Generating synthetic financial data...", style="cyan")
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=60)
    console.print(f"  ✓ Ledger records:  {len(dataset.ledger_records)}")
    console.print(f"  ✓ Bank records:    {len(dataset.bank_records)}")
    console.print(f"  ✓ Invoice records: {len(dataset.invoice_records)}")
    console.print(f"  ✓ Ground truth:    {dataset.ground_truth_store.total_transactions} transactions")
    console.print()

    # ── Step 2: Run Pipeline ──
    console.print("[bold]Step 2:[/bold] Running reconciliation pipeline...", style="cyan")
    pipeline = ReconciliationPipeline()
    result = pipeline.run(dataset.ledger_records, dataset.bank_records, dataset.invoice_records)

    # Stage-by-stage counts
    stage_table = Table(title="Stage-by-Stage Progress", show_header=True, header_style="bold green")
    stage_table.add_column("Stage", style="white")
    stage_table.add_column("Matched Pairs", style="bright_yellow", justify="right")
    stage_table.add_row("Exact Match", str(result.exact_match_count))
    stage_table.add_row("Fuzzy Match (≥0.85)", str(result.fuzzy_match_count))
    stage_table.add_row("AI Verified", str(result.ai_match_count))
    stage_table.add_row("AI Invocations", str(result.ai_invocations))
    stage_table.add_row("AI Rejected", str(result.ai_rejected))
    console.print(stage_table)
    console.print()

    # ── Step 3: Evaluate ──
    console.print("[bold]Step 3:[/bold] Evaluating against ground truth...", style="cyan")
    evaluator = Evaluator(dataset.ground_truth_store)
    metrics = evaluator.evaluate_pipeline_result(result)
    console.print()

    # ── Step 4: Dashboard ──
    console.print("[bold]Step 4:[/bold] Rendering evaluation dashboard...", style="cyan")
    dashboard = Dashboard()

    # Sample decisions — mix of resolved and exceptions
    resolved = [d for d in result.decisions if d.status == ResolutionStatus.RESOLVED][:5]
    exceptions = [d for d in result.decisions if d.status == ResolutionStatus.EXCEPTION][:5]
    sample = resolved + exceptions

    dashboard.render(metrics, sample, "AI Finance Controller — Evaluation Dashboard")

    # ── Step 5: Exception List ──
    console.print("[bold]Step 5:[/bold] Exception queue for human review:", style="cyan")
    exception_decisions = [d for d in result.decisions if d.status == ResolutionStatus.EXCEPTION]
    records_by_key = {r.summary_key(): r for r in result.records}
    investigator = ExceptionInvestigator()
    escalation_queue = investigator.package_escalation_queue(exception_decisions, records_by_key)

    exc_table = Table(title="Human Escalation Queue", show_header=True, header_style="bold red")
    exc_table.add_column("#", style="dim")
    exc_table.add_column("Record ID", style="cyan", max_width=28)
    exc_table.add_column("Source", style="white")
    exc_table.add_column("Counterparty", style="white", max_width=22)
    exc_table.add_column("Amount", style="yellow", justify="right")
    exc_table.add_column("Reason", style="bright_red")
    exc_table.add_column("Action", style="dim", max_width=30)

    for i, item in enumerate(escalation_queue[:15], 1):
        exc_table.add_row(
            str(i),
            item.record_id,
            item.source,
            item.counterparty[:22] if item.counterparty else "—",
            f"${item.amount:,.2f}",
            item.reason_code,
            item.suggested_action[:30],
        )
    console.print(exc_table)
    console.print()

    # ── Step 6: Export ──
    os.makedirs("outputs/reports", exist_ok=True)
    dashboard.export_json(metrics, "outputs/reports/metrics.json")
    console.print()

    # ── Step 7: Live 5-Minute Pitch Failure Demonstration ──
    console.rule("[bold bright_red]Live Failure Demonstration: Deterministic Validator Overrides AI[/bold bright_red]")
    console.print()
    ai_val_fails = [v for v in result.validation_failure_details if v.get("stage") == "AI_VERIFICATION"]
    if ai_val_fails:
        fail_table = Table(title="AI Proposed MATCH → Deterministic Validator Overrode & Blocked", show_header=True, header_style="bold red")
        fail_table.add_column("Candidate Pair Key", style="cyan")
        fail_table.add_column("AI Decision", style="bright_green")
        fail_table.add_column("Validator Result", style="bright_red")
        fail_table.add_column("Financial Violations Detected", style="white")
        fail_table.add_column("Final Disposition", style="bright_yellow")
        for v in ai_val_fails:
            fail_table.add_row(
                v.get("pair_key", "—"),
                "PROPOSE MATCH",
                "BLOCKED",
                ", ".join(v.get("failed_checks", [])),
                "AI_VALIDATION_FAILED → EXCEPTION QUEUE",
            )
        console.print(fail_table)
        console.print()
        console.print(
            "  [bold bright_white]Financial Safety Guarantee:[/bold bright_white] "
            "[green]AI proposes based on semantic similarity,[/green] "
            "[red]but deterministic controls protect the books by strictly blocking matches that exceed financial tolerances.[/red]",
        )
        console.print()
    console.rule("[dim]Demo Complete[/dim]")


if __name__ == "__main__":
    main()
