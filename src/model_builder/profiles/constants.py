"""Shared constants for strategy profile management."""

PROFILE_SCHEMA_VERSION = "1.0.0"

# Default warmup period applied when a strategy profile does not provide one.
DEFAULT_ATR_WARMUP_DAYS = 14

# Guardrail to ensure at least one day of holdout data is available.
MIN_HOLDOUT_DAYS = 1

# Directory names used by storage helpers; kept here for single-source of truth.
STRATEGY_PROFILES_DIRNAME = "strategy_profiles"
EVALUATIONS_DIRNAME = "evaluations"
