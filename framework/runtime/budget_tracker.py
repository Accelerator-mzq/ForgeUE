"""BudgetPolicy enforcement —— preflight + per-step runtime accumulator.

Two layers:

1. **DryRunPass `budget_cap_sane_check`** —— declared `total_cost_cap_usd` must
   exist on production / ue_export tasks (warn if missing on runs that include
   LLM calls). Cost *estimation* is deliberately NOT done preflight; budgets
   are observed against realised spend during the run.

2. **BudgetTracker** —— accumulates `ProviderResult.usage` / per-call cost
   after every LLM or image call; before the next step runs the orchestrator
   queries `would_exceed(cap)` and, if True, synthesises a
   `Decision.human_review_required` verdict via the FailureModeMap so the run
   terminates cleanly (with a `termination_reason="budget_exceeded"`) instead
   of silently burning cap.

Cost is estimated via LiteLLM's `completion_cost` when available; for models
LiteLLM doesn't know, we estimate `prompt_tokens * cost_per_1k / 1000` using
pricing hints in `BudgetPolicy.cost_per_1k_usd` (optional dict).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from framework.core.policies import BudgetPolicy


@dataclass
class BudgetSpend:
    """Per-run running total + per-step breakdown."""

    total_usd: float = 0.0
    by_step: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, float] = field(default_factory=dict)
    call_count: int = 0


class BudgetExceeded(RuntimeError):
    """Raised when a step's marginal cost would push total over the cap."""


class BudgetTracker:
    """Per-Run cost accumulator. Cheap, dict-only; no external IO."""

    def __init__(self, policy: BudgetPolicy | None = None) -> None:
        self._policy = policy or BudgetPolicy()
        self._spend = BudgetSpend()

    @property
    def spend(self) -> BudgetSpend:
        return self._spend

    @property
    def policy(self) -> BudgetPolicy:
        return self._policy

    @property
    def cap_usd(self) -> float | None:
        return self._policy.total_cost_cap_usd

    def record(self, *, step_id: str, model: str, cost_usd: float) -> None:
        """Add a call's cost to the running tally."""
        self._spend.total_usd += cost_usd
        self._spend.by_step[step_id] = self._spend.by_step.get(step_id, 0.0) + cost_usd
        self._spend.by_model[model] = self._spend.by_model.get(model, 0.0) + cost_usd
        self._spend.call_count += 1

    def check(self) -> bool:
        """True if total is still under the cap (or cap is unset)."""
        cap = self.cap_usd
        return cap is None or self._spend.total_usd <= cap

    def would_exceed_after(self, extra_usd: float) -> bool:
        """Preflight: would adding *extra_usd* push us over the cap?"""
        cap = self.cap_usd
        if cap is None:
            return False
        return self._spend.total_usd + extra_usd > cap

    def assert_within(self) -> None:
        """Raise BudgetExceeded if already past the cap."""
        if not self.check():
            raise BudgetExceeded(
                f"budget cap {self.cap_usd} USD exceeded: "
                f"spent {self._spend.total_usd:.4f} in {self._spend.call_count} calls"
            )

    def summary(self) -> dict:
        return {
            "cap_usd": self.cap_usd,
            "total_usd": round(self._spend.total_usd, 6),
            "call_count": self._spend.call_count,
            "by_step_usd": {k: round(v, 6) for k, v in self._spend.by_step.items()},
            "by_model_usd": {k: round(v, 6) for k, v in self._spend.by_model.items()},
        }


def estimate_call_cost_usd(*, model: str, usage: dict[str, int] | None = None,
                            fallback_cost_per_1k: float = 0.0) -> float:
    """Best-effort cost estimation for one completed LLM call.

    Uses LiteLLM's built-in pricing table when available (most Anthropic /
    OpenAI / Google models have entries). Falls back to `fallback_cost_per_1k`
    applied to total usage tokens for unknown models.

    Image-gen / mesh calls where usage is unknown default to a small fixed
    estimate per call (`fallback_cost_per_1k` interpreted as per-call cost).
    """
    try:
        from litellm import completion_cost
    except ImportError:
        return _fallback_cost(usage, fallback_cost_per_1k)
    try:
        # LiteLLM accepts either a response object or (model, prompt_tokens,
        # completion_tokens) args. We pass model + usage as completion_response
        # kwargs; easier path is constructing a minimal mock.
        prompt = (usage or {}).get("prompt", 0) if usage else 0
        completion = (usage or {}).get("completion", 0) if usage else 0
        mock_resp = {
            "model": model,
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
        }
        cost = completion_cost(completion_response=mock_resp, model=model)
        return float(cost) if cost else _fallback_cost(usage, fallback_cost_per_1k)
    except Exception:
        return _fallback_cost(usage, fallback_cost_per_1k)


def _fallback_cost(usage: dict[str, int] | None, cost_per_1k: float) -> float:
    if not usage:
        return cost_per_1k      # treated as per-call when no token info
    total_tokens = (usage.get("prompt", 0) + usage.get("completion", 0))
    return total_tokens / 1000.0 * cost_per_1k


def estimate_image_call_cost_usd(
    *, model: str, n: int = 1, size: str = "1024x1024",
    fallback_per_image_usd: float = 0.01,
) -> float:
    """Best-effort cost estimate for one `image_generation` call producing *n* images.

    LiteLLM's pricing table covers DALL-E / Flux / Imagen sizes; for
    unknown image models (Qwen DashScope, Hunyuan tokenhub, self-hosted
    Comfy) we fall back to a flat *fallback_per_image_usd × n* so the
    BudgetTracker has something non-zero to accumulate.
    """
    if n <= 0:
        return 0.0
    try:
        from litellm import completion_cost
    except ImportError:
        return fallback_per_image_usd * n
    try:
        cost = completion_cost(
            model=model, call_type="image_generation",
            size=size, n=n, quality="standard",
        )
        if cost:
            return float(cost)
    except Exception:
        pass
    return fallback_per_image_usd * n
