from __future__ import annotations
import pytest
from src.data_generation.generator import SyntheticDataGenerator
from src.pipeline.reconciliation_pipeline import ReconciliationPipeline
from src.schemas.enums import ResolutionStatus, MatchStage


def test_ai_accepted_accounting_invariant():
    """Verify that every AI accepted candidate ends in an explicit state and is accounted for."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    # 1. Invariant: committed <= accepted <= invocations
    assert result.ai_match_count <= result.ai_accepted <= result.ai_invocations

    # 2. Invariant: Every record has an explicit terminal decision
    all_record_keys = {r.summary_key() for r in result.records}
    decided_record_ids = {d.record_id for d in result.decisions}
    assert all_record_keys == decided_record_ids, "Silent drops detected: records without terminal decisions"

    # 3. Invariant: Superseded decisions are explicitly recorded with reasons and conflicting keys
    for d in result.superseded_decisions:
        assert d.status == ResolutionStatus.SUPERSEDED
        assert "superseded" in d.rationale.lower()
        assert "conflicting_record" in d.metadata

    # 4. Invariant: All decisions have audit provenance
    event_record_ids = {e.record_id for e in result.audit_trail.entries}
    for d in result.decisions:
        assert d.record_id in event_record_ids, f"Record {d.record_id} lacks audit trail"


def test_collision_resolution_records_superseded():
    """Verify that colliding candidate pairs produce explicit SUPERSEDED decisions."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(30)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    assert len(result.superseded_decisions) > 0, "Expected superseded candidates in multi-source reconciliation"
    assert all(d.status == ResolutionStatus.SUPERSEDED for d in result.superseded_decisions)


def test_ai_accepted_exact_terminal_decomposition():
    """Phase 2: Invariant: AI accepted = AI committed + AI superseded + AI validation failures + AI failed."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    # All AI-accepted candidate pairs must decompose into explicit terminal outcomes
    ai_validation_failed = result.ai_validation_failed_count
    ai_failed = result.ai_failed_count
    
    total_accounted = result.ai_committed_count + result.ai_superseded_count + ai_validation_failed + ai_failed
    assert result.ai_accepted == total_accounted, (
        f"AI accepted ({result.ai_accepted}) does not match decomposed outcomes: "
        f"committed={result.ai_committed_count}, superseded={result.ai_superseded_count}, "
        f"validation_failed={ai_validation_failed}, failed={ai_failed}"
    )


def test_no_silent_drops_terminal_partition():
    """Phase 3: Invariant: Every input record maps to exactly one terminal state with zero overlap."""
    gen = SyntheticDataGenerator(seed=42)
    ds = gen.generate(60)
    pipeline = ReconciliationPipeline()
    result = pipeline.run(ds.ledger_records, ds.bank_records, ds.invoice_records)

    all_input_keys = {r.summary_key() for r in result.records}
    resolved_keys = {d.record_id for d in result.decisions if d.status == ResolutionStatus.RESOLVED}
    exception_keys = {d.record_id for d in result.decisions if d.status == ResolutionStatus.EXCEPTION}

    # Invariant A: Total input equals union of terminal partitions
    assert all_input_keys == (resolved_keys | exception_keys)
    # Invariant B: Zero overlap between resolved and exceptions
    assert len(resolved_keys & exception_keys) == 0, "Record assigned to both RESOLVED and EXCEPTION"
    # Invariant C: Exactly one decision per input record
    assert len(result.decisions) == len(all_input_keys), "Duplicate terminal decision assignments detected"

