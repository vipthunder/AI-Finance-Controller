from __future__ import annotations
import datetime as dt
import re
from typing import List, Dict, Any, Optional

from src.schemas.enums import SourceType
from src.schemas.records import Record
from src.config import get_config


LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "LLC", "LTD",
    "LIMITED", "PLC", "PTY", "LLP", "CO", "COMPANY", "GMBH", "SE",
}

# Controlled canonical catalog mapping for deterministic entity resolution
CANONICAL_ENTITY_CATALOG = {
    "AMAZON WEB SERVICES INC": [
        "AWS", "AMAZON", "AMAZON WEB SERVICES", "AWS CLOUD SERVICES",
        "AMZN WEB SERVICES", "AWS US-EAST-1", "AWS WEB SERVICES",
    ],
    "GOOGLE CLOUD": [
        "GCP", "GOOGLE", "GOOGLE CLOUD PLATFORM", "GCP CLOUD", "GOOGLE CLOUD",
    ],
    "MICROSOFT AZURE": [
        "MSFT", "AZURE", "MICROSOFT", "MSFT AZURE", "AZURE CLOUD SERVICES",
        "MS AZURE COMPUTING", "MICROSOFT AZURE",
    ],
    "STRIPE": [
        "STRIPE", "STRIPE INC", "STRIPE PAYMENTS", "STRIPE CHECKOUT",
    ],
    "SALESFORCE": [
        "SALESFORCE", "SALESFORCE COM", "SALESFORCE CRM", "SFDC", "SALESFORCE INC",
    ],
    "SLACK": [
        "SLACK", "SLACK TECHNOLOGIES", "SLACK WORK", "SLACK TECH", "SLACKHQ",
    ],
    "ATLASSIAN": [
        "ATLASSIAN", "JIRA", "CONFLUENCE", "ATLASSIAN JIRA", "ATLASSIAN PTY", "JIRA CONFLUENCE",
    ],
    "DATADOG": [
        "DATADOG", "DATADOG INC", "DATADOG MONITOR", "DATADOG MONITORING",
    ],
    "SNOWFLAKE": [
        "SNOWFLAKE", "SNOWFLAKE COMPUTING", "SNOWFLAKE INC", "SNOWFLAKE DB",
    ],
    "GUSTO PAYROLL": [
        "GUSTO", "GUSTO PAYROLL", "GUSTO INC", "GUSTO HR",
    ],
    "DEEL": [
        "DEEL", "DEEL INC", "DEEL CONTRACTOR", "DEEL GLOBAL", "DEEL HR",
    ],
    "LATHAM & WATKINS": [
        "LATHAM", "LATHAM & WATKINS", "LATHAM WATKINS", "LATHAM WATKINS LLP",
        "L&W LEGAL", "LATHAM AND WATKINS",
    ],
    "KPMG": [
        "KPMG", "KPMG LLP", "KPMG AUDIT", "KPMG ADVISORY",
    ],
    "WEWORK": [
        "WEWORK", "WEWORK COMPANIES", "WEWORK OFFICE", "WEWORK RENT",
    ],
    "APPLE ENTERPRISE": [
        "APPLE", "APPLE INC", "APPLE ENTERPRISE", "APPLE B2B",
        "APPLE STORE BIZ", "APPLE COMP",
    ],
    "SAP": [
        "SAP", "SAP SE", "SAP ERP", "SAP GLOBAL", "SAP SOFTWARE",
    ],
    "BRITISH TELECOM": [
        "BT", "BRITISH TELECOM", "BT GROUP", "BT COMMUNICATIONS", "BRITISH TELECOM PLC",
    ],
    "FEDEX": [
        "FEDEX", "FEDERAL EXPRESS", "FEDEX SHIPPING", "FEDEX CORP", "FEDEX INC",
    ],
    "SILICON VALLEY BANK": [
        "SVB", "SILICON VALLEY BANK", "SVB FEES", "SILICON VALLEY BANK INC",
    ],
    "ACME GLOBAL SOLUTIONS": [
        "ACME", "ACME GLOBAL", "ACME GLOBAL SOLUTIONS", "ACME SOLUTIONS",
        "ACME CONSULTING", "ACME GLOBAL INC",
    ],
}

# Reverse lookup dictionary: uppercase alias -> canonical name
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in CANONICAL_ENTITY_CATALOG.items():
    _ALIAS_TO_CANONICAL[canonical.upper()] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.upper()] = canonical


class RecordNormalizer:
    """Normalizes multi-source raw records into standard Record schema.
    Performs case normalization, whitespace cleanup, punctuation normalization,
    legal suffix identification, and controlled canonical entity mapping.
    """

    def __init__(self):
        self.config = get_config().normalization

    def normalize_batch(
        self,
        ledger_raw: List[Dict[str, Any]],
        bank_raw: List[Dict[str, Any]],
        invoice_raw: List[Dict[str, Any]],
    ) -> List[Record]:
        records: List[Record] = []
        for raw in ledger_raw:
            records.append(self._normalize_ledger_record(raw))
        for raw in bank_raw:
            records.append(self._normalize_bank_record(raw))
        for raw in invoice_raw:
            records.append(self._normalize_invoice_record(raw))
        return records

    def _normalize_ledger_record(self, raw: Dict[str, Any]) -> Record:
        raw_name = raw.get("vendor_account", "")
        norm_name, notes = self.normalize_counterparty_with_notes(raw_name)
        canonical = self.map_canonical_entity(norm_name)
        if canonical:
            notes.append(f"Mapped to canonical entity '{canonical}'")

        return Record(
            id=str(raw["ledger_id"]),
            source=SourceType.LEDGER,
            date=self.normalize_date(raw["posting_date"]),
            amount=self.normalize_amount(raw["amount"]),
            currency=self.normalize_currency(raw.get("currency", "USD")),
            counterparty=norm_name,
            canonical_entity=canonical,
            reference_id=str(raw.get("reference", "")),
            raw_data=raw,
            normalization_notes=notes,
        )

    def _normalize_bank_record(self, raw: Dict[str, Any]) -> Record:
        raw_name = raw.get("statement_narrative", "")
        norm_name, notes = self.normalize_counterparty_with_notes(raw_name)
        canonical = self.map_canonical_entity(norm_name)
        if canonical:
            notes.append(f"Mapped to canonical entity '{canonical}'")

        return Record(
            id=str(raw["transaction_id"]),
            source=SourceType.BANK,
            date=self.normalize_date(raw["value_date"]),
            amount=self.normalize_amount(raw["settled_amount"]),
            currency=self.normalize_currency(raw.get("currency_code", "USD")),
            counterparty=norm_name,
            canonical_entity=canonical,
            reference_id=str(raw.get("ref_code", "")),
            raw_data=raw,
            normalization_notes=notes,
        )

    def _normalize_invoice_record(self, raw: Dict[str, Any]) -> Record:
        raw_name = raw.get("supplier_name", "")
        norm_name, notes = self.normalize_counterparty_with_notes(raw_name)
        canonical = self.map_canonical_entity(norm_name)
        if canonical:
            notes.append(f"Mapped to canonical entity '{canonical}'")

        return Record(
            id=str(raw["internal_invoice_id"]),
            source=SourceType.INVOICE,
            date=self.normalize_date(raw["invoice_date"]),
            amount=self.normalize_amount(raw["total_amount"]),
            currency=self.normalize_currency(raw.get("billing_currency", "USD")),
            counterparty=norm_name,
            canonical_entity=canonical,
            reference_id=str(raw.get("invoice_number", "")),
            raw_data=raw,
            normalization_notes=notes,
        )

    def normalize_counterparty_name(self, name: str) -> str:
        norm, _ = self.normalize_counterparty_with_notes(name)
        return norm

    def normalize_counterparty_with_notes(self, name: str) -> tuple[str, List[str]]:
        if not name or not isinstance(name, str):
            return "", []

        notes: List[str] = []
        cleaned = name.strip().upper()

        # Clean noise characters: asterisks, underscores, slashes, hash
        if re.search(r"[*_/#]", cleaned):
            cleaned = re.sub(r"[*_/#]", " ", cleaned)
            notes.append("Punctuation symbols replaced with space")

        # Collapse whitespace
        cleaned = " ".join(cleaned.split())

        return cleaned, notes

    def strip_legal_suffix(self, name: str) -> str:
        """Strip trailing corporate / legal suffixes safely."""
        if not name:
            return ""
        tokens = name.strip().upper().split()
        if len(tokens) > 1 and tokens[-1] in LEGAL_SUFFIXES:
            return " ".join(tokens[:-1])
        return name.strip().upper()

    def map_canonical_entity(self, name: str) -> Optional[str]:
        """Look up canonical entity from the controlled catalog.
        Checks exact alias, stripped legal suffix, and key containment.
        """
        if not name or not isinstance(name, str):
            return None

        upper = self.normalize_counterparty_name(name)
        if not upper:
            return None

        # Direct lookup
        if upper in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[upper]

        # Suffix-stripped lookup
        stripped = self.strip_legal_suffix(upper)
        if stripped in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[stripped]

        # Cleaned containment lookup
        clean = re.sub(r"[^A-Z0-9 ]", "", upper)
        for alias, canonical in _ALIAS_TO_CANONICAL.items():
            clean_alias = re.sub(r"[^A-Z0-9 ]", "", alias)
            if clean == clean_alias:
                return canonical

        return None

    def normalize_date(self, date_val: str) -> dt.date:
        if not date_val or not isinstance(date_val, str):
            return dt.date(1970, 1, 1)

        if "T" in date_val:
            date_val = date_val.split("T")[0]
        if "/" in date_val:
            parts = date_val.split("/")
            if len(parts) == 3:
                # MM/DD/YYYY
                try:
                    return dt.date(int(parts[2]), int(parts[0]), int(parts[1]))
                except ValueError:
                    pass
        try:
            return dt.date.fromisoformat(date_val)
        except ValueError:
            return dt.date(1970, 1, 1)

    def normalize_amount(self, amount: Any) -> float:
        try:
            # Handle currency strings like "$1,250.50" or "-1500"
            if isinstance(amount, str):
                cleaned = re.sub(r"[\$,]", "", amount.strip())
                return abs(float(cleaned))
            return abs(float(amount))
        except (ValueError, TypeError):
            return 0.0

    def normalize_currency(self, currency: str) -> str:
        return currency.strip().upper() if currency else "USD"
