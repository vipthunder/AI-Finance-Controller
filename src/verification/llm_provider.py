from __future__ import annotations
import os
import time
import json
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from src.schemas.candidates import CandidatePair
from src.verification.prompts import KNOWN_ALIASES
from src.config import get_config


class AIVerificationResponse(BaseModel):
    decision: str = Field(description="Either 'MATCH' or 'NO_MATCH'")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    rationale: str = Field(description="Human-readable explanation of AI judgment")
    evidence: List[str] = Field(default_factory=list, description="Specific supporting evidence points")
    entity_match: bool = Field(default=False, description="Whether counterparties are judged to be the same entity")
    amount_assessment: str = Field(default="AGREES", description="Assessment of amount alignment")
    date_assessment: str = Field(default="PLAUSIBLE", description="Assessment of date alignment")
    risk_flags: List[str] = Field(default_factory=list, description="Any identified financial risk flags")
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    model_used: str = "mock-deterministic-v1"
    provider_mode: str = "MOCK"
    is_error: bool = False


class BaseLLMProvider(ABC):
    @abstractmethod
    def verify(self, pair: CandidatePair) -> AIVerificationResponse:
        """Evaluate ambiguous candidate pair and return structured verification response."""
        pass


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, offline LLM provider for tests and reproducible benchmarking.
    Generates structured AI verification responses using deep entity and context reasoning.
    """

    def verify(self, pair: CandidatePair) -> AIVerificationResponse:
        t0 = time.time()
        r1 = pair.record_a
        r2 = pair.record_b
        name_a = (r1.counterparty or "").strip().upper()
        name_b = (r2.counterparty or "").strip().upper()

        evidence: List[str] = []
        risk_flags: List[str] = []

        # 1. Alias and Entity Evaluation
        canonical_a = self._resolve_alias(name_a)
        canonical_b = self._resolve_alias(name_b)

        entity_match = False
        confidence = 0.0

        if canonical_a and canonical_b and canonical_a == canonical_b:
            entity_match = True
            confidence = 0.92
            evidence.append(f"Counterparties match canonical entity '{canonical_a}' via controlled catalog.")
        elif canonical_a and canonical_b and canonical_a != canonical_b:
            entity_match = False
            confidence = 0.15
            risk_flags.append(f"Conflicting canonical entities: '{canonical_a}' vs '{canonical_b}'.")
            evidence.append("Explicit cross-entity mismatch detected.")
        else:
            # Substring containment
            clean_a = name_a.replace("*", " ")
            clean_b = name_b.replace("*", " ")
            if clean_a and clean_b and (clean_a in clean_b or clean_b in clean_a):
                entity_match = True
                confidence = 0.88
                evidence.append("Counterparty substring containment match.")
            else:
                sim = fuzz.token_sort_ratio(clean_a, clean_b) / 100.0
                if sim >= 0.80:
                    entity_match = True
                    confidence = 0.60 + sim * 0.30
                    evidence.append(f"High token similarity: {sim:.2f}")
                elif sim >= 0.55:
                    confidence = 0.40 + sim * 0.25
                    evidence.append(f"Moderate token similarity: {sim:.2f}")
                else:
                    confidence = sim * 0.4
                    risk_flags.append(f"Low name similarity: {sim:.2f}")

        # 2. Financial Amount & Date Assessment
        amount_diff = pair.feature_scores.amount_diff
        max_amount = max(r1.amount, r2.amount)
        pct_diff = (amount_diff / max_amount) if max_amount > 0 else 0.0

        if amount_diff == 0.0:
            amount_assessment = "EXACT_PARITY"
            evidence.append("Exact amount agreement ($0.00 diff).")
        elif amount_diff <= 28.0 or pct_diff <= 0.05:
            amount_assessment = "WITHIN_FEE_TOLERANCE"
            evidence.append(f"Minor amount discrepancy (${amount_diff:.2f}, {pct_diff:.1%}) consistent with wire/processing fees.")
        else:
            amount_assessment = "DISCREPANT"
            risk_flags.append(f"Significant amount variance: ${amount_diff:.2f} ({pct_diff:.1%}).")
            confidence = max(0.0, confidence - 0.25)

        date_diff = pair.feature_scores.date_diff_days
        if date_diff == 0:
            date_assessment = "SAME_DAY"
            evidence.append("Same-day settlement.")
        elif date_diff <= 5:
            date_assessment = "PLAUSIBLE_TIMING_LAG"
            evidence.append(f"Plausible business day settlement lag ({date_diff} days).")
        elif date_diff <= 10:
            date_assessment = "EXTENDED_LAG"
            evidence.append(f"Extended settlement lag ({date_diff} days).")
        else:
            date_assessment = "OUT_OF_WINDOW"
            risk_flags.append(f"Date lag exceeds standard window ({date_diff} days).")
            confidence = max(0.0, confidence - 0.20)

        # Threshold decision
        acceptance_threshold = get_config().ai_verification.acceptance_threshold
        is_match = confidence >= acceptance_threshold and len(risk_flags) == 0

        decision = "MATCH" if is_match else "NO_MATCH"
        rationale = f"AI verification judged {decision} (confidence {confidence:.2f}). Evidence: {'; '.join(evidence)}."
        if risk_flags:
            rationale += f" Risks: {'; '.join(risk_flags)}."

        latency = (time.time() - t0) * 1000.0 + 1.2  # realistic simulated latency
        cost = 0.00012  # estimated standard token cost for prompt + completion

        return AIVerificationResponse(
            decision=decision,
            confidence=round(confidence, 4),
            rationale=rationale,
            evidence=evidence,
            entity_match=entity_match,
            amount_assessment=amount_assessment,
            date_assessment=date_assessment,
            risk_flags=risk_flags,
            latency_ms=round(latency, 2),
            cost_usd=cost,
            model_used="mock-deterministic-v1",
        )

    @staticmethod
    def _resolve_alias(name: str) -> Optional[str]:
        upper = name.upper()
        clean = upper.replace("*", " ")
        for aliases, canonical in KNOWN_ALIASES:
            for alias in aliases:
                alias_u = alias.upper()
                if alias_u == clean or alias_u in clean or clean in alias_u:
                    return canonical
        return None


class LiveLLMProvider(BaseLLMProvider):
    """Production provider that calls real LLMs (Gemini / OpenAI) with structured schemas."""

    def __init__(self, model: str = "gemini-1.5-flash", timeout: float = 10.0, allow_fallback: bool = False):
        self.model = model
        self.timeout = timeout
        self.allow_fallback = allow_fallback
        self.fallback = MockLLMProvider()

    def verify(self, pair: CandidatePair) -> AIVerificationResponse:
        # Check for live API keys
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if not gemini_key and not openai_key:
            if self.allow_fallback:
                res = self.fallback.verify(pair)
                res.model_used = f"{self.model}-simulated-fallback"
                res.provider_mode = "MOCK"
                return res
            return AIVerificationResponse(
                decision="ERROR",
                confidence=0.0,
                rationale="Live LLM provider invoked without API credentials (neither GEMINI_API_KEY nor OPENAI_API_KEY configured).",
                evidence=[],
                risk_flags=["MISSING_CREDENTIALS"],
                latency_ms=0.0,
                cost_usd=0.0,
                model_used=self.model,
                provider_mode="ERROR",
                is_error=True,
            )

        t0 = time.time()
        prompt = self._build_prompt(pair)

        try:
            if gemini_key:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                # Google Gemini v1beta model list with seamless resilience against demand spikes (503/404)
                candidate_models = [self.model, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-pro-latest"]
                seen = set()
                models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]
                
                response = None
                last_err = None
                for m in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=m,
                            contents=prompt,
                        )
                        self.model = m
                        break
                    except Exception as me:
                        last_err = me
                        continue
                if response is None:
                    raise last_err or RuntimeError("Failed to generate content with Gemini")

                raw_text = response.text or "{}"
                clean_text = raw_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                data = json.loads(clean_text.strip())
            else:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                raw_response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    timeout=self.timeout,
                )
                data = json.loads(raw_response.choices[0].message.content or "{}")

            latency = (time.time() - t0) * 1000.0
            return AIVerificationResponse(
                decision=data.get("decision", "NO_MATCH"),
                confidence=float(data.get("confidence", 0.0)),
                rationale=data.get("rationale", "Live LLM response"),
                evidence=data.get("evidence", []),
                entity_match=bool(data.get("entity_match", False)),
                amount_assessment=data.get("amount_assessment", "UNKNOWN"),
                date_assessment=data.get("date_assessment", "UNKNOWN"),
                risk_flags=data.get("risk_flags", []),
                latency_ms=round(latency, 2),
                cost_usd=0.00025,
                model_used=self.model,
                provider_mode="LIVE",
                is_error=False,
            )
        except Exception as e:
            latency = (time.time() - t0) * 1000.0
            if self.allow_fallback:
                fallback_res = self.fallback.verify(pair)
                fallback_res.rationale += f" (Live API call error: {str(e)[:40]}; used fallback)"
                fallback_res.model_used = f"{self.model}-error-fallback"
                fallback_res.provider_mode = "MOCK"
                return fallback_res
            return AIVerificationResponse(
                decision="ERROR",
                confidence=0.0,
                rationale=f"Live API call to {self.model} failed: {str(e)}",
                evidence=[],
                risk_flags=["API_CALL_FAILED"],
                latency_ms=round(latency, 2),
                cost_usd=0.0,
                model_used=self.model,
                provider_mode="ERROR",
                is_error=True,
            )

    def _build_prompt(self, pair: CandidatePair) -> str:
        return (
            f"You are a strict financial controller AI for Razorpay payment reconciliation.\n"
            f"Evaluate whether these two financial records refer to the same underlying transaction:\n"
            f"Record A: source={pair.record_a.source.value}, counterparty='{pair.record_a.counterparty}', "
            f"amount={pair.record_a.amount} {pair.record_a.currency}, date={pair.record_a.date}\n"
            f"Record B: source={pair.record_b.source.value}, counterparty='{pair.record_b.counterparty}', "
            f"amount={pair.record_b.amount} {pair.record_b.currency}, date={pair.record_b.date}\n"
            f"Composite similarity score: {pair.score:.4f}.\n"
            f"Respond with JSON conforming to: decision ('MATCH'|'NO_MATCH'), confidence (0.0-1.0), "
            f"rationale, evidence (list), entity_match (bool), amount_assessment, date_assessment, risk_flags (list)."
        )


def get_llm_provider(provider_type: Optional[str] = None) -> BaseLLMProvider:
    cfg = get_config().ai_verification
    p_type = provider_type or cfg.provider
    if p_type == "live":
        return LiveLLMProvider(model=cfg.model, timeout=cfg.timeout_seconds)
    return MockLLMProvider()
