from __future__ import annotations
from typing import List
from rapidfuzz import fuzz

from src.schemas.candidates import CandidatePair

class FuzzyScorer:
    def score_candidates(self, candidates: List[CandidatePair]) -> List[CandidatePair]:
        scored_candidates = []
        for pair in candidates:
            r1 = pair.record_a
            r2 = pair.record_b
            
            name_sim = fuzz.token_sort_ratio(r1.counterparty or "", r2.counterparty or "") / 100.0
            
            max_amount = max(r1.amount, r2.amount)
            if max_amount > 0:
                amount_prox = max(0.0, 1.0 - (pair.feature_scores.amount_diff / max_amount))
            else:
                amount_prox = 1.0
                
            date_prox = max(0.0, 1.0 - (pair.feature_scores.date_diff_days / 14.0))
            
            composite = (name_sim * 0.4) + (amount_prox * 0.4) + (date_prox * 0.2)
            
            pair.feature_scores.name_similarity = name_sim
            pair.feature_scores.amount_proximity = amount_prox
            pair.feature_scores.date_proximity = date_prox
            pair.feature_scores.composite_score = composite
            pair.score = composite
            
            scored_candidates.append(pair)
            
        scored_candidates.sort(key=lambda p: p.score, reverse=True)
        return scored_candidates
