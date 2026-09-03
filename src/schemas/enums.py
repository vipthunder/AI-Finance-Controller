from __future__ import annotations
from enum import Enum

class SourceType(str, Enum):
    LEDGER = "LEDGER"
    BANK = "BANK"
    INVOICE = "INVOICE"

class RecordStatus(str, Enum):
    UNPROCESSED = "UNPROCESSED"
    EXACT_MATCHED = "EXACT_MATCHED"
    FUZZY_MATCHED = "FUZZY_MATCHED"
    AI_MATCHED = "AI_MATCHED"
    RESOLVED = "RESOLVED"
    EXCEPTION = "EXCEPTION"

class TransactionDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

class MatchStage(str, Enum):
    EXACT = "EXACT"
    FUZZY_DIRECT = "FUZZY_DIRECT"
    AI_VERIFIED = "AI_VERIFIED"
    UNMATCHED = "UNMATCHED"

class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    EXCEPTION = "EXCEPTION"
    SUPERSEDED = "SUPERSEDED"

class ExceptionReason(str, Enum):
    NO_CANDIDATE = "NO_CANDIDATE"
    AMBIGUOUS = "AMBIGUOUS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LIKELY_DUPLICATE = "LIKELY_DUPLICATE"
    SOURCE_MISSING = "SOURCE_MISSING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SUPERSEDED = "SUPERSEDED"
