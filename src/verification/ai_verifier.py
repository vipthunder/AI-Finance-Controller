from __future__ import annotations
from typing import List, Tuple, Optional
from pydantic import BaseModel

from src.schemas.candidates import CandidatePair
from src.schemas.enums import MatchStage
from src.config import get_config
from src.verification.llm_provider import (
    BaseLLMProvider,
    AIVerificationResponse,
    get_llm_provider,
)


def get_ai_acceptance_threshold() -> float:
    return get_config().ai_verification.acceptance_threshold


# Backward-compatible alias
AI_CONFIDENCE_THRESHOLD = get_ai_acceptance_threshold()


class AIVerificationResult(BaseModel):
    is_match: bool
    confidence: float
    reasoning: str
    evidence: List[str] = []
    risk_flags: List[str] = []
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    model_used: str = ""


class AIVerifier:
    """Runs on ambiguous candidates routed to AI (e.g. mid-band 0.50–0.85).

    Delegates to a structured LLM provider (LiveLLMProvider or MockLLMProvider)
    to obtain auditable, multi-attribute financial assessments.
    """

    def __init__(self, provider: Optional[BaseLLMProvider] = None, acceptance_threshold: Optional[float] = None):
        self.provider = provider or get_llm_provider()
        self.acceptance_threshold = (
            acceptance_threshold if acceptance_threshold is not None else get_ai_acceptance_threshold()
        )
        self.total_latency_ms: float = 0.0
        self.total_cost_usd: float = 0.0

    def verify_candidates(
        self, mid_band: List[CandidatePair]
    ) -> Tuple[List[CandidatePair], List[Tuple[CandidatePair, AIVerificationResult]]]:
        verified: List[CandidatePair] = []
        rejected: List[Tuple[CandidatePair, AIVerificationResult]] = []

        for pair in mid_band:
            result = self._verify_single(pair)
            self.total_latency_ms += result.latency_ms
            self.total_cost_usd += result.cost_usd

            if result.is_match and result.confidence >= self.acceptance_threshold:
                pair.stage = MatchStage.AI_VERIFIED
                pair.score = result.confidence
                pair.metadata["ai_rationale"] = result.reasoning
                pair.metadata["ai_evidence"] = result.evidence
                pair.metadata["ai_risk_flags"] = result.risk_flags
                pair.metadata["ai_latency_ms"] = result.latency_ms
                pair.metadata["ai_cost_usd"] = result.cost_usd
                pair.metadata["ai_model"] = result.model_used
                verified.append(pair)
            else:
                rejected.append((pair, result))

        return verified, rejected

    def _verify_single(self, pair: CandidatePair) -> AIVerificationResult:
        resp: AIVerificationResponse = self.provider.verify(pair)
        is_match = resp.decision == "MATCH" and resp.confidence >= self.acceptance_threshold

        return AIVerificationResult(
            is_match=is_match,
            confidence=resp.confidence,
            reasoning=resp.rationale,
            evidence=resp.evidence,
            risk_flags=resp.risk_flags,
            latency_ms=resp.latency_ms,
            cost_usd=resp.cost_usd,
            model_used=resp.model_used,
        )
