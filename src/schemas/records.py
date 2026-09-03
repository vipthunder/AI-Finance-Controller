from __future__ import annotations
import datetime as dt
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from .enums import SourceType, RecordStatus, TransactionDirection

class Record(BaseModel):
    id: str
    source: SourceType
    date: dt.date
    amount: float
    currency: str = 'USD'
    counterparty: str
    direction: TransactionDirection = TransactionDirection.DEBIT
    reference_id: Optional[str] = None
    canonical_entity: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    status: RecordStatus = RecordStatus.UNPROCESSED
    normalization_notes: List[str] = Field(default_factory=list)

    def summary_key(self) -> str:
        return f"{self.source.value}:{self.id}"
