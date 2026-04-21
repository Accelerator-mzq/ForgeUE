"""Connectivity probe for every route in every alias of config/models.yaml.

Routes dispatch by `kind` + model-id-prefix because each provider family has
its own wire protocol:

| Kind/Prefix                      | Protocol                                                                   |
| -------------------------------- | -------------------------------------------------------------------------- |
| text / vision,  prefix=anthropic | POST <base>/v1/messages    (x-api-key header, Anthropic-style)             |
| text / vision,  prefix=openai    | POST <base>/chat/completions (Bearer, OpenAI compat — GLM / Qwen-Plus)      |
| text / vision,  prefix=gemini    | skip (native GOOGLE key probe — we don't have it in .env right now)        |
| image,          prefix=openai    | POST <base>/images/generations (OpenAI compat — GLM-Image candidate)        |
| image/edit,     prefix=qwen      | POST dashscope .../multimodal-generation/generation  (DashScope native)    |
| image/edit,     prefix=hunyuan   | POST tokenhub /image/submit + /image/query  (submit+poll)                  |
| mesh,           prefix=hunyuan   | POST tokenhub /3d/submit    + /3d/query                                    |
| mesh,           prefix=tripo3d   | POST api.tripo3d.ai/v2/task (already-implemented Tripo3DWorker surface)    |

Each probe tries ONE minimal call and reports status + first 200 chars of
response body. The point is to see whether `.env` key + URL + model id combine
correctly — not to do real work.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

from framework.observability.secrets import hydrate_env
from framework.providers.model_registry import (
    get_model_registry,
    reset_model_registry,
)

# NOTE: `hydrate_env()` + `reset_model_registry()` are intentionally
# deferred to runtime. Module-level env mutation + registry reset would
# fire on `import probe_aliases` even in read-only sandboxes (CI) or
# clean environments, blocking static-analysis callers like
# `tests/unit/test_probe_framework.py::inspect.getsource(...)`. Mirrors
# the pattern in probe_hunyuan_3d_format.py / probe_glm_*.py. 2026-04
# 共性平移 PR-3.

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
_TINY_PNG_B64 = (
    # 1×1 red pixel PNG (70 bytes) — used as source for edit probes
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+h"
    "HgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _env_flag_enabled(name: str) -> bool:
    """Explicit opt-in parse: only "1" / "true" / "yes" / "on" (case-insensitive)
    count as enabled. Guards against `.env` entries like `FLAG=0` or
    `FLAG=false` being treated as truthy by plain `os.environ.get`.
    Shared semantics with probe_framework.py."""
    val = (os.environ.get(name) or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _post(url: str, headers: dict, body: bytes, timeout: float = 40.0) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"<transport {type(e).__name__}: {e}>"


def _get(url: str, headers: dict, timeout: float = 30.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"<transport {type(e).__name__}: {e}>"


# ---- per-protocol probes ------------------------------------------------------

def probe_anthropic_chat(*, base: str, key: str, model_raw: str) -> tuple[int, str]:
    """For prefix=anthropic/... → strip prefix, POST to /v1/messages."""
    model = model_raw.split("/", 1)[1] if model_raw.startswith("anthropic/") else model_raw
    body = json.dumps({
        "model": model, "max_tokens": 12,
        "messages": [{"role": "user", "content": "reply only the word pong"}],
    }).encode()
    headers = {
        "x-api-key": key, "anthropic-version": "2023-06-01",
        "content-type": "application/json", "User-Agent": _UA,
    }
    return _post(f"{base.rstrip('/')}/v1/messages", headers, body)


def probe_openai_chat(*, base: str, key: str, model_raw: str) -> tuple[int, str]:
    """For prefix=openai/... + compat endpoints → POST /chat/completions."""
    model = model_raw.split("/", 1)[1] if model_raw.startswith("openai/") else model_raw
    body = json.dumps({
        "model": model, "max_tokens": 12,
        "messages": [{"role": "user", "content": "reply only the word pong"}],
    }).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "User-Agent": _UA,
    }
    return _post(f"{base.rstrip('/')}/chat/completions", headers, body)


def probe_openai_image(*, base: str, key: str, model_raw: str) -> tuple[int, str]:
    """For OpenAI-compat image endpoints (GLM-Image candidate)."""
    model = model_raw.split("/", 1)[1] if model_raw.startswith("openai/") else model_raw
    body = json.dumps({
        "model": model, "prompt": "a tiny red square", "n": 1, "size": "512x512",
    }).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "User-Agent": _UA,
    }
    return _post(f"{base.rstrip('/')}/images/generations", headers, body)


def probe_qwen_multimodal(*, key: str, model_raw: str,
                           include_source_image: bool = False) -> tuple[int, str]:
    """DashScope 原生 multimodal-generation for Qwen-Image(/Edit).

    Note: this endpoint is NOT at api_base from the registry —
    it's at dashscope.aliyuncs.com/api/v1/... directly.
    """
    model = model_raw.split("/", 1)[1] if "/" in model_raw else model_raw
    content = []
    if include_source_image:
        content.append({"image": f"data:image/png;base64,{_TINY_PNG_B64}"})
    content.append({"text": "a tiny red square" if not include_source_image
                    else "add a blue border around the square"})
    body = json.dumps({
        "model": model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": {"n": 1, "size": "512*512"},
    }).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "User-Agent": _UA,
    }
    url = ("https://dashscope.aliyuncs.com/api/v1/services/aigc/"
           "multimodal-generation/generation")
    return _post(url, headers, body, timeout=90.0)


def probe_hunyuan_tokenhub(*, base: str, key: str, model_raw: str,
                            kind: str) -> tuple[int, str]:
    """tokenhub.tencentmaas.com /v1/api/{image,3d}/submit + /query.

    Just hits submit — reports 200 if task accepted. Full polling + download
    skipped in connectivity probe.
    """
    model = model_raw.split("/", 1)[1] if "/" in model_raw else model_raw
    body = json.dumps({
        "model": model,
        "prompt": ("a small red square" if kind != "mesh" else "a simple cube"),
    }).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "User-Agent": _UA,
    }
    # base already has /image or /3d suffix per registry
    return _post(f"{base.rstrip('/')}/submit", headers, body)


def probe_tripo3d(*, base: str, key: str) -> tuple[int, str]:
    """Tripo3D is already covered by Tripo3DWorker + earlier probe_chat.py —
    just sanity-ping /v2/openapi/task endpoint."""
    headers = {"Authorization": f"Bearer {key}", "User-Agent": _UA}
    return _get(f"{base.rstrip('/')}/openapi/user/balance", headers)


# ---- dispatcher --------------------------------------------------------------

def _pick_probe(route, env_key: str | None) -> tuple[str, tuple[int | None, str]]:
    """Return (protocol_label, (status, body)). `status=None` signals
    deliberate skip (no key, opt-in gated, unrecognized prefix) so `main()`
    can render ⏭️ instead of ❌ — skipping is not failure."""
    model = route.model
    api_base = route.api_base
    if not env_key:
        return "skip(no key)", (None, "env var not set")

    # Text / Anthropic (packycode / minimaxi)
    if model.startswith("anthropic/"):
        return "anthropic/chat", probe_anthropic_chat(
            base=api_base, key=env_key, model_raw=model)

    # Gemini — no probe here (requires native google auth, separate flow)
    if model.startswith("gemini/"):
        return "skip(native gemini)", (None, "native Gemini SDK path not in this probe")

    # Qwen image / edit — DashScope native multimodal-generation
    if model.startswith("qwen/"):
        return "qwen/multimodal", probe_qwen_multimodal(
            key=env_key, model_raw=model,
            include_source_image=(route.kind == "image_edit"),
        )

    # Hunyuan tokenhub (image + 3D)
    if model.startswith("hunyuan/"):
        if route.kind == "mesh" and not _env_flag_enabled("FORGEUE_PROBE_MESH"):
            # Mesh submits always bill server-side even if we don't poll;
            # opt in via FORGEUE_PROBE_MESH=1 to avoid surprise charges.
            return "skip(mesh opt-in)", (None, "set FORGEUE_PROBE_MESH=1 to include")
        return "hunyuan/tokenhub-submit", probe_hunyuan_tokenhub(
            base=api_base, key=env_key, model_raw=model, kind=route.kind)

    # Tripo3D
    if model.startswith("tripo3d/"):
        return "tripo3d/balance", probe_tripo3d(base=api_base, key=env_key)

    # OpenAI-compat:
    if model.startswith("openai/") or model.startswith("xai/") \
            or model.startswith("openrouter/"):
        # text/vision via chat completions; image via /images/generations
        if route.kind == "image":
            return "openai-compat/image", probe_openai_image(
                base=api_base, key=env_key, model_raw=model)
        return "openai-compat/chat", probe_openai_chat(
            base=api_base, key=env_key, model_raw=model)

    return f"skip(unrecognized prefix {model.split('/', 1)[0]})", (None, "unrecognized")


def main() -> int:
    # Lazy init — env hydration + registry reset happen on probe invocation,
    # not at module import. Safe for `inspect.getsource(...)` static checks
    # in read-only / no-key sandboxes.
    hydrate_env()
    reset_model_registry()
    reg = get_model_registry()

    print(f"{'alias':<24} {'model':<42} {'kind':<11} {'status':<7} protocol / snippet")
    print("-" * 140)

    seen: set[tuple[str, str]] = set()
    for alias_name in reg.names():
        alias = reg.resolve(alias_name)
        for r in alias.routes():
            dedup = (alias_name, r.model)
            if dedup in seen:
                continue
            seen.add(dedup)
            env_key = os.environ.get(r.api_key_env) if r.api_key_env else None
            proto, (status, body) = _pick_probe(r, env_key)
            snippet = body[:140].replace("\n", " ")
            # Tri-state rendering — status=None means deliberate skip (no key,
            # mesh opt-in gated, unrecognized prefix), NOT failure. Rendering
            # it as ❌ used to mislead users into chasing a non-existent bug.
            if status is None:
                status_disp = "skip"
                mark = "⏭️"
            elif status == 200:
                status_disp = "ok  "
                mark = "✅"
            else:
                status_disp = f"{status:>4d}"
                mark = "⚠️ " if 200 < status < 500 else "❌"
            print(f"{alias_name:<24} {r.model:<42} {r.kind:<11} "
                  f"{mark} {status_disp} [{proto}] {snippet}")
            time.sleep(1.2)    # gentle pace; avoid rate-limit bursts
    return 0


if __name__ == "__main__":
    sys.exit(main())
