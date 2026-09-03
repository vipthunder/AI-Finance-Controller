from __future__ import annotations
import json
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

from src.evaluation.metrics import EvaluationMetrics
from src.schemas.decisions import Decision
from src.schemas.enums import ResolutionStatus


class Dashboard:
    def __init__(self, console: Console | None = None):
        self.console = console or Console(legacy_windows=False, force_terminal=True)

    def render(self, metrics: EvaluationMetrics, decisions: List[Decision] | None = None, title: str = "Dashboard"):
        decisions = decisions or []
        self.console.print()
        self.console.rule(f"[bold bright_cyan]{title}[/bold bright_cyan]")
        self.console.print()

        # ──── RECONCILIATION ────
        recon = Table(title="RELATIONSHIP-LEVEL RECONCILIATION METRICS", show_header=True, header_style="bold magenta")
        recon.add_column("Metric", style="white", min_width=28)
        recon.add_column("Value", style="bright_yellow", justify="right")
        recon.add_row("Precision", f"{metrics.precision:.4f}")
        recon.add_row("Recall", f"{metrics.recall:.4f}")
        recon.add_row("F1", f"{metrics.f1_score:.4f}")
        recon.add_row("Raw Candidate Recall", f"{metrics.raw_candidate_recall:.4f}")
        recon.add_row("Exact Match Coverage", f"{metrics.exact_match_coverage:.4f}")
        recon.add_row("Fuzzy Resolution Coverage", f"{metrics.fuzzy_resolution_coverage:.4f}")
        recon.add_row("Final Reconciliation Recall", f"{metrics.final_reconciliation_recall:.4f}")
        recon.add_row("Auto-Resolution Precision", f"{metrics.auto_resolution_precision:.4f}")
        self.console.print(recon)
        self.console.print()

        # ──── TRANSACTION LEVEL ────
        tx_table = Table(title="TRANSACTION-LEVEL RECONCILIATION METRICS", show_header=True, header_style="bold bright_cyan")
        tx_table.add_column("Metric", style="white", min_width=32)
        tx_table.add_column("Value", style="bright_yellow", justify="right")
        tx_table.add_row("Canonical Transactions", str(metrics.canonical_transactions))
        tx_table.add_row("Fully Reconciled Transactions", str(metrics.fully_reconciled_transactions))
        tx_table.add_row("Partially Reconciled Transactions", str(metrics.partially_reconciled_transactions))
        tx_table.add_row("Unresolved Transactions", str(metrics.unresolved_transactions))
        tx_table.add_row("Fully Reconciled Rate", f"{metrics.fully_reconciled_tx_rate:.2%}")
        tx_table.add_row("Partial Transaction Coverage", f"{metrics.partial_transaction_coverage:.2%}")
        self.console.print(tx_table)
        self.console.print()

        # ──── AUTOMATION ────
        auto = Table(title="AUTOMATION METRICS", show_header=True, header_style="bold green")
        auto.add_column("Metric", style="white", min_width=28)
        auto.add_column("Value", style="bright_cyan", justify="right")
        auto.add_row("Auto-resolution rate", f"{metrics.auto_resolution_rate:.2%}")
        auto.add_row("Auto-resolution precision", f"{metrics.auto_resolution_precision:.4f}")
        auto.add_row("Auto-resolution recall", f"{metrics.auto_resolution_recall:.4f}")
        self.console.print(auto)
        self.console.print()

        # ──── AI ────
        ai = Table(title="AI METRICS (Mid-Band Reasoning)", show_header=True, header_style="bold blue")
        ai.add_column("Metric", style="white", min_width=28)
        ai.add_column("Value", style="bright_magenta", justify="right")
        ai.add_row("AI provider mode", metrics.ai_provider_mode)
        ai.add_row("AI model", metrics.ai_model)
        ai.add_row("AI invocation count", str(metrics.ai_invocations_count))
        ai.add_row("AI acceptance count", str(metrics.ai_accepted_count))
        ai.add_row("AI committed count", str(metrics.ai_committed_count))
        ai.add_row("AI superseded count", str(metrics.ai_superseded_count))
        ai.add_row("AI validation failures", str(metrics.ai_validation_failed_count))
        ai.add_row("AI failed count", str(metrics.ai_failed_count))
        ai.add_row("AI recommendation precision", f"{metrics.ai_recommendation_precision:.4f}")
        ai.add_row("AI recommendation recall", f"{metrics.ai_recommendation_recall:.4f}")
        ai.add_row("AI latency (ms)", f"{metrics.ai_latency_ms:.2f}")
        self.console.print(ai)
        self.console.print()

        # ──── EXCEPTIONS SUMMARY ────
        exc = Table(title="EXCEPTIONS SUMMARY", show_header=True, header_style="bold red")
        exc.add_column("Metric", style="white", min_width=24)
        exc.add_column("Value", style="bright_red", justify="right")
        exc.add_row("Exception count", str(metrics.exceptions_count))
        exc.add_row("Exception precision", f"{metrics.exception_precision:.4f}")
        exc.add_row("Exception recall", f"{metrics.exception_recall:.4f}")
        if metrics.exceptions_by_reason:
            exc.add_row("", "", style="dim")
            exc.add_row("[bold]Reasons", "[bold]Count", style="dim")
            for reason, count in sorted(metrics.exceptions_by_reason.items(), key=lambda x: -x[1]):
                exc.add_row(f"  {reason}", str(count))
        self.console.print(exc)
        self.console.print()

        # ──── FINANCIAL ────
        fin = Table(title="FINANCIAL METRICS", show_header=True, header_style="bold yellow")
        fin.add_column("Metric", style="white", min_width=34)
        fin.add_column("Value", style="bright_green", justify="right")
        fin.add_row("Total Canonical Business Value", f"${metrics.total_canonical_value:,.2f}")
        fin.add_row("Fully Reconciled Value (all records)", f"${metrics.fully_reconciled_value:,.2f}")
        fin.add_row("Partially Reconciled Value (>=2 records)", f"${metrics.partially_reconciled_value:,.2f}")
        fin.add_row("Unresolved Canonical Value", f"${metrics.unresolved_canonical_value:,.2f}")
        fin.add_row("Incorrectly Matched Value (capital at risk)", f"${metrics.incorrectly_matched_value:,.2f}")
        fin.add_row("Exception Source-Record Exposure", f"${metrics.exception_exposure_value:,.2f}")
        fin.add_row("Full Value Reconciliation Rate", f"{metrics.full_value_reconciliation_rate:.2%}")
        fin.add_row("Financial Value Coverage (Partial + Full)", f"{metrics.financial_value_coverage:.2%}")
        fin.add_row("", "", style="dim")
        fin.add_row("[dim]Source-level totals (sum across sources)", "[dim]", style="dim")
        fin.add_row("  Source total value", f"${metrics.total_value:,.2f}")
        fin.add_row("  Source matched value", f"${metrics.matched_value:,.2f}")
        fin.add_row("  Source exception value", f"${metrics.exception_value:,.2f}")
        fin.add_row("  Source value reconciliation rate", f"{metrics.value_reconciliation_rate:.2%}")
        self.console.print(fin)
        self.console.print()

        # ──── FALSE-NEGATIVE DIAGNOSTICS ────
        if metrics.fn_diagnostics:
            fnd = Table(title="FALSE-NEGATIVE DIAGNOSTICS (Uncommitted Relationships)", show_header=True, header_style="bold bright_blue")
            fnd.add_column("Cause / Stage", style="white", min_width=34)
            fnd.add_column("Count", style="bright_yellow", justify="right")
            for cause, count in metrics.fn_diagnostics.items():
                fnd.add_row(cause, str(count))
            self.console.print(fnd)
            self.console.print()

        # ──── DISCREPANCY BREAKDOWN ────
        if metrics.discrepancy_metrics:
            disc = Table(title="DISCREPANCY & CATEGORY BREAKDOWN", show_header=True, header_style="bold cyan")
            disc.add_column("Category / Profile", style="white", min_width=24)
            disc.add_column("Total Tx", style="bright_yellow", justify="right")
            disc.add_column("Reconciled", style="bright_green", justify="right")
            disc.add_column("Reconciliation Rate", style="bright_cyan", justify="right")
            for cat, data in sorted(metrics.discrepancy_metrics.items()):
                disc.add_row(
                    cat,
                    str(data.get("total_tx", 0)),
                    str(data.get("reconciled_tx", 0)),
                    f"{data.get('reconciliation_rate', 0.0):.1%}",
                )
            self.console.print(disc)
            self.console.print()

        # ──── SAFETY ────
        safe = Table(title="SAFETY METRICS", show_header=True, header_style="bold bright_red")
        safe.add_column("Metric", style="white", min_width=24)
        safe.add_column("Value", style="bright_white", justify="right")
        safe.add_row("Duplicate escape rate", f"{metrics.duplicate_escape_rate:.4f}")
        safe.add_row("Critical error rate", f"{metrics.critical_error_rate:.4f}")
        safe.add_row("Silent-drop count", str(metrics.silent_drop_count))
        self.console.print(safe)
        self.console.print()

        # ──── PERFORMANCE & THROUGHPUT ────
        perf = Table(title="PERFORMANCE & THROUGHPUT", show_header=True, header_style="bold bright_cyan")
        perf.add_column("Metric", style="white", min_width=32)
        perf.add_column("Value", style="bright_yellow", justify="right")
        perf.add_row("Pipeline Execution Time", f"{metrics.processing_time_ms:.2f} ms")
        perf.add_row("Pipeline Throughput (excl. dataset gen)", f"{metrics.throughput_records_per_sec:,.0f} rec/sec")
        self.console.print(perf)
        self.console.print()

        # ──── ACTIONABLE EXCEPTION INVESTIGATION QUEUE ────
        exceptions = [d for d in decisions if d.status == ResolutionStatus.EXCEPTION]
        if exceptions:
            exc_queue = Table(title="ACTIONABLE EXCEPTION INVESTIGATION QUEUE", show_header=True, header_style="bold red")
            exc_queue.add_column("Record ID", style="cyan", min_width=18)
            exc_queue.add_column("Reason Code", style="bright_red", min_width=18)
            exc_queue.add_column("Confidence", style="yellow", justify="right")
            exc_queue.add_column("Investigation Rationale / Next Steps", style="white", max_width=60)

            for d in exceptions[:15]:
                reason = d.exception_reason.value if d.exception_reason else "UNKNOWN"
                exc_queue.add_row(
                    str(d.record_id),
                    reason,
                    f"{d.confidence:.2f}",
                    d.rationale or "—"
                )
            if len(exceptions) > 15:
                exc_queue.add_row(
                    f"... and {len(exceptions) - 15} more records",
                    "—",
                    "—",
                    "Exported to outputs/reports/exceptions.json",
                    style="dim"
                )
            self.console.print(exc_queue)
            self.console.print()

        # ──── Sample Resolved Decisions ────
        resolved = [d for d in decisions if d.status == ResolutionStatus.RESOLVED]
        if resolved:
            d_table = Table(title="SAMPLE RESOLVED DECISIONS", show_header=True, header_style="bold green")
            d_table.add_column("Record ID", style="cyan", max_width=25)
            d_table.add_column("Status", style="green")
            d_table.add_column("Stage", style="bright_cyan")
            d_table.add_column("Matched With", style="white", max_width=25)
            d_table.add_column("Confidence", style="bright_yellow", justify="right")
            d_table.add_column("Rationale", style="dim", max_width=35)

            for d in resolved[:10]:
                d_table.add_row(
                    str(d.record_id),
                    Text(d.status.value, style="green"),
                    d.stage_resolved or "—",
                    ", ".join(d.matched_with_ids) if d.matched_with_ids else "—",
                    f"{d.confidence:.2f}",
                    d.rationale[:35] if d.rationale else "—",
                )
            self.console.print(d_table)

        self.console.print()
        self.console.rule("[dim]End of Report[/dim]")
        self.console.print()

    def export_json(self, metrics: EvaluationMetrics, filepath: str) -> None:
        """Export metrics to a JSON file."""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(metrics.to_dict(), f, indent=2, default=str)
        self.console.print(f"[dim]Metrics exported to {filepath}[/dim]")

    def export_exceptions(self, decisions: List[Decision], filepath: str) -> None:
        """Export per-record actionable exception queue to a JSON file."""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        exceptions = [
            d.model_dump() if hasattr(d, "model_dump") else d.dict()
            for d in decisions
            if d.status == ResolutionStatus.EXCEPTION
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(exceptions, f, indent=2, default=str)
        self.console.print(f"[dim]Exceptions exported ({len(exceptions)} records) to {filepath}[/dim]")

    def export_decisions(self, decisions: List[Decision], filepath: str) -> None:
        """Export all terminal and superseded decisions to a JSON file."""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        dump = [d.model_dump() if hasattr(d, "model_dump") else d.dict() for d in decisions]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, default=str)
        self.console.print(f"[dim]Decisions exported ({len(dump)} records) to {filepath}[/dim]")

    def export_audit_trail(self, audit_trail: Any, filepath: str) -> None:
        """Export audit trail events to a JSON file."""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        dump = audit_trail.model_dump() if hasattr(audit_trail, "model_dump") else (
            audit_trail.dict() if hasattr(audit_trail, "dict") else [e.dict() for e in audit_trail.entries]
        )
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, default=str)
        self.console.print(f"[dim]Audit trail exported to {filepath}[/dim]")
