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

import hashlib
import json
import struct
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any


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
# Tencent Hunyuan3D worker —— SubmitHunyuanTo3DRapidJob + poll + GLB download
# API doc: https://intl.cloud.tencent.com/document/api/1284/75976
# ----------------------------------------------------------------------------


class HunyuanMeshWorker(MeshWorker):
    """Tencent Hunyuan3D rapid-job client.

    Authentication: TC3-HMAC-SHA256 signing (Tencent Cloud's standard).
    Needs SecretId + SecretKey (not a bearer token).

    Flow:
      1. POST SubmitHunyuanTo3DRapidJob  -> JobId
      2. Poll QueryHunyuanTo3DRapidJob   -> wait Status == "DONE"
      3. GET ResultFile3Ds[0].Url        -> GLB bytes

    Rate limits: 1 concurrent job by default, 20 req/s global.
    """

    name = "hunyuan_3d"
    _SERVICE = "hunyuan"
    _HOST_INTL = "hunyuan.intl.tencentcloudapi.com"
    _HOST_CN = "hunyuan.tencentcloudapi.com"
    _ACTION_SUBMIT = "SubmitHunyuanTo3DRapidJob"
    _ACTION_QUERY = "QueryHunyuanTo3DRapidJob"
    _VERSION = "2023-09-01"

    def __init__(
        self,
        *,
        secret_id: str,
        secret_key: str,
        region: str = "ap-singapore",
        endpoint_host: str | None = None,
        poll_interval_s: float = 3.0,
        default_timeout_s: float = 300.0,
    ) -> None:
        self._secret_id = secret_id
        self._secret_key = secret_key
        self._region = region
        self._host = endpoint_host or self._HOST_INTL
        self._poll = poll_interval_s
        self._default_timeout_s = default_timeout_s

    def _import_requests(self):
        try:
            import requests
        except ImportError as exc:
            raise MeshWorkerError(
                "`requests` not installed. pip install requests to use HunyuanMeshWorker."
            ) from exc
        return requests

    def generate(
        self,
        *,
        source_image_bytes: bytes,
        spec: dict,
        num_candidates: int = 1,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        import base64
        requests = self._import_requests()
        budget = timeout_s or self._default_timeout_s
        image_b64 = base64.b64encode(source_image_bytes).decode("ascii")

        results: list[MeshCandidate] = []
        for i in range(num_candidates):
            job_id = self._submit(requests, image_b64=image_b64, spec=spec, budget=budget)
            model_url = self._poll_until_done(requests, job_id=job_id, budget=budget)
            dr = requests.get(model_url, timeout=60.0)
            if dr.status_code != 200:
                raise MeshWorkerError(f"model download {dr.status_code}")
            results.append(MeshCandidate(
                data=dr.content,
                format=str(spec.get("format", "glb")).lower(),
                mime_type="model/gltf-binary",
                metadata={
                    "job_id": job_id, "model_url": model_url,
                    "source": "hunyuan_3d", "index": i,
                },
            ))
        return results

    def _submit(self, requests, *, image_b64: str, spec: dict, budget: float) -> str:
        payload = {
            "ImageBase64": image_b64,
            "ResultFormat": str(spec.get("format", "GLB")).upper(),
            "EnablePBR": bool(spec.get("pbr", True)),
            "EnableGeometry": bool(spec.get("geometry_only", False)),
        }
        resp = self._signed_post(requests, action=self._ACTION_SUBMIT,
                                 payload=payload, timeout=min(30.0, budget))
        job_id = ((resp.get("Response") or {}).get("JobId"))
        if not job_id:
            raise MeshWorkerError(
                f"SubmitHunyuanTo3DRapidJob returned no JobId: {resp}"
            )
        return job_id

    def _poll_until_done(self, requests, *, job_id: str, budget: float) -> str:
        start = time.monotonic()
        while True:
            if time.monotonic() - start > budget:
                raise MeshWorkerTimeout(
                    f"Hunyuan3D job {job_id} exceeded {budget}s"
                )
            resp = self._signed_post(
                requests, action=self._ACTION_QUERY,
                payload={"JobId": job_id}, timeout=20.0,
            )
            data = resp.get("Response") or {}
            status = data.get("Status")
            if status == "DONE":
                files = data.get("ResultFile3Ds") or []
                if not files:
                    raise MeshWorkerError(
                        f"Hunyuan3D job {job_id} DONE but no ResultFile3Ds"
                    )
                url = files[0].get("Url")
                if not url:
                    raise MeshWorkerError(
                        f"Hunyuan3D job {job_id}: ResultFile3Ds[0].Url missing"
                    )
                return url
            if status == "FAIL":
                raise MeshWorkerError(
                    f"Hunyuan3D job {job_id} FAIL: "
                    f"{data.get('ErrorCode')} {data.get('ErrorMessage')}"
                )
            time.sleep(self._poll)

    # ---- TC3-HMAC-SHA256 signing helper ----------------------------------

    def _signed_post(
        self, requests, *, action: str, payload: dict, timeout: float,
    ) -> dict:
        import hashlib
        import hmac
        import json as _json
        import time as _time

        body = _json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        body_bytes = body.encode("utf-8")
        ts = int(_time.time())
        date = _time.strftime("%Y-%m-%d", _time.gmtime(ts))

        method = "POST"
        uri = "/"
        query = ""
        canonical_headers = (
            "content-type:application/json; charset=utf-8\n"
            f"host:{self._host}\n"
            f"x-tc-action:{action.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_body = hashlib.sha256(body_bytes).hexdigest()
        canonical_request = (
            f"{method}\n{uri}\n{query}\n{canonical_headers}\n"
            f"{signed_headers}\n{hashed_body}"
        )

        credential_scope = f"{date}/{self._SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(
            canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (
            f"TC3-HMAC-SHA256\n{ts}\n{credential_scope}\n{hashed_canonical}"
        )

        def _hmac(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _hmac(("TC3" + self._secret_key).encode("utf-8"), date)
        secret_service = _hmac(secret_date, self._SERVICE)
        secret_signing = _hmac(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        authorization = (
            f"TC3-HMAC-SHA256 Credential={self._secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self._host,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(ts),
            "X-TC-Version": self._VERSION,
            "X-TC-Region": self._region,
        }
        r = requests.post(
            f"https://{self._host}", data=body_bytes,
            headers=headers, timeout=timeout,
        )
        if r.status_code != 200:
            raise MeshWorkerError(
                f"Hunyuan3D {action} {r.status_code}: {r.text[:300]}"
            )
        parsed = r.json()
        err = (parsed.get("Response") or {}).get("Error")
        if err:
            raise MeshWorkerError(
                f"Hunyuan3D {action} error "
                f"{err.get('Code')}: {err.get('Message')}"
            )
        return parsed
