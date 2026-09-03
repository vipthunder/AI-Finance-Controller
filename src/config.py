from __future__ import annotations
import os
import yaml
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class RouterConfig(BaseModel):
    high_confidence: float = 0.85
    mid_band_min: float = 0.50


class AIVerificationConfig(BaseModel):
    acceptance_threshold: float = 0.75
    provider: str = "mock"  # "live" or "mock"
    model: str = "gemini-1.5-flash"
    max_retries: int = 2
    timeout_seconds: float = 10.0


class ValidatorConfig(BaseModel):
    max_amount_abs_tolerance: float = 28.0
    max_amount_pct_tolerance: float = 0.05
    max_date_tolerance_days: int = 10


class CandidateGenerationConfig(BaseModel):
    max_date_diff_days: int = 14
    max_amount_pct_diff: float = 0.20
    max_amount_abs_diff: float = 60.0
    enable_reference_blocking: bool = True
    enable_entity_blocking: bool = True
    enable_proximity_blocking: bool = True


class ScoringConfig(BaseModel):
    weight_name: float = 0.40
    weight_amount: float = 0.40
    weight_date: float = 0.20


class NormalizationConfig(BaseModel):
    strip_corporate_suffixes: bool = True
    clean_punctuation: bool = True


class AppConfig(BaseModel):
    router: RouterConfig = Field(default_factory=RouterConfig)
    ai_verification: AIVerificationConfig = Field(default_factory=AIVerificationConfig)
    validator: ValidatorConfig = Field(default_factory=ValidatorConfig)
    candidate_generation: CandidateGenerationConfig = Field(default_factory=CandidateGenerationConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    normalization: NormalizationConfig = Field(default_factory=NormalizationConfig)

    @classmethod
    def load(
        cls,
        thresholds_path: Optional[str] = None,
        settings_path: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> AppConfig:
        config_data: Dict[str, Any] = {}

        # Resolve paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        t_path = thresholds_path or os.path.join(base_dir, "configs", "thresholds.yaml")
        s_path = settings_path or os.path.join(base_dir, "configs", "settings.yaml")

        # Load base settings first
        if os.path.exists(s_path):
            with open(s_path, "r", encoding="utf-8") as f:
                s_data = yaml.safe_load(f) or {}
                if "normalization" in s_data:
                    config_data.setdefault("normalization", {}).update(s_data["normalization"])

        # Load authoritative locked thresholds second so they take precedence
        if os.path.exists(t_path):
            with open(t_path, "r", encoding="utf-8") as f:
                t_data = yaml.safe_load(f) or {}
                config_data.update(t_data)

        if overrides:
            for k, v in overrides.items():
                if isinstance(v, dict) and k in config_data and isinstance(config_data[k], dict):
                    config_data[k].update(v)
                else:
                    config_data[k] = v

        return cls.model_validate(config_data)


# Global default configuration instance
_CONFIG_INSTANCE: Optional[AppConfig] = None


def get_config(reload: bool = False, overrides: Optional[Dict[str, Any]] = None) -> AppConfig:
    global _CONFIG_INSTANCE
    if _CONFIG_INSTANCE is None or reload or overrides is not None:
        _CONFIG_INSTANCE = AppConfig.load(overrides=overrides)
    return _CONFIG_INSTANCE


def reset_config() -> AppConfig:
    global _CONFIG_INSTANCE
    _CONFIG_INSTANCE = AppConfig.load()
    return _CONFIG_INSTANCE
