from __future__ import annotations
import datetime as dt
from src.schemas.records import Record
from src.schemas.enums import SourceType
from src.matching.exact_matcher import ExactMatcher


def test_exact_matching_init():
    matcher = ExactMatcher()
    assert matcher is not None


def test_exact_match_same_date_amount_counterparty():
    matcher = ExactMatcher()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD"),
    ]
    candidates, unmatched = matcher.match(records)
    assert len(candidates) == 1
    assert len(unmatched) == 0
    assert candidates[0].score == 1.0


def test_exact_no_match_different_amount():
    matcher = ExactMatcher()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
               amount=501.0, counterparty="ACME", currency="USD"),
    ]
    candidates, unmatched = matcher.match(records)
    assert len(candidates) == 0
    assert len(unmatched) == 2


def test_exact_no_match_same_source():
    matcher = ExactMatcher()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD"),
        Record(id="L2", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=500.0, counterparty="ACME", currency="USD"),
    ]
    candidates, unmatched = matcher.match(records)
    assert len(candidates) == 0
