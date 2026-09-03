from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional

@dataclass(frozen=True)
class GroundTruthTransaction:
    gt_id: str
    date: dt.date
    base_amount: float
    base_currency: str
    canonical_counterparty: str
    category: str
    description: str
    source_record_ids: Dict[str, List[str]] = field(default_factory=dict)

class GroundTruthStore:
    def __init__(self) -> None:
        self._transactions: Dict[str, GroundTruthTransaction] = {}
        self._record_to_gt: Dict[Tuple[str, str], str] = {}
        self._duplicate_record_ids: Set[Tuple[str, str]] = set()
        self._singleton_record_ids: Set[Tuple[str, str]] = set()

    def add_transaction(self, tx: GroundTruthTransaction) -> None:
        self._transactions[tx.gt_id] = tx
        for source, ids in tx.source_record_ids.items():
            for record_id in ids:
                self._record_to_gt[(source, record_id)] = tx.gt_id
                
    def get_gt_id(self, source: str, record_id: str) -> Optional[str]:
        return self._record_to_gt.get((source, record_id))

    def get_transaction(self, gt_id: str) -> Optional[GroundTruthTransaction]:
        return self._transactions.get(gt_id)

    def is_true_match(self, src_a: str, id_a: str, src_b: str, id_b: str) -> bool:
        gt_a = self.get_gt_id(src_a, id_a)
        gt_b = self.get_gt_id(src_b, id_b)
        return bool(gt_a and gt_b and gt_a == gt_b)

    def get_all_ground_truth_pairs(self) -> Set[Tuple[str, str]]:
        pairs: Set[Tuple[str, str]] = set()
        for tx in self._transactions.values():
            all_records = []
            for src, ids in tx.source_record_ids.items():
                for rid in ids:
                    all_records.append(f"{src}:{rid}")
            for i in range(len(all_records)):
                for j in range(i + 1, len(all_records)):
                    pairs.add(tuple(sorted([all_records[i], all_records[j]])))
        return pairs

    @property
    def total_transactions(self) -> int:
        return len(self._transactions)
