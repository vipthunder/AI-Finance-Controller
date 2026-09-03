from __future__ import annotations
import time
from typing import List, Dict, Any, Tuple, Set, Optional
from pydantic import BaseModel, Field

from src.schemas.records import Record
from src.schemas.candidates import CandidatePair
from src.schemas.decisions import Decision
from src.schemas.exceptions import HumanEscalationItem
from src.schemas.enums import MatchStage, ResolutionStatus, ExceptionReason
from src.schemas.audit import AuditTrail
from src.ingestion.normalizer import RecordNormalizer
from src.matching.exact_matcher import ExactMatcher
from src.matching.candidate_generator import CandidateGenerator
from src.matching.fuzzy_matcher import FuzzyScorer
from src.verification.ai_verifier import AIVerifier
from src.validation.deterministic_validator import DeterministicValidator
from src.controller.decision_controller import DecisionController
from src.investigation.exception_investigator import ExceptionInvestigator
from src.audit.audit_logger import AuditLogger
from src.config import get_config


class PipelineResult(BaseModel):
    records: List[Record]
    decisions: List[Decision]
    audit_trail: AuditTrail
    processing_time_ms: float

    # Stage-level stats for the evaluator
    exact_match_count: int = 0
    fuzzy_match_count: int = 0
    ai_match_count: int = 0
    ai_invocations: int = 0
    ai_accepted: int = 0
    ai_rejected: int = 0
    ai_superseded_count: int = 0
    ai_validation_failed_count: int = 0
    ai_failed_count: int = 0
    ai_provider_mode: str = "MOCK"

    # Candidate pair keys for candidate-recall computation
    raw_candidate_pair_keys: List[Tuple[str, str]] = []
    exact_match_pair_keys: List[Tuple[str, str]] = []
    ai_candidate_pair_keys: List[Tuple[str, str]] = []
    ai_verified_pair_keys: List[Tuple[str, str]] = []

    @property
    def candidate_pair_keys(self) -> List[Tuple[str, str]]:
        return self.raw_candidate_pair_keys

    @property
    def ai_committed_count(self) -> int:
        return self.ai_match_count

    # Validation failure details for safety metrics
    validation_failure_details: List[Dict[str, Any]] = []
    critical_error_count: int = 0

    # Explicitly tracked superseded candidates and packaged escalation queue
    superseded_decisions: List[Decision] = []
    exception_queue: List[HumanEscalationItem] = []


class ReconciliationPipeline:
    def __init__(self, config: Optional[Any] = None):
        self.config = config or get_config()
        self.normalizer = RecordNormalizer()
        self.exact_matcher = ExactMatcher()
        self.candidate_gen = CandidateGenerator(self.config.candidate_generation)
        self.fuzzy_scorer = FuzzyScorer()
        self.ai_verifier = AIVerifier(acceptance_threshold=self.config.ai_verification.acceptance_threshold)
        self.validator = DeterministicValidator()
        self.controller = DecisionController()
        self.investigator = ExceptionInvestigator()
        self.router_high = self.config.router.high_confidence
        self.router_mid = self.config.router.mid_band_min

    def run(
        self,
        ledger_raw: List[Dict[str, Any]],
        bank_raw: List[Dict[str, Any]],
        invoice_raw: List[Dict[str, Any]],
    ) -> PipelineResult:
        start_time = time.time()
        audit_trail = AuditTrail(entries=[])
        logger = AuditLogger(audit_trail)

        committed_keys: Set[str] = set()
        decisions: List[Decision] = []
        superseded_decisions: List[Decision] = []
        validation_failures: List[Tuple[CandidatePair, Any]] = []
        validation_failure_details: List[Dict[str, Any]] = []

        exact_count = 0
        fuzzy_count = 0
        ai_count = 0
        critical_error_count = 0

        # ─── Stage 1: Normalization ───
        records = self.normalizer.normalize_batch(ledger_raw, bank_raw, invoice_raw)
        logger.log_event(
            record_id="PIPELINE",
            stage="NORMALIZATION",
            event="batch_normalized",
            decision="OK",
            input_state={"ledger": len(ledger_raw), "bank": len(bank_raw), "invoice": len(invoice_raw)},
            score=0.0,
            threshold_applied=None,
            rationale=f"Normalized {len(records)} records from 3 sources with canonical mapping",
            metadata={},
        )

        # Identify intra-source duplicate clones
        source_records_seen: Dict[Tuple[str, float, str, str, str], str] = {}
        duplicate_map: Dict[str, str] = {}
        for r in records:
            sig = (r.source.value, r.amount, r.date.isoformat(), r.currency, r.counterparty)
            if sig in source_records_seen:
                duplicate_map[r.summary_key()] = source_records_seen[sig]
            else:
                source_records_seen[sig] = r.summary_key()

        # ─── Stage 2: Candidate Generation (Multi-Signal Blocking) ───
        # Generate candidates across all records to establish complete candidate universe
        all_candidate_pairs = self.candidate_gen.generate(records)
        raw_candidate_pair_keys: List[Tuple[str, str]] = [
            tuple(sorted([p.record_a.summary_key(), p.record_b.summary_key()]))
            for p in all_candidate_pairs
        ]

        # ─── Stage 3: Exact Matching (Proposals) ───
        exact_candidates, _ = self.exact_matcher.match(records)
        exact_match_pair_keys: List[Tuple[str, str]] = [
            tuple(sorted([p.record_a.summary_key(), p.record_b.summary_key()]))
            for p in exact_candidates
        ]
        for p in exact_candidates:
            p.stage = MatchStage.EXACT

        # ─── Stage 4: Fuzzy Scoring ───
        scored_candidates = self.fuzzy_scorer.score_candidates(all_candidate_pairs)

        # ─── Stage 5: Confidence Router & Proposal Generation ───
        direct_matches: List[CandidatePair] = []
        mid_band: List[CandidatePair] = []

        for pair in scored_candidates:
            if pair.score >= self.router_high:
                pair.stage = MatchStage.FUZZY_DIRECT
                direct_matches.append(pair)
                logger.log_event(
                    record_id=pair.record_a.summary_key(),
                    stage="CONFIDENCE_ROUTER",
                    event="routed_direct",
                    decision="HIGH_CONFIDENCE",
                    input_state={},
                    score=pair.score,
                    threshold_applied=self.router_high,
                    rationale=f"Score {pair.score:.4f} >= {self.router_high} → direct match proposal",
                    metadata={},
                )
            elif pair.score >= self.router_mid:
                mid_band.append(pair)
                logger.log_event(
                    record_id=pair.record_a.summary_key(),
                    stage="CONFIDENCE_ROUTER",
                    event="routed_ai",
                    decision="MID_BAND",
                    input_state={},
                    score=pair.score,
                    threshold_applied=self.router_mid,
                    rationale=f"Score {pair.score:.4f} in [{self.router_mid}, {self.router_high}) → AI verification",
                    metadata={},
                )

        # ─── Stage 6: AI Verification (mid-band) ───
        ai_candidate_pair_keys: List[Tuple[str, str]] = [
            tuple(sorted([p.record_a.summary_key(), p.record_b.summary_key()]))
            for p in mid_band
        ]
        ai_invocations = len(mid_band)
        verified_candidates, ai_rej = self.ai_verifier.verify_candidates(mid_band)
        ai_verified_pair_keys: List[Tuple[str, str]] = [
            tuple(sorted([p.record_a.summary_key(), p.record_b.summary_key()]))
            for p in verified_candidates
        ]
        ai_accepted = len(verified_candidates)
        ai_rejected = len(ai_rej)
        ai_superseded_count = 0
        ai_validation_failed_count = 0
        ai_failed_count = 0

        for pair in verified_candidates:
            pair.stage = MatchStage.AI_VERIFIED

        for pair, ai_res in ai_rej:
            logger.log_event(
                record_id=pair.record_a.summary_key(),
                stage="AI_VERIFICATION",
                event="rejected",
                decision="EXCEPTION",
                input_state={},
                score=ai_res.confidence,
                threshold_applied=self.config.ai_verification.acceptance_threshold,
                rationale=ai_res.reasoning,
                metadata={},
            )

        # ─── Stage 7: Deterministic Validation Across All Proposals ───
        proposals_to_compete: List[Tuple[CandidatePair, Any]] = []

        # Validate Exact Proposals
        for pair in exact_candidates:
            val_result = self.validator.validate(pair, set(), duplicate_map=duplicate_map)
            if val_result.is_valid:
                proposals_to_compete.append((pair, val_result))
            else:
                validation_failures.append((pair, val_result))
                if any("Currency mismatch" in c or "Same source" in c for c in val_result.failed_checks):
                    critical_error_count += 1
                validation_failure_details.append({
                    "pair_key": pair.pair_key,
                    "failed_checks": val_result.failed_checks,
                    "stage": "EXACT_MATCH",
                })

        # Validate Fuzzy Proposals
        for pair in direct_matches:
            val_result = self.validator.validate(pair, set(), duplicate_map=duplicate_map)
            if val_result.is_valid:
                proposals_to_compete.append((pair, val_result))
            else:
                validation_failures.append((pair, val_result))
                if any("Currency mismatch" in c or "Same source" in c for c in val_result.failed_checks):
                    critical_error_count += 1
                validation_failure_details.append({
                    "pair_key": pair.pair_key,
                    "failed_checks": val_result.failed_checks,
                    "stage": "FUZZY_MATCH",
                })

        # Validate AI Proposals
        for pair in verified_candidates:
            val_result = self.validator.validate(pair, set(), duplicate_map=duplicate_map)
            if val_result.is_valid:
                proposals_to_compete.append((pair, val_result))
            else:
                ai_validation_failed_count += 1
                validation_failures.append((pair, val_result))
                d_f1, d_f2 = self.controller.record_validation_failed(pair, val_result)
                if any("Currency mismatch" in c or "Same source" in c for c in val_result.failed_checks):
                    critical_error_count += 1
                validation_failure_details.append({
                    "pair_key": pair.pair_key,
                    "record_a_key": pair.record_a.summary_key(),
                    "record_b_key": pair.record_b.summary_key(),
                    "failed_checks": val_result.failed_checks,
                    "stage": "AI_VERIFICATION",
                })
                logger.log_event(
                    record_id=pair.record_a.summary_key(),
                    stage="AI_VERIFICATION",
                    event="validation_failed",
                    decision="VALIDATION_FAILED",
                    input_state={},
                    score=pair.score,
                    threshold_applied=self.config.ai_verification.acceptance_threshold,
                    rationale=f"AI candidate failed validator: {', '.join(val_result.failed_checks)}",
                    metadata={"failed_checks": val_result.failed_checks},
                )

        # ─── Stage 8: Global Proposal Ranking & Source-Pair Slot Commitment ───
        def proposal_rank_key(item: Tuple[CandidatePair, Any]):
            pair, _ = item
            is_exact = 1 if pair.stage == MatchStage.EXACT else 0
            conf = pair.metadata.get("ai_confidence", pair.score) if pair.stage == MatchStage.AI_VERIFIED else pair.score
            amount_diff = pair.feature_scores.amount_diff if pair.feature_scores else 0.0
            date_diff = pair.feature_scores.date_diff_days if pair.feature_scores else 0
            return (is_exact, round(conf, 4), round(pair.score, 4), -amount_diff, -date_diff)

        proposals_to_compete.sort(key=proposal_rank_key, reverse=True)

        committed_slots: Dict[str, Dict[str, Tuple[str, CandidatePair]]] = {}

        for pair, val_result in proposals_to_compete:
            ka = pair.record_a.summary_key()
            kb = pair.record_b.summary_key()
            sa = pair.record_a.source.value
            sb = pair.record_b.source.value

            slots_a = committed_slots.setdefault(ka, {})
            slots_b = committed_slots.setdefault(kb, {})

            # Slot-based conflict check: does record_a already have a partner for source sb, or record_b for source sa?
            if sb in slots_a or sa in slots_b:
                winning_partner, winning_pair = slots_a.get(sb) or slots_b.get(sa)
                conflicting_src = sb if sb in slots_a else sa
                reason = f"Candidate superseded: slot for source {conflicting_src} already committed to {winning_partner}"
                d_sup1, d_sup2 = self.controller.record_superseded(
                    pair, winning_partner, reason, winning_pair=winning_pair
                )
                superseded_decisions.extend([d_sup1, d_sup2])
                if pair.stage == MatchStage.AI_VERIFIED:
                    ai_superseded_count += 1
                logger.log_event(
                    record_id=ka,
                    stage=pair.stage.value,
                    event="superseded",
                    decision="SUPERSEDED",
                    input_state={"conflicting": winning_partner},
                    score=pair.score,
                    threshold_applied=None,
                    rationale=reason,
                    metadata={"pair_key": pair.pair_key, "winning_candidate": winning_pair.pair_key},
                )
                logger.log_event(
                    record_id=kb,
                    stage=pair.stage.value,
                    event="superseded",
                    decision="SUPERSEDED",
                    input_state={"conflicting": winning_partner},
                    score=pair.score,
                    threshold_applied=None,
                    rationale=reason,
                    metadata={"pair_key": pair.pair_key, "winning_candidate": winning_pair.pair_key},
                )
            else:
                # Winning proposal commits to source slots!
                slots_a[sb] = (kb, pair)
                slots_b[sa] = (ka, pair)
                committed_keys.add(ka)
                committed_keys.add(kb)
                self.controller.commit_match(pair, val_result)

                if pair.stage == MatchStage.EXACT:
                    exact_count += 1
                elif pair.stage == MatchStage.FUZZY_DIRECT:
                    fuzzy_count += 1
                elif pair.stage == MatchStage.AI_VERIFIED:
                    ai_count += 1

                logger.log_event(
                    record_id=ka,
                    stage=pair.stage.value,
                    event="committed",
                    decision="RESOLVED",
                    input_state={},
                    score=pair.score,
                    threshold_applied=None,
                    rationale=f"{pair.stage.value} match validated and committed",
                    metadata={"matched_with": kb},
                )
                logger.log_event(
                    record_id=kb,
                    stage=pair.stage.value,
                    event="committed",
                    decision="RESOLVED",
                    input_state={},
                    score=pair.score,
                    threshold_applied=None,
                    rationale=f"{pair.stage.value} match validated and committed",
                    metadata={"matched_with": ka},
                )

        # Collect all resolved decisions from controller
        decisions.extend(self.controller._decisions.values())

        # ─── Stage 8: Exception Investigation ───
        final_unmatched = [r for r in records if r.summary_key() not in committed_keys]
        for r in final_unmatched:
            # Check for duplicate clone
            if r.summary_key() in duplicate_map:
                twin = duplicate_map[r.summary_key()]
                dec = Decision(
                    record_id=r.summary_key(),
                    status=ResolutionStatus.EXCEPTION,
                    stage_resolved=None,
                    matched_with_ids=[],
                    confidence=0.0,
                    rationale=f"Exception: LIKELY_DUPLICATE. Cloned duplicate in {r.source.value} matching {twin}.",
                    exception_reason=ExceptionReason.LIKELY_DUPLICATE,
                    validation_result=None,
                    raw_scores={},
                    metadata={"duplicate_of": twin},
                )
            else:
                rel_failures = [
                    (p, v) for p, v in validation_failures
                    if p.record_a.summary_key() == r.summary_key()
                    or p.record_b.summary_key() == r.summary_key()
                ]
                rel_candidates = [
                    p for p in scored_candidates
                    if p.record_a.summary_key() == r.summary_key()
                    or p.record_b.summary_key() == r.summary_key()
                ]

                dec = self.investigator.investigate(r, rel_candidates, rel_failures)
                if dec.exception_reason == ExceptionReason.NO_CANDIDATE:
                    miss_reasons = self.candidate_gen.get_miss_reasons(r.summary_key())
                    if miss_reasons:
                        dec.metadata["blocking_miss_reasons"] = miss_reasons[:3]
                        dec.rationale += f" Blocking checks: {'; '.join(miss_reasons[:2])}."

            decisions.append(dec)

            logger.log_event(
                record_id=r.summary_key(),
                stage="EXCEPTION",
                event="investigation",
                decision="EXCEPTION",
                input_state={},
                score=0.0,
                threshold_applied=None,
                rationale=dec.rationale,
                metadata={"reason": dec.exception_reason.value if dec.exception_reason else ""},
            )

        # Package actionable exception queue
        exception_decisions = [d for d in decisions if d.status == ResolutionStatus.EXCEPTION]
        records_by_key = {r.summary_key(): r for r in records}
        exception_queue = self.investigator.package_escalation_queue(
            exception_decisions, records_by_key, all_candidate_pairs
        )

        processing_time_ms = (time.time() - start_time) * 1000.0
        return PipelineResult(
            records=records,
            decisions=decisions,
            audit_trail=audit_trail,
            processing_time_ms=processing_time_ms,
            exact_match_count=exact_count,
            fuzzy_match_count=fuzzy_count,
            ai_match_count=ai_count,
            ai_invocations=ai_invocations,
            ai_accepted=ai_accepted,
            ai_rejected=ai_rejected,
            ai_superseded_count=ai_superseded_count,
            ai_validation_failed_count=ai_validation_failed_count,
            ai_failed_count=ai_failed_count,
            raw_candidate_pair_keys=raw_candidate_pair_keys,
            exact_match_pair_keys=exact_match_pair_keys,
            ai_candidate_pair_keys=ai_candidate_pair_keys,
            ai_verified_pair_keys=ai_verified_pair_keys,
            validation_failure_details=validation_failure_details,
            critical_error_count=critical_error_count,
            superseded_decisions=superseded_decisions,
            exception_queue=exception_queue,
        )
