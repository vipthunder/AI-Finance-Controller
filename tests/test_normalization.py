from __future__ import annotations
from src.ingestion.normalizer import RecordNormalizer


def test_normalization_init():
    norm = RecordNormalizer()
    assert norm is not None


def test_normalize_date_iso():
    norm = RecordNormalizer()
    d = norm.normalize_date("2024-03-15")
    assert d.year == 2024
    assert d.month == 3
    assert d.day == 15


def test_normalize_date_us_format():
    norm = RecordNormalizer()
    d = norm.normalize_date("01/25/2024")
    assert d.year == 2024
    assert d.month == 1
    assert d.day == 25


def test_normalize_amount():
    norm = RecordNormalizer()
    assert norm.normalize_amount("-1500.50") == 1500.50
    assert norm.normalize_amount("abc") == 0.0


def test_normalize_counterparty():
    norm = RecordNormalizer()
    assert norm.normalize_counterparty_name("  acme corp  ") == "ACME CORP"
    assert norm.normalize_counterparty_name("") == ""


def test_normalize_batch():
    norm = RecordNormalizer()
    ledger = [{"ledger_id": "L1", "posting_date": "2024-01-01", "amount": "100",
               "currency": "USD", "vendor_account": "Acme"}]
    bank = [{"transaction_id": "B1", "value_date": "01/01/2024", "settled_amount": "100",
             "currency_code": "USD", "statement_narrative": "ACME INC"}]
    invoice = [{"internal_invoice_id": "I1", "invoice_date": "2024-01-01", "total_amount": "100",
                "billing_currency": "USD", "supplier_name": "Acme Corp"}]
    records = norm.normalize_batch(ledger, bank, invoice)
    assert len(records) == 3
    assert records[0].source.value == "LEDGER"
    assert records[1].source.value == "BANK"
    assert records[2].source.value == "INVOICE"
    assert records[0].canonical_entity == "ACME GLOBAL SOLUTIONS"
    assert records[1].canonical_entity == "ACME GLOBAL SOLUTIONS"
    assert records[2].canonical_entity == "ACME GLOBAL SOLUTIONS"


def test_normalize_legal_suffixes():
    norm = RecordNormalizer()
    assert norm.strip_legal_suffix("STRIPE INC") == "STRIPE"
    assert norm.strip_legal_suffix("SLACK TECHNOLOGIES LLC") == "SLACK TECHNOLOGIES"
    assert norm.strip_legal_suffix("KPMG LLP") == "KPMG"
    assert norm.strip_legal_suffix("SINGLE") == "SINGLE"
    assert norm.strip_legal_suffix("") == ""


def test_normalize_canonical_aliases():
    norm = RecordNormalizer()
    assert norm.map_canonical_entity("AWS CLOUD SERVICES") == "AMAZON WEB SERVICES INC"
    assert norm.map_canonical_entity("AWS*US-EAST-1") == "AMAZON WEB SERVICES INC"
    assert norm.map_canonical_entity("MSFT AZURE") == "MICROSOFT AZURE"
    assert norm.map_canonical_entity("GOOGLE*CLOUD") == "GOOGLE CLOUD"
    assert norm.map_canonical_entity("SFDC") == "SALESFORCE"


def test_normalize_unrelated_companies():
    norm = RecordNormalizer()
    c1 = norm.map_canonical_entity("STRIPE PAYMENTS")
    c2 = norm.map_canonical_entity("SLACK TECHNOLOGIES")
    assert c1 != c2
    assert c1 == "STRIPE"
    assert c2 == "SLACK"


def test_normalize_empty_and_none():
    norm = RecordNormalizer()
    assert norm.normalize_counterparty_name(None) == ""
    assert norm.normalize_counterparty_name("") == ""
    assert norm.map_canonical_entity(None) is None
    assert norm.map_canonical_entity("") is None
