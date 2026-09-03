from __future__ import annotations
import datetime as dt
from src.schemas.records import Record
from src.schemas.enums import SourceType, ResolutionStatus, ExceptionReason
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.enums import MatchStage
from src.schemas.validation import ValidationResult
from src.investigation.exception_investigator import ExceptionInvestigator


def test_investigation_init():
    inv = ExceptionInvestigator()
    assert inv is not None


def test_investigation_no_candidates():
    inv = ExceptionInvestigator()
    r = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD")
    dec = inv.investigate(r, [], [])
    assert dec.status == ResolutionStatus.EXCEPTION
    assert dec.exception_reason == ExceptionReason.NO_CANDIDATE


def test_investigation_validation_failure():
    inv = ExceptionInvestigator()
    r = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
                amount=500.0, counterparty="ACME", currency="USD")
    fs = FeatureScores(name_similarity=1.0, amount_proximity=1.0, date_proximity=1.0,
                       composite_score=1.0, amount_diff=0.0, date_diff_days=0)
    pair = CandidatePair(record_a=r, record_b=r2, score=0.9, feature_scores=fs,
                         matched_on=[], stage=MatchStage.FUZZY_DIRECT)
    val_fail = ValidationResult(is_valid=False, failed_checks=["currency mismatch"])
    dec = inv.investigate(r, [pair], [(pair, val_fail)])
    assert dec.exception_reason == ExceptionReason.VALIDATION_FAILED
