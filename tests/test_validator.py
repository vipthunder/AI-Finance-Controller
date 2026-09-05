from __future__ import annotations
import datetime as dt
from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.enums import SourceType, MatchStage
from src.validation.deterministic_validator import DeterministicValidator


def test_validator_init():
    val = DeterministicValidator()
    assert val is not None


def _make_pair(amount_a=1000.0, amount_b=1000.0, date_a=dt.date(2024, 1, 1),
    date_b=dt.date(2024, 1, 1), currency_a="USD", currency_b="USD",
    source_a=SourceType.LEDGER, source_b=SourceType.BANK):
    r1 = Record(id="L1", source=source_a, date=date_a, amount=amount_a,
                counterparty="ACME", currency=currency_a)
    r2 = Record(id="B1", source=source_b, date=date_b, amount=amount_b,
                counterparty="ACME", currency=currency_b)
    fs = FeatureScores(name_similarity=1.0, amount_proximity=1.0, date_proximity=1.0,
                    composite_score=1.0, amount_diff=abs(amount_a - amount_b),
                    date_diff_days=abs((date_a - date_b).days))
    return CandidatePair(record_a=r1, record_b=r2, score=1.0, feature_scores=fs,
                matched_on=["all"], stage=MatchStage.EXACT)


def test_valid_pair_passes():
    val = DeterministicValidator()
    pair = _make_pair()
    result = val.validate(pair, set())
    assert result.is_valid is True
    assert len(result.failed_checks) == 0


def test_currency_mismatch_fails():
    val = DeterministicValidator()
    pair = _make_pair(currency_a="USD", currency_b="EUR")
    result = val.validate(pair, set())
    assert result.is_valid is False
    assert any("Currency mismatch" in c for c in result.failed_checks)


def test_amount_over_tolerance_fails():
    val = DeterministicValidator()
    pair = _make_pair(amount_a=1000.0, amount_b=1050.0)  # diff = 50 > 28
    result = val.validate(pair, set())
    assert result.is_valid is False
    assert any("Amount diff" in c for c in result.failed_checks)


def test_date_over_tolerance_fails():
    val = DeterministicValidator()
    pair = _make_pair(date_a=dt.date(2024, 1, 1), date_b=dt.date(2024, 1, 15))  # 14 > 10
    result = val.validate(pair, set())
    assert result.is_valid is False
    assert any("Date diff" in c for c in result.failed_checks)


def test_duplicate_commit_fails():
    val = DeterministicValidator()
    pair = _make_pair()
    committed = {pair.record_a.summary_key()}
    result = val.validate(pair, committed)
    assert result.is_valid is False
    assert any("already committed" in c for c in result.failed_checks)
