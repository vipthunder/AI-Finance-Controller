from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .enums import ResolutionStatus, ExceptionReason
from .validation import ValidationResult

class Decision(BaseModel):
    record_id: str
    status: ResolutionStatus
    stage_resolved: Optional[str] = None
    matched_with_ids: List[str] = Field(default_factory=list)
    confidence: float
    rationale: str
    exception_reason: Optional[ExceptionReason] = None
    validation_result: Optional[ValidationResult] = None
    raw_scores: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
