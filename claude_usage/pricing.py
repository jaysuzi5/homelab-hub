"""
Blended cost-per-token computation for API-equivalent cost estimation.
Prices are stored in HubConfig so they can be updated without a deploy.
All costs are reference-only — not actual billing (Pro plan, costUSD is always 0).
"""

import json
from decimal import Decimal
from config.utils import get_config

# HubConfig key for the pricing table JSON blob
PRICING_KEY = "claude_pricing_table"

DEFAULT_PRICING = {
    "claude-opus": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-sonnet": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-haiku": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.03,
        "cache_write": 0.30,
    },
}


def get_pricing_table() -> dict:
    raw = get_config(PRICING_KEY)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return DEFAULT_PRICING


def _model_family(model_id: str) -> str:
    """Map a full model ID like 'claude-sonnet-4-5-20250929' to a pricing family key."""
    lower = model_id.lower()
    if "opus" in lower:
        return "claude-opus"
    if "sonnet" in lower:
        return "claude-sonnet"
    if "haiku" in lower:
        return "claude-haiku"
    return "claude-sonnet"


def compute_blended_rates(model_usage: dict) -> dict[str, Decimal]:
    """
    Given the lifetime modelUsage dict from stats-cache.json, return a mapping of
    model_id -> blended cost-per-token (USD) derived from the lifetime input/output/cache split.

    Used to estimate daily costs from dailyModelTokens (which only has totals, not split).
    """
    pricing = get_pricing_table()
    rates: dict[str, Decimal] = {}

    for model_id, usage in model_usage.items():
        input_t = usage.get("inputTokens", 0)
        output_t = usage.get("outputTokens", 0)
        cache_read_t = usage.get("cacheReadInputTokens", 0)
        cache_write_t = usage.get("cacheCreationInputTokens", 0)
        total = input_t + output_t + cache_read_t + cache_write_t

        if total == 0:
            rates[model_id] = Decimal("0")
            continue

        family = _model_family(model_id)
        p = pricing.get(family, pricing["claude-sonnet"])

        # USD per million tokens -> USD per token
        cost = (
            input_t * p["input"]
            + output_t * p["output"]
            + cache_read_t * p["cache_read"]
            + cache_write_t * p["cache_write"]
        ) / 1_000_000

        rates[model_id] = Decimal(str(round(cost / total, 10)))

    return rates


def cost_for_tokens(model_id: str, total_tokens: int, blended_rates: dict[str, Decimal]) -> Decimal:
    """Return estimated USD cost for `total_tokens` of a given model."""
    rate = blended_rates.get(model_id)
    if rate is None:
        pricing = get_pricing_table()
        family = _model_family(model_id)
        p = pricing.get(family, pricing["claude-sonnet"])
        # No lifetime data — use input price as conservative estimate
        rate = Decimal(str(p["input"] / 1_000_000))
    return (rate * total_tokens).quantize(Decimal("0.000001"))
