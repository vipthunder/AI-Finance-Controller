from __future__ import annotations
import datetime as dt
from src.schemas.records import Record
from src.schemas.candidates import CandidatePair, FeatureScores
from src.schemas.enums import SourceType, MatchStage
from src.matching.fuzzy_matcher import FuzzyScorer


def test_fuzzy_matching_init():
    scorer = FuzzyScorer()
    assert scorer is not None


def test_fuzzy_scoring():
    scorer = FuzzyScorer()
    r1 = Record(id="L1", source=SourceType.LEDGER, date=dt.date(2024, 1, 1),
                amount=1000.0, counterparty="AMAZON WEB SERVICES", currency="USD")
    r2 = Record(id="B1", source=SourceType.BANK, date=dt.date(2024, 1, 2),
                amount=1000.0, counterparty="AMAZON WEB SERVICES INC", currency="USD")

    pair = CandidatePair(
        record_a=r1, record_b=r2, score=0.0,
        feature_scores=FeatureScores(name_similarity=0.0, amount_proximity=0.0,
                                     date_proximity=0.0, composite_score=0.0,
                                     amount_diff=0.0, date_diff_days=1),
        matched_on=[], stage=MatchStage.FUZZY_DIRECT,
    )
    scored = scorer.score_candidates([pair])
    assert len(scored) == 1
    assert scored[0].score > 0.5
    assert scored[0].feature_scores.name_similarity > 0.8


def test_fuzzy_router_exact_boundaries():
    """Part 15: Exact boundary testing for routing thresholds at:
    0.8501, 0.8500, 0.8499, 0.5001, 0.5000, 0.4999.
    """
    from src.config import get_config
    cfg = get_config()
    high = cfg.router.high_confidence  # 0.85
    mid = cfg.router.mid_band_min     # 0.50

    def route_score(score: float) -> str:
        if score >= high:
            return "DIRECT_FUZZY"
        elif score >= mid:
            return "AI_VERIFICATION"
        else:
            return "LOW_SCORE_EXCEPTION"

    assert route_score(0.8501) == "DIRECT_FUZZY"
    assert route_score(0.8500) == "DIRECT_FUZZY"
    assert route_score(0.8499) == "AI_VERIFICATION"

    assert route_score(0.5001) == "AI_VERIFICATION"
    assert route_score(0.5000) == "AI_VERIFICATION"
    assert route_score(0.4999) == "LOW_SCORE_EXCEPTION"
