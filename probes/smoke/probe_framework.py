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
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Project-local scratch for probe outputs. See CLAUDE.md §产物路径约定 — never use /tmp on Windows.
# First call to _get_out_dir() lazily picks a timestamped subdir under
# ./demo_artifacts/<YYYY-MM-DD>/probes/smoke/framework/<HHMMSS>/; later calls
# reuse it so all artifacts from one run land together.
_OUT_DIR_CACHE: Path | None = None


def _get_out_dir() -> Path:
    global _OUT_DIR_CACHE
    if _OUT_DIR_CACHE is None:
        from probes._output import probe_output_dir
        _OUT_DIR_CACHE = probe_output_dir("smoke", "framework")
    return _OUT_DIR_CACHE


def _env_flag_enabled(name: str) -> bool:
    """Explicit opt-in parse: only "1" / "true" / "yes" / "on" (case-insensitive)
    count as enabled. Empty string, "0", "false", "no", "off" → disabled.

    Plain `os.environ.get(name)` truthy check treats *any* non-empty value
    as set, which silently enables flags written `FLAG=0` or `FLAG=false`
    in `.env` files — exactly the anti-pattern the flag is supposed to
    prevent for billable probes like Hunyuan 3D mesh.
    """
    val = (os.environ.get(name) or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _save(alias: str, model: str, ext: str, data: bytes) -> str:
    """Write probe output bytes to demo_artifacts/<date>/probes/smoke/framework/<HHMMSS>/.
    Returns relative path."""
    out_dir = _get_out_dir()
    safe_model = model.replace("/", "_").replace(":", "_")
    out = out_dir / f"{alias}__{safe_model}.{ext}"
    out.write_bytes(data)
    return out.as_posix()

from framework.observability.secrets import hydrate_env

# NOTE: `hydrate_env()` is intentionally deferred to `main()`. Module-level
# env mutation would fire on `import probe_framework` even in read-only
# sandboxes, blocking static-analysis callers like
# `tests/unit/test_probe_framework.py::inspect.getsource(...)`. Mirrors
# the pattern in probe_hunyuan_3d_format.py. 2026-04 共性平移 PR-3.

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


def _probe_route(router: CapabilityRouter, alias: str, route) -> tuple[str, str]:
    """Return ("ok" | "fail" | "skip", detail). Tristate matters because
    non-availability (no API key, mesh opt-in guard) is a deliberate
    decision, not a bug — main() must not conflate it with failures or
    return a nonzero exit code."""
    if not route.api_key_env:
        return "skip", "skip (no api_key_env on route)"
    if not os.environ.get(route.api_key_env):
        return "skip", f"skip (env {route.api_key_env} not set)"

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
            # Mesh probes are expensive (~¥0.5-2/call for Hunyuan 3D). Guard
            # behind FORGEUE_PROBE_MESH=1 so casual `python probe_framework.py`
            # runs don't silently burn 3D quota. Opt in explicitly when you
            # actually want to verify the mesh pipeline.
            if not _env_flag_enabled("FORGEUE_PROBE_MESH"):
                return "skip", "skip (mesh is opt-in; set FORGEUE_PROBE_MESH=1)"
            # Dedicated worker path —— bypass router
            key = os.environ[route.api_key_env]
            if route.model.startswith("hunyuan/"):
                worker = HunyuanMeshWorker(api_key=key)
                worker._poll = 1.0      # 快速 polling for test
                worker._default_timeout_s = 120.0
            elif route.model.startswith("tripo3d/"):
                worker = Tripo3DWorker(api_key=key, poll_interval_s=2.0)
            else:
                return "fail", f"no worker known for {route.model}"
            cands = worker.generate(
                source_image_bytes=_TINY_PNG_BYTES, spec={"format": "glb"},
                num_candidates=1, timeout_s=180.0,
            )
            # Use the worker's detected format (not a hardcoded "glb"), so
            # OBJ / FBX / other legitimate responses land with the correct
            # extension and label. Pre-fix this line always saved `.glb`,
            # which would recreate the "corrupted .glb on disk" bug the
            # mesh_worker magic-byte detection was meant to eliminate.
            detected_fmt = cands[0].format or "bin"
            saved = _save(alias, route.model, detected_fmt, cands[0].data)
            return "ok", (
                f"ok — {len(cands[0].data)}B {detected_fmt.upper()} → {saved}"
            )

        if route.kind in ("image", "image_edit"):
            # Size 1024x1024 (原来是 512x512) —— 512 是多家 provider 的合法下限
            # 但非推荐尺寸,GLM-Image 在 512 下产物会退化到近乎空白(见
            # probe_glm_image_debug.py 验证);1024 对所有 provider 都落在
            # "正常训练分布"里,probe 结论才公平。
            kwargs = dict(policy=policy, prompt="a tiny red square",
                           n=1, size="1024x1024", timeout_s=120.0)
            if route.kind == "image_edit":
                results, chosen = router.image_edit(
                    source_image_bytes=_TINY_PNG_BYTES, **kwargs
                )
            else:
                results, chosen = router.image_generation(**kwargs)
            ext = getattr(results[0], "format", "png") or "png"
            saved = _save(alias, route.model, ext, results[0].data)
            return "ok", f"ok via {chosen} — {len(results[0].data)}B → {saved}"

        # text / vision
        call = ProviderCall(
            model="<routed>",
            messages=[{"role": "user", "content": "reply only the word pong"}],
            temperature=0.0, max_tokens=32,
        )
        res, chosen = router.completion(policy=policy, call_template=call)
        return "ok", f"ok via {chosen} — {res.text[:40].strip()!r}"
    except ProviderError as e:
        return "fail", f"ProviderError: {str(e)[:200]}"
    except Exception as e:
        return "fail", f"{type(e).__name__}: {str(e)[:200]}"


def main() -> int:
    # Lazy init — hydrate env + reset registry on probe invocation, not
    # at module import (safe for static-analysis callers in no-key envs).
    hydrate_env()
    reset_model_registry()
    reg = get_model_registry()
    router = _build_router()

    seen = set()
    ok = fail = skip = 0
    print(f"{'alias':<22} {'model':<40} {'kind':<11} status detail")
    print("-" * 130)
    for alias_name in reg.names():
        alias = reg.resolve(alias_name)
        for r in alias.routes():
            key = (alias_name, r.model, r.kind)
            if key in seen:
                continue
            seen.add(key)
            outcome, detail = _probe_route(router, alias_name, r)
            mark = {"ok": "✅", "fail": "❌", "skip": "⏭️"}[outcome]
            if outcome == "ok":
                ok += 1
            elif outcome == "fail":
                fail += 1
            else:
                skip += 1
            print(f"{alias_name:<22} {r.model:<40} {r.kind:<11} {mark} {detail}")
            time.sleep(1.0)

    print("-" * 130)
    # Exit status reflects real failures only; explicit skips (missing key,
    # mesh opt-in) are deliberate non-executions and must not fail the run.
    total = ok + fail + skip
    print(f"Totals: {ok}/{total} ok, {fail} fail, {skip} skip")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
