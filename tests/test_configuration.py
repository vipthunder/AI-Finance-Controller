from __future__ import annotations
import pytest
from src.config import AppConfig, get_config, reset_config
from src.validation.deterministic_validator import DeterministicValidator
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.records import Record
from src.schemas.enums import SourceType, MatchStage
import datetime as dt


def _make_pair(amount_a: float = 1000.0, amount_b: float = 1040.0):
    r1 = Record(
        id="L-0001",
        source=SourceType.LEDGER,
        date=dt.date(2024, 1, 1),
        amount=amount_a,
        counterparty="ACME",
        currency="USD",
    )
    r2 = Record(
        id="B-0001",
        source=SourceType.BANK,
        date=dt.date(2024, 1, 1),
        amount=amount_b,
        counterparty="ACME",
        currency="USD",
    )
    return CandidatePair(
        record_a=r1,
        record_b=r2,
        score=0.90,
        feature_scores=FeatureScores(
            name_similarity=1.0,
            amount_proximity=0.96,
            date_proximity=1.0,
            composite_score=0.90,
            amount_diff=abs(amount_a - amount_b),
            date_diff_days=0,
        ),
        matched_on=[],
        stage=MatchStage.FUZZY_DIRECT,
    )


def test_validator_uses_central_config():
    reset_config()
    val = DeterministicValidator()
    # Default tolerance is $28.00; difference is $40.00 -> should fail
    pair = _make_pair(1000.0, 1040.0)
    res = val.validate(pair, set())
    assert res.is_valid is False
    assert any("exceeds abs tolerance" in c for c in res.failed_checks)


def test_changing_configuration_changes_behavior_without_modifying_code():
    # Override configuration to allow $50.00 tolerance
    get_config(overrides={"validator": {"max_amount_abs_tolerance": 50.0}})
    val_lenient = DeterministicValidator()

    pair = _make_pair(1000.0, 1040.0)  # $40 diff <= $50 tolerance
    res = val_lenient.validate(pair, set())
    assert res.is_valid is True

    # Reset config back to standard
    reset_config()
    val_strict = DeterministicValidator()
    res_strict = val_strict.validate(pair, set())
    assert res_strict.is_valid is False
