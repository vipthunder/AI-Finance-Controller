from __future__ import annotations

import json
import datetime as dt
from typing import List, Dict, Any, Optional

from src.schemas.audit import AuditEntry, AuditTrail


class AuditLogger:
    def __init__(self, audit_trail: Optional[AuditTrail] = None) -> None:
        self.trail = audit_trail or AuditTrail(entries=[])

    def log_event(
        self,
        record_id: str,
        stage: str,
        event: str,
        decision: str,
        input_state: Dict[str, Any],
        score: float,
        threshold_applied: Optional[float],
        rationale: str,
        metadata: Dict[str, Any],
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=dt.datetime.now(dt.UTC),
            record_id=record_id,
            stage=stage,
            event=event,
            decision=decision,
            input_state=input_state,
            score=score,
            threshold_applied=threshold_applied,
            rationale=rationale,
            metadata=metadata,
        )
        self.trail.append(entry)
        return entry

    def get_trail(self) -> AuditTrail:
        return self.trail

    def get_entries_for_record(self, record_id: str) -> List[AuditEntry]:
        return self.trail.for_record(record_id)

    def get_entries_for_stage(self, stage: str) -> List[AuditEntry]:
        return self.trail.for_stage(stage)

    def export_json(self, filepath: str) -> None:
        data = [e.model_dump() for e in self.trail.entries]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
