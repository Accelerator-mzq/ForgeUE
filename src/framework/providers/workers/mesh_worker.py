"""Mesh worker —— image-to-3D 生成抽象（L4）.

同 `ComfyWorker` 的模式：外部 HTTP 服务不适合塞进 LiteLLM 的 chat-completion
协议（返回的是几何数据而不是 token 文本），所以给它独立 Worker 抽象。

实现：
- `FakeMeshWorker` —— 测试用，合成最小合法 glTF（~120 bytes）
- `Tripo3DWorker` —— 真实 HTTP 调用 api.tripo3d.ai/v2/openapi/task（懒加载 requests）
- `HunyuanMeshWorker` —— 腾讯混元生3D，SubmitHunyuanTo3DRapidJob + 轮询 +
  ResultFile3Ds 下载。认证走 TC3-HMAC-SHA256（Tencent Cloud 标准签名）。

生成结果包成 `MeshCandidate`，`GenerateMeshExecutor` 再落成 file-backed
`mesh.gltf` Artifact。UE 导入侧 `ue_scripts/domain_mesh.py` 已就绪。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import struct
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx


class MeshWorkerError(RuntimeError):
    """Generic mesh worker failure."""


class MeshWorkerTimeout(MeshWorkerError):
    """Mesh worker exceeded wall-clock budget."""


class MeshWorkerUnsupportedResponse(MeshWorkerError):
    """Provider returned a response shape this worker can't consume (e.g.
    a ZIP bundle with no directly-importable mesh URL). Distinct from
    generic `MeshWorkerError` so RetryPolicy can skip pointless retries —
    the response is deterministic; retrying the same submit burns more
    quota for the same unusable output. Orchestrator still routes this
    to `worker_error` → `fallback_model` via FailureModeMap."""


@dataclass
class MeshCandidate:
    """One mesh result from a MeshWorker call."""

    data: bytes
    format: str = "glb"            # "glb" | "gltf" | "fbx" | "obj"
    mime_type: str = "model/gltf-binary"
    poly_count: int | None = None
    has_uv: bool = True
    has_rig: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class MeshWorker(ABC):
    """Adapter surface used by generate_mesh executor."""

    name: str = "mesh"

    @abstractmethod
    def generate(
        self,
        *,
        source_image_bytes: bytes,
        spec: dict[str, Any],
        num_candidates: int = 1,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        """Produce *num_candidates* meshes from *source_image_bytes*."""


# ----------------------------------------------------------------------------
# Fake —— deterministic, offline
# ----------------------------------------------------------------------------


@dataclass
class _MeshScript:
    candidates: list[MeshCandidate] | None = None
    raise_error: BaseException | None = None


class FakeMeshWorker(MeshWorker):
    """Deterministic fake worker. Synthesises a minimal GLB when unprogrammed."""

    name = "fake_mesh"

    def __init__(self) -> None:
        self._scripts: deque[_MeshScript] = deque()
        self.calls: list[dict[str, Any]] = []

    def program(self, candidates: list[MeshCandidate]) -> None:
        self._scripts.append(_MeshScript(candidates=list(candidates)))

    def program_error(self, exc: BaseException) -> None:
        self._scripts.append(_MeshScript(raise_error=exc))

    def generate(
        self,
        *,
        source_image_bytes: bytes,
        spec: dict[str, Any],
        num_candidates: int = 1,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        self.calls.append({
            "spec": dict(spec), "num_candidates": num_candidates,
            "source_size": len(source_image_bytes),
            "timeout_s": timeout_s,
        })
        if self._scripts:
            script = self._scripts.popleft()
            if script.raise_error is not None:
                raise script.raise_error
            assert script.candidates is not None
            return list(script.candidates)
        return [
            _synth_mesh_candidate(source_image_bytes, spec=spec, index=i)
            for i in range(num_candidates)
        ]


def _synth_mesh_candidate(
    source_image_bytes: bytes, *, spec: dict, index: int,
) -> MeshCandidate:
    """Produce a tiny but valid GLB for tests (~130 bytes).

    Not a real mesh — just a well-formed container with empty buffers so
    downstream code can treat it as a file-backed mesh artifact.
    """
    json_chunk = json.dumps({
        "asset": {"version": "2.0", "generator": "forgeue-fake-mesh"},
        "meshes": [{"name": f"stub_{index}", "primitives": [{"attributes": {}}]}],
        "scenes": [{"nodes": []}],
        "scene": 0,
        "nodes": [],
    }).encode("utf-8")
    # Pad to 4-byte boundary
    pad = (4 - len(json_chunk) % 4) % 4
    json_chunk += b" " * pad
    bin_chunk = b""                                          # empty binary payload

    # GLB header: magic + version + total_length
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    # JSON chunk: length + type(0x4E4F534A "JSON") + data
    json_header = struct.pack("<II", len(json_chunk), 0x4E4F534A)
    # BIN chunk: length + type(0x004E4942 "BIN") + data
    bin_header = struct.pack("<II", len(bin_chunk), 0x004E4942)

    data = header + json_header + json_chunk + bin_header + bin_chunk
    return MeshCandidate(
        data=data, format="glb", mime_type="model/gltf-binary",
        poly_count=0, has_uv=False, has_rig=False,
        metadata={
            "synthetic": True,
            "spec": dict(spec),
            "index": index,
            "source_image_hash": hashlib.sha1(source_image_bytes).hexdigest()[:12],
        },
    )


# ----------------------------------------------------------------------------
# Tripo3D HTTP worker —— real API integration（lazy-import requests）
# ----------------------------------------------------------------------------


class Tripo3DWorker(MeshWorker):
    """Minimal Tripo3D API client. Submits an image-to-3D task, polls until
    complete, and returns the GLB bytes.

    Endpoints assumed (api.tripo3d.ai/v2/openapi):
      POST /task          body={type:"image_to_model", file:{ ... }, ...}
      GET  /task/<id>     → {status, progress, output: {pbr_model: <url>}}
      GET  <pbr_model_url> → GLB bytes
    """

    name = "tripo3d_http"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.tripo3d.ai/v2/openapi",
        poll_interval_s: float = 2.0,
        default_timeout_s: float = 300.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._poll = poll_interval_s
        self._default_timeout_s = default_timeout_s

    def _import_requests(self):
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise MeshWorkerError(
                "`requests` not installed. pip install requests to use Tripo3DWorker."
            ) from exc
        return requests

    def generate(
        self,
        *,
        source_image_bytes: bytes,
        spec: dict[str, Any],
        num_candidates: int = 1,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:  # pragma: no cover - real network
        import base64
        requests = self._import_requests()
        headers = {"Authorization": f"Bearer {self._api_key}"}
        budget = timeout_s or self._default_timeout_s

        # Step 1: submit task (image embedded as base64 per v2 spec)
        img_b64 = base64.b64encode(source_image_bytes).decode("ascii")
        submit_body = {
            "type": "image_to_model",
            "file": {"type": "image/png", "object": img_b64},
            "model_version": spec.get("model_version", "v2.5-20250212"),
            "texture": bool(spec.get("texture", True)),
            "pbr": bool(spec.get("pbr", True)),
        }
        r = requests.post(f"{self._base_url}/task", json=submit_body,
                          headers={**headers, "Content-Type": "application/json"},
                          timeout=min(30.0, budget))
        if r.status_code != 200:
            raise MeshWorkerError(f"/task submit {r.status_code}: {r.text[:200]}")
        task_id = r.json().get("data", {}).get("task_id")
        if not task_id:
            # Deterministic protocol mismatch — retrying the same submit
            # produces the same bad response. Route via abort_or_fallback
            # instead of fallback_model (which would rebill Tripo3D for the
            # same no-op). Mirror of the Hunyuan empty-URL-list case.
            raise MeshWorkerUnsupportedResponse(
                f"Tripo3D /task response has no task_id: {r.text[:200]}"
            )

        # Step 2: poll. Every /task/<id> request clamps to the remaining
        # budget so a slow CDN on one poll can't monopolise the caller's
        # timeout_s. Pre-2026-04 this used a hardcoded 20s; with 10 polls
        # a stalled provider could block for 200s past the nominal budget.
        start = time.monotonic()
        model_url: str | None = None
        while True:
            elapsed = time.monotonic() - start
            if elapsed > budget:
                raise MeshWorkerTimeout(f"task {task_id} exceeded {budget}s")
            remaining = budget - elapsed
            pr = requests.get(
                f"{self._base_url}/task/{task_id}", headers=headers,
                timeout=min(20.0, max(1.0, remaining)),
            )
            if pr.status_code != 200:
                raise MeshWorkerError(f"/task/{task_id} {pr.status_code}")
            data = pr.json().get("data") or {}
            status = data.get("status")
            if status == "success":
                model_url = (data.get("output") or {}).get("pbr_model") or \
                            (data.get("output") or {}).get("model")
                if not model_url:
                    # Deterministic empty output — Tripo3D completed the job
                    # but returned no downloadable URL. Same task_id poll
                    # again would return the same result; resubmitting
                    # produces a new job with no reason to emit a URL where
                    # the last one didn't. Route via abort_or_fallback.
                    raise MeshWorkerUnsupportedResponse(
                        f"Tripo3D task {task_id} succeeded but output has no "
                        f"model URL (keys={list((data.get('output') or {}))})"
                    )
                break
            if status in ("failed", "cancelled"):
                raise MeshWorkerError(f"task {task_id} {status}: {data.get('error')}")
            time.sleep(self._poll)

        # Step 3: download GLB. Clamp the download timeout to the remaining
        # step budget; a stuck CDN can't silently push the step past its
        # nominal wall-clock limit.
        remaining = budget - (time.monotonic() - start)
        if remaining <= 0:
            raise MeshWorkerTimeout(
                f"Tripo3D task {task_id} exceeded {budget}s before model "
                f"download (submit+poll alone exhausted budget)"
            )
        dr = requests.get(model_url, timeout=min(60.0, remaining))
        if dr.status_code != 200:
            raise MeshWorkerError(f"model download {dr.status_code}")
        return [MeshCandidate(
            data=dr.content, format="glb", mime_type="model/gltf-binary",
            metadata={"task_id": task_id, "model_url": model_url, "source": "tripo3d"},
        )]


# ----------------------------------------------------------------------------
# Tencent Hunyuan3D worker —— tokenhub.tencentmaas.com 代理 (Bearer auth)
# API 文档: docs/api_des/HunYuan.md
#   POST /v1/api/3d/submit   body={model, prompt, image?} → {id, status}
#       `image` carries the source as a `data:image/png;base64,...` data URL,
#       identical to the image-generation tokenhub endpoint.
#   POST /v1/api/3d/query    body={model, id}              → {status, ...urls}
#
# 注：早期本项目有一版 TC3-HMAC-SHA256 签名实现，走 hunyuan.tencentcloudapi.com；
# 那条路径与您的 `HUNYUAN_3D_KEY`（sk-xxx bearer）不匹配，连通测试失败。这版
# 与 HunyuanImageAdapter 共享 submit/poll/download 逻辑（通过 urllib，不依赖
# tencentcloud-sdk-python）。
# ----------------------------------------------------------------------------


class HunyuanMeshWorker(MeshWorker):
    """Tencent Hunyuan3D via tokenhub.tencentmaas.com.

    Auth: `Authorization: Bearer <HUNYUAN_3D_KEY>` (sk-... token).

    Flow:
      1. POST <base>/submit {model, prompt, image=data-URL}  → {id, status:queued}
      2. Poll <base>/query  {model, id}                      → eventually status=done
      3. Download result URL → GLB bytes

    The image field uses the same `data:image/png;base64,...` shape the
    sibling HunyuanImageAdapter uses for 2D generation — tokenhub accepts
    that form across both endpoints, so we stay consistent.
    """

    name = "hunyuan_3d"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://tokenhub.tencentmaas.com/v1/api/3d",
        poll_interval_s: float = 3.0,
        default_timeout_s: float = 300.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._poll = poll_interval_s
        self._default_timeout_s = default_timeout_s

    async def agenerate(
        self,
        *,
        source_image_bytes: bytes,
        spec: dict,
        num_candidates: int = 1,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        """Async variant: fan out num_candidates submit+poll+download jobs
        in parallel via `asyncio.gather`. Overall latency ≈ slowest job."""
        import base64

        budget = timeout_s or self._default_timeout_s
        image_b64 = base64.b64encode(source_image_bytes).decode("ascii")
        fallback_prompt = "3D model from provided reference image"
        prompt_text = str(
            spec.get("prompt") or spec.get("prompt_summary") or fallback_prompt
        )
        on_poll_progress = spec.get("_forge_progress_cb")
        on_download_progress = spec.get("_forge_download_cb")
        model_id = str(spec.get("model_id", "hy-3d-3.1"))
        fmt = str(spec.get("format", "glb")).lower()

        # Per-URL default download cap (kept as a ceiling so a single
        # slow CDN can't monopolise the whole budget). Gets clamped
        # down to the remaining step budget inside the fallthrough loop.
        _PER_URL_DOWNLOAD_CAP = 90.0

        async def _one(index: int) -> MeshCandidate:
            loop = asyncio.get_running_loop()
            step_start = loop.time()

            submit_body = {
                "model": model_id, "prompt": prompt_text,
                "image": f"data:image/png;base64,{image_b64}",
            }
            job_id = await self._atokenhub_submit(
                submit_body, timeout_s=min(30.0, budget),
            )
            done_resp = await self._atokenhub_poll(
                job_id=job_id, budget_s=budget, model_id=model_id,
                on_progress=on_poll_progress,
            )
            # Sidecar semantics depend on whether the step asked for
            # materials. When `spec.texture` AND `spec.pbr` are BOTH
            # explicitly False, the caller opted into geometry-only —
            # external .mtl / textures don't matter; UE imports raw mesh
            # with default materials. External-buffer .gltf is NOT covered
            # by this escape — the sidecar `.bin` carries vertex/index
            # data, so geometry-only can't save it.
            geometry_only = (
                spec.get("texture", True) is False
                and spec.get("pbr", True) is False
            )

            # Rank every candidate URL in the DONE response so a
            # non-self-contained first pick (e.g. .obj with `mtllib`)
            # doesn't sink the step when the same response also carries
            # a self-contained alternative (e.g. a .gltf with data URIs).
            # Hunyuan 3D typically returns 1-3 URLs per job, so the extra
            # download round-trips on fallthrough are bounded.
            ranked_urls = _rank_hunyuan_3d_urls(done_resp)
            if not ranked_urls:
                # `_rank_hunyuan_3d_urls` drops `preview_*` thumbnails and
                # explicitly excluded extensions (`.usd`/`.usdz`). If the
                # DONE response legitimately had no importable mesh URL
                # at all, retrying the exact same job would return the
                # exact same set of URLs (same filter, same exclusion) —
                # the failure is deterministic. Classify as
                # `MeshWorkerUnsupportedResponse` so FailureModeMap routes
                # via `abort_or_fallback` (terminate or on_fallback) rather
                # than `worker_error` → `fallback_model` → same-step retry,
                # which would rebill the provider for nothing. (Codex P2
                # round 3 2026-04.)
                raise MeshWorkerUnsupportedResponse(
                    f"tokenhub 3d DONE response had no importable mesh URL "
                    f"(all URLs filtered as preview/unsupported ext); "
                    f"keys={list(done_resp)} sample={str(done_resp)[:400]}"
                )

            last_unsupported: MeshWorkerUnsupportedResponse | None = None
            last_download_error: MeshWorkerError | None = None
            for url in ranked_urls:
                # Each download iteration must respect the remaining
                # step budget (Codex P2 round 2). Without this clamp,
                # N unsupported URLs each got a fresh 90s cap, so a
                # step with `worker_timeout_s=60` could block for
                # 30+poll+3×90 seconds — defeating the orchestrator's
                # timeout policy. Clamp to min(cap, remaining) and
                # bail out before the download call when the budget
                # is already spent, so the failure is attributed to
                # timeout (not a mis-reported network error).
                remaining = budget - (loop.time() - step_start)
                if remaining <= 0:
                    raise MeshWorkerTimeout(
                        f"mesh step exceeded {budget}s budget before "
                        f"downloading {url!r} (ranked URL "
                        f"{ranked_urls.index(url) + 1}/{len(ranked_urls)}); "
                        f"{'previous URLs unsupported' if last_unsupported else 'submit+poll alone exhausted budget'}"
                    )
                per_url_timeout = min(_PER_URL_DOWNLOAD_CAP, remaining)
                # Download + validate inside a single try so a download
                # failure on URL N (404 / 5xx / network) falls through
                # to URL N+1 rather than aborting the whole step. Codex
                # P2 round 4: previously the download call sat OUTSIDE
                # the try block, so a broken first link killed a step
                # whose DONE response still carried a usable .glb on
                # the second URL — forcing a full resubmit + rebill.
                # Order of `except` matters: MeshWorkerUnsupportedResponse
                # (a MeshWorkerError subclass) must be matched FIRST so
                # deterministic "bad shape" bytes route to the abort_or_
                # fallback path, not retry-same-step. Generic download
                # errors (MeshWorkerError / MeshWorkerTimeout) land in
                # the second branch and surface as worker_error →
                # fallback_model if every URL failed the same way.
                try:
                    mesh_bytes = await self._atokenhub_download(
                        url, timeout_s=per_url_timeout,
                        on_progress=on_download_progress,
                    )
                    return _build_candidate(
                        mesh_bytes=mesh_bytes, url=url, job_id=job_id,
                        index=index, requested_fmt=fmt,
                        geometry_only=geometry_only,
                    )
                except MeshWorkerUnsupportedResponse as exc:
                    last_unsupported = exc
                    continue
                except MeshWorkerError as exc:
                    # 404 / 5xx / network / per-URL download timeout —
                    # may still recover from a sibling URL.
                    last_download_error = exc
                    continue
            # Exhausted every ranked URL. Prefer the download-error raise
            # when any network failure occurred, because a retried Hunyuan
            # submit could yield fresh working URLs (transient CDN issue);
            # only raise the unsupported verdict when every URL was
            # deterministically malformed, in which case resubmitting
            # would just produce the same unusable shapes.
            if last_download_error is not None:
                raise last_download_error
            assert last_unsupported is not None
            raise last_unsupported

        return list(await asyncio.gather(*[_one(i) for i in range(num_candidates)]))

    def generate(
        self,
        *,
        source_image_bytes: bytes,
        spec: dict,
        num_candidates: int = 1,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        """Sync shim around `agenerate`. Use for back-compat callers."""
        return asyncio.run(self.agenerate(
            source_image_bytes=source_image_bytes, spec=spec,
            num_candidates=num_candidates, timeout_s=timeout_s,
        ))

    # ---- async tokenhub helpers -----------------------------------------

    async def _atokenhub_submit(self, body: dict, *, timeout_s: float) -> str:
        resp = await self._apost(f"{self._base_url}/submit", body, timeout_s=timeout_s)
        status = str(resp.get("status", "")).lower()
        if status in ("failed", "fail", "error"):
            err = resp.get("error") or {}
            raise MeshWorkerError(
                f"tokenhub /3d/submit failed: "
                f"{err.get('message') or err or resp}"
            )
        job_id = resp.get("id") or resp.get("job_id")
        if not job_id:
            raise MeshWorkerError(f"tokenhub /3d/submit returned no id: {resp}")
        return str(job_id)

    async def _atokenhub_poll(self, *, job_id: str, budget_s: float,
                                model_id: str, on_progress=None) -> dict:
        """Async poll /query; `await asyncio.sleep` between iterations so
        external cancellation is honoured immediately."""
        from framework.providers.hunyuan_tokenhub_adapter import _dispatch_progress
        loop = asyncio.get_running_loop()
        start = loop.time()
        while True:
            elapsed = loop.time() - start
            if elapsed > budget_s:
                raise MeshWorkerTimeout(
                    f"tokenhub 3d job {job_id} exceeded {budget_s}s"
                )
            # Clamp single-poll timeout so a slow /query can't push the
            # step past its nominal budget. Same shape as Tripo3D's
            # min(20.0, max(1.0, remaining)) clamp.
            remaining = budget_s - elapsed
            poll_timeout = min(30.0, max(1.0, remaining))
            resp = await self._apost(
                f"{self._base_url}/query",
                {"model": model_id, "id": job_id}, timeout_s=poll_timeout,
            )
            status = str(resp.get("status", "")).lower()
            if on_progress is not None:
                _dispatch_progress(on_progress, status, elapsed, resp)
            # Ambient EventBus (WS subscribers)
            from framework.observability.event_bus import (
                ProgressEvent as _PE,
                current_run_step as _current_run_step,
                publish as _publish,
            )
            from framework.providers.hunyuan_tokenhub_adapter import (
                _extract_progress_pct as _pct,
            )
            _rid, _sid = _current_run_step()
            _publish(_PE(
                run_id=_rid, step_id=_sid, phase="mesh_poll",
                elapsed_s=elapsed, progress_pct=_pct(resp),
                raw={"job_id": job_id, "status": status, "model": model_id},
            ))
            if status in ("done", "success", "finished", "completed"):
                return resp
            if status in ("failed", "fail", "error", "cancelled"):
                # TBD-006 A2 verification surfaced: Hunyuan returns
                # {'message': '配额超限', 'code': 'FailedOperation.InnerError'}
                # when HUNYUAN_3D_KEY quota is exhausted. Naive
                # MeshWorkerError maps to worker_error -> retry_same_step
                # + fallback_model, i.e. every retry re-issues a paid
                # /submit that will fail the same deterministic way —
                # just burning quota at the provider. Classify quota /
                # rate-limit exhaustion as `Unsupported` so FailureModeMap
                # routes via `abort_or_fallback` (honour on_fallback,
                # else terminate) and the run stops billing immediately.
                err_detail = resp.get("error") or resp.get("message") or resp
                if _is_quota_or_rate_limit_error(resp):
                    raise MeshWorkerUnsupportedResponse(
                        f"tokenhub 3d job {job_id} {status} "
                        f"(deterministic quota/rate-limit exhausted; "
                        f"retry will not help): {err_detail}"
                    )
                raise MeshWorkerError(
                    f"tokenhub 3d job {job_id} {status}: {err_detail}"
                )
            await asyncio.sleep(self._poll)

    async def _apost(self, url: str, body: dict, *, timeout_s: float) -> dict:
        """Async POST with transient retry (SSL EOF / timeout / 5xx → 2s backoff).
        Permanent 4xx bubbles immediately."""
        from framework.providers._retry_async import (
            is_transient_network_message, with_transient_retry_async,
        )
        import json as _json

        async def _attempt() -> dict:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as c:
                    r = await c.post(url, headers=headers, content=_json.dumps(
                        body, separators=(",", ":"), ensure_ascii=False,
                    ).encode("utf-8"))
            except httpx.TimeoutException as exc:
                raise MeshWorkerTimeout(str(exc)) from exc
            except httpx.HTTPError as exc:
                raise MeshWorkerError(str(exc)) from exc

            if r.status_code >= 400:
                err_body = r.text
                raise MeshWorkerError(
                    f"tokenhub {url} {r.status_code}: {err_body[:300]}"
                )
            try:
                return r.json()
            except ValueError as exc:
                # 200 + non-JSON body (proxy/WAF HTML, truncated). Mirror
                # of the image adapter fix — without the catch, downstream
                # crashes with raw json.JSONDecodeError instead of routing
                # through the failure-mode map.
                raise MeshWorkerUnsupportedResponse(
                    f"tokenhub {url} returned 200 but body is not JSON: "
                    f"{r.text[:200]!r}"
                ) from exc

        return await with_transient_retry_async(
            _attempt,
            # Exclude MeshWorkerUnsupportedResponse — same reasoning as
            # the image adapters: HTML/WAF body may carry transient
            # marker words, and a deterministic 200-non-JSON shape
            # shouldn't cost a second paid /submit call.
            transient_check=lambda e: not isinstance(
                e, MeshWorkerUnsupportedResponse,
            ) and (
                isinstance(e, MeshWorkerTimeout) or (
                    isinstance(e, MeshWorkerError)
                    and is_transient_network_message(str(e))
                )
            ),
            max_attempts=2, backoff_s=2.0,
        )

    async def _atokenhub_download(self, url: str, *, timeout_s: float,
                                    on_progress=None) -> bytes:
        """Async chunked download with Range resume."""
        from framework.providers._download_async import chunked_download_async
        try:
            return await chunked_download_async(
                url, timeout_s=timeout_s, on_chunk=on_progress,
            )
        except Exception as exc:
            raise MeshWorkerError(f"tokenhub /3d download {url}: {exc}") from exc


_QUOTA_KEYWORDS = (
    # Chinese (Tencent Hunyuan tokenhub returns "配额超限" literally).
    "配额",     # "quota"
    "超限",     # "over limit"
    "限额",     # "cap / limit"
    "超出",     # "exceeds" (often paired with "限制/额度")
    "充值",     # "recharge" — only appears in billing/quota contexts
    # English (DashScope / Zhipu / generic OpenAI-compat providers).
    "quota",
    "rate limit",
    "rate-limit",
    "rate_limit",
    "limit exceeded",
    "exceeded your",
    "too many requests",
    "insufficient",   # insufficient_quota / insufficient balance
    "billing",        # often appears in quota-related error bodies
)


def _is_quota_or_rate_limit_error(resp: dict) -> bool:
    """Detect deterministic quota / rate-limit / billing exhaustion.

    Returned from poll-body on terminal `status: failed`. Tencent Hunyuan
    tokenhub returns shapes like:
        {"status": "failed",
         "error": {"message": "配额超限", "type": "api_error",
                   "code": "FailedOperation.InnerError"}}
    or sometimes the message travels in top-level `resp["message"]`.

    Checks every string-shaped field under `resp["error"]` (dict or str)
    plus `resp["message"]` / `resp["error_code"]` against a multilingual
    keyword list. Case-insensitive substring match; short list is fine
    because quota errors are the one category worth burning a compile
    cycle on (they're the costliest-to-misclassify).

    Returns False on any decode surprise — prefer `worker_error` (with
    retry_same_step) over a false-positive `Unsupported` (which would
    terminate a genuinely transient failure).
    """
    try:
        err_obj = resp.get("error") if isinstance(resp, dict) else None
        parts: list[str] = []
        if isinstance(err_obj, dict):
            for key in ("message", "code", "type"):
                v = err_obj.get(key)
                if isinstance(v, str):
                    parts.append(v)
        elif isinstance(err_obj, str):
            parts.append(err_obj)
        if isinstance(resp, dict):
            for key in ("message", "error_code", "code"):
                v = resp.get(key)
                if isinstance(v, str):
                    parts.append(v)
        haystack = " ".join(parts).lower()
        if not haystack.strip():
            return False
        return any(kw in haystack for kw in _QUOTA_KEYWORDS)
    except Exception:
        return False


def _is_self_contained_obj(data: bytes) -> bool:
    """Return True when text OBJ bytes have no external sidecar dependencies.

    Wavefront .obj commonly references `.mtl` via a `mtllib` directive;
    the .mtl in turn references texture files (`map_Kd`, `map_Ka`, etc.)
    via relative paths. The framework's single-URL MeshCandidate model
    can only ship the .obj itself — sidecar files won't be downloaded
    and UE import produces an untextured / no-material mesh.

    Rule: presence of ANY `mtllib` directive → non-self-contained.
    Geometry-only OBJs (no `mtllib`) import fine as raw meshes with
    default materials; those pass.

    Searches the first ~8 KB — `mtllib` typically appears in the first
    few lines of the file.
    """
    head = data[:8192]
    for line in head.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(b"mtllib"):
            return False
    return True


def _is_data_uri(value: object) -> bool:
    """Return True when `value` is a string whose leading scheme is
    the `data:` data URI (RFC 2397). The RFC defines URI schemes as
    case-insensitive, so `DATA:`/`Data:`/`data:` all qualify — earlier
    checks used `startswith("data:")` literally, which rejected the
    mixed-case form and falsely flagged valid self-contained glTFs
    as non-self-contained (Codex P3 round 5). Centralising the check
    keeps `_is_self_contained_gltf` and `_gltf_has_external_geometry`
    in lock-step.
    """
    if not isinstance(value, str):
        return False
    return value.lstrip().lower().startswith("data:")


def _is_http_url(value: object) -> bool:
    """Return True when `value` is a string whose scheme is `http:` or
    `https:`. Case-insensitive per RFC 3986 — `HTTP://`/`Https://` are
    legal though rare. Pre-2026-04 the URL walker used
    `startswith("http")` which would accept lower-case `http://` /
    `https://` only. Unifying via this predicate mirrors `_is_data_uri`
    and the matching helper in hunyuan_tokenhub_adapter. 共性平移 PR-3.
    """
    if not isinstance(value, str):
        return False
    head = value.lstrip().lower()
    return head.startswith("http://") or head.startswith("https://")


def _is_self_contained_gltf(data: bytes) -> bool:
    """Return True when text glTF 2.0 bytes embed all external resources
    via data URIs (no sidecar dependencies). Real-world glTF exports
    commonly reference external `.bin` buffers and texture files via
    relative URIs; those would be lost when the framework stores just
    the single downloaded .gltf as a MeshCandidate, breaking downstream
    UE import.

    Validation rule: every `"uri"` field inside `buffers[]` and `images[]`
    must start with the `data:` scheme (case-insensitive per RFC 2397).
    Any URI that doesn't (relative path, absolute http URL to a sidecar,
    etc.) means the glTF is non-self-contained — worker should raise
    `MeshWorkerUnsupportedResponse` rather than ship a broken artifact.

    Parse-failure policy (Codex P2 round 6 2026-04): returns False when
    the bytes don't parse as a JSON object. `_detect_mesh_format()`
    classifies as `gltf` from a loose 2 KB token heuristic (leading `{`
    plus `"asset"`/`"version"`), so truncated / corrupted glTF bodies
    can pass the detector but fail JSON parse. Shipping those as valid
    self-contained candidates writes broken artifacts to disk that UE
    rejects on import — safer to flag them here so `_build_candidate()`
    raises `MeshWorkerUnsupportedResponse` and routes via the
    fallthrough / fallback path instead.
    """
    import json as _json
    try:
        obj = _json.loads(data.decode("utf-8", errors="replace"))
    except (_json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(obj, dict):
        return False
    # buffers[]: text glTF requires every buffer to have `uri` (no BIN chunk
    # available outside .glb). Any missing `uri` is genuinely non-self-contained.
    for entry in obj.get("buffers") or []:
        if not isinstance(entry, dict):
            continue
        uri = entry.get("uri")
        if uri is None:
            return False
        if not _is_data_uri(uri):
            return False
    # images[]: glTF 2.0 allows EITHER `uri` (data URI when self-contained)
    # OR `{bufferView, mimeType}` — the latter reuses an already-validated
    # buffer, so no external file is needed. Both patterns are self-contained
    # as long as buffers[] passed the check above.
    for entry in obj.get("images") or []:
        if not isinstance(entry, dict):
            continue
        uri = entry.get("uri")
        if uri is None:
            # Legal self-contained form only if bufferView is referenced.
            # A bare image entry with neither uri nor bufferView is broken
            # (no way to locate pixels) — treat as non-self-contained.
            if not isinstance(entry.get("bufferView"), int):
                return False
            continue
        if not _is_data_uri(uri):
            return False
    return True


def _gltf_has_external_geometry(data: bytes) -> bool:
    """Return True when a text glTF's `buffers[]` references external .bin
    data (non-data URI, or missing `uri` which in a text .gltf implies a
    GLB BIN chunk that can't exist here).

    Semantic distinction from `_is_self_contained_gltf`: that one collapses
    buffer AND image sidecars into a single boolean, so callers can't tell
    whether the missing asset is mesh geometry or just textures. The
    geometry-only escape hatch in `_one()` (spec.texture=False AND
    spec.pbr=False) is safe for missing textures (UE imports with default
    materials) but UNSAFE for missing buffers (the `.bin` carries the
    vertex/index stream; without it the resulting .gltf has no geometry
    and UE import either fails or produces an empty mesh). This predicate
    lets `_one()` gate the fallthrough correctly.

    Parse-failure policy (Codex P2 round 6 2026-04): returns True when
    the bytes don't parse as a JSON object. `_detect_mesh_format()` uses
    a loose 2 KB token heuristic to label bodies as `gltf`, so corrupted
    / truncated glTF can reach this function despite being unusable.
    Claiming `has_external_geometry=True` for those keeps the stricter
    raise path in `_build_candidate()` — even under the geometry-only
    escape hatch the worker refuses to ship bytes it can't structurally
    verify, preventing empty / broken meshes from landing on disk.
    """
    import json as _json
    try:
        obj = _json.loads(data.decode("utf-8", errors="replace"))
    except (_json.JSONDecodeError, UnicodeDecodeError):
        return True
    if not isinstance(obj, dict):
        return True
    for entry in obj.get("buffers") or []:
        if not isinstance(entry, dict):
            continue
        uri = entry.get("uri")
        if uri is None:
            # Text glTF with `byteLength` but no `uri` → buffer lives in a
            # GLB BIN chunk that doesn't exist in a standalone .gltf.
            # That's a missing-geometry situation.
            return True
        # `data:` scheme is case-insensitive per RFC 2397 — accept any
        # capitalisation as inline. See `_is_data_uri` for the shared
        # predicate used by `_is_self_contained_gltf` too.
        if not _is_data_uri(uri):
            return True
    return False


def _build_candidate(
    *,
    mesh_bytes: bytes, url: str, job_id: str, index: int,
    requested_fmt: str, geometry_only: bool,
) -> "MeshCandidate":
    """Validate `mesh_bytes` and construct a MeshCandidate, or raise
    `MeshWorkerUnsupportedResponse` when the bytes can't be shipped as-is.

    Extracted from `_one()` so the per-URL retry loop can catch the
    unsupported raise and try the next candidate URL without duplicating
    the format-detect / self-containment logic.
    """
    detected_fmt, detected_mime = _detect_mesh_format(mesh_bytes)
    if detected_fmt == "glb" and mesh_bytes[:4] != b"glTF":
        # `_detect_mesh_format` labels unknown bytes as "glb" to preserve
        # legacy downstream behaviour. For the runtime path that's
        # dangerous: a CDN serving an HTML error page, a truncated
        # binary, or any payload whose first 4 bytes aren't the glTF
        # magic would be shipped as a `.glb` candidate and fail during
        # UE import. The probe layer already re-validates via
        # `data[:4] == b"glTF"` (Codex P3 round 4); runtime must too
        # so non-magic bytes route via abort_or_fallback rather than
        # landing on disk as a broken artifact. 2026-04 共性平移 PR-3.
        raise MeshWorkerUnsupportedResponse(
            f"tokenhub /3d detector labelled job {job_id} as glb but the "
            f"first 4 bytes ({mesh_bytes[:4]!r}) are not the `glTF` magic; "
            f"likely an HTML error page or truncated payload. Refusing to "
            f"ship a broken .glb artifact — route to on_fallback or "
            f"retry the submit."
        )
    if detected_fmt == "zip":
        raise MeshWorkerUnsupportedResponse(
            f"tokenhub /3d returned a ZIP bundle for job {job_id} "
            f"(no directly-importable mesh URL in response). "
            f"Framework does not unpack bundles; configure a "
            f"fallback mesh provider (e.g. Tripo3D) or pick a "
            f"different Hunyuan 3D model that emits GLB directly."
        )
    missing_materials = False
    if detected_fmt == "gltf" and not _is_self_contained_gltf(mesh_bytes):
        # External-buffer means the `.bin` carries vertex/index data —
        # geometry is not in this downloaded .gltf. `geometry_only` does
        # NOT save this case (UE can fall back to default materials, but
        # it can't synthesize missing geometry). Always raise.
        if _gltf_has_external_geometry(mesh_bytes):
            raise MeshWorkerUnsupportedResponse(
                f"tokenhub /3d returned a .gltf for job {job_id} that "
                f"references external buffer(s) via `buffers[].uri` — "
                f"the sidecar .bin carries the actual vertex/index data "
                f"and the framework does not download mesh sidecars. "
                f"Even with spec.texture=False AND spec.pbr=False, the "
                f"geometry itself is missing; use a provider that emits "
                f"GLB (binary, self-contained) or a .gltf that embeds "
                f"buffers as data URIs."
            )
        # Remaining non-self-contained case: textures only (external
        # image uri or image without uri/bufferView). Safe to accept
        # under explicit geometry-only opt-in.
        if geometry_only:
            missing_materials = True
        else:
            raise MeshWorkerUnsupportedResponse(
                f"tokenhub /3d returned a non-self-contained .gltf "
                f"for job {job_id} — text glTF references external "
                f"sidecar textures that the framework does not "
                f"download. Use a provider that emits GLB (binary, "
                f"self-contained), a .gltf that embeds images as "
                f"data URIs, or set spec.texture=False AND "
                f"spec.pbr=False for geometry-only output."
            )
    if detected_fmt == "obj" and not _is_self_contained_obj(mesh_bytes):
        if geometry_only:
            missing_materials = True
        else:
            raise MeshWorkerUnsupportedResponse(
                f"tokenhub /3d returned a non-self-contained .obj "
                f"for job {job_id} — OBJ references an external "
                f".mtl via `mtllib` (and likely external textures). "
                f"Framework does not download mesh sidecars. Use "
                f"a provider that emits GLB, or set "
                f"spec.texture=False AND spec.pbr=False for "
                f"geometry-only output."
            )
    return MeshCandidate(
        data=mesh_bytes, format=detected_fmt,
        mime_type=detected_mime,
        metadata={
            "job_id": job_id, "model_url": url,
            "source": "hunyuan_3d_tokenhub", "index": index,
            "requested_format": requested_fmt,
            "detected_format": detected_fmt,
            "missing_materials": missing_materials,
        },
    )


def _detect_mesh_format(data: bytes) -> tuple[str, str]:
    """Return (format, mime_type) by inspecting the first few bytes.

    Handles the common shapes Hunyuan 3D / Tripo3D / similar workers
    actually ship: raw GLB, raw FBX-binary, text OBJ, text glTF 2.0 (JSON),
    or a ZIP archive wrapping OBJ + textures. Unknown magic falls back to
    the GLB label we historically used so existing downstream code doesn't
    break hard — but callers should prefer `detected_format` from
    MeshCandidate.metadata when deciding how to consume the bytes.
    """
    if len(data) < 4:
        return "glb", "model/gltf-binary"
    if data[:4] == b"glTF":
        # Binary glTF container (GLB).
        return "glb", "model/gltf-binary"
    if data[:4] == b"PK\x03\x04":
        # ZIP archive — typically Hunyuan 3D's "OBJ + MTL + texture" bundle.
        return "zip", "application/zip"
    if data[:20].startswith(b"Kaydara FBX Binary"):
        return "fbx", "application/octet-stream"
    # Text glTF 2.0: JSON object with required top-level `"asset"` whose
    # value carries `"version"`. Conservative heuristic — must lead with
    # `{` (ignoring whitespace) AND both tokens appear within the first
    # 2 KB. Caller is downloading from a URL tokenhub/etc already labeled
    # `.gltf`, so a full JSON parse would be overkill; we only need a
    # positive-ID check that distinguishes glTF from other JSON blobs.
    probe = data[:2048]
    head_stripped = probe.lstrip()
    if head_stripped.startswith(b"{") and b'"asset"' in probe and b'"version"' in probe:
        return "gltf", "model/gltf+json"
    # ASCII FBX — per spec the file leads with a semicolon-comment header
    # (`; FBX <version>`) and the first non-comment line is the
    # `FBXHeaderExtension:` top-level node. Detect both markers so ASCII
    # FBX doesn't fall through to the GLB default label. Without this,
    # providers that return ASCII FBX (e.g. some Tripo3D export profiles,
    # older Autodesk exporters) land on disk as a `.glb` file full of
    # ASCII text — UE import rejects it, and the misuse also bypasses
    # the ok-bucket ranking since `.fbx` is preferred over `.gltf` on
    # the assumption that the detector can verify FBX. (Codex P3 round
    # 3 2026-04.)
    head_stripped_32 = probe.lstrip()[:32]
    if (head_stripped_32.startswith(b"; FBX")
        or b"FBXHeaderExtension:" in probe):
        return "fbx", "application/octet-stream"
    # Heuristic for text OBJ. Previously only caught the Blender-default
    # exporters (comment / `v ` / `mtllib`), but real-world OBJ files
    # commonly lead with one of: `o `/`g `/`vn`/`vt`/`vp`/`f `/`l `/`s `/
    # `usemtl`. Without this wider list, provider-returned OBJ bodies
    # mislabel as the GLB fallback and downstream writes `.glb` files
    # containing text OBJ → UE import fails.
    head_32 = data[:32].lstrip()
    _OBJ_LEADS = (
        b"#",            # comment (Blender default)
        b"mtllib ",      # material library reference
        b"usemtl ",      # material use
        b"v ", b"vn ", b"vt ", b"vp ",   # vertex / normal / texcoord / parameter
        b"f ",           # face
        b"l ",           # line element
        b"o ", b"g ",    # object / group
        b"s ",           # smoothing group
    )
    if any(head_32.startswith(lead) for lead in _OBJ_LEADS):
        return "obj", "model/obj"
    return "glb", "model/gltf-binary"


def _rank_hunyuan_3d_urls(resp: dict) -> list[str]:
    """Return every candidate mesh URL in a tokenhub /3d/query DONE response,
    ranked best-first.

    Empirically Hunyuan 3D returns THREE URLs per job (cos.ap-guangzhou.tencentcos.cn):
      1. `<uuid>_0.zip`          — OBJ + MTL + PNG texture bundle
      2. `preview_<uuid>_0.png`  — 2D preview thumbnail
      3. `<uuid>_0.glb`          — native GLB (what the model actually emits)
    The `result_format` / `output_format` / `format` submit-body hints are
    silently ignored by tokenhub (verified 2026-04 via probe_hunyuan_3d_format.py),
    but the GLB URL is always in the response — we just have to pick it.

    Ranking (highest to lowest):
      A. URL path ends with `.glb` — binary glTF, always self-contained
         (JSON + BIN in one file). Magic-verifiable; safest single-file pick.
      B. URL path ends with `.gltf` / `.fbx` / `.obj` — magic-verifiable and
         supported downstream. `.gltf` is demoted here because text glTF
         typically references external sidecar files (`.bin`, textures) via
         `buffers[].uri` / `images[].uri`; the framework only downloads one
         URL per MeshCandidate, so a non-self-contained `.gltf` would land
         on disk without its sidecars and UE would import a broken mesh.
         Self-containment is validated later in worker `_one()` after
         download; non-self-contained `.gltf` there triggers a
         `MeshWorkerUnsupportedResponse` — `_one()` then falls through to
         the next URL in this ranked list.
      C. URL under a dict key matching `model_url`/`pbr_model`/etc.
      D. URL path ends with `.zip` — last resort (bundle format; worker raises)

    Previews (`preview_*`) are never selected — they're 2D thumbnails.
    Explicitly EXCLUDED extensions (never enter any bucket — if only these
    URLs exist, the caller sees an empty list):
      - `.usd` / `.usdz` — neither magic-detected nor supported by
        `mesh_spec.MeshFormat` or `ue_scripts/domain_mesh`. Earlier the
        catch-all `other_hits` bucket would accept them and the worker's
        fallback format-detection then mislabeled the bytes as GLB —
        producing a .glb artifact with USD content. Now they're dropped
        before classification so the step routes to a fallback provider.

    Returning a FULL ranked list (rather than just the top pick) lets
    `HunyuanMeshWorker._one()` retry the next URL when the first one
    fails self-containment checks. Prior behaviour returned only the
    winner, so a response containing [non-self-contained .obj, self-
    contained .gltf] would raise on the .obj and never try the .gltf.
    """
    _MESH_EXTS_STRONG = (".glb",)
    # OK tier — ordering matters (Codex P2 round 6 revision 2026-04).
    # Current `_build_candidate()` has explicit self-containment checks
    # for `.gltf` (buffers[]/images[] uri data-URI audit) and `.obj`
    # (`mtllib` directive), but NOT for `.fbx` — the binary-FBX format
    # is too complex to parse inline, so we can't verify whether a
    # provider-returned `.fbx` depends on external textures. Rank the
    # VERIFIED formats first so sidecar issues trigger the fallthrough
    # path toward a better candidate; keep `.fbx` LAST in the bucket
    # so it's only chosen when no verifiable alternative exists. Pre-
    # fix `.fbx` sat first on the (wrong) assumption that binary FBX
    # always self-packs media — real provider outputs violate that.
    _MESH_EXTS_OK = (".gltf", ".obj", ".fbx")
    _MESH_EXTS_UNSUPPORTED = (".usd", ".usdz")
    _KEY_PREFER = ("model_url", "pbr_model", "result_url", "url",
                   "file_url", "asset_url")

    def _url_basename(u: str) -> str:
        # Strip query string; take last path segment.
        path = u.split("?", 1)[0]
        return path.rsplit("/", 1)[-1].lower()

    def _is_preview(u: str) -> bool:
        return _url_basename(u).startswith("preview_")

    def _ext_of(u: str) -> str:
        base = _url_basename(u)
        # Take the last dot-segment that's a known extension.
        for ext in (*_MESH_EXTS_STRONG, *_MESH_EXTS_OK,
                    *_MESH_EXTS_UNSUPPORTED, ".zip", ".png", ".jpg"):
            if base.endswith(ext):
                return ext
        return ""

    strong_hits: list[str] = []   # A: .glb only
    ok_hits: list[str] = []       # B: .gltf / .fbx / .obj
    key_hits: list[str] = []      # C: preferred dict key
    zip_hits: list[str] = []      # D: .zip last resort
    other_hits: list[str] = []    # E: other unknown — still usable

    def _classify(url: str, key_matched: bool) -> None:
        if _is_preview(url):
            return   # 2D preview, never a valid mesh
        ext = _ext_of(url)
        if ext in _MESH_EXTS_UNSUPPORTED:
            return   # explicitly excluded; caller sees these as no URL
        if ext in _MESH_EXTS_STRONG:
            strong_hits.append(url)
        elif ext in _MESH_EXTS_OK:
            ok_hits.append(url)
        elif key_matched:
            key_hits.append(url)
        elif ext == ".zip":
            zip_hits.append(url)
        else:
            other_hits.append(url)

    def _walk(node, key_context: bool = False) -> None:
        if isinstance(node, str):
            if _is_http_url(node):
                _classify(node, key_context)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item, key_context)
            return
        if isinstance(node, dict):
            for k, v in node.items():
                kc = k in _KEY_PREFER
                if isinstance(v, str) and _is_http_url(v):
                    _classify(v, kc)
                else:
                    _walk(v, kc)

    _walk(resp)
    # Within ok_hits, sort by `_MESH_EXTS_OK` index so the tuple ordering
    # (.fbx > .obj > .gltf) actually governs which URL we try first. Pre-fix
    # this was walk-order which could pick an .obj before an .fbx in the
    # same response, then fail the sidecar check and lose the .fbx.
    ok_hits.sort(key=lambda u: _MESH_EXTS_OK.index(_ext_of(u)))
    # De-duplicate while preserving rank order. Some responses echo the
    # same URL under multiple keys; we don't want to re-download the
    # same bytes on fallthrough.
    #
    # Bucket order note (Codex P2 round 5 2026-04): `other_hits`
    # (no-extension / unknown-extension URLs, e.g. signed CDN links
    # `.../objects/abc123?sig=...`) MUST rank ABOVE `zip_hits`. Rationale:
    # `_build_candidate()` uses magic-byte detection on downloaded bytes,
    # so a no-ext URL that actually carries GLB/GLTF/OBJ/FBX will be
    # correctly classified once downloaded. `.zip` is known-bad — the
    # worker always raises `MeshWorkerUnsupportedResponse` for bundles —
    # so trying it first wastes the step's download budget on a
    # guaranteed failure and may trigger a budget-exhaust raise before
    # the real mesh URL is even attempted.
    seen: set[str] = set()
    ranked: list[str] = []
    for bucket in (strong_hits, ok_hits, key_hits, other_hits, zip_hits):
        for u in bucket:
            if u in seen:
                continue
            seen.add(u)
            ranked.append(u)
    return ranked


def _extract_hunyuan_3d_url(resp: dict) -> str:
    """Return the single best mesh URL from a tokenhub /3d/query DONE
    response. Thin wrapper around `_rank_hunyuan_3d_urls` preserved for
    probes and back-compat. New callers that want fallthrough-on-
    unsupported should use `_rank_hunyuan_3d_urls` directly."""
    ranked = _rank_hunyuan_3d_urls(resp)
    if not ranked:
        raise MeshWorkerError(
            f"tokenhub 3d DONE response missing result URL: "
            f"keys={list(resp)} sample={str(resp)[:400]}"
        )
    return ranked[0]
