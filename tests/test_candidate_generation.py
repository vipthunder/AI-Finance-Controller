from __future__ import annotations
import datetime as dt
from src.schemas.records import Record
from src.schemas.enums import SourceType
from src.matching.candidate_generator import CandidateGenerator


def test_candidate_generation_init():
    gen = CandidateGenerator()
    assert gen is not None


def test_candidate_generation_basic():
    gen = CandidateGenerator()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="ACME", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 3),
               amount=1010.0, counterparty="ACME INC", currency="USD"),
    ]
    candidates = gen.generate(records)
    assert len(candidates) == 1  # within tolerances


def test_candidate_gen_skips_same_source():
    gen = CandidateGenerator()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="ACME", currency="USD"),
        Record(id="L2", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="ACME", currency="USD"),
    ]
    candidates = gen.generate(records)
    assert len(candidates) == 0


def test_candidate_gen_skips_different_currency():
    gen = CandidateGenerator()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="ACME", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="ACME", currency="EUR"),
    ]
    candidates = gen.generate(records)
    assert len(candidates) == 0
    # Verify explicit currency miss reason is tracked
    miss_reasons = gen.get_miss_reasons("LEDGER:L1")
    assert any("Currency mismatch" in r for r in miss_reasons)


def test_candidate_adversarial_canonical_entity_blocking():
    """Canonical entities match even with wider date lag (up to 42 days)."""
    gen = CandidateGenerator()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=5000.0, counterparty="AMAZON WEB SERVICES INC",
               canonical_entity="AMAZON WEB SERVICES INC", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 28),
               amount=5000.0, counterparty="AWS CLOUD SERVICES",
               canonical_entity="AMAZON WEB SERVICES INC", currency="USD"),
    ]
    candidates = gen.generate(records)
    assert len(candidates) == 1
    assert "canonical_entity_match" in candidates[0].matched_on


def test_candidate_adversarial_reference_blocking():
    """Shared reference IDs match across arbitrary date windows."""
    gen = CandidateGenerator()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=2500.0, counterparty="VENDOR A", reference_id="REF-TX9988", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 2, 20),
               amount=2500.0, counterparty="VENDOR B", reference_id="REF-TX9988", currency="USD"),
    ]
    candidates = gen.generate(records)
    assert len(candidates) == 1
    assert "reference_match" in candidates[0].matched_on


def test_candidate_adversarial_blocking_miss_reasons():
    """Unmatched records have detailed, explainable blocking miss reasons."""
    gen = CandidateGenerator()
    records = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=100.0, counterparty="ALPHA CORP", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 3, 1),
               amount=100.0, counterparty="BETA CORP", currency="USD"),
        Record(id="I1", source=SourceType.INVOICE, date=dt.date(2024, 1, 2),
               amount=9000.0, counterparty="GAMMA CORP", currency="USD"),
    ]
    candidates = gen.generate(records)
    assert len(candidates) == 0

    reasons_l1 = gen.get_miss_reasons("LEDGER:L1")
    assert any("Date lag" in r for r in reasons_l1)
    assert any("Amount diff" in r for r in reasons_l1)


def test_candidate_adversarial_tolerance_boundaries():
    """Test proximity boundary: within 14 days and $60/20% passes, beyond fails."""
    gen = CandidateGenerator()
    # Case A: Within tolerance (diff $50 < $60, 10 days < 14 days)
    records_pass = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="COMPANY", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 11),
               amount=1050.0, counterparty="COMPANY", currency="USD"),
    ]
    candidates_pass = gen.generate(records_pass)
    assert len(candidates_pass) == 1

    # Case B: Outside date tolerance (15 days > 14 days) with no shared entity or reference
    records_fail = [
        Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
               amount=1000.0, counterparty="CORP X", currency="USD"),
        Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 20),
               amount=1000.0, counterparty="CORP Y", currency="USD"),
    ]
    candidates_fail = gen.generate(records_fail)
    assert len(candidates_fail) == 0
    assert any("Date lag 19d" in r for r in gen.get_miss_reasons("LEDGER:L1"))

