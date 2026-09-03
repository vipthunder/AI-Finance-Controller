from __future__ import annotations
from typing import List, Dict, Any, Set, Tuple

from src.schemas.records import Record
from src.schemas.decisions import Decision
from src.schemas.enums import ResolutionStatus
from src.schemas.audit import AuditTrail
from src.schemas.ground_truth import GroundTruthStore
from src.evaluation.metrics import EvaluationMetrics
from src.pipeline.reconciliation_pipeline import PipelineResult


class Evaluator:
    def __init__(self, gt_store: GroundTruthStore):
        self.gt_store = gt_store

    def evaluate_pipeline_result(self, result: PipelineResult) -> EvaluationMetrics:
        """Convenience wrapper that extracts everything from PipelineResult."""
        return self.evaluate(
            decisions=result.decisions,
            audit_trail=result.audit_trail,
            processing_time_ms=result.processing_time_ms,
            total_records=len(result.records),
            exact_count=result.exact_match_count,
            fuzzy_count=result.fuzzy_match_count,
            ai_count=result.ai_match_count,
            ai_invocations=result.ai_invocations,
            ai_accepted=result.ai_accepted,
            ai_rejected=result.ai_rejected,
            records=result.records,
            raw_candidate_pair_keys=result.raw_candidate_pair_keys,
            exact_match_pair_keys=result.exact_match_pair_keys,
            ai_candidate_pair_keys=result.ai_candidate_pair_keys,
            ai_verified_pair_keys=result.ai_verified_pair_keys,
            validation_failure_details=result.validation_failure_details,
            superseded_decisions=result.superseded_decisions,
            ai_failed_count=result.ai_failed_count,
            ai_provider_mode=result.ai_provider_mode,
        )

    def evaluate(
        self,
        decisions: List[Decision],
        audit_trail: AuditTrail,
        processing_time_ms: float,
        total_records: int,
        exact_count: int = 0,
        fuzzy_count: int = 0,
        ai_count: int = 0,
        ai_invocations: int = 0,
        ai_accepted: int = 0,
        ai_rejected: int = 0,
        records: List[Record] | None = None,
        raw_candidate_pair_keys: List[Tuple[str, str]] | None = None,
        exact_match_pair_keys: List[Tuple[str, str]] | None = None,
        ai_candidate_pair_keys: List[Tuple[str, str]] | None = None,
        ai_verified_pair_keys: List[Tuple[str, str]] | None = None,
        validation_failure_details: List[Dict[str, Any]] | None = None,
        critical_error_count: int = 0,
        superseded_decisions: List[Decision] | None = None,
        ai_failed_count: int = 0,
        ai_provider_mode: str = "MOCK",
    ) -> EvaluationMetrics:
        records = records or []
        raw_candidate_pair_keys = raw_candidate_pair_keys or []
        exact_match_pair_keys = exact_match_pair_keys or []
        validation_failure_details = validation_failure_details or []
        superseded_decisions = superseded_decisions or []

        # ─── Build amount lookup for financial metrics ───
        amount_by_key: Dict[str, float] = {}
        for r in records:
            amount_by_key[r.summary_key()] = abs(r.amount)

        # ─── Core classification ───
        true_positives = 0
        false_positives = 0
        resolved_count = 0
        exception_count = 0
        exceptions_by_reason: Dict[str, int] = {}
        seen_pairs: Set[Tuple[str, str]] = set()

        # Per-stage tracking
        auto_tp = 0          # exact + fuzzy true positives
        auto_fp = 0          # exact + fuzzy false positives
        exact_tp = 0         # exact match true positives
        fuzzy_tp = 0         # fuzzy match true positives
        auto_pairs = 0       # total auto-resolved pairs
        ai_committed_tp = 0  # AI-committed true positives
        ai_committed_fp = 0  # AI-committed false positives
        ai_committed_pairs = 0

        # Financial accumulators
        total_value = 0.0
        matched_value = 0.0
        exception_value = 0.0
        incorrectly_matched_value = 0.0

        # Safety: track record_ids that appear in decisions
        decided_record_ids: Set[str] = set()
        # Track records committed in multiple matches
        commit_counts: Dict[str, int] = {}

        for d in decisions:
            decided_record_ids.add(d.record_id)
            amt = amount_by_key.get(d.record_id, 0.0)

            if d.status == ResolutionStatus.RESOLVED:
                resolved_count += 1
                matched_value += amt

                # Count commits for duplicate escape detection
                commit_counts[d.record_id] = commit_counts.get(d.record_id, 0) + 1

                r1_key = d.record_id
                for r2_key in d.matched_with_ids:
                    pair_key = tuple(sorted([r1_key, r2_key]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    src_a, id_a = r1_key.split(":", 1)
                    src_b, id_b = r2_key.split(":", 1)

                    is_tp = self.gt_store.is_true_match(src_a, id_a, src_b, id_b)
                    if is_tp:
                        true_positives += 1
                    else:
                        false_positives += 1
                        # Financial: incorrectly matched value
                        incorrectly_matched_value += amt

                    # Per-stage classification
                    stage = d.stage_resolved or ""
                    if stage == "EXACT":
                        auto_pairs += 1
                        if is_tp:
                            exact_tp += 1
                            auto_tp += 1
                        else:
                            auto_fp += 1
                    elif stage == "FUZZY_DIRECT":
                        auto_pairs += 1
                        if is_tp:
                            fuzzy_tp += 1
                            auto_tp += 1
                        else:
                            auto_fp += 1
                    elif stage == "AI_VERIFIED":
                        ai_committed_pairs += 1
                        if is_tp:
                            ai_committed_tp += 1
                        else:
                            ai_committed_fp += 1

            elif d.status == ResolutionStatus.EXCEPTION:
                exception_count += 1
                exception_value += amt
                reason = d.exception_reason.value if d.exception_reason else "UNKNOWN"
                exceptions_by_reason[reason] = exceptions_by_reason.get(reason, 0) + 1

        # ─── Ground truth & Set-Theoretic Evaluation ───
        all_gt = self.gt_store.get_all_ground_truth_pairs()
        total_gt_pairs = len(all_gt)
        proposed_pairs = len(seen_pairs)

        # Independent set-based calculation (Section 4)
        tp_set = seen_pairs.intersection(all_gt)
        fp_set = seen_pairs.difference(all_gt)
        fn_set = all_gt.difference(seen_pairs)

        true_positives = len(tp_set)
        false_positives = len(fp_set)
        false_negatives = len(fn_set)

        # ─── Total value (sum of all unique record amounts) ───
        total_value = sum(amount_by_key.values())

        # ─── RECONCILIATION metrics ───
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / total_gt_pairs if total_gt_pairs > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Candidate recall: fraction of GT pairs found in the candidate set
        raw_candidate_set = set(raw_candidate_pair_keys)
        exact_match_set = set(exact_match_pair_keys)
        
        gt_in_raw_candidates = sum(1 for gt_pair in all_gt if gt_pair in raw_candidate_set)
        raw_candidate_recall = gt_in_raw_candidates / total_gt_pairs if total_gt_pairs > 0 else 0.0
        
        gt_in_exact_matches = sum(1 for gt_pair in all_gt if gt_pair in exact_match_set)
        exact_match_coverage = gt_in_exact_matches / total_gt_pairs if total_gt_pairs > 0 else 0.0
        fuzzy_resolution_coverage = fuzzy_tp / total_gt_pairs if total_gt_pairs > 0 else 0.0
        ai_resolution_coverage = ai_committed_tp / total_gt_pairs if total_gt_pairs > 0 else 0.0
        
        final_reconciliation_recall = true_positives / total_gt_pairs if total_gt_pairs > 0 else 0.0

        # Accuracy & false match rate
        true_negatives = max(0, total_records - resolved_count - exception_count)
        false_match_rate = false_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0

        # ─── AUTOMATION metrics (exact + fuzzy, no AI) ───
        auto_resolved_decisions = sum(
            1 for d in decisions
            if d.status == ResolutionStatus.RESOLVED and d.stage_resolved in ("EXACT", "FUZZY_DIRECT")
        )
        auto_resolution_rate = auto_resolved_decisions / total_records if total_records > 0 else 0.0
        auto_resolution_precision = auto_tp / (auto_tp + auto_fp) if (auto_tp + auto_fp) > 0 else 0.0
        auto_resolution_recall = auto_tp / total_gt_pairs if total_gt_pairs > 0 else 0.0

        # Match & automation rates (overall)
        match_rate = resolved_count / total_records if total_records > 0 else 0.0
        automation_rate = resolved_count / total_records if total_records > 0 else 0.0

        # ─── AI metrics ───
        ai_validation_failed_count = sum(1 for d in validation_failure_details if d.get("stage") == "AI_VERIFICATION")
        
        # A superseded decision is generated for each record in the pair, so divide by 2
        ai_superseded_count = sum(1 for d in superseded_decisions if d.stage_resolved == "AI_VERIFIED") // 2
        ai_committed_count = ai_count
        
        # Calculate AI recommendation precision
        # To do this, we evaluate TP/FP across ALL pairs AI accepted.
        if ai_verified_pair_keys is not None:
            verified_unique = set(ai_verified_pair_keys)
            ai_accepted_tp = sum(1 for k in verified_unique if k in all_gt)
            ai_accepted_fp = sum(1 for k in verified_unique if k not in all_gt)
        else:
            ai_accepted_tp = ai_committed_tp
            ai_accepted_fp = ai_committed_fp
            
            # Process superseded for AI precision
            seen_ai_superseded_pairs = set()
            for d in superseded_decisions:
                if d.stage_resolved == "AI_VERIFIED":
                    for r2_key in d.matched_with_ids:
                        pair_key = tuple(sorted([d.record_id, r2_key]))
                        if pair_key not in seen_ai_superseded_pairs:
                            seen_ai_superseded_pairs.add(pair_key)
                            src_a, id_a = pair_key[0].split(":", 1)
                            src_b, id_b = pair_key[1].split(":", 1)
                            if self.gt_store.is_true_match(src_a, id_a, src_b, id_b):
                                ai_accepted_tp += 1
                            else:
                                ai_accepted_fp += 1

            # Process validation failed for AI precision
            for vfd in validation_failure_details:
                if vfd.get("stage") == "AI_VERIFICATION":
                    key_a = vfd.get("record_a_key")
                    key_b = vfd.get("record_b_key")
                    if key_a and key_b:
                        src_a, id_a = key_a.split(":", 1)
                        src_b, id_b = key_b.split(":", 1)
                        if self.gt_store.is_true_match(src_a, id_a, src_b, id_b):
                            ai_accepted_tp += 1
                        else:
                            ai_accepted_fp += 1
                    else:
                        pair_key_str = vfd.get("pair_key", "")
                        if "::" in pair_key_str:
                            parts = pair_key_str.split("::")
                            if len(parts) == 2 and ":" in parts[0] and ":" in parts[1]:
                                src_a, id_a = parts[0].split(":", 1)
                                src_b, id_b = parts[1].split(":", 1)
                                if self.gt_store.is_true_match(src_a, id_a, src_b, id_b):
                                    ai_accepted_tp += 1
                                else:
                                    ai_accepted_fp += 1
        
        ai_usage_rate = ai_invocations / total_records if total_records > 0 else 0.0
        ai_acceptance_rate = ai_accepted / ai_invocations if ai_invocations > 0 else 0.0
        ai_commitment_rate = ai_committed_count / ai_accepted if ai_accepted > 0 else 0.0
        ai_supersession_rate = ai_superseded_count / ai_accepted if ai_accepted > 0 else 0.0
        ai_validation_failure_rate = ai_validation_failed_count / ai_accepted if ai_accepted > 0 else 0.0
        
        ai_candidate_pair_set = set(ai_candidate_pair_keys) if ai_candidate_pair_keys else set()
        ai_eligible_candidates = len(ai_candidate_pair_set) if ai_candidate_pair_set else ai_invocations
        ai_eligible_gt_set = ai_candidate_pair_set.intersection(all_gt) if ai_candidate_pair_set else set()
        ai_eligible_gt_relationships = len(ai_eligible_gt_set) if ai_candidate_pair_set else ai_accepted_tp

        ai_recommendation_precision = ai_accepted_tp / (ai_accepted_tp + ai_accepted_fp) if (ai_accepted_tp + ai_accepted_fp) > 0 else 0.0
        ai_recommendation_recall = ai_accepted_tp / ai_eligible_gt_relationships if ai_eligible_gt_relationships > 0 else 0.0
        ai_contribution_recall = ai_accepted_tp / total_gt_pairs if total_gt_pairs > 0 else 0.0

        # ─── EXCEPTION metrics ───
        # Exception precision: fraction of exceptions that are truly unmatched
        # (record has no ground-truth match among all other committed records)
        correctly_excepted = 0
        for d in decisions:
            if d.status == ResolutionStatus.EXCEPTION:
                record_key = d.record_id
                parts = record_key.split(":", 1)
                if len(parts) == 2:
                    gt_id = self.gt_store.get_gt_id(parts[0], parts[1])
                    if gt_id is None:
                        # Record genuinely has no ground-truth match → correct exception
                        correctly_excepted += 1
                    else:
                        # Check if the GT pair was already resolved by another decision
                        # If so, this exception is also correct (the record's match was
                        # already consumed)
                        gt_tx = self.gt_store.get_transaction(gt_id)
                        if gt_tx:
                            partner_keys = set()
                            for src, ids in gt_tx.source_record_ids.items():
                                for rid in ids:
                                    pk = f"{src}:{rid}"
                                    if pk != record_key:
                                        partner_keys.add(pk)
                            # If all partners are committed, this record's exception is valid
                            all_partners_committed = all(
                                pk in decided_record_ids
                                and any(
                                    dd.record_id == pk and dd.status == ResolutionStatus.RESOLVED
                                    for dd in decisions
                                )
                                for pk in partner_keys
                            ) if partner_keys else False
                            if not all_partners_committed:
                                pass  # genuinely missed → not correctly excepted
                            else:
                                correctly_excepted += 1

        exception_precision = correctly_excepted / exception_count if exception_count > 0 else 0.0

        # Exception recall: correctly excepted / total records that should be exceptions
        # "Should be exceptions" = records with no GT match at all, or records whose
        # GT partners have all been consumed by other matches
        total_true_exceptions = 0
        for r in records:
            parts = r.summary_key().split(":", 1)
            if len(parts) == 2:
                gt_id = self.gt_store.get_gt_id(parts[0], parts[1])
                if gt_id is None:
                    total_true_exceptions += 1
                else:
                    # Check if all GT partners are already committed (consumed)
                    gt_tx = self.gt_store.get_transaction(gt_id)
                    if gt_tx:
                        partner_keys = set()
                        for src, ids in gt_tx.source_record_ids.items():
                            for rid in ids:
                                pk = f"{src}:{rid}"
                                if pk != r.summary_key():
                                    partner_keys.add(pk)
                        # If all partners are resolved, this record is truly an exception
                        all_partners_resolved = all(
                            any(
                                dd.record_id == pk and dd.status == ResolutionStatus.RESOLVED
                                for dd in decisions
                            )
                            for pk in partner_keys
                        ) if partner_keys else False
                        if all_partners_resolved:
                            total_true_exceptions += 1
        exception_recall = correctly_excepted / total_true_exceptions if total_true_exceptions > 0 else 0.0

        # ─── FINANCIAL metrics ───
        value_reconciliation_rate = matched_value / total_value if total_value > 0 else 0.0

        # Canonical Business Transaction Values (de-duplicated across systems)
        canonical_transactions = len(self.gt_store._transactions)
        total_business_value = 0.0
        fully_reconciled_value = 0.0
        partially_reconciled_value = 0.0
        exception_business_value = 0.0

        resolved_record_ids = {
            d.record_id for d in decisions if d.status == ResolutionStatus.RESOLVED
        }

        fully_reconciled_transactions = 0
        partially_reconciled_transactions = 0
        unresolved_transactions = 0

        for tx in self.gt_store._transactions.values():
            total_business_value += tx.base_amount
            tx_record_keys = [
                f"{src}:{rid}"
                for src, ids in tx.source_record_ids.items()
                for rid in ids
            ]

            # Determine required ground-truth relationships for this transaction
            required_gt_pairs = set()
            for i in range(len(tx_record_keys)):
                for j in range(i + 1, len(tx_record_keys)):
                    required_gt_pairs.add(tuple(sorted([tx_record_keys[i], tx_record_keys[j]])))

            # Correctly predicted relationships for this transaction
            correctly_predicted_pairs = required_gt_pairs.intersection(seen_pairs)

            if len(required_gt_pairs) == 0:
                # Singleton transaction with no required cross-source pairs
                if any(k in resolved_record_ids for k in tx_record_keys):
                    fully_reconciled_value += tx.base_amount
                    fully_reconciled_transactions += 1
                else:
                    exception_business_value += tx.base_amount
                    unresolved_transactions += 1
            elif len(correctly_predicted_pairs) == len(required_gt_pairs):
                # FULLY_RECONCILED: Every required ground-truth relationship is correctly predicted
                fully_reconciled_value += tx.base_amount
                fully_reconciled_transactions += 1
            elif len(correctly_predicted_pairs) > 0:
                # PARTIALLY_RECONCILED: At least one required relationship is correctly predicted, but not all
                partially_reconciled_value += tx.base_amount
                partially_reconciled_transactions += 1
            else:
                # UNRESOLVED: Zero required relationships are correctly predicted
                exception_business_value += tx.base_amount
                unresolved_transactions += 1

        reconciled_business_value = fully_reconciled_value + partially_reconciled_value
        financial_value_coverage = (
            reconciled_business_value / total_business_value if total_business_value > 0 else 0.0
        )
        business_value_reconciliation_rate = financial_value_coverage
        total_canonical_value = total_business_value
        full_value_reconciliation_rate = (
            fully_reconciled_value / total_canonical_value if total_canonical_value > 0 else 0.0
        )
        fully_reconciled_tx_rate = (
            fully_reconciled_transactions / canonical_transactions if canonical_transactions > 0 else 0.0
        )
        partial_transaction_coverage = (
            (fully_reconciled_transactions + partially_reconciled_transactions) / canonical_transactions
            if canonical_transactions > 0 else 0.0
        )

        # ─── FALSE NEGATIVE DIAGNOSTICS ───
        fn_diagnostics: Dict[str, int] = {
            "FN_CANDIDATE_GENERATION": 0,
            "FN_LOW_SCORE": 0,
            "FN_ROUTER_REJECTION": 0,
            "FN_AI_REJECTION": 0,
            "FN_AI_FAILURE": 0,
            "FN_VALIDATION_FAILURE": 0,
            "FN_SUPERSEDED": 0,
            "FN_DUPLICATE_CONFLICT": 0,
            "FN_OTHER": 0,
        }

        superseded_pairs = {
            tuple(sorted([d.record_id, m]))
            for d in superseded_decisions
            for m in d.matched_with_ids
        }

        unresolved_gt_pairs = all_gt - seen_pairs
        for p in unresolved_gt_pairs:
            r1, r2 = p
            if p not in raw_candidate_set and p not in exact_match_set:
                fn_diagnostics["FN_CANDIDATE_GENERATION"] += 1
            elif p in superseded_pairs:
                fn_diagnostics["FN_SUPERSEDED"] += 1
            else:
                d1 = next((d for d in decisions if d.record_id == r1), None)
                d2 = next((d for d in decisions if d.record_id == r2), None)
                r1_committed = d1 and d1.status == ResolutionStatus.RESOLVED
                r2_committed = d2 and d2.status == ResolutionStatus.RESOLVED
                if r1_committed or r2_committed:
                    fn_diagnostics["FN_SUPERSEDED"] += 1
                elif (d1 and d1.exception_reason == ExceptionReason.LIKELY_DUPLICATE) or (d2 and d2.exception_reason == ExceptionReason.LIKELY_DUPLICATE):
                    fn_diagnostics["FN_DUPLICATE_CONFLICT"] += 1
                else:
                    fn_diagnostics["FN_OTHER"] += 1

        auto_resolved_value = sum(
            amount_by_key.get(d.record_id, 0.0)
            for d in decisions
            if d.status == ResolutionStatus.RESOLVED and d.stage_resolved in ("EXACT", "FUZZY_DIRECT")
        )

        # ─── DISCREPANCY-LEVEL BREAKDOWN ───
        discrepancy_metrics: Dict[str, Dict[str, Any]] = {}
        for tx in self.gt_store._transactions.values():
            category = tx.category or "STANDARD"
            if category not in discrepancy_metrics:
                discrepancy_metrics[category] = {"total_tx": 0, "reconciled_tx": 0, "total_value": 0.0}
            discrepancy_metrics[category]["total_tx"] += 1
            discrepancy_metrics[category]["total_value"] += tx.base_amount

            tx_keys = [f"{src}:{rid}" for src, ids in tx.source_record_ids.items() for rid in ids]
            req_pairs = {tuple(sorted([tx_keys[i], tx_keys[j]])) for i in range(len(tx_keys)) for j in range(i + 1, len(tx_keys))}
            if (len(req_pairs) == 0 and any(k in resolved_record_ids for k in tx_keys)) or (len(req_pairs) > 0 and len(req_pairs.intersection(seen_pairs)) == len(req_pairs)):
                discrepancy_metrics[category]["reconciled_tx"] += 1

        for cat, data in discrepancy_metrics.items():
            data["reconciliation_rate"] = data["reconciled_tx"] / data["total_tx"] if data["total_tx"] > 0 else 0.0

        # ─── SAFETY metrics ───
        # Duplicate escape: records appearing in more than one RESOLVED decision
        duplicate_escapes = sum(1 for v in commit_counts.values() if v > 1)
        duplicate_escape_rate = duplicate_escapes / total_records if total_records > 0 else 0.0

        # Critical error rate
        total_proposed = proposed_pairs + len(validation_failure_details)
        critical_error_rate = critical_error_count / total_proposed if total_proposed > 0 else 0.0

        # Silent drop: records that entered the pipeline but appear in no decision
        all_record_keys = {r.summary_key() for r in records}
        silent_drop_count = len(all_record_keys - decided_record_ids)

        # ─── THROUGHPUT ───
        throughput = (total_records / (processing_time_ms / 1000.0)) if processing_time_ms > 0 else 0.0

        return EvaluationMetrics(
            # Core counts
            total_records=total_records,
            total_ground_truth_pairs=total_gt_pairs,
            proposed_pairs_count=proposed_pairs,

            # Reconciliation
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            true_negatives=true_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            raw_candidate_recall=raw_candidate_recall,
            exact_match_coverage=exact_match_coverage,
            fuzzy_resolution_coverage=fuzzy_resolution_coverage,
            ai_resolution_coverage=ai_resolution_coverage,
            final_reconciliation_recall=final_reconciliation_recall,
            candidate_recall=raw_candidate_recall,
            false_match_rate=false_match_rate,

            # Automation
            match_rate=match_rate,
            exact_matches_count=exact_count,
            fuzzy_matches_count=fuzzy_count,
            auto_resolution_rate=auto_resolution_rate,
            auto_resolution_precision=auto_resolution_precision,
            auto_resolution_recall=auto_resolution_recall,

            # AI
            ai_matches_count=ai_count,
            ai_invocations_count=ai_invocations,
            ai_accepted_count=ai_accepted,
            ai_rejected_count=ai_rejected,
            ai_validation_failed_count=ai_validation_failed_count,
            ai_superseded_count=ai_superseded_count,
            ai_failed_count=ai_failed_count,
            ai_committed_count=ai_committed_count,
            ai_provider_mode=ai_provider_mode,
            ai_usage_rate=ai_usage_rate,
            ai_acceptance_rate=ai_acceptance_rate,
            ai_commitment_rate=ai_commitment_rate,
            ai_supersession_rate=ai_supersession_rate,
            ai_validation_failure_rate=ai_validation_failure_rate,
            ai_recommendation_precision=ai_recommendation_precision,
            ai_recommendation_recall=ai_recommendation_recall,
            ai_precision=ai_recommendation_precision,
            ai_recall=ai_recommendation_recall,

            # Exceptions
            automation_rate=automation_rate,
            exceptions_count=exception_count,
            exceptions_by_reason=exceptions_by_reason,
            exception_precision=exception_precision,
            exception_recall=exception_recall,

            # Financial
            total_value=total_value,
            matched_value=matched_value,
            exception_value=exception_value,
            incorrectly_matched_value=incorrectly_matched_value,
            value_reconciliation_rate=value_reconciliation_rate,
            canonical_transactions=canonical_transactions,
            fully_reconciled_transactions=fully_reconciled_transactions,
            partially_reconciled_transactions=partially_reconciled_transactions,
            unresolved_transactions=unresolved_transactions,
            fully_reconciled_tx_rate=fully_reconciled_tx_rate,
            partial_transaction_coverage=partial_transaction_coverage,
            total_business_value=total_business_value,
            total_canonical_value=total_canonical_value,
            fully_reconciled_value=fully_reconciled_value,
            partially_reconciled_value=partially_reconciled_value,
            reconciled_business_value=reconciled_business_value,
            exception_business_value=exception_business_value,
            unresolved_canonical_value=exception_business_value,
            exception_exposure_value=exception_value,
            auto_resolved_value=auto_resolved_value,
            business_value_reconciliation_rate=business_value_reconciliation_rate,
            full_value_reconciliation_rate=full_value_reconciliation_rate,
            financial_value_coverage=financial_value_coverage,
            ai_contribution_recall=ai_contribution_recall,
            ai_eligible_candidates=ai_eligible_candidates,
            ai_eligible_gt_relationships=ai_eligible_gt_relationships,

            # Safety
            duplicate_escape_rate=duplicate_escape_rate,
            critical_error_rate=critical_error_rate,
            silent_drop_count=silent_drop_count,

            # Throughput
            processing_time_ms=processing_time_ms,
            throughput_records_per_sec=throughput,

            # Diagnostics & Discrepancy Breakdown
            fn_diagnostics=fn_diagnostics,
            discrepancy_metrics=discrepancy_metrics,
        )
