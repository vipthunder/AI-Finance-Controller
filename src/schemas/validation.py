from __future__ import annotations
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class ValidationResult(BaseModel):
    is_valid: bool
    failed_checks: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
