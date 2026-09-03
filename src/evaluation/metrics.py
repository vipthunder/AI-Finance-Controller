from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class EvaluationMetrics:
    """All metrics required by the 6-category reconciliation scorecard."""

    # ──── CORE COUNTS ────
    total_records: int = 0
    total_ground_truth_pairs: int = 0
    proposed_pairs_count: int = 0

    # ──── RECONCILIATION ────
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    raw_candidate_recall: float = 0.0      # GT pairs found in raw candidate set / total GT pairs
    exact_match_coverage: float = 0.0      # GT pairs found in exact matches / total GT pairs
    fuzzy_resolution_coverage: float = 0.0 # GT pairs resolved via direct fuzzy matching / total GT pairs
    ai_resolution_coverage: float = 0.0    # GT pairs resolved via AI verification / total GT pairs
    final_reconciliation_recall: float = 0.0 # GT pairs ultimately resolved / total GT pairs
    candidate_recall: float = 0.0          # Backward-compatibility alias
    false_match_rate: float = 0.0

    # ──── AUTOMATION (exact + fuzzy, no AI) ────
    match_rate: float = 0.0
    exact_matches_count: int = 0
    fuzzy_matches_count: int = 0
    auto_resolution_rate: float = 0.0       # (exact + fuzzy) / total_records
    auto_resolution_precision: float = 0.0  # TP among auto-resolved / auto-resolved total
    auto_resolution_recall: float = 0.0     # auto-resolved TP / total GT pairs

    # ──── AI ────
    ai_matches_count: int = 0
    ai_invocations_count: int = 0
    ai_accepted_count: int = 0
    ai_rejected_count: int = 0
    ai_validation_failed_count: int = 0
    ai_superseded_count: int = 0
    ai_failed_count: int = 0        # AI invocation failed completely
    ai_committed_count: int = 0     # AI-accepted AND validation-passed AND not superseded
    ai_provider_mode: str = "MOCK"
    ai_model: str = "gemini-1.5-flash"
    ai_latency_ms: float = 0.0
    
    ai_usage_rate: float = 0.0
    ai_acceptance_rate: float = 0.0
    ai_commitment_rate: float = 0.0
    ai_supersession_rate: float = 0.0
    ai_validation_failure_rate: float = 0.0
    
    ai_recommendation_precision: float = 0.0  # Correct AI-accepted TP / all AI-accepted recommendations
    ai_recommendation_recall: float = 0.0     # Correct AI-accepted TP / AI-eligible GT relationships
    ai_contribution_recall: float = 0.0       # Correct AI-accepted TP / all GT relationships
    ai_precision: float = 0.0                 # Backward-compatibility alias
    ai_recall: float = 0.0                    # Backward-compatibility alias

    # ──── EXCEPTIONS ────
    automation_rate: float = 0.0
    exceptions_count: int = 0
    exceptions_by_reason: Dict[str, int] = field(default_factory=dict)
    exception_precision: float = 0.0    # correctly-excepted / total exceptions
    exception_recall: float = 0.0       # correctly-excepted / total true non-matches

    # ──── FINANCIAL ────
    # Source-level sums (raw currency totals across ledger, bank, invoice)
    total_value: float = 0.0
    matched_value: float = 0.0
    exception_value: float = 0.0
    incorrectly_matched_value: float = 0.0
    value_reconciliation_rate: float = 0.0  # matched_value / total_value

    # Canonical Business Transaction Level (de-duplicated across systems)
    canonical_transactions: int = 0
    fully_reconciled_transactions: int = 0
    partially_reconciled_transactions: int = 0
    unresolved_transactions: int = 0
    fully_reconciled_tx_rate: float = 0.0
    partial_transaction_coverage: float = 0.0

    total_business_value: float = 0.0
    total_canonical_value: float = 0.0
    fully_reconciled_value: float = 0.0
    partially_reconciled_value: float = 0.0
    reconciled_business_value: float = 0.0
    exception_business_value: float = 0.0
    unresolved_canonical_value: float = 0.0
    exception_exposure_value: float = 0.0
    auto_resolved_value: float = 0.0
    business_value_reconciliation_rate: float = 0.0
    full_value_reconciliation_rate: float = 0.0
    financial_value_coverage: float = 0.0

    # AI Eligibility
    ai_eligible_candidates: int = 0
    ai_eligible_gt_relationships: int = 0

    # ──── SAFETY ────
    duplicate_escape_rate: float = 0.0  # records committed > 1 time / total records
    critical_error_rate: float = 0.0    # critical errors (currency, same-source) / total proposed
    silent_drop_count: int = 0          # records with no terminal decision

    # ──── PERFORMANCE ────
    processing_time_ms: float = 0.0
    throughput_records_per_sec: float = 0.0

    # ──── DIAGNOSTICS & BREAKDOWN ────
    fn_diagnostics: Dict[str, int] = field(default_factory=dict)
    discrepancy_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
