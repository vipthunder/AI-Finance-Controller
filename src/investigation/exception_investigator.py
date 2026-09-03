from __future__ import annotations
from typing import List, Dict, Tuple
from pydantic import BaseModel

from src.schemas.records import Record
from src.schemas.candidates import CandidatePair
from src.schemas.decisions import Decision
from src.schemas.enums import ResolutionStatus, ExceptionReason
from src.schemas.validation import ValidationResult
from src.schemas.exceptions import HumanEscalationItem


class ExceptionInvestigator:
    """Assigns reason codes and packages exceptions for human review."""

    def investigate(
        self,
        record: Record,
        candidate_pairs: List[CandidatePair],
        validation_failures: List[Tuple[CandidatePair, ValidationResult]],
    ) -> Decision:
        reason = self._determine_reason(record, candidate_pairs, validation_failures)
        rationale = self._build_rationale(reason, candidate_pairs, validation_failures)

        return Decision(
            record_id=record.summary_key(),
            status=ResolutionStatus.EXCEPTION,
            stage_resolved=None,
            matched_with_ids=[],
            confidence=0.0,
            rationale=rationale,
            exception_reason=reason,
            validation_result=None,
            raw_scores={},
            metadata={},
        )

    def _determine_reason(
        self,
        record: Record,
        candidate_pairs: List[CandidatePair],
        validation_failures: List[Tuple[CandidatePair, ValidationResult]],
    ) -> ExceptionReason:
        if validation_failures:
            return ExceptionReason.VALIDATION_FAILED

        if not candidate_pairs:
            return ExceptionReason.NO_CANDIDATE

        scores = [p.score for p in candidate_pairs]
        top_score = max(scores) if scores else 0.0

        # Multiple candidates with similar scores → ambiguous
        close_scores = [s for s in scores if abs(s - top_score) < 0.10]
        if len(close_scores) >= 2:
            return ExceptionReason.AMBIGUOUS

        if top_score < 0.50:
            return ExceptionReason.LOW_CONFIDENCE

        return ExceptionReason.LOW_CONFIDENCE

    def _build_rationale(
        self,
        reason: ExceptionReason,
        candidate_pairs: List[CandidatePair],
        validation_failures: List[Tuple[CandidatePair, ValidationResult]],
    ) -> str:
        parts = [f"Exception: {reason.value}."]
        if validation_failures:
            checks = validation_failures[0][1].failed_checks
            parts.append(f"Failed checks: {', '.join(checks)}.")
        if candidate_pairs:
            parts.append(f"{len(candidate_pairs)} candidate(s) found, top score={max(p.score for p in candidate_pairs):.2f}.")
        return " ".join(parts)

    def package_escalation_queue(
        self,
        exception_decisions: List[Decision],
        records_by_key: Dict[str, Record],
        all_candidates: List[CandidatePair] | None = None,
    ) -> List[HumanEscalationItem]:
        all_candidates = all_candidates or []
        queue: List[HumanEscalationItem] = []

        for dec in exception_decisions:
            record = records_by_key.get(dec.record_id)
            closest = []
            if all_candidates:
                related = [
                    p for p in all_candidates
                    if p.record_a.summary_key() == dec.record_id
                    or p.record_b.summary_key() == dec.record_id
                ]
                for p in sorted(related, key=lambda x: -x.score)[:3]:
                    other = p.record_b if p.record_a.summary_key() == dec.record_id else p.record_a
                    closest.append({
                        "record_id": other.summary_key(),
                        "score": round(p.score, 4),
                        "counterparty": other.counterparty,
                    })

            evidence = [dec.rationale]
            if dec.validation_result:
                evidence.extend(dec.validation_result.failed_checks)

            queue.append(HumanEscalationItem(
                exception_id=f"EXC-{dec.record_id.replace(':', '-')}",
                record_id=dec.record_id,
                source=record.source.value if record else "UNKNOWN",
                source_record_ids=[dec.record_id],
                date=record.date.isoformat() if record else "",
                amount=record.amount if record else 0.0,
                currency=record.currency if record else "USD",
                counterparty=record.counterparty if record else "",
                reason_code=dec.exception_reason.value if dec.exception_reason else "UNKNOWN",
                confidence=dec.confidence,
                explanation=dec.rationale,
                evidence=evidence,
                closest_candidates=closest,
                failed_validation_checks=dec.validation_result.failed_checks if dec.validation_result else [],
                suggested_action=self._suggest_action(dec.exception_reason),
                stage=dec.stage_resolved or "EXCEPTION_INVESTIGATION",
            ))

        return queue

    @staticmethod
    def _suggest_action(reason: ExceptionReason | None) -> str:
        suggestions = {
            ExceptionReason.NO_CANDIDATE: "Search for missing source records or confirm write-off.",
            ExceptionReason.AMBIGUOUS: "Review top candidates and manually resolve.",
            ExceptionReason.LOW_CONFIDENCE: "Verify counterparty and amount with vendor.",
            ExceptionReason.LIKELY_DUPLICATE: "Check for duplicate entry and void if confirmed.",
            ExceptionReason.SOURCE_MISSING: "Confirm record exists in source system.",
            ExceptionReason.VALIDATION_FAILED: "Review failed validation checks and correct data.",
        }
        return suggestions.get(reason, "Manual review required.")
