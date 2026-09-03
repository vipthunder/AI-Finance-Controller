from __future__ import annotations
import datetime as dt
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AuditEntry(BaseModel):
    timestamp: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    record_id: str
    stage: str
    event: str
    input_state: Dict[str, Any] = Field(default_factory=dict)
    decision: str
    score: Optional[float] = None
    threshold_applied: Optional[float] = None
    rationale: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AuditTrail(BaseModel):
    entries: List[AuditEntry] = Field(default_factory=list)

    def append(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def for_record(self, record_id: str) -> List[AuditEntry]:
        return [entry for entry in self.entries if entry.record_id == record_id]

    def for_stage(self, stage: str) -> List[AuditEntry]:
        return [entry for entry in self.entries if entry.stage == stage]
