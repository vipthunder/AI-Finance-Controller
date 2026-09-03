from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.schemas.enums import ExceptionReason


class HumanEscalationItem(BaseModel):
    exception_id: str
    record_id: str
    source: str
    source_record_ids: List[str] = Field(default_factory=list)
    date: str
    amount: float
    currency: str
    counterparty: str
    reason_code: str
    confidence: float
    explanation: str
    evidence: List[str] = Field(default_factory=list)
    closest_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    failed_validation_checks: List[str] = Field(default_factory=list)
    suggested_action: str = ""
    stage: str = "EXCEPTION_INVESTIGATION"
