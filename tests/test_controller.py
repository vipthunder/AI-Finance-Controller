from __future__ import annotations
from src.controller.decision_controller import DecisionController
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.records import Record
from src.schemas.enums import SourceType, MatchStage, ResolutionStatus
from src.schemas.validation import ValidationResult
import datetime as dt


def test_controller_init():
    controller = DecisionController()
    assert controller is not None


def test_commit_match():
    controller = DecisionController()
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=500.0, counterparty="ACME", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
                amount=500.0, counterparty="ACME", currency="USD")
    fs = FeatureScores(name_similarity=1.0, amount_proximity=1.0, date_proximity=1.0,
                       composite_score=1.0, amount_diff=0.0, date_diff_days=0)
    pair = CandidatePair(record_a=r1, record_b=r2, score=1.0, feature_scores=fs,
                         matched_on=["all"], stage=MatchStage.EXACT)
    val = ValidationResult(is_valid=True)

    d1, d2 = controller.commit_match(pair, val)
    assert d1.status == ResolutionStatus.RESOLVED
    assert d2.status == ResolutionStatus.RESOLVED
    assert d1.record_id == "LEDGER:L1"
    assert d2.matched_with_ids == ["LEDGER:L1"]
