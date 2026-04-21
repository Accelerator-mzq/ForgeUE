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
            raise MeshWorkerError(f"/task response has no task_id: {r.text[:200]}")

        # Step 2: poll
        start = time.monotonic()
        model_url: str | None = None
        while True:
            if time.monotonic() - start > budget:
                raise MeshWorkerTimeout(f"task {task_id} exceeded {budget}s")
            pr = requests.get(f"{self._base_url}/task/{task_id}", headers=headers,
                              timeout=20.0)
            if pr.status_code != 200:
                raise MeshWorkerError(f"/task/{task_id} {pr.status_code}")
            data = pr.json().get("data") or {}
            status = data.get("status")
            if status == "success":
                model_url = (data.get("output") or {}).get("pbr_model") or \
                            (data.get("output") or {}).get("model")
                if not model_url:
                    raise MeshWorkerError("task succeeded but no model URL in output")
                break
            if status in ("failed", "cancelled"):
                raise MeshWorkerError(f"task {task_id} {status}: {data.get('error')}")
            time.sleep(self._poll)

        # Step 3: download GLB
        dr = requests.get(model_url, timeout=60.0)
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

        async def _one(index: int) -> MeshCandidate:
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
            url = _extract_hunyuan_3d_url(done_resp)
            glb_bytes = await self._atokenhub_download(
                url, timeout_s=90.0, on_progress=on_download_progress,
            )
            return MeshCandidate(
                data=glb_bytes, format=fmt,
                mime_type="model/gltf-binary",
                metadata={
                    "job_id": job_id, "model_url": url,
                    "source": "hunyuan_3d_tokenhub", "index": index,
                },
            )

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
            resp = await self._apost(
                f"{self._base_url}/query",
                {"model": model_id, "id": job_id}, timeout_s=30.0,
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
                raise MeshWorkerError(
                    f"tokenhub 3d job {job_id} {status}: "
                    f"{resp.get('error') or resp.get('message') or resp}"
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
            return r.json()

        return await with_transient_retry_async(
            _attempt,
            transient_check=lambda e: isinstance(e, MeshWorkerTimeout) or (
                isinstance(e, MeshWorkerError)
                and is_transient_network_message(str(e))
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


def _extract_hunyuan_3d_url(resp: dict) -> str:
    """Find the GLB URL in a tokenhub /3d/query DONE response.

    Walks the response tree recursively — tokenhub variants put URLs in
    several places (top-level, `result.model_url`, `data[0].pbr_model`,
    etc.). Prefer keys named like a 3D model URL over generic http strings.
    """
    prefer = ("model_url", "pbr_model", "result_url", "url", "file_url", "asset_url")
    prefer_hits: list[str] = []
    other_hits: list[str] = []

    def _walk(node) -> None:
        if isinstance(node, str):
            if node.startswith("http"):
                other_hits.append(node)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and v.startswith("http"):
                    (prefer_hits if k in prefer else other_hits).append(v)
                else:
                    _walk(v)

    _walk(resp)
    if prefer_hits:
        return prefer_hits[0]
    if other_hits:
        return other_hits[0]
    raise MeshWorkerError(
        f"tokenhub 3d DONE response missing result URL: "
        f"keys={list(resp)} sample={str(resp)[:400]}"
    )
