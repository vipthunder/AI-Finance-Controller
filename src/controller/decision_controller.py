from __future__ import annotations
from typing import Tuple, Dict, Any

from src.schemas.candidates import CandidatePair
from src.schemas.decisions import Decision
from src.schemas.enums import ResolutionStatus, ExceptionReason
from src.schemas.validation import ValidationResult


class DecisionController:
    """Authoritative decision controller for committing valid matches,
    recording superseded candidates, and creating explicit terminal decisions.
    """

    def __init__(self):
        self._decisions: Dict[str, Decision] = {}

    def commit_match(self, pair: CandidatePair, validation_result: ValidationResult) -> Tuple[Decision, Decision]:
        ka = pair.record_a.summary_key()
        kb = pair.record_b.summary_key()

        if ka in self._decisions and self._decisions[ka].status == ResolutionStatus.RESOLVED:
            d1 = self._decisions[ka]
            d1.stage_resolved = pair.stage.value
            if kb not in d1.matched_with_ids:
                d1.matched_with_ids.append(kb)
        else:
            d1 = Decision(
                record_id=ka,
                status=ResolutionStatus.RESOLVED,
                stage_resolved=pair.stage.value,
                matched_with_ids=[kb],
                confidence=pair.score,
                rationale="Deterministic and threshold rules passed",
                exception_reason=None,
                validation_result=validation_result,
                raw_scores={"composite": pair.feature_scores.composite_score},
                metadata={
                    "matched_stage": pair.stage.value,
                    "amount": pair.record_a.amount,
                    "currency": pair.record_a.currency,
                },
            )
            self._decisions[ka] = d1

        if kb in self._decisions and self._decisions[kb].status == ResolutionStatus.RESOLVED:
            d2 = self._decisions[kb]
            d2.stage_resolved = pair.stage.value
            if ka not in d2.matched_with_ids:
                d2.matched_with_ids.append(ka)
        else:
            d2 = Decision(
                record_id=kb,
                status=ResolutionStatus.RESOLVED,
                stage_resolved=pair.stage.value,
                matched_with_ids=[ka],
                confidence=pair.score,
                rationale="Deterministic and threshold rules passed",
                exception_reason=None,
                validation_result=validation_result,
                raw_scores={"composite": pair.feature_scores.composite_score},
                metadata={
                    "matched_stage": pair.stage.value,
                    "amount": pair.record_b.amount,
                    "currency": pair.record_b.currency,
                },
            )
            self._decisions[kb] = d2

        return d1, d2

    def record_superseded(
        self,
        pair: CandidatePair,
        conflicting_record_id: str,
        reason: str,
        winning_pair: Optional[CandidatePair] = None,
    ) -> Tuple[Decision, Decision]:
        """Explicitly record a candidate pair that was superseded by an existing commitment."""
        winning_cand = winning_pair.pair_key if winning_pair else conflicting_record_id
        d1 = Decision(
            record_id=pair.record_a.summary_key(),
            status=ResolutionStatus.SUPERSEDED,
            stage_resolved=pair.stage.value,
            matched_with_ids=[pair.record_b.summary_key()],
            confidence=pair.score,
            rationale=reason,
            exception_reason=ExceptionReason.SUPERSEDED,
            validation_result=None,
            raw_scores={"composite": pair.feature_scores.composite_score},
            metadata={
                "proposal_id": pair.pair_key,
                "source_records": [pair.record_a.summary_key(), pair.record_b.summary_key()],
                "losing_candidate": pair.pair_key,
                "winning_candidate": winning_cand,
                "conflicting_record": conflicting_record_id,
                "winning_decision": "RESOLVED",
                "candidate_score": pair.score,
                "stage": pair.stage.value,
            },
        )

        d2 = Decision(
            record_id=pair.record_b.summary_key(),
            status=ResolutionStatus.SUPERSEDED,
            stage_resolved=pair.stage.value,
            matched_with_ids=[pair.record_a.summary_key()],
            confidence=pair.score,
            rationale=reason,
            exception_reason=ExceptionReason.SUPERSEDED,
            validation_result=None,
            raw_scores={"composite": pair.feature_scores.composite_score},
            metadata={
                "proposal_id": pair.pair_key,
                "source_records": [pair.record_a.summary_key(), pair.record_b.summary_key()],
                "losing_candidate": pair.pair_key,
                "winning_candidate": winning_cand,
                "conflicting_record": conflicting_record_id,
                "winning_decision": "RESOLVED",
                "candidate_score": pair.score,
                "stage": pair.stage.value,
            },
        )

        return d1, d2

    def record_validation_failed(
        self,
        pair: CandidatePair,
        validation_result: ValidationResult,
    ) -> Tuple[Decision, Decision]:
        """Explicitly record a candidate pair that failed deterministic validation."""
        reason_str = f"Validation failed: {', '.join(validation_result.failed_checks)}"
        d1 = Decision(
            record_id=pair.record_a.summary_key(),
            status=ResolutionStatus.EXCEPTION,
            stage_resolved=pair.stage.value,
            matched_with_ids=[pair.record_b.summary_key()],
            confidence=pair.score,
            rationale=reason_str,
            exception_reason=ExceptionReason.VALIDATION_FAILED,
            validation_result=validation_result,
            raw_scores={"composite": pair.feature_scores.composite_score},
            metadata={"failed_checks": validation_result.failed_checks},
        )
        d2 = Decision(
            record_id=pair.record_b.summary_key(),
            status=ResolutionStatus.EXCEPTION,
            stage_resolved=pair.stage.value,
            matched_with_ids=[pair.record_a.summary_key()],
            confidence=pair.score,
            rationale=reason_str,
            exception_reason=ExceptionReason.VALIDATION_FAILED,
            validation_result=validation_result,
            raw_scores={"composite": pair.feature_scores.composite_score},
            metadata={"failed_checks": validation_result.failed_checks},
        )
        return d1, d2
