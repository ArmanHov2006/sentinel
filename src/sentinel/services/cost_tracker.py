"""Per-request cost tracking based on model pricing tables."""

from dataclasses import dataclass, field

from sentinel.core.metrics import sentinel_metrics
from sentinel.domain.models import CostCalculation, TokenUsage


@dataclass(frozen=True)
class ModelPricing:
    """Pricing for a model."""

    input_price: float = field(default=0.0)
    output_price: float = field(default=0.0)


MODEL_PRICING = {
    "gpt-4o": ModelPricing(input_price=2.50, output_price=10.00),
    "gpt-4o-mini": ModelPricing(input_price=0.15, output_price=0.60),
    "claude-3-5-sonnet-20241022": ModelPricing(input_price=3.00, output_price=15.00),
    "claude-3-5-haiku-20241022": ModelPricing(input_price=0.80, output_price=4.00),
}


class CostTracker:
    """Cost tracker for a request."""

    def calculate(self, usage: TokenUsage) -> CostCalculation:
        pricing = MODEL_PRICING.get(usage.model, ModelPricing())
        prompt_cost = (usage.prompt_tokens / 1_000_000) * pricing.input_price
        completion_cost = (usage.completion_tokens / 1_000_000) * pricing.output_price
        cost = CostCalculation(
            prompt_cost=prompt_cost, completion_cost=completion_cost, usage=usage
        )
        sentinel_metrics.record_cost(cost=cost)
        return cost
