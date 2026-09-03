from __future__ import annotations
from typing import List, Dict, Set, Tuple, Optional
from rapidfuzz import fuzz

from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.enums import MatchStage
from src.config import get_config


class CandidateGenerator:
    """Multi-signal candidate generation with systematic blocking.
    Combines:
      1. Reference identifier matching
      2. Canonical entity + date/amount window
      3. Strict proximity blocking (amount/date tolerances)
    Deduplicates candidates and records blocking miss reasons for records
    that fail to generate candidate pairs.
    """

    def __init__(self, config: Optional[Any] = None):
        self.config = config or get_config().candidate_generation
        self.blocking_miss_reasons: Dict[str, List[str]] = {}

    def generate(self, records: List[Record]) -> List[CandidatePair]:
        """Generate deduplicated candidate pairs across input records using multi-signal blocking."""
        candidates_map: Dict[Tuple[str, str], CandidatePair] = {}
        self.blocking_miss_reasons.clear()

        # Initialize miss reason tracking for every record
        for r in records:
            self.blocking_miss_reasons[r.summary_key()] = []

        max_date_days = self.config.max_date_diff_days
        max_pct_diff = self.config.max_amount_pct_diff
        max_abs_diff = self.config.max_amount_abs_diff

        n = len(records)
        for i in range(n):
            for j in range(i + 1, n):
                r1 = records[i]
                r2 = records[j]

                # Rule 1: Cross-source only
                if r1.source == r2.source:
                    continue

                # Rule 2: Currency restriction check
                if r1.currency != r2.currency:
                    self.blocking_miss_reasons[r1.summary_key()].append(f"Currency mismatch with {r2.summary_key()}")
                    self.blocking_miss_reasons[r2.summary_key()].append(f"Currency mismatch with {r1.summary_key()}")
                    continue

                amount_diff = abs(r1.amount - r2.amount)
                max_amount = max(r1.amount, r2.amount)
                pct_diff = (amount_diff / max_amount) if max_amount > 0 else 0.0
                date_diff = abs((r1.date - r2.date).days)

                matched_signals: List[str] = []

                # Signal 1: Reference Identifier Match
                ref1 = (r1.reference_id or "").strip().upper()
                ref2 = (r2.reference_id or "").strip().upper()
                if self.config.enable_reference_blocking and ref1 and ref2:
                    if ref1 == ref2 or (len(ref1) >= 6 and (ref1 in ref2 or ref2 in ref1)):
                        # Reference match is a primary identifier; valid across arbitrary date lag
                        matched_signals.append("reference_match")

                # Signal 2: Canonical Entity Match
                c1 = r1.canonical_entity
                c2 = r2.canonical_entity
                if self.config.enable_entity_blocking and c1 and c2 and c1 == c2:
                    # Canonical enterprise entities share wide settlement window (up to 3x standard)
                    if date_diff <= max_date_days * 3:
                        matched_signals.append("canonical_entity_match")

                # Signal 3: Proximity Window
                within_amount = (pct_diff <= max_pct_diff) or (amount_diff <= max_abs_diff)
                within_date = date_diff <= max_date_days
                if self.config.enable_proximity_blocking:
                    if within_amount and within_date:
                        matched_signals.append("proximity_window")

                if matched_signals:
                    pair_key = tuple(sorted([r1.summary_key(), r2.summary_key()]))
                    if pair_key not in candidates_map:
                        pair = CandidatePair(
                            record_a=r1,
                            record_b=r2,
                            score=0.0,
                            feature_scores=FeatureScores(
                                name_similarity=0.0,
                                amount_proximity=max(0.0, 1.0 - pct_diff),
                                date_proximity=max(0.0, 1.0 - (date_diff / 14.0)),
                                composite_score=0.0,
                                amount_diff=amount_diff,
                                date_diff_days=date_diff,
                            ),
                            matched_on=matched_signals,
                            stage=MatchStage.FUZZY_DIRECT,
                            metadata={"blocking_signals": matched_signals},
                        )
                        candidates_map[pair_key] = pair
                    else:
                        for s in matched_signals:
                            if s not in candidates_map[pair_key].matched_on:
                                candidates_map[pair_key].matched_on.append(s)
                else:
                    # Cleanly record blocking miss reasons ONLY when all signals fail
                    if not within_date:
                        self.blocking_miss_reasons[r1.summary_key()].append(f"Date lag {date_diff}d with {r2.summary_key()}")
                        self.blocking_miss_reasons[r2.summary_key()].append(f"Date lag {date_diff}d with {r1.summary_key()}")
                    if not within_amount:
                        self.blocking_miss_reasons[r1.summary_key()].append(f"Amount diff ${amount_diff:.2f} ({pct_diff:.1%}) with {r2.summary_key()}")
                        self.blocking_miss_reasons[r2.summary_key()].append(f"Amount diff ${amount_diff:.2f} ({pct_diff:.1%}) with {r1.summary_key()}")

        return list(candidates_map.values())

    def get_miss_reasons(self, record_id: str) -> List[str]:
        """Return blocking miss reasons for a specific record."""
        return self.blocking_miss_reasons.get(record_id, [])
