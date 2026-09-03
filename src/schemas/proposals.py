from __future__ import annotations
from pydantic import BaseModel
from .candidates import CandidatePair
from .enums import MatchStage

class MatchProposal(BaseModel):
    pair: CandidatePair
    proposed_by: MatchStage
    confidence: float
    rationale: str
