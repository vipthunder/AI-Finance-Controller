from __future__ import annotations
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from .records import Record
from .enums import MatchStage

class FeatureScores(BaseModel):
    name_similarity: float
    amount_proximity: float
    date_proximity: float
    composite_score: float
    amount_diff: float
    date_diff_days: int

class CandidatePair(BaseModel):
    record_a: Record
    record_b: Record
    score: float
    feature_scores: FeatureScores
    matched_on: List[str]
    stage: MatchStage
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pair_key(self) -> str:
        key_a = self.record_a.summary_key()
        key_b = self.record_b.summary_key()
        return "::".join(sorted([key_a, key_b]))
