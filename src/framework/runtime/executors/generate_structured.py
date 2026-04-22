"""generate(structured) executor — LLM → Pydantic Artifact (§F1-2).

Consults the Step's ProviderPolicy via the injected CapabilityRouter and
asks for a schema-conformant response. Retry on SchemaValidationError or
ProviderTimeout is honored per RetryPolicy.
"""
from __future__ import annotations

import time
from typing import Callable

from pydantic import BaseModel

from framework.core.artifact import (
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind, StepType
from framework.core.policies import RetryPolicy
from framework.providers.base import (
    ProviderCall,
    ProviderError,
    ProviderTimeout,
    SchemaValidationError,
)
from framework.providers.capability_router import CapabilityRouter
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor
from framework.schemas.registry import SchemaRegistry


PromptBuilder = Callable[[StepContext], list[dict[str, str]]]


def default_prompt_builder(ctx: StepContext) -> list[dict[str, str]]:
    """Compose a minimal chat prompt: system from config + user from resolved inputs."""
    system = str(ctx.step.config.get("system_prompt") or (
        "You are a production pipeline extractor. Respond strictly in the required schema."
    ))
    user_parts: list[str] = []
    task_goal = ctx.step.config.get("task_goal")
    if task_goal:
        user_parts.append(f"Goal: {task_goal}")
    for k, v in ctx.inputs.items():
        user_parts.append(f"{k}: {v}")
    if not user_parts:
        user_parts.append("Produce a valid schema instance from the task context.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


class GenerateStructuredExecutor(StepExecutor):
    """LLM → structured Artifact. Expects step.output_schema['schema_ref'] → registry key."""

    step_type = StepType.generate
    capability_ref = "text.structured"

    def __init__(
        self,
        *,
        router: CapabilityRouter,
        schema_registry: SchemaRegistry,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._router = router
        self._schemas = schema_registry
        self._prompt = prompt_builder or default_prompt_builder

    def execute(self, ctx: StepContext) -> ExecutorResult:
        if ctx.step.provider_policy is None:
            raise RuntimeError(
                f"Step {ctx.step.step_id} is 'text.structured' but has no provider_policy"
            )
        schema_ref = (ctx.step.output_schema or {}).get("schema_ref")
        if not schema_ref:
            raise RuntimeError(
                f"Step {ctx.step.step_id} missing output_schema.schema_ref"
            )
        schema_cls = self._schemas.get(schema_ref)

        messages = self._prompt(ctx)
        call = ProviderCall(
            model="<routed>", messages=messages,
            temperature=float(ctx.step.config.get("temperature", 0.0)),
            max_tokens=ctx.step.config.get("max_tokens"),
            seed=ctx.step.config.get("seed"),
        )

        policy = ctx.step.retry_policy or RetryPolicy()
        attempts = max(1, policy.max_attempts)
        last_exc: Exception | None = None
        obj: BaseModel | None = None
        chosen_model: str | None = None
        attempt_count = 0
        usage: dict[str, int] = {}
        for attempt in range(attempts):
            attempt_count = attempt + 1
            try:
                obj, chosen_model, usage = self._router.structured(
                    policy=ctx.step.provider_policy,
                    call_template=call,
                    schema=schema_cls,
                )
                last_exc = None
                break
            except (SchemaValidationError, ProviderTimeout, ProviderError) as exc:
                last_exc = exc
                if attempt + 1 >= attempts or not _should_retry(policy, exc):
                    break
                _backoff(policy, attempt)
                continue
        if obj is None:
            # Re-raise the original typed exception so FailureModeMap can
            # classify it (ProviderTimeout / SchemaValidationError /
            # ProviderError → retry/fallback). Wrapping in RuntimeError
            # was a silent bug: classify() returned None and the run
            # crashed instead of routing through the recovery path.
            assert last_exc is not None
            raise last_exc

        payload = obj.model_dump(mode="json")
        artifact_id = f"{ctx.run.run_id}_{ctx.step.step_id}_out"
        art = ctx.repository.put(
            artifact_id=artifact_id,
            value=payload,
            artifact_type=ArtifactType(
                modality="text", shape="structured", display_name="structured_answer",
            ),
            role=ArtifactRole.intermediate,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="litellm", model=chosen_model or "<unknown>",
            ),
            lineage=Lineage(
                source_artifact_ids=list(ctx.upstream_artifact_ids),
                source_step_ids=[ctx.step.step_id],
            ),
            validation=ValidationRecord(
                status="passed",
                checks=[ValidationCheck(name="schema.instructor_parse", result="passed")],
            ),
            metadata={"schema_ref": schema_ref},
        )
        metrics = {
            "attempts": attempt_count,
            "model": chosen_model or "",
            "usage": usage,
        }
        return ExecutorResult(artifacts=[art], metrics=metrics)


def _should_retry(policy: RetryPolicy, exc: Exception) -> bool:
    # Deterministic unsupported-response shapes never retry — same paid
    # call would yield the same bytes. Mirror of generate_mesh.py.
    from framework.providers.base import ProviderUnsupportedResponse
    if isinstance(exc, ProviderUnsupportedResponse):
        return False
    if "timeout" in policy.retry_on and isinstance(exc, ProviderTimeout):
        return True
    if "schema_fail" in policy.retry_on and isinstance(exc, SchemaValidationError):
        return True
    if "provider_error" in policy.retry_on and isinstance(exc, ProviderError):
        return True
    return False


def _backoff(policy: RetryPolicy, attempt_zero_based: int) -> None:
    if policy.backoff == "exponential":
        time.sleep(min(2 ** attempt_zero_based, 8) * 0.01)   # small test-friendly scale
    # fixed: no sleep
