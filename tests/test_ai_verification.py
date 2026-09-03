from __future__ import annotations
import datetime as dt
from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.enums import SourceType, MatchStage
from src.verification.ai_verifier import AIVerifier, AI_CONFIDENCE_THRESHOLD


def test_ai_verification_init():
    verifier = AIVerifier()
    assert verifier is not None


def test_ai_threshold_is_locked():
    assert AI_CONFIDENCE_THRESHOLD == 0.75


def test_ai_verifies_substring_match():
    verifier = AIVerifier()
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=1000.0, counterparty="AMAZON WEB SERVICES", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
                amount=1000.0, counterparty="AMAZON WEB SERVICES INC", currency="USD")

    pair = CandidatePair(
        record_a=r1, record_b=r2, score=0.6,
        feature_scores=FeatureScores(name_similarity=0.8, amount_proximity=1.0,
                                     date_proximity=1.0, composite_score=0.6,
                                     amount_diff=0.0, date_diff_days=0),
        matched_on=[], stage=MatchStage.FUZZY_DIRECT,
    )
    verified, rejected = verifier.verify_candidates([pair])
    assert len(verified) == 1
    assert verified[0].stage == MatchStage.AI_VERIFIED


def test_ai_rejects_low_similarity():
    verifier = AIVerifier()
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=1000.0, counterparty="ACME GLOBAL", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
                amount=1000.0, counterparty="STRIPE INC", currency="USD")

    pair = CandidatePair(
        record_a=r1, record_b=r2, score=0.55,
        feature_scores=FeatureScores(name_similarity=0.3, amount_proximity=1.0,
                                     date_proximity=1.0, composite_score=0.55,
                                     amount_diff=0.0, date_diff_days=0),
        matched_on=[], stage=MatchStage.FUZZY_DIRECT,
    )
    verified, rejected = verifier.verify_candidates([pair])
    assert len(verified) == 0
    assert len(rejected) == 1


def test_ai_accepted_but_validator_rejected_is_not_resolved():
    """Phase 20: Mandatory regression test: AI -> ACCEPT, Validator -> REJECT => NOT RESOLVED."""
    from src.validation.deterministic_validator import DeterministicValidator
    from src.controller.decision_controller import DecisionController
    from src.schemas.enums import ResolutionStatus, ExceptionReason

    verifier = AIVerifier()
    # Amount difference exceeds $28 validator threshold ($50 > $28)
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=1000.0, counterparty="AMAZON WEB SERVICES", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 2),
                amount=1050.0, counterparty="AMAZON WEB SERVICES INC", currency="USD")

    pair = CandidatePair(
        record_a=r1, record_b=r2, score=0.70,
        feature_scores=FeatureScores(name_similarity=0.9, amount_proximity=0.95,
                                     date_proximity=0.99, composite_score=0.70,
                                     amount_diff=50.0, date_diff_days=1),
        matched_on=[], stage=MatchStage.FUZZY_DIRECT,
    )

    # 1. AI accepts candidate based on semantic match
    verified, rejected = verifier.verify_candidates([pair])
    assert len(verified) == 1, "AI should recommend accepted pair based on strong alias"

    # 2. Authoritative deterministic validator independently checks the AI recommendation
    validator = DeterministicValidator()
    val_res = validator.validate(verified[0], committed_keys=set())
    assert val_res.is_valid is False, "Deterministic validator must reject amount difference exceeding $28"
    assert any("amount" in f.lower() for f in val_res.failed_checks)

    # 3. Decision controller verifies it is NOT committed as RESOLVED
    controller = DecisionController()
    d1, d2 = controller.record_validation_failed(verified[0], val_res)
    assert d1.status == ResolutionStatus.EXCEPTION
    assert d2.status == ResolutionStatus.EXCEPTION
    assert d1.exception_reason == ExceptionReason.VALIDATION_FAILED
    assert d2.exception_reason == ExceptionReason.VALIDATION_FAILED
    assert "amount" in d1.rationale.lower()


def test_live_llm_provider_honesty_on_failure(monkeypatch):
    """Phase 16: LiveLLMProvider with missing/invalid credentials returns error, never silent mock."""
    from src.verification.llm_provider import LiveLLMProvider

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    provider = LiveLLMProvider(model="gemini-1.5-flash", allow_fallback=False)
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=100.0, counterparty="CORP A", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 1),
                amount=100.0, counterparty="CORP B", currency="USD")
    pair = CandidatePair(
        record_a=r1, record_b=r2, score=0.6,
        feature_scores=FeatureScores(name_similarity=0.5, amount_proximity=1.0,
                                     date_proximity=1.0, composite_score=0.6,
                                     amount_diff=0.0, date_diff_days=0),
        matched_on=[], stage=MatchStage.FUZZY_DIRECT,
    )

    response = provider.verify(pair)
    assert response.is_error is True, "Live provider must signal is_error=True on credential failure"
    assert response.provider_mode == "ERROR"


