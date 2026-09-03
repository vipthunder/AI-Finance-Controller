from __future__ import annotations
from typing import List, Tuple, Dict, Set
from collections import defaultdict

from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.enums import MatchStage

class ExactMatcher:
    def match(self, records: List[Record]) -> Tuple[List[CandidatePair], List[Record]]:
        buckets: Dict[str, List[Record]] = defaultdict(list)
        for r in records:
            key = f"{r.date.isoformat()}|{r.amount:.2f}|{r.currency}"
            buckets[key].append(r)
        
        candidates = []
        matched_keys: Set[str] = set()
        
        for key, bucket_records in buckets.items():
            if len(bucket_records) < 2:
                continue
            
            for i in range(len(bucket_records)):
                for j in range(i + 1, len(bucket_records)):
                    r1 = bucket_records[i]
                    r2 = bucket_records[j]
                    if r1.source != r2.source and r1.counterparty == r2.counterparty and r1.counterparty:
                        if r1.summary_key() in matched_keys or r2.summary_key() in matched_keys:
                            continue
                        
                        pair = CandidatePair(
                            record_a=r1,
                            record_b=r2,
                            score=1.0,
                            feature_scores=FeatureScores(
                                name_similarity=1.0,
                                amount_proximity=1.0,
                                date_proximity=1.0,
                                composite_score=1.0,
                                amount_diff=0.0,
                                date_diff_days=0
                            ),
                            matched_on=["date", "amount", "currency", "counterparty"],
                            stage=MatchStage.EXACT,
                            metadata={}
                        )
                        candidates.append(pair)
                        matched_keys.add(r1.summary_key())
                        matched_keys.add(r2.summary_key())
        
        unmatched = [r for r in records if r.summary_key() not in matched_keys]
        return candidates, unmatched
