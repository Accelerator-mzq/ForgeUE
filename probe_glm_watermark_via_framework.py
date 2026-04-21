"""Verify `watermark_enabled=false` propagates through the framework path:
  Bundle config → CapabilityRouter.aimage_generation → LiteLLMAdapter →
  litellm.aimage_generation → POST /v4/images/generations.

If this works, bundle authors can drop `step.config.extra.watermark_enabled=false`
and get clean output automatically. If LiteLLM drops the unknown param, we'd
need a different surface.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# NOTE: filesystem + env side-effects + framework imports are intentionally
# deferred to runtime. Module-level `hydrate_env()` / `_OUT.mkdir()` / heavy
# framework imports would crash on import in read-only sandboxes or clean
# environments without the key, blocking static-analysis callers that only
# need `inspect.getsource(mod)`. Mirrors the pattern in probe_hunyuan_3d_format.py.

_OUT = Path("./demo_artifacts/probe_debug")


async def _go() -> None:
    # Lazy: hydrate env + import framework bits inside the runtime path so
    # module import stays side-effect-free.
    from framework.observability.secrets import hydrate_env
    hydrate_env()

    from framework.core.policies import PreparedRoute, ProviderPolicy
    from framework.providers.capability_router import CapabilityRouter
    from framework.providers.litellm_adapter import LiteLLMAdapter

    _OUT.mkdir(parents=True, exist_ok=True)   # lazy — never at import

    router = CapabilityRouter()
    router.register(LiteLLMAdapter())

    import os
    if "ZHIPU_API_KEY" not in os.environ:
        raise SystemExit(
            "ZHIPU_API_KEY not found in environment or .env; "
            "cannot run GLM framework watermark probe"
        )
    policy = ProviderPolicy(
        capability_required="probe",
        prepared_routes=[PreparedRoute(
            model="openai/glm-image",
            api_key_env="ZHIPU_API_KEY",
            api_base="https://open.bigmodel.cn/api/paas/v4",
            kind="image",
        )],
    )

    # Two trials: with and without the watermark param via `extra`.
    for label, extra in [
        ("default_expect_watermark", {}),
        ("extra_watermark_enabled_false", {"watermark_enabled": False}),
    ]:
        print(f"\n===== {label} =====")
        print(f"extra payload: {extra}")
        results, chosen = await router.aimage_generation(
            policy=policy,
            prompt="a tiny red square on a plain white background, centered",
            n=1, size="1024x1024", timeout_s=120.0, extra=extra,
        )
        r = results[0]
        out = _OUT / f"framework_{label}.png"
        out.write_bytes(r.data)
        print(f"chosen model: {chosen}")
        print(f"raw payload keys: {list(r.raw.keys())}")
        print(f"url (for reference): {r.raw.get('url', '<no url>')}")
        print(f"saved → {out.as_posix()} ({len(r.data)} bytes)")
        print("→ Inspect bottom-right corner for 'AI生成' label.")


if __name__ == "__main__":
    asyncio.run(_go())
