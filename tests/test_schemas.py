from __future__ import annotations
import datetime as dt
from src.schemas.enums import SourceType, RecordStatus, MatchStage
from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.decisions import Decision
from src.schemas.validation import ValidationResult
from src.schemas.audit import AuditEntry, AuditTrail
from src.schemas.enums import ResolutionStatus, ExceptionReason


def test_record_summary_key():
    r = Record(id="R001", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=100.0, counterparty="ACME")
    assert r.summary_key() == "LEDGER:R001"


def test_candidate_pair_key():
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=100.0, counterparty="ACME")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
                amount=100.0, counterparty="ACME")
    fs = FeatureScores(name_similarity=1.0, amount_proximity=1.0, date_proximity=1.0,
                       composite_score=1.0, amount_diff=0.0, date_diff_days=0)
    pair = CandidatePair(record_a=r1, record_b=r2, score=1.0, feature_scores=fs,
                         matched_on=["all"], stage=MatchStage.EXACT)
    assert "BANK:B1" in pair.pair_key
    assert "LEDGER:L1" in pair.pair_key


def test_audit_trail():
    trail = AuditTrail(entries=[])
    entry = AuditEntry(record_id="L1", stage="EXACT", event="match", decision="PASS")
    trail.append(entry)
    assert len(trail.entries) == 1
    assert trail.for_record("L1") == [entry]
    assert trail.for_stage("EXACT") == [entry]
