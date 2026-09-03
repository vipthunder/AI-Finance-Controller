from __future__ import annotations
from typing import Set, List, Optional

from src.schemas.candidates import CandidatePair
from src.schemas.validation import ValidationResult
from src.config import get_config


class DeterministicValidator:
    """Every proposed match passes through the same deterministic checks:
    amount tolerance, date tolerance, currency consistency, duplicate
    conflict, and basic accounting constraints.

    Thresholds are loaded from the centralized configuration (configs/thresholds.yaml).
    """

    def __init__(
        self,
        max_amount_abs: Optional[float] = None,
        max_amount_pct: Optional[float] = None,
        max_date_days: Optional[int] = None,
    ):
        cfg = get_config().validator
        self.max_amount_abs = max_amount_abs if max_amount_abs is not None else cfg.max_amount_abs_tolerance
        self.max_amount_pct = max_amount_pct if max_amount_pct is not None else cfg.max_amount_pct_tolerance
        self.max_date_days = max_date_days if max_date_days is not None else cfg.max_date_tolerance_days

    def validate(
        self,
        pair: CandidatePair,
        committed_keys: Set[str],
        duplicate_map: Optional[Dict[str, str]] = None,
    ) -> ValidationResult:
        r1 = pair.record_a
        r2 = pair.record_b

        failed_checks: List[str] = []
        notes: List[str] = []

        # 1) Duplicate-commit check
        if r1.summary_key() in committed_keys:
            failed_checks.append(f"{r1.summary_key()} already committed")
        if r2.summary_key() in committed_keys:
            failed_checks.append(f"{r2.summary_key()} already committed")

        # 1b) Intra-source duplicate check (prevents duplicate clones from committing)
        if duplicate_map:
            if r1.summary_key() in duplicate_map:
                failed_checks.append(
                    f"Intra-source duplicate: {r1.summary_key()} is a duplicate clone of {duplicate_map[r1.summary_key()]}"
                )
            if r2.summary_key() in duplicate_map:
                failed_checks.append(
                    f"Intra-source duplicate: {r2.summary_key()} is a duplicate clone of {duplicate_map[r2.summary_key()]}"
                )

        # 2) Currency consistency
        if r1.currency != r2.currency:
            failed_checks.append(
                f"Currency mismatch: {r1.currency} vs {r2.currency}"
            )

        # 3) Amount tolerance — both absolute and percentage
        amount_diff = abs(r1.amount - r2.amount)
        max_amount = max(r1.amount, r2.amount)
        pct_diff = (amount_diff / max_amount) if max_amount > 0 else 0.0

        if amount_diff > self.max_amount_abs:
            failed_checks.append(
                f"Amount diff ${amount_diff:.2f} exceeds abs tolerance ${self.max_amount_abs:.2f}"
            )
        elif pct_diff > self.max_amount_pct:
            failed_checks.append(
                f"Amount diff {pct_diff:.2%} exceeds pct tolerance {self.max_amount_pct:.2%}"
            )
        else:
            notes.append(f"Amount diff ${amount_diff:.2f} ({pct_diff:.2%}) within tolerance")

        # 4) Date tolerance
        date_diff = abs((r1.date - r2.date).days)
        if date_diff > self.max_date_days:
            failed_checks.append(
                f"Date diff {date_diff} days exceeds tolerance {self.max_date_days} days"
            )
        else:
            notes.append(f"Date diff {date_diff} days within tolerance")

        # 5) Same-source guard (should never match records from the same source)
        if r1.source == r2.source:
            failed_checks.append(
                f"Same source: both from {r1.source.value}"
            )

        is_valid = len(failed_checks) == 0
        return ValidationResult(
            is_valid=is_valid,
            failed_checks=failed_checks,
            notes=notes,
            details={
                "amount_diff": round(amount_diff, 2),
                "amount_pct_diff": round(pct_diff, 4),
                "date_diff_days": date_diff,
            },
        )
