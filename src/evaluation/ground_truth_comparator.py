from __future__ import annotations
from typing import Set, Optional, Tuple
from src.schemas.ground_truth import GroundTruthStore


class GroundTruthComparator:
    """Thin wrapper over GroundTruthStore for evaluator use."""

    def __init__(self, ground_truth_store: GroundTruthStore):
        self.ground_truth_store = ground_truth_store

    def compare_pair(self, src_a: str, id_a: str, src_b: str, id_b: str) -> bool:
        return self.ground_truth_store.is_true_match(src_a, id_a, src_b, id_b)

    def get_all_true_pairs(self) -> Set[Tuple[str, str]]:
        return self.ground_truth_store.get_all_ground_truth_pairs()
