"""Verify every alias actually routes through the framework (CapabilityRouter +
adapters + workers) —— not just raw HTTP. Confirms C-plan wiring.

For each alias and each of its prepared_routes, pick the correct entrypoint:
  kind=text/vision  → router.structured or .completion
  kind=image        → router.image_generation
  kind=image_edit   → router.image_edit with a 1×1 red PNG source
  kind=mesh         → GenerateMeshExecutor via MeshWorker

Runs serially with throttle; reports per-route status.
"""
from __future__ import annotations

import base64
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8")

from framework.observability.secrets import hydrate_env
hydrate_env()

from framework.providers.capability_router import CapabilityRouter
from framework.providers.litellm_adapter import LiteLLMAdapter
from framework.providers.qwen_multimodal_adapter import QwenMultimodalAdapter
from framework.providers.hunyuan_tokenhub_adapter import HunyuanImageAdapter
from framework.providers.workers.mesh_worker import HunyuanMeshWorker, Tripo3DWorker
from framework.providers.base import ProviderError, ProviderCall
from framework.providers.model_registry import (
    get_model_registry, reset_model_registry,
)
from framework.core.policies import PreparedRoute, ProviderPolicy


_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+h"
    "HgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)
_TINY_PNG_BYTES = base64.b64decode(_TINY_PNG_B64)


def _build_router() -> CapabilityRouter:
    router = CapabilityRouter()
    # Specialized adapters first (for qwen/* and hunyuan/* prefixes);
    # LiteLLM last (it claims supports(*)=True).
    router.register(QwenMultimodalAdapter())
    router.register(HunyuanImageAdapter())
    router.register(LiteLLMAdapter())
    return router


def _probe_route(router: CapabilityRouter, alias: str, route) -> tuple[bool, str]:
    if not route.api_key_env:
        return False, "skip (no api_key_env on route)"
    if not os.environ.get(route.api_key_env):
        return False, f"skip (env {route.api_key_env} not set)"

    # ResolvedRoute (dataclass from registry) → PreparedRoute (Pydantic for policy)
    prepared = PreparedRoute(
        model=route.model,
        api_key_env=route.api_key_env,
        api_base=route.api_base,
        kind=route.kind,
    )
    policy = ProviderPolicy(
        capability_required="probe",
        prepared_routes=[prepared],
    )
    # Hereafter use `prepared` as the route proxy
    route = prepared
    try:
        if route.kind == "mesh":
            # Dedicated worker path —— bypass router
            key = os.environ[route.api_key_env]
            if route.model.startswith("hunyuan/"):
                worker = HunyuanMeshWorker(api_key=key)
                worker._poll = 1.0      # 快速 polling for test
                worker._default_timeout_s = 120.0
            elif route.model.startswith("tripo3d/"):
                worker = Tripo3DWorker(api_key=key, poll_interval_s=2.0)
            else:
                return False, f"no worker known for {route.model}"
            cands = worker.generate(
                source_image_bytes=_TINY_PNG_BYTES, spec={"format": "glb"},
                num_candidates=1, timeout_s=180.0,
            )
            return True, f"ok — {len(cands[0].data)}B GLB bytes"

        if route.kind in ("image", "image_edit"):
            kwargs = dict(policy=policy, prompt="a tiny red square",
                           n=1, size="512x512", timeout_s=120.0)
            if route.kind == "image_edit":
                results, chosen = router.image_edit(
                    source_image_bytes=_TINY_PNG_BYTES, **kwargs
                )
            else:
                results, chosen = router.image_generation(**kwargs)
            return True, f"ok via {chosen} — {len(results[0].data)}B"

        # text / vision
        call = ProviderCall(
            model="<routed>",
            messages=[{"role": "user", "content": "reply only the word pong"}],
            temperature=0.0, max_tokens=32,
        )
        res, chosen = router.completion(policy=policy, call_template=call)
        return True, f"ok via {chosen} — {res.text[:40].strip()!r}"
    except ProviderError as e:
        return False, f"ProviderError: {str(e)[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def main() -> int:
    reset_model_registry()
    reg = get_model_registry()
    router = _build_router()

    seen = set()
    total = ok = 0
    print(f"{'alias':<22} {'model':<40} {'kind':<11} status detail")
    print("-" * 130)
    for alias_name in reg.names():
        alias = reg.resolve(alias_name)
        for r in alias.routes():
            key = (alias_name, r.model, r.kind)
            if key in seen:
                continue
            seen.add(key)
            total += 1
            success, detail = _probe_route(router, alias_name, r)
            mark = "✅" if success else "❌"
            if success:
                ok += 1
            print(f"{alias_name:<22} {r.model:<40} {r.kind:<11} {mark} {detail}")
            time.sleep(1.0)

    print("-" * 130)
    print(f"Totals: {ok}/{total} routes verified through framework")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
