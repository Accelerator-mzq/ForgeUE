"""ComfyUI agent CLI worker (v3 since executor-async-rewrite TBD-010).

架构:ComfyUI 作为用户管理的外部 GPU 进程运行(见 provider-routing/spec.md
Invariants — `lifecycle="none"` 在本 change scope 仅支持)。本模块通过
asyncio.create_subprocess_exec 异步启动 agent CLI(`python -m comfyui_api`)
并解析 stdout JSON。Worker 配置(scripts_dir / python_exe / default_lifecycle)
从 env vars `FORGEUE_COMFY_*` 读取,不从 `ProviderDef` 字段(round 2 OQ-6 = F-B 决策;
ProviderDef schema NOT extended — F-A 登记 SRS TBD-011 后续 change)。

v1 HTTPComfyWorker (raw HTTP /prompt + /history + /view) 在 commit 292420a 前。
v2 (comfy-agent-cli-adoption): subprocess.run 同步 subprocess。
v3 (executor-async-rewrite TBD-010): asyncio.create_subprocess_exec 异步 subprocess
   + comfy-submission 串行锁 + agenerate* async 主面 + generate* sync shim 兼容。
v4 (comfy-detach-wait-adoption): 阻塞 `run` 换 `run --detach` + `wait --prompt-id`
   两段式 submit-then-poll;cancel 升级 `cancel --prompt-id` 精确取消。

四个暴露的类:
- ComfyWorker     : ABC adapter surface(GenerateImageExecutor 使用)
- FakeComfyWorker : 确定性 scripted/synth adapter(离线测试)
- ComfyAgentWorker: 真实 adapter,通过 asyncio.create_subprocess_exec 启动子进程

生产流程:
  GenerateImageExecutor._should_use_worker_path 检测 model=='comfy/local'
  → 构建 ComfyAgentWorker(scripts_dir=env, run_id, project_id, artifacts_dir=ctx.run_dir)
  → 调用 worker.agenerate(spec={comfy_workflow, comfy_params, comfy_lifecycle},
    num_candidates, seed, timeout_s)
  → _run_comfy_prompt 两段式(锁内全程串行):
    1. submit: `comfyui_api run --workflow X --params P --project ID
       --lifecycle none --timeout N --detach` → 立即返回 prompt_id
    2. wait:   `comfyui_api wait --prompt-id <id> --timeout N` → 收割 outputs
  → 解析 wait stdout JSON,复制 outputs.images 到 artifacts_dir/comfy/,
    构建 list[ImageCandidate](metadata 含 comfy_prompt_id 可追溯)

并发安全:comfy-submission 串行锁(_comfy_submit_lock())确保同一 event loop 内
同时只有 1 个 comfy subprocess 在运行。per-loop WeakKeyDictionary 防止跨 loop
RuntimeError(asyncio.Lock 绑定到首次 waiter 的 loop,模块级单一 Lock 跨 loop 会炸)。

Cancel 语义:async 主面下 CancelledError 在 await 点到达 _run_comfy_prompt,
归因集中在 except 层 — wait 段被取消发 `cancel --prompt-id <id>`(interrupt +
从 queue 删除;注意上游 interrupt 部分仍是全局 /interrupt,"精确"只体现在 queue
删除),submit 段被取消退回裸 cancel(窄窗口 fallback)。CLI 子进程清理
(terminate → grace → kill)由 _invoke_comfy_cli_once finally 负责。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import struct
import subprocess
import sys
import weakref
import zlib
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# comfy-submission 串行锁 — per-loop WeakKeyDictionary
# (TBD-010 executor-async-rewrite Task 3)
# ---------------------------------------------------------------------------

# 每个 event loop 对应一个独立的 asyncio.Lock。
# asyncio.Lock 在 Python 3.10+ 绑定到首次 waiter 所在的 loop(_LoopBoundMixin);
# 模块级单一 Lock 从不同 loop 使用会 RuntimeError("bound to a different event loop")。
# WeakKeyDictionary 使 loop 被 GC 后对应的 Lock 自动删除,无泄漏。
_COMFY_SUBMIT_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _comfy_submit_lock() -> asyncio.Lock:
    """获取当前 event loop 对应的 comfy-submission 锁(遅延生成)。

    同一 loop 内的并发 comfy(DAG fan-out)共享 1 个锁 → 直列化,
    取消时的 POST /interrupt 没有歧义(/interrupt 是 ComfyUI 全局操作)。
    不同 loop 各自独立的锁 — 跨 loop 本来无并发(asyncio.run 顺次阻塞),
    cross-loop RuntimeError 也避免了。
    """
    loop = asyncio.get_running_loop()
    lock = _COMFY_SUBMIT_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _COMFY_SUBMIT_LOCKS[loop] = lock
    return lock


# subprocess buffer:等待 proc.communicate() 超时时的宽余量(秒)
_SUBPROC_BUFFER_S: float = 30.0
# terminate 后等待进程退出的宽余量(秒)
_PROC_GRACE_S: float = 5.0
# cancel 路径 best-effort:POST /interrupt 子进程的最大等待时间(秒)
# 10 秒足够 comfyui_api cancel 发送 HTTP 请求并退出;超时只 warning 不阻塞 cancel
_ABORT_TIMEOUT_S: float = 10.0

# detach submit 段(run --detach)的 wall-clock 上限(秒):
# 覆盖 manifest 校验 + mesh staging PNG 的 input_image auto-upload,无 GPU 等待。
# 超时不发 server abort(prompt 若未 enqueue 则无事可清;若恰已 enqueue 将继续
# 执行,后续 retry 可能带来重复 prompt — detach 模式 enqueue 即返回,60s 已极宽裕,
# 实际风险极低,Task 3 code review M-1 记录此降级语义)
_SUBMIT_TIMEOUT_S: float = 60.0

# Mesh capability(OpenSpec change comfy-agent-cli-mesh-audio-video-adoption Phase 1):
# generate_mesh 返回 MeshCandidate(从 mesh_worker module 复用 dataclass,
# 不扩字段 — provenance 走 metadata dict per design D5)。
from framework.providers.workers.audio_worker import AudioCandidate
from framework.providers.workers.mesh_worker import MeshCandidate
from framework.providers.workers.video_worker import VideoCandidate
from framework.providers.workers.video_metadata import parse_video_metadata

# 模块级 logger(R2-F4 fix:auxiliary outputs.images SHALL emit INFO via 此 logger,
# fence 用 caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker") 抓)
_COMFY_LOGGER = logging.getLogger("framework.providers.workers.comfy_worker")


def _read_prefix(path: Path, size: int) -> bytes:
    """只读取文件头部做格式校验,避免把大 payload 全量读进内存。"""
    with path.open("rb") as fh:
        return fh.read(size)


class WorkerError(RuntimeError):
    """Generic worker failure (bad request, upstream error)."""


class WorkerTimeout(WorkerError):
    """Worker exceeded wall-clock budget."""


class WorkerUnsupportedResponse(WorkerError):
    """Worker observed a deterministically bad response shape that it
    cannot consume — e.g. agent CLI exit 2 with `Missing required
    param`, stdout not valid JSON, outputs.images empty, non-empty
    outputs.glb / outputs.audio in image-generation path.

    Distinct from generic `WorkerError` so FailureModeMap routes this
    to `unsupported_response` → `Decision.abort_or_fallback` rather
    than `worker_error` → `fallback_model` → same-step retry.
    Preserves the FR-RUNTIME-012 invariant (round 2 spec)."""


@dataclass
class ImageCandidate:
    """One image result from a ComfyWorker call."""

    data: bytes                          # raw image bytes (PNG by default)
    width: int
    height: int
    seed: int
    mime_type: str = "image/png"
    format: str = "png"
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None       # FOR-13:本地文件优先走 repo.put(source_path=...)


class ComfyWorker(ABC):
    """Adapter surface used by the generate(image) executor."""

    name: str = "comfy"

    @abstractmethod
    async def agenerate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """异步产出 num_candidates 张图片。超时时 raise WorkerTimeout。
        async 主面(TBD-010 executor-async-rewrite Task 3)。"""

    @abstractmethod
    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """Produce *num_candidates* images for *spec*. Must raise WorkerTimeout on timeout.
        sync shim — 内部调用 asyncio.run(self.agenerate(...)),保持旧调用路径兼容。"""


# ----------------------------------------------------------------------------
# Fake worker — deterministic, offline, scriptable.
# ----------------------------------------------------------------------------


@dataclass
class _Script:
    """One scripted response for one `generate()` call."""

    candidates: list[ImageCandidate] | None = None
    raise_error: BaseException | None = None


class FakeComfyWorker(ComfyWorker):
    """Deterministic fake worker. Prefer explicit programming; falls back to
    synthesised stub PNGs derived from the spec + seed when unprogrammed.

    v2 schema gate (OpenSpec change comfy-agent-cli-adoption Task 6):
    if `spec` contains the new ComfyUI bundle fields (`comfy_workflow`),
    enforce schema constraints (`comfy_workflow` is str, `comfy_params`
    is dict, `comfy_lifecycle` defaults to "none" — must be "none" if
    present). Specs without `comfy_workflow` are accepted as-is for
    backward compatibility with pre-change tests (v1 inline-workflow_graph
    path; legacy `prompt_summary` / `style_tags` synth path).
    """

    name = "fake_comfy"

    def __init__(self) -> None:
        self._scripts: deque[_Script] = deque()
        self.calls: list[dict[str, Any]] = []

    # -- programming --

    def program(self, candidates: list[ImageCandidate]) -> None:
        self._scripts.append(_Script(candidates=list(candidates)))

    def program_error(self, exc: BaseException) -> None:
        self._scripts.append(_Script(raise_error=exc))

    # -- surface --

    async def agenerate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        source_image_bytes: bytes | None = None,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate] | list[MeshCandidate]:
        """异步主面(TBD-010 Task 3):Fake worker 也真实让出一次 event loop。

        `source_image_bytes` 是 FOR-6 兼容层:mesh executor 的远端注入路径调
        `worker.agenerate(source_image_bytes=...)`,这里返回 MeshCandidate。
        """
        await asyncio.sleep(0)
        if source_image_bytes is not None:
            return self._generate_mesh_candidates(
                spec=spec,
                num_candidates=num_candidates,
                seed=seed,
                timeout_s=timeout_s,
                source_image_bytes=source_image_bytes,
                source_image_filename=None,
            )
        return self.generate(
            spec=spec, num_candidates=num_candidates, seed=seed, timeout_s=timeout_s,
        )

    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        # v2 schema gate (OpenSpec change Task 6): only enforced if spec
        # uses the new `comfy_workflow` field; legacy `prompt_summary`
        # specs pass through unchanged for back-compat.
        _validate_fake_comfy_spec(spec, surface="FakeComfyWorker.generate")
        self.calls.append({
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
        })
        if self._scripts:
            script = self._scripts.popleft()
            if script.raise_error is not None:
                raise script.raise_error
            assert script.candidates is not None
            return list(script.candidates)
        return [
            _synth_candidate(spec=spec, index=i, seed=seed)
            for i in range(num_candidates)
        ]

    async def agenerate_mesh(
        self,
        *,
        spec: dict[str, Any],
        source_image_filename: str,
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        """FOR-6:Comfy mesh async stub,供 executor 单测直接注入 fake worker。"""
        await asyncio.sleep(0)
        return self._generate_mesh_candidates(
            spec=spec,
            num_candidates=num_candidates,
            seed=seed,
            timeout_s=timeout_s,
            source_image_bytes=None,
            source_image_filename=source_image_filename,
        )

    async def agenerate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
        """FOR-6:Comfy audio async stub,返回 deterministic minimal FLAC。"""
        await asyncio.sleep(0)
        _validate_fake_comfy_spec(spec, surface="FakeComfyWorker.agenerate_audio")
        self.calls.append({
            "kind": "audio",
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
        })
        return [
            _synth_audio_candidate(spec=spec, index=i, seed=seed)
            for i in range(max(1, num_candidates))
        ]

    async def agenerate_video(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[VideoCandidate]:
        """FOR-6:Comfy video async stub,返回 deterministic minimal BMFF mp4。"""
        await asyncio.sleep(0)
        _validate_fake_comfy_spec(spec, surface="FakeComfyWorker.agenerate_video")
        self.calls.append({
            "kind": "video",
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
        })
        return [
            _synth_video_candidate(spec=spec, index=i, seed=seed)
            for i in range(max(1, num_candidates))
        ]

    def _generate_mesh_candidates(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None,
        timeout_s: float | None,
        source_image_bytes: bytes | None,
        source_image_filename: str | None,
    ) -> list[MeshCandidate]:
        """FOR-6:mesh 两种调用面共享同一 deterministic fake 输出。"""
        _validate_fake_comfy_spec(spec, surface="FakeComfyWorker.agenerate_mesh")
        source_token = (
            source_image_bytes
            if source_image_bytes is not None
            else (source_image_filename or "").encode("utf-8")
        )
        self.calls.append({
            "kind": "mesh",
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
            "source_size": len(source_image_bytes or b""),
            "source_image_filename": source_image_filename,
        })
        return [
            _synth_mesh_candidate(
                source_token=source_token, spec=spec, index=i, seed=seed,
            )
            for i in range(max(1, num_candidates))
        ]


def _validate_fake_comfy_spec(spec: dict[str, Any], *, surface: str) -> None:
    """FakeComfyWorker v2 schema gate;只在 spec 使用 comfy_workflow 时启用。"""
    if "comfy_workflow" not in spec:
        return
    if not isinstance(spec["comfy_workflow"], str) or not spec["comfy_workflow"]:
        raise WorkerUnsupportedResponse(
            f"{surface}: spec.comfy_workflow must be a non-empty string"
        )
    if "comfy_params" in spec and not isinstance(spec["comfy_params"], dict):
        raise WorkerUnsupportedResponse(f"{surface}: spec.comfy_params must be a dict")
    lifecycle = spec.get("comfy_lifecycle", "none")
    # Task 10:FakeComfyWorker 同步解锁 — 接受四个合法值,集合外才 raise。
    valid_lifecycles = {
        "none", "ensure_running", "ensure_release", "self_managed_session",
    }
    if lifecycle not in valid_lifecycles:
        raise WorkerUnsupportedResponse(
            f"{surface}: spec.comfy_lifecycle={lifecycle!r} 不合法; "
            f"合法值为 {sorted(valid_lifecycles)}。"
        )


def _synth_candidate(*, spec: dict[str, Any], index: int, seed: int | None) -> ImageCandidate:
    width = int(spec.get("width", 64))
    height = int(spec.get("height", 64))
    effective_seed = (seed or 0) + index
    # Derive a deterministic colour from (prompt_summary, seed, index).
    digest = hashlib.sha1(
        f"{spec.get('prompt_summary', '')}|{effective_seed}".encode("utf-8")
    ).digest()
    r, g, b = digest[0], digest[1], digest[2]
    data = _make_solid_png(width=width, height=height, rgb=(r, g, b))
    return ImageCandidate(
        data=data, width=width, height=height, seed=effective_seed,
        metadata={
            "prompt_summary": spec.get("prompt_summary"),
            "style_tags": list(spec.get("style_tags") or []),
            "synthetic": True,
            "rgb": [r, g, b],
            "index": index,
        },
    )


def _make_solid_png(*, width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Produce a minimal valid PNG of a solid colour. ~50 bytes for 1x1."""
    r, g, b = rgb
    raw = bytearray()
    row = bytes([0]) + bytes([r, g, b] * width)   # filter byte = 0, then RGB pixels
    for _ in range(height):
        raw += row
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        length = struct.pack(">I", len(payload))
        crc = struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        return length + tag + payload + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)   # 8-bit RGB
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    return bytes(png)


def _synth_mesh_candidate(
    *,
    source_token: bytes,
    spec: dict[str, Any],
    index: int,
    seed: int | None,
) -> MeshCandidate:
    """生成最小 GLB 容器,足够 executor 当 file-backed mesh 使用。"""
    json_chunk = json.dumps({
        "asset": {"version": "2.0", "generator": "forgeue-fake-comfy-mesh"},
        "meshes": [{"name": f"fake_comfy_{index}", "primitives": [{"attributes": {}}]}],
        "scenes": [{"nodes": []}],
        "scene": 0,
        "nodes": [],
    }).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8
    data = (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", 0, 0x004E4942)
    )
    return MeshCandidate(
        data=data,
        format="glb",
        mime_type="model/gltf-binary",
        poly_count=0,
        has_uv=False,
        has_rig=False,
        metadata={
            "synthetic": True,
            "source": "fake_comfy",
            "index": index,
            "seed": (seed or 0) + index,
            "source_image_hash": hashlib.sha1(source_token).hexdigest()[:12],
            "spec": dict(spec),
        },
    )


def _synth_audio_candidate(
    *, spec: dict[str, Any], index: int, seed: int | None,
) -> AudioCandidate:
    """生成最小 FLAC bytes,保持 FakeAudioWorker 同类测试语义。"""
    return AudioCandidate(
        data=_make_minimal_flac(payload=f"fake-comfy-{index}".encode("utf-8")),
        format="flac",
        metadata={
            "synthetic": True,
            "source": "fake_comfy",
            "index": index,
            "seed": (seed or 0) + index,
            "spec": dict(spec),
        },
        duration_seconds=None,
        sample_rate=None,
    )


def _make_minimal_flac(*, payload: bytes) -> bytes:
    """最小 FLAC 头:magic + STREAMINFO,不依赖外部 codec。"""
    out = bytearray(b"fLaC")
    out.extend(b"\x80\x00\x00\x22")
    streaminfo = bytearray()
    streaminfo.extend(struct.pack(">H", 4096))
    streaminfo.extend(struct.pack(">H", 4096))
    streaminfo.extend(b"\x00\x00\x00")
    streaminfo.extend(b"\x00\x00\x00")
    sr = 44100
    streaminfo.append((sr >> 12) & 0xFF)
    streaminfo.append((sr >> 4) & 0xFF)
    streaminfo.append(((sr & 0x0F) << 4) | (1 << 1))
    streaminfo.append(0xF0)
    streaminfo.extend(b"\x00\x00\x00\x00")
    streaminfo.extend(b"\x00" * 16)
    out.extend(streaminfo)
    out.extend(b"\xff\xf8")
    out.extend(payload[:8])
    return bytes(out)


def _synth_video_candidate(
    *, spec: dict[str, Any], index: int, seed: int | None,
) -> VideoCandidate:
    """生成最小 BMFF mp4 ftyp box,匹配 video worker 的 mp4-only contract。"""
    return VideoCandidate(
        data=_make_minimal_mp4(),
        format="mp4",
        metadata={
            "synthetic": True,
            "source": "fake_comfy",
            "index": index,
            "seed": (seed or 0) + index,
            "spec": dict(spec),
        },
    )


def _make_minimal_mp4() -> bytes:
    """最小 ftyp box:len + b'ftyp' + major_brand + compatible brands。"""
    return (
        b"\x00\x00\x00\x20"
        b"ftyp"
        b"isom"
        b"\x00\x00\x02\x00"
        b"isomiso2mp41mp42"
    )


# ----------------------------------------------------------------------------
# Real worker — invoke `python -m comfyui_api` as subprocess.
# ----------------------------------------------------------------------------


# Failure-mode discriminators (round 2 spec D5 + round 3 P2 sync probe).
# v3.3(2026-06-11)起为 fallback:上游失败 JSON 带 error_code 结构化字段时
# code 优先(_raise_comfy_failure),marker 只兜旧版 CLI 无 code 的场景。
# "out of range" 修正:patcher 实际串是 `value {N} out of range`(中间含数值),
# 旧 marker "value out of range" 永匹配不上(latent bug,本次随 v3.3 适配修复,
# fence: test_real_patcher_out_of_range_string_maps_to_unsupported)。
_UNSUPPORTED_ERROR_MARKERS = (
    "Missing required param",
    "out of range",
    "value_not_in_list",
)

# error_code → WorkerUnsupportedResponse 的 deterministic 集合
# (retry 无意义:参数错 / manifest 错 / 模型未装 / 输入文件缺 / prompt 校验错)。
# code 清单契约见上游 AGENT_API.md §5(v3.3)。
_ERROR_CODE_UNSUPPORTED = frozenset({
    "missing_required_param", "param_out_of_range", "value_not_in_list",
    "workflow_not_found", "input_image_not_found", "invalid_arguments",
    "comfy_rejected",
})


def _raise_comfy_failure(data: dict, returncode: int | None, context: str) -> None:
    """ok=false 统一分类:error_code 结构化字段优先,error 文案 marker fallback。

    上游 comfyui_api v3.3(2026-06-11)起失败 JSON 带 error_code 稳定契约;
    code 存在时完全接管分类(timeout → WorkerTimeout / deterministic 集 →
    WorkerUnsupportedResponse / 其余 → WorkerError 可 retry)。code 缺失
    (旧版 CLI)时退回字符串 marker 分类,行为与 round 2 spec D5 一致。
    """
    error_msg = str(data.get("error", ""))
    error_code = data.get("error_code")
    if isinstance(error_code, str) and error_code:
        if error_code == "timeout":
            raise WorkerTimeout(
                f"{context}: comfyui_api timeout (error_code=timeout): {error_msg}")
        if error_code in _ERROR_CODE_UNSUPPORTED:
            raise WorkerUnsupportedResponse(
                f"{context}: deterministic error (error_code={error_code}): {error_msg}")
        raise WorkerError(
            f"{context}: comfyui_api returned ok=false "
            f"(exit {returncode}, error_code={error_code}, error: {error_msg})")
    if "TimeoutError" in error_msg:
        raise WorkerTimeout(f"{context}: ComfyUI reported TimeoutError: {error_msg}")
    for marker in _UNSUPPORTED_ERROR_MARKERS:
        if marker in error_msg:
            raise WorkerUnsupportedResponse(
                f"{context}: deterministic param error: {error_msg}")
    raise WorkerError(
        f"{context}: comfyui_api returned ok=false "
        f"(exit {returncode}, error: {error_msg})")


class ComfyAgentWorker(ComfyWorker):
    """Subprocess adapter for ComfyUI agent CLI (`python -m comfyui_api`).

    Constructor is keyword-only with REQUIRED args first per Python rules
    (round 3 H3 fix — round 2 contract sketch had required positional
    after default which is SyntaxError). REQUIRED `run_id` / `project_id`
    / `artifacts_dir` raise `WorkerUnsupportedResponse` if missing or
    invalid (round 2 F4 + G3 fixes).

    Worker config (scripts_dir / python_exe / default_lifecycle) is
    sourced from the executor's env-var read (round 2 OQ-6 = F-B
    decision; ProviderDef schema NOT extended).

    `default_lifecycle` is asserted to be "none" — the only value
    supported in this change scope (D6; cancel best-effort under
    orchestrator's to_thread wrapping; ensure_running / ensure_release /
    self_managed_session deferred to TBD-010 executor-async-rewrite).

    `generate()` / `generate_mesh()` / `generate_audio()` / `generate_video()`
    are thin sync shims that delegate to the async primaries `agenerate*` via
    `asyncio.run(...)`; the primaries invoke the agent CLI through
    `asyncio.create_subprocess_exec` (TBD-010 executor-async-rewrite Task 3).
    Calling a sync shim from inside a running event loop raises RuntimeError
    (nested `asyncio.run`) — async callers MUST use the `agenerate*` primaries.

    `aprobe()` is the async dry-run preflight used by the now-async
    `DryRunPass.run`; `probe_sync()` is its `asyncio.run(...)` sync shim,
    kept for probe scripts / tests that run outside an event loop.
    """

    name = "comfy_agent_cli"

    # Capability dispatch(OpenSpec change comfy-agent-cli-mesh-audio-video-adoption
    # design D1 + comfy-agent-cli-audio-adoption Phase 2 D1 +
    # comfy-agent-cli-video-adoption Phase 3 D6):capability 由 model_id 推断,
    # bundle 不引入 outputs_kind 字段。未知 model_id → __init__ raise(不静默 fallback)。
    # All TBD-009 phases closed:image (Phase 1) + mesh (Phase 1 mesh) +
    # audio (Phase 2) + video (Phase 3)。
    _CAPABILITY_BY_MODEL_ID: dict[str, str] = {
        "comfy/local": "image",
        "comfy/local-mesh": "mesh",
        "comfy/local-audio": "audio",  # Phase 2 audio (F1 round-1 修订)
        "comfy/local-video": "video",  # Phase 3 video (D6)
    }

    # Output validation 三段表(design D2 + B4 修订:mesh-mode auxiliary outputs.images
    # 容忍,不构造 candidate 但 SHALL emit INFO log per R2-F4;Phase 2 D2 audio 行
    # 加 — audio capability 无 auxiliary tolerance;Phase 3 D6 video 行加 —
    # video capability 无 auxiliary tolerance,REJECTED 含 images/glb/audio)。
    # REQUIRED:capability 必须产出此 key non-empty
    # AUXILIARY:允许 non-empty 但不消费(emit INFO log;audio / video 无 auxiliary)
    # REJECTED:non-empty 即 raise WorkerUnsupportedResponse
    _REQUIRED_OUTPUT_KEY: dict[str, str] = {
        "image": "images",
        "mesh": "glb",
        "audio": "audio",  # Phase 2 audio
        "video": "video",  # Phase 3 video (round-3 PF1 D-Runner-Extension:user-authored
                           # runner.py 已加 video collection block 把 VHS gifs UI key 装到
                           # outputs.video,沿 image / audio / glb 同款 4-dict 协议)
    }
    _AUXILIARY_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
        "image": set(),                # image-mode 无 auxiliary
        "mesh": {"images"},            # mesh-mode 容忍 PNG preview(B4)
        "audio": set(),                # audio-mode 无 auxiliary tolerance(Phase 2 D2)
        "video": set(),                # video-mode 无 auxiliary tolerance(Phase 3 D6;
                                       # VHS_VideoCombine 默认只输出 video file,无 PNG preview)
    }
    _REJECTED_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
        "image": {"glb", "audio", "video"},
        "mesh": {"audio", "video"},
        "audio": {"images", "glb", "video"},  # Phase 2 audio
        "video": {"images", "glb", "audio"},  # Phase 3 video (D6;reject 其它三 capability output keys)
    }

    # Task 10 round 2:comfy_lifecycle 四合法值集合 — 类级常量,供 __init__ 和
    # agenerate* 四个方法共同引用,避免重复定义。D6 原 "none"-only gate 已在
    # TBD-010 executor-async-rewrite 中解锁为集合检查。
    _VALID_LIFECYCLES: frozenset[str] = frozenset({
        "none", "ensure_running", "ensure_release", "self_managed_session",
    })

    # Audio capability whitelist(Phase 2 D10:format ∈ {flac, mp3, wav};
    # F5 round-1 magic bytes 二次校验 + F-Plan-4 round-2 path trust-boundary 防护)
    _AUDIO_FORMAT_WHITELIST: set[str] = {"flac", "mp3", "wav"}

    # Video capability whitelist(Phase 3 D8 + round-2 F2 + round-3 PF3 sweep:
    # mp4-only,webm follow-on `comfy-video-webm-adoption`;round-2 F4 + round-3 PF2
    # BMFF strict header 5-tuple 校验在 _run_once_video 内部 enforce — len + ftyp +
    # box_size in [8,len] reject box_size==1 + major_brand non-empty/non-zero/non-spaces)
    _VIDEO_FORMAT_WHITELIST: set[str] = {"mp4"}

    def __init__(
        self,
        *,                                       # H3: keyword-only
        scripts_dir: Path,                       # REQUIRED
        model_id: str,                           # REQUIRED (capability dispatch per D1)
        run_id: str,                             # REQUIRED (F4 fix)
        project_id: str,                         # REQUIRED (F4 fix)
        artifacts_dir: Path,                     # REQUIRED (G3 fix; ctx.run_dir)
        python_exe: Path | None = None,          # OPTIONAL (= sys.executable)
        default_lifecycle: str = "none",         # OPTIONAL (only "none" supported in this change)
        capability: str | None = None,           # 可选:provider metadata 可显式指定 capability
        output_root: Path | None = None,         # 可选:覆盖 comfy outputs containment 根目录
    ) -> None:
        # F4 fix: REQUIRED project_id None/empty raise.
        if not project_id:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: project_id is REQUIRED; "
                "executor must pass ctx.task.project_id (round 2 OQ-3)"
            )
        if not run_id:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: run_id is REQUIRED; "
                "executor must pass ctx.run.run_id"
            )
        # G3 fix: REQUIRED artifacts_dir None or non-directory raise.
        if artifacts_dir is None:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: artifacts_dir is REQUIRED; "
                "executor must pass ctx.run_dir (round 2 OQ-7 = G-A; "
                "Path('.') default is test-mock convenience only)"
            )
        artifacts_dir = Path(artifacts_dir)
        if not artifacts_dir.is_dir():
            # Auto-create — this is a normal first-run condition for the
            # production path where Orchestrator computes run_dir but
            # the directory may not yet exist. ImageCandidate copy
            # target needs a real directory.
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        # Task 10:解锁 lifecycle gate — 接受四个合法值,集合外才 raise。
        # D6 原锁 "none"-only 已被 TBD-010 executor-async-rewrite 解锁。
        # _VALID_LIFECYCLES 为类级常量(round 2 Important-1:各 agenerate* 复用同一常量)。
        if default_lifecycle not in self._VALID_LIFECYCLES:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.__init__: 不支持的 default_lifecycle={default_lifecycle!r}; "
                f"合法值为 {sorted(self._VALID_LIFECYCLES)}。"
            )
        # capability 可由 provider metadata 显式传入;未传时保留旧 model_id 推断。
        # 这样自定义 model id 仍能复用同一 ComfyAgentWorker 输出校验表。
        if capability is None:
            capability = self._CAPABILITY_BY_MODEL_ID.get(model_id)
            if capability is None:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.__init__: unsupported model_id={model_id!r}, "
                    f"expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)} "
                    f"(all TBD-009 phases closed: image / mesh / audio / video)"
                )
        elif capability not in self._REQUIRED_OUTPUT_KEY:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.__init__: unsupported capability={capability!r}; "
                f"expected one of {sorted(self._REQUIRED_OUTPUT_KEY)}"
            )
        self.scripts_dir = Path(scripts_dir)
        self.python_exe = Path(python_exe) if python_exe else Path(sys.executable)
        self.default_lifecycle = default_lifecycle
        self.run_id = run_id
        self.project_id = project_id
        self.artifacts_dir = artifacts_dir
        self.model_id = model_id
        self._capability = capability
        # Task 4 测试钩子:最近一次 _run_once*_async 创建的子进程(供 cancel 测试断言);
        # 在 __init__ 初始化,避免 agenerate 调用前访问触发 AttributeError
        self._last_proc: asyncio.subprocess.Process | None = None
        # detach-wait change 测试/探针钩子:最近一次 submit 解析出的 prompt_id
        self._last_prompt_id: str | None = None
        # OpenSpec change `comfy-agent-cli-path-containment-hardening`(2026-05-04
        # follow-on for G11-F2):the ComfyUI subprocess outputs files anywhere
        # the CLI's `extract_outputs` resolved them — by default under
        # `D:/AI/ComfyUI/outputs/main/...`. To prevent a buggy / compromised
        # ComfyUI from returning paths *outside* the ComfyUI install tree
        # (e.g. `/etc/secrets`), each `_run_once*` resolves output paths and
        # asserts they live under `comfy_output_root` before reading bytes.
        # Resolution order(first non-None wins):
        #   1. `FORGEUE_COMFY_OUTPUT_ROOT` env var(explicit override for
        #      ComfyUI installs that write outputs to a non-default location)
        #   2. `scripts_dir.parent`(heuristic — matches the typical layout
        #      `D:/AI/ComfyUI/scripts` + `D:/AI/ComfyUI/outputs/main/...`,
        #      both under `D:/AI/ComfyUI`. Also works for unit tests where
        #      `scripts_dir = tmp_path / "scripts"` → `scripts_dir.parent
        #      = tmp_path` covers fake outputs under tmp_path.)
        # The check uses `Path.resolve()` to normalise symlinks / relative
        # segments before `is_relative_to()`. This is defense-in-depth on top
        # of the existing `is_file()` + `is_symlink()` + extension whitelist
        # + magic-bytes checks.
        env_output_root = os.environ.get("FORGEUE_COMFY_OUTPUT_ROOT")
        if output_root is not None:
            self.comfy_output_root = Path(output_root).resolve()
        elif env_output_root:
            self.comfy_output_root = Path(env_output_root).resolve()
        else:
            # Heuristic fallback: scripts_dir parent (covers ComfyUI install
            # tree including outputs/ + tests' tmp_path layout)
            self.comfy_output_root = self.scripts_dir.parent.resolve()

    async def agenerate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """image capability async 主面(TBD-010 executor-async-rewrite Task 3)。

        每个 candidate 通过 asyncio.create_subprocess_exec 异步启动子进程,
        整个 submit→poll 段在 async with _comfy_submit_lock(): 内运行,
        确保同一 loop 内最多 1 个 comfy subprocess 同时运行。
        per-call timeout 是 timeout_s(默认 300s);total wall-clock = num_candidates × per-call。
        """
        # capability 守门
        if self._capability != "image":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local' 的 worker 可调 agenerate(image-mode);"
                f"mesh-mode worker 应调 agenerate_mesh"
            )
        # 拒绝 legacy v1 spec shape
        if "workflow_graph" in spec:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate: spec.workflow_graph is deprecated "
                "since OpenSpec change comfy-agent-cli-adoption; use "
                "spec.comfy_workflow + spec.comfy_params instead"
            )
        comfy_workflow = spec.get("comfy_workflow")
        if not isinstance(comfy_workflow, str) or not comfy_workflow:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate: spec.comfy_workflow REQUIRED, "
                "must be non-empty string (manifest name like "
                "'GameAssets/01b_singleview_sdxl')"
            )
        comfy_params = spec.get("comfy_params", {})
        if not isinstance(comfy_params, dict):
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate: spec.comfy_params must be a dict"
            )
        lifecycle = spec.get("comfy_lifecycle", "none")
        # Task 10 round 2 Important-1:旧 D6 "none"-only gate 替换为集合检查(四合法值)。
        # 集合外才 raise;合法值列举在消息中便于排查。
        if lifecycle not in self._VALID_LIFECYCLES:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate: spec.comfy_lifecycle={lifecycle!r} 不合法; "
                f"合法值为 {sorted(self._VALID_LIFECYCLES)}。"
            )
        per_call_timeout = float(timeout_s) if timeout_s else 300.0
        results: list[ImageCandidate] = []
        for i in range(max(1, num_candidates)):
            call_seed = (seed or 0) + i
            params_for_call = dict(comfy_params)
            # per-candidate seed 直接覆盖,不用 setdefault(comfy-worker-seed-setdefault-bug-fix)
            params_for_call["seed"] = call_seed
            results.extend(await self._run_once_async(
                comfy_workflow=comfy_workflow,
                params=params_for_call,
                seed=call_seed,
                timeout_s=per_call_timeout,
            ))
        return results

    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """sync shim — 委托 asyncio.run(self.agenerate(...))。
        保持 probe 脚本 / 旧调用路径兼容(TBD-010 Task 3)。
        注意:已有 event loop 运行时调用会 RuntimeError;在 to_thread 内可安全使用。
        """
        # capability 守门(与 agenerate 一致,允许在 sync 路径早期 raise)
        if self._capability != "image":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.generate: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local' 的 worker 可调 generate(image-mode);"
                f"mesh-mode worker 应调 generate_mesh"
            )
        # 拒绝 legacy v1 spec shape(提前 raise 不走 asyncio.run)
        if "workflow_graph" in spec:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.generate: spec.workflow_graph is deprecated "
                "since OpenSpec change comfy-agent-cli-adoption; use "
                "spec.comfy_workflow + spec.comfy_params instead"
            )
        return asyncio.run(self.agenerate(
            spec=spec, num_candidates=num_candidates, seed=seed, timeout_s=timeout_s,
        ))

    async def _run_once_async(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        seed: int,
        timeout_s: float,
    ) -> list[ImageCandidate]:
        """image capability 的一次异步 subprocess 调用 → 1+ ImageCandidate。

        detach-wait 两段式协议(detach-wait change Task 3):
        委托 _run_comfy_prompt(submit run --detach → wait --prompt-id)。
        """
        outputs, returncode, prompt_id = await self._run_comfy_prompt(
            comfy_workflow=comfy_workflow,
            params=params,
            timeout_s=timeout_s,
            context="ComfyAgentWorker",
        )
        # OpenSpec change comfy-agent-cli-mesh-audio-video-adoption:capability-aware
        # 三段表守门(design D2 + B4 修订)。原硬编码 image-only 守门替换为表驱动。
        # mesh-mode auxiliary outputs.images 容忍 + INFO log,只 raise rejected key。
        self._validate_outputs(outputs, comfy_workflow=comfy_workflow)
        # image-mode 后续 candidate 构造(mesh-mode 不走 _run_once,见 generate_mesh)
        images = outputs.get("images") or []

        # Copy each output PNG into <artifacts_dir>/comfy/ for in-tree
        # placement (round 2 G3 + artifact-contract spec).
        comfy_subdir = self.artifacts_dir / "comfy"
        comfy_subdir.mkdir(parents=True, exist_ok=True)
        candidates: list[ImageCandidate] = []
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        for src_str in images:
            src = Path(src_str)
            if not src.is_file():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images path does not exist: {src}"
                )
            # G11 R2 fix: reject symlinks (and Windows junctions) to prevent
            # a buggy / compromised agent CLI from redirecting reads to
            # arbitrary host files (e.g. /etc/secrets via ../symlink).
            if src.is_symlink():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images path is a symlink, "
                    f"refusing to follow: {src}"
                )
            # OpenSpec change `comfy-agent-cli-path-containment-hardening`
            # (2026-05-04 follow-on for G11-F2):assert path under
            # `comfy_output_root` before reading header bytes — defense-in-depth
            self._assert_path_within_comfy_output_root(src, output_kind="images")
            dst = comfy_subdir / src.name
            shutil.copy2(src, dst)
            header = _read_prefix(dst, 8)
            # G11 R2 fix: validate PNG magic bytes (8-byte signature
            # 89 50 4E 47 0D 0A 1A 0A). image-generation path must reject
            # non-PNG bytes — a workflow producing JPG/WEBP/etc. should be
            # treated as deterministic mismatch (caller declared image
            # capability with implicit PNG expectation per ImageCandidate
            # mime_type default). Future change can broaden the magic
            # allowlist to JPEG/WEBP if needed.
            if header != b"\x89PNG\r\n\x1a\n":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images file {src.name!r} is "
                    f"not a valid PNG (first 8 bytes {header!r}); "
                    f"image-generation path requires PNG magic bytes"
                )
            candidates.append(ImageCandidate(
                data=header,
                width=width,
                height=height,
                seed=seed,
                metadata={
                    "comfy_workflow": comfy_workflow,
                    "filename": src.name,
                    "in_tree_path": str(dst),
                    "source": "comfy_agent_cli",
                    "comfy_project_id": self.project_id,
                    "comfy_outputs_orig": str(src),
                    "comfy_prompt_id": prompt_id,
                },
                source_path=str(dst),
            ))
        return candidates

    def _validate_outputs(self, outputs: dict, *, comfy_workflow: str) -> None:
        """Capability-aware output validation 三段表(design D2 + B4 修订)。

        顺序(沿用原 image-mode 行为模式):
        1. REJECTED key non-empty → raise(优先报告 workflow type 错,例如
           image-mode 跑了 mesh manifest 应该报「outputs.glb 不该有」而非「images empty」)
        2. REQUIRED key missing → raise
        3. AUXILIARY key non-empty → SHALL emit INFO log + 不消费(R2-F4)

        Per OpenSpec change comfy-agent-cli-mesh-audio-video-adoption Phase 1
        mesh:image-mode 行为不变(rejected = {glb, audio, video});mesh-mode
        新加(rejected = {audio, video},auxiliary = {images} 容忍 PNG preview)。
        """
        cap = self._capability
        # 1. REJECTED 先(fail-fast 优先报告 workflow type 错)
        rejected_present = self._REJECTED_OUTPUT_KEYS_BY_CAP[cap] & {
            k for k, v in outputs.items() if v
        }
        if rejected_present:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker(capability={cap!r}): rejected non-empty "
                f"outputs {sorted(rejected_present)!r} for workflow "
                f"{comfy_workflow!r}; see SRS TBD-009 for follow-on "
                f"capability changes (audio / video)"
            )
        # 2. REQUIRED 后
        required_key = self._REQUIRED_OUTPUT_KEY[cap]
        if not outputs.get(required_key):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker(capability={cap!r}): outputs.{required_key} "
                f"empty for workflow {comfy_workflow!r}; deterministic empty "
                f"response cannot be recovered by same-step retry"
            )
        # 3. AUXILIARY:R2-F4 SHALL emit INFO log,不消费,不 raise
        for aux_key in self._AUXILIARY_OUTPUT_KEYS_BY_CAP[cap]:
            aux_val = outputs.get(aux_key)
            if aux_val:
                _COMFY_LOGGER.info(
                    f"{cap}-mode auxiliary outputs.{aux_key}: "
                    f"count={len(aux_val)} paths={list(aux_val)!r} capability={cap!r}"
                )

    def _assert_path_within_comfy_output_root(self, src: Path, *, output_kind: str) -> None:
        """OpenSpec change `comfy-agent-cli-path-containment-hardening`(2026-05-04
        follow-on for G11-F2):assert that a subprocess-returned output path
        resolves to a location *under* `self.comfy_output_root`. Raises
        `WorkerUnsupportedResponse` otherwise — defense-in-depth on top of
        existing `is_file()` + `is_symlink()` + extension whitelist + magic
        bytes checks. Threat model = buggy / compromised ComfyUI subprocess
        returning paths outside the ComfyUI install tree(typical example:
        path traversal via `..` segments resolved to a host root path);
        threat model is NOT a fully-compromised subprocess(in which case
        the entire user account is already breached and framework-level
        containment cannot recover)."""
        try:
            resolved = src.resolve()
        except (OSError, RuntimeError) as exc:
            # OSError on Windows for invalid UNC; RuntimeError for symlink loop
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: outputs.{output_kind} path could not be "
                f"resolved: {src} ({type(exc).__name__}: {exc})"
            ) from exc
        # Path.is_relative_to was added in Python 3.9; use it directly.
        if not resolved.is_relative_to(self.comfy_output_root):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: outputs.{output_kind} path {resolved!r} "
                f"is outside comfy_output_root {self.comfy_output_root!r}; "
                f"refusing to read bytes from unverified location. Configure "
                f"FORGEUE_COMFY_OUTPUT_ROOT env var if your ComfyUI install "
                f"writes outputs to a non-default directory."
            )

    async def _abort_comfy_prompt(self, prompt_id: str | None = None) -> None:
        """cancel 路径 best-effort:有 prompt_id 时 `cancel --prompt-id <id>`
        (interrupt + 从 queue 删除;注意上游 interrupt 部分仍是全局 /interrupt,
        "精确"只体现在 queue 删除 — detach-wait change 核验结论,LLD 已标注),
        无 id 退回裸 cancel(submit 段被取消的窄窗口 fallback)。
        失败只 warning,不抛;_ABORT_TIMEOUT_S 守门 + kill 清理。
        """
        ap = None
        cancel_cmd = [str(self.python_exe), "-m", "comfyui_api", "cancel"]
        if prompt_id:
            cancel_cmd += ["--prompt-id", prompt_id]
        try:
            ap = await asyncio.create_subprocess_exec(
                *cancel_cmd,
                cwd=str(self.scripts_dir),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(ap.wait(), timeout=_ABORT_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — best-effort,失败只 warning
            _COMFY_LOGGER.warning("comfy prompt abort failed: %s", exc)
        finally:
            # abort 子进程 cleanup:wait_for 超时只取消 ap.wait() 协程,不停 ap 进程;
            # 未退出则 kill,避免 ComfyUI server 挂死时孤儿 CLI 进程累积
            if ap is not None and ap.returncode is None:
                try:
                    ap.kill()
                    await ap.wait()
                except Exception:  # noqa: BLE001 — cleanup best-effort
                    pass

    async def _invoke_comfy_cli_once(
        self,
        *,
        cmd: list[str],
        wall_timeout_s: float,
        cli_timeout_s: float,
        context: str,
        abort_on_cleanup: bool = False,
    ) -> tuple[dict, int]:
        """一次 comfyui_api CLI 子进程调用的共享低层封装(detach-wait change Task 1)。

        收敛原 4 条 _run_once_*_async 的同构块:spawn → communicate(wall-clock
        守门)→ cleanup(abort/terminate/kill)→ decode → stdout JSON 解析 →
        ok=false 走 _raise_comfy_failure 分类。调用方负责持有 _comfy_submit_lock
        (本方法整体在锁内执行,**包括 JSON 解析段** — 解析无 await 点,与原
        锁外解析并发语义等价,但后续在本方法内加异步操作时须留意锁持有范围)
        与 outputs 字段校验(detach submit 响应没有 outputs 字段)。
        abort_on_cleanup:cleanup 时是否先发 server-side abort(裸 cancel)。
        detach 协议下取消归因在 _run_comfy_prompt except 层,当前所有调用方
        均传/默认 False;True 仅为非 detach 场景扩展点保留(final review 后
        默认值与实际调用对齐,避免误导性默认)。
        返回 (stdout JSON dict, returncode)。
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.scripts_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # 测试钩子:保存当前 proc 供 cancel 测试断言终态
            self._last_proc = proc
        except FileNotFoundError as exc:
            raise WorkerUnsupportedResponse(
                f"{context}: failed to spawn subprocess "
                f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
            ) from exc
        try:
            raw_out, raw_err = await asyncio.wait_for(
                proc.communicate(), timeout=wall_timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise WorkerTimeout(
                f"{context} subprocess wall-clock exceeded "
                f"{wall_timeout_s}s (CLI internal timeout was {cli_timeout_s}s)"
            ) from exc
        finally:
            if proc.returncode is None:
                if abort_on_cleanup:
                    await self._abort_comfy_prompt()
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                except asyncio.TimeoutError:
                    proc.kill()
                await proc.wait()

        # stdout/stderr 转 UTF-8 文本
        stdout_text = raw_out.decode("utf-8", errors="replace").strip() if raw_out else ""
        stderr_text = raw_err.decode("utf-8", errors="replace").strip() if raw_err else ""
        returncode = proc.returncode

        # 空 stdout 守门
        if not stdout_text:
            raise WorkerUnsupportedResponse(
                f"{context}: empty stdout (exit code {returncode}; "
                f"stderr first 500 chars: {stderr_text[:500]!r})"
            )
        # JSON 解析守门
        try:
            data = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"{context}: stdout is not valid JSON "
                f"(exit code {returncode}; first 500 chars: {stdout_text[:500]!r})"
            ) from exc
        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"{context}: stdout JSON is not a dict (got {type(data).__name__})"
            )
        # ok=false 走共享分类 helper(v3.3 error_code 优先 + marker fallback)
        if not data.get("ok"):
            _raise_comfy_failure(data, returncode, context)
        return data, returncode

    async def _run_comfy_prompt(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        timeout_s: float,
        context: str,
    ) -> tuple[dict, int, str]:
        """detach+wait 两段式协议(detach-wait change,spec §3.2)。

        整段在 _comfy_submit_lock() 内(D2 全程串行,与原阻塞 run 等价):
        1. submit: run --detach → 立即返回 prompt_id(上游在返回前同步完成
           manifest 校验 + input_image* auto-upload)
        2. wait:   wait --prompt-id <id> --timeout N → 收割 outputs
        cancel 归因集中在本层 except:wait 段被取消带 prompt_id 精确取消,
        submit 段被取消退回裸 cancel(窄窗口 fallback)。
        返回 (outputs dict, wait 段 returncode, prompt_id)。
        """
        base = [str(self.python_exe), "-m", "comfyui_api"]
        submit_cmd = base + [
            "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
            "--detach",
        ]
        async with _comfy_submit_lock():
            try:
                sdata, _submit_rc = await self._invoke_comfy_cli_once(
                    cmd=submit_cmd,
                    wall_timeout_s=_SUBMIT_TIMEOUT_S,
                    cli_timeout_s=timeout_s,
                    context=context,
                    abort_on_cleanup=False,
                )
            except (WorkerTimeout, asyncio.CancelledError):
                # submit 段超时 / 被取消:prompt 可能已 queue 也可能没有 →
                # 裸 cancel best-effort(残留边界见 LLD cancel 小节)
                await self._abort_comfy_prompt(None)
                raise
            prompt_id = sdata.get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id:
                raise WorkerUnsupportedResponse(
                    f"{context}: run --detach response missing prompt_id "
                    f"(got {sdata.get('prompt_id')!r}); upstream AGENT_API.md "
                    f"§1.8 contract requires it — check comfyui_api version"
                )
            self._last_prompt_id = prompt_id
            wait_cmd = base + [
                "wait",
                "--prompt-id", prompt_id,
                "--timeout", str(int(timeout_s)),
            ]
            try:
                wdata, wait_rc = await self._invoke_comfy_cli_once(
                    cmd=wait_cmd,
                    wall_timeout_s=timeout_s + _SUBPROC_BUFFER_S,
                    cli_timeout_s=timeout_s,
                    context=context,
                    abort_on_cleanup=False,
                )
            except (WorkerTimeout, asyncio.CancelledError):
                # wait 段超时(CLI 内部 error_code=timeout 或 wall-clock 挂死)
                # / 被取消:精确取消自己的 prompt(interrupt + queue 删除),
                # 防僵尸 GPU prompt 继续烧卡 + retry 叠加(spec §4)
                await self._abort_comfy_prompt(prompt_id)
                raise
            if "outputs" not in wdata or not isinstance(wdata["outputs"], dict):
                raise WorkerUnsupportedResponse(
                    f"{context}: stdout JSON missing 'outputs' field or "
                    f"not a dict (got {wdata.get('outputs')!r})"
                )
            return wdata["outputs"], wait_rc, prompt_id

    async def agenerate_mesh(
        self,
        *,
        spec: dict[str, Any],
        source_image_filename: str,
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        """Mesh capability async 主面(TBD-010 executor-async-rewrite Task 3)。

        与 image-mode agenerate() 平行,但:
        - 仅在 _capability == "mesh" 时可调(否则 raise)
        - 接 source_image_filename: filename only(round 5 D10)
        - 返 MeshCandidate(data=GLB bytes, metadata={comfy provenance})
        - 通过 _run_once_mesh_async 使用 asyncio.create_subprocess_exec
        """
        if self._capability != "mesh":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local-mesh' 的 worker 可调 agenerate_mesh"
            )
        # bundle spec 校验
        if "workflow_graph" in spec:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_mesh: spec.workflow_graph is deprecated; "
                "use spec.comfy_workflow + spec.comfy_params instead"
            )
        comfy_workflow = spec.get("comfy_workflow")
        if not isinstance(comfy_workflow, str) or not comfy_workflow:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_mesh: spec.comfy_workflow REQUIRED, "
                "must be non-empty string (manifest name like 'Mesh/02_mini_textured_3d_hunyuan')"
            )
        comfy_params = spec.get("comfy_params", {})
        if not isinstance(comfy_params, dict):
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_mesh: spec.comfy_params must be a dict"
            )
        lifecycle = spec.get("comfy_lifecycle", "none")
        # Task 10 round 2 Important-1:旧 D6 "none"-only gate 替换为集合检查(四合法值)。
        if lifecycle not in self._VALID_LIFECYCLES:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: spec.comfy_lifecycle={lifecycle!r} 不合法; "
                f"合法值为 {sorted(self._VALID_LIFECYCLES)}。"
            )
        image_param_key = spec.get("comfy_image_param_key") or "input_image"
        # v3.3 守门:source_image_filename 是路径(含分隔符,executor in-tree staging
        # 绝对路径)时,上游 auto-upload 只对 input_image* 前缀参数触发(AGENT_API.md
        # §1.3);非前缀 key 配路径值 upload 不发生,LoadImage 拿到绝对路径必然运行期
        # 失败 → fail-fast。裸文件名 + 任意 key 仍合法(视为已在 ComfyUI input 目录)。
        _is_path_value = ("/" in source_image_filename) or ("\\" in source_image_filename)
        if _is_path_value and not image_param_key.startswith("input_image"):
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_mesh: spec.comfy_image_param_key="
                f"{image_param_key!r} 不以 'input_image' 开头,而 source_image_filename "
                f"是本地路径({source_image_filename!r});comfyui_api v3 的 input_image* "
                "本地路径自动上传只对该前缀参数生效 — 改用 input_image* 前缀 key,或传"
                "已在 ComfyUI input 目录内的裸文件名"
            )
        per_call_timeout = float(timeout_s) if timeout_s else 600.0
        results: list[MeshCandidate] = []
        for i in range(max(1, num_candidates)):
            call_seed = (seed or 0) + i
            params_for_call = dict(comfy_params)
            params_for_call["seed"] = call_seed
            params_for_call[image_param_key] = source_image_filename
            results.extend(await self._run_once_mesh_async(
                comfy_workflow=comfy_workflow,
                params=params_for_call,
                params_snapshot=dict(params_for_call),
                seed=call_seed,
                timeout_s=per_call_timeout,
                source_image_filename=source_image_filename,
            ))
        return results

    def generate_mesh(
        self,
        *,
        spec: dict[str, Any],
        source_image_filename: str,
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[MeshCandidate]:
        """Mesh capability sync shim — 委托 asyncio.run(self.agenerate_mesh(...))。
        保持 probe 脚本 / 旧调用路径兼容(TBD-010 Task 3)。
        """
        # capability 守门(与 agenerate_mesh 一致,允许在 sync 路径早期 raise)
        if self._capability != "mesh":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.generate_mesh: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local-mesh' 的 worker 可调 generate_mesh"
            )
        return asyncio.run(self.agenerate_mesh(
            spec=spec, source_image_filename=source_image_filename,
            num_candidates=num_candidates, seed=seed, timeout_s=timeout_s,
        ))

    async def _run_once_mesh_async(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        params_snapshot: dict[str, Any],
        seed: int,
        timeout_s: float,
        source_image_filename: str,
    ) -> list[MeshCandidate]:
        """mesh capability 的一次异步 subprocess 调用 → 1+ MeshCandidate。

        detach-wait 两段式协议(detach-wait change Task 3):
        委托 _run_comfy_prompt(submit run --detach → wait --prompt-id)。
        产物构造走 mesh path:
        - 从 outputs.glb 路径读 GLB bytes 到 MeshCandidate.data
        - 不做 worker 内部 in-tree copy(由 ArtifactRepository.put 自动落 in-tree)
        - GLB magic bytes 校验(b"glTF" prefix)
        - metadata 含 comfy_manifest / comfy_params_snapshot / comfy_capability / ...
        """
        outputs, returncode, prompt_id = await self._run_comfy_prompt(
            comfy_workflow=comfy_workflow,
            params=params,
            timeout_s=timeout_s,
            context="ComfyAgentWorker.agenerate_mesh",
        )
        # 三段表守门(mesh-mode:REQUIRED outputs.glb;auxiliary outputs.images 容忍 + INFO log;
        # rejected outputs.audio / video raise)。
        self._validate_outputs(outputs, comfy_workflow=comfy_workflow)

        glbs = outputs.get("glb") or []
        candidates: list[MeshCandidate] = []
        for src_str in glbs:
            src = Path(src_str)
            if not src.is_file():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.generate_mesh: outputs.glb path does not exist: {src}"
                )
            if src.is_symlink():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.generate_mesh: outputs.glb path is a symlink, "
                    f"refusing to follow: {src}"
                )
            # OpenSpec change `comfy-agent-cli-path-containment-hardening`
            # (2026-05-04 follow-on for G11-F2):assert path under
            # `comfy_output_root` before reading header bytes
            self._assert_path_within_comfy_output_root(src, output_kind="glb")
            glb_header = _read_prefix(src, 4)
            # GLB magic bytes 校验:`b"glTF"`(4-byte signature for binary glTF)
            if glb_header != b"glTF":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.generate_mesh: outputs.glb file {src.name!r} is "
                    f"not a valid GLB (first 4 bytes {glb_header!r}); "
                    f"mesh-generation path requires glTF binary magic bytes"
                )
            candidates.append(MeshCandidate(
                data=glb_header,
                format="glb",
                mime_type="model/gltf-binary",
                metadata={
                    "comfy_manifest": comfy_workflow,
                    "comfy_params_snapshot": params_snapshot,
                    "comfy_capability": "mesh",
                    "comfy_original_filename": src.name,
                    # v3.3(comfy-agent-api-v3-adaptation):值为 executor in-tree staging
                    # 绝对路径(<run_dir>/comfy/forgeue_<sha1>.png),CLI 侧 auto-upload 到
                    # ComfyUI input/;legacy 裸文件名模式(已在 input 目录)也原样记录。
                    "comfy_input_filename": source_image_filename,
                    "comfy_project_id": self.project_id,
                    "source": "comfy_agent_cli",
                    "seed": seed,
                    "comfy_prompt_id": prompt_id,
                },
                source_path=str(src),
            ))
        return candidates

    async def agenerate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
        """Audio capability async 主面(TBD-010 executor-async-rewrite Task 3)。

        - 仅在 _capability == "audio" 时可调(否则 raise)
        - audio capability 是 text-to-audio,无 source bytes 输入
        - 通过 _run_once_audio_async 使用 asyncio.create_subprocess_exec
        """
        # Capability 守门
        if self._capability != "audio":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local-audio' 的 worker 可调 agenerate_audio(audio-mode);"
                f"image-mode worker 应调 agenerate(),mesh-mode worker 应调 agenerate_mesh()"
            )
        # Reject legacy v1 spec shape
        if "workflow_graph" in spec:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_audio: spec.workflow_graph is deprecated; "
                "use spec.comfy_workflow + spec.comfy_params instead"
            )
        comfy_workflow = spec.get("comfy_workflow")
        if not isinstance(comfy_workflow, str) or not comfy_workflow:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_audio: spec.comfy_workflow REQUIRED, "
                "must be non-empty string (manifest name like "
                "'Audio_Workflows/audio_stable_audio_example')"
            )
        comfy_params = spec.get("comfy_params", {})
        if not isinstance(comfy_params, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: spec.comfy_params must be dict "
                f"(got {type(comfy_params).__name__})"
            )
        lifecycle = spec.get("comfy_lifecycle", "none")
        # Task 10 round 2 Important-1:旧 D6 "none"-only gate 替换为集合检查(四合法值)。
        if lifecycle not in self._VALID_LIFECYCLES:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: spec.comfy_lifecycle={lifecycle!r} 不合法; "
                f"合法值为 {sorted(self._VALID_LIFECYCLES)}。"
            )
        per_call_timeout = float(timeout_s) if timeout_s else 300.0

        results: list[AudioCandidate] = []
        for i in range(max(1, num_candidates)):
            call_seed = (seed or 0) + i
            params_for_call = dict(comfy_params)
            params_for_call["seed"] = call_seed
            results.extend(await self._run_once_audio_async(
                comfy_workflow=comfy_workflow,
                params=params_for_call,
                params_snapshot=dict(params_for_call),
                seed=call_seed,
                timeout_s=per_call_timeout,
            ))
        return results

    def generate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
        """Audio capability sync shim — 委托 asyncio.run(self.agenerate_audio(...))。
        保持 probe 脚本 / 旧调用路径兼容(TBD-010 Task 3)。
        """
        # Capability 守门
        if self._capability != "audio":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.generate_audio: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local-audio' 的 worker 可调 generate_audio(audio-mode);"
                f"image-mode worker 应调 generate(),mesh-mode worker 应调 generate_mesh()"
            )
        return asyncio.run(self.agenerate_audio(
            spec=spec, num_candidates=num_candidates, seed=seed, timeout_s=timeout_s,
        ))

    async def _run_once_audio_async(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        params_snapshot: dict[str, Any],
        seed: int,
        timeout_s: float,
    ) -> list[AudioCandidate]:
        """audio capability 的一次异步 subprocess 调用 → 1+ AudioCandidate。

        detach-wait 两段式协议(detach-wait change Task 3):
        委托 _run_comfy_prompt(submit run --detach → wait --prompt-id)。
        产物构造走 audio path:
        - 从 outputs.audio 路径读 audio bytes
        - 扩展名 whitelist + magic bytes 二次校验(F5 round-1)
        - 不做 worker 内部 in-tree copy(由 ArtifactRepository.put 自动落 in-tree)
        """
        outputs, returncode, prompt_id = await self._run_comfy_prompt(
            comfy_workflow=comfy_workflow,
            params=params,
            timeout_s=timeout_s,
            context="ComfyAgentWorker.agenerate_audio",
        )
        # 三段表守门(audio-mode:REQUIRED outputs.audio non-empty;无 auxiliary;
        # rejected outputs.images / glb / video raise)
        self._validate_outputs(outputs, comfy_workflow=comfy_workflow)

        audio_paths = outputs.get("audio") or []
        candidates: list[AudioCandidate] = []
        for src_str in audio_paths:
            src = Path(src_str)
            # F-Plan-4 round-2 path trust-boundary 防护
            if not src.is_file():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_audio: outputs.audio path does not exist: {src}"
                )
            if src.is_symlink():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_audio: outputs.audio path is a symlink, "
                    f"refusing to follow: {src}"
                )
            self._assert_path_within_comfy_output_root(src, output_kind="audio")
            # D10:扩展名 whitelist + magic bytes 二次校验(F5 round-1 mandatory)
            ext = src.suffix.lower().lstrip(".")
            if ext not in self._AUDIO_FORMAT_WHITELIST:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_audio: unsupported audio format {ext!r}, "
                    f"expected one of {sorted(self._AUDIO_FORMAT_WHITELIST)} "
                    f"(file: {src.name})"
                )
            audio_head = _read_prefix(src, 64 * 1024)
            # F5 round-1 mandatory magic bytes 二次校验
            magic_ok = (
                (ext == "flac" and audio_head[:4] == b"fLaC")
                or (ext == "mp3" and (
                    audio_head[:3] == b"ID3"
                    or audio_head[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2")
                ))
                or (ext == "wav" and audio_head[:4] == b"RIFF" and audio_head[8:12] == b"WAVE")
            )
            if not magic_ok:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_audio: audio format mismatch "
                    f"(file: {src.name}; extension={ext!r}; magic bytes={audio_head[:12].hex()}) — "
                    f"扩展名与 payload bytes 不一致;F5 round-1 二次校验拒绝"
                )
            from framework.providers.workers.audio_metadata import parse_audio_metadata
            duration_seconds, sample_rate = parse_audio_metadata(audio_head, ext)
            candidates.append(AudioCandidate(
                data=audio_head,
                format=ext,  # type: ignore[arg-type]
                metadata={
                    "comfy_manifest": comfy_workflow,
                    "comfy_params_snapshot": params_snapshot,
                    "comfy_capability": "audio",
                    "comfy_original_filename": src.name,
                    "comfy_prompt_id": prompt_id,
                    "comfy_subprocess_run_metadata": {
                        "exit_code": returncode,
                        "project_id": self.project_id,
                        "seed": seed,
                        "model_id": self.model_id,
                    },
                },
                duration_seconds=duration_seconds,
                sample_rate=sample_rate,
                source_path=str(src),
            ))
        return candidates

    # ------------------------------------------------------------------------
    # Video capability (Phase 3 — comfy-agent-cli-video-adoption)
    # ------------------------------------------------------------------------

    async def agenerate_video(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[VideoCandidate]:
        """Video capability async 主面(TBD-010 executor-async-rewrite Task 3)。

        - 仅在 _capability == "video" 时可调(否则 raise)
        - video capability 是 text-to-video,无 source bytes 输入
        - 通过 _run_once_video_async 使用 asyncio.create_subprocess_exec
        """
        # Capability 守门
        if self._capability != "video":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local-video' 的 worker 可调 agenerate_video(video-mode);"
                f"image-mode 应调 agenerate(),mesh-mode 应调 agenerate_mesh(),audio-mode 应调 agenerate_audio()"
            )
        # Reject legacy v1 spec shape
        if "workflow_graph" in spec:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_video: spec.workflow_graph is deprecated; "
                "use spec.comfy_workflow + spec.comfy_params instead"
            )
        comfy_workflow = spec.get("comfy_workflow")
        if not isinstance(comfy_workflow, str) or not comfy_workflow:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_video: spec.comfy_workflow REQUIRED, "
                "must be non-empty string (manifest name like "
                "'Vedio/Wan2.1-T2V-1.3B_native_5sec' — D5 上游 'Vedio/' 拼写照实跟随,不做翻译)"
            )
        comfy_params = spec.get("comfy_params", {})
        if not isinstance(comfy_params, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: spec.comfy_params must be dict "
                f"(got {type(comfy_params).__name__})"
            )
        lifecycle = spec.get("comfy_lifecycle", "none")
        # Task 10 round 2 Important-1:旧 D6 "none"-only gate 替换为集合检查(四合法值)。
        if lifecycle not in self._VALID_LIFECYCLES:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: spec.comfy_lifecycle={lifecycle!r} 不合法; "
                f"合法值为 {sorted(self._VALID_LIFECYCLES)}。"
            )
        # D3 默认 worker_timeout_s: 600(Wan T2V 1.3B 5sec ≈ 7 分钟 + 启动余量)
        per_call_timeout = float(timeout_s) if timeout_s else 600.0

        results: list[VideoCandidate] = []
        for i in range(max(1, num_candidates)):
            call_seed = (seed or 0) + i
            params_for_call = dict(comfy_params)
            params_for_call["seed"] = call_seed
            results.extend(await self._run_once_video_async(
                comfy_workflow=comfy_workflow,
                params=params_for_call,
                params_snapshot=dict(params_for_call),
                seed=call_seed,
                timeout_s=per_call_timeout,
            ))
        return results

    def generate_video(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[VideoCandidate]:
        """Video capability sync shim — 委托 asyncio.run(self.agenerate_video(...))。
        保持 probe 脚本 / 旧调用路径兼容(TBD-010 Task 3)。
        """
        # Capability 守门
        if self._capability != "video":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.generate_video: called on _capability={self._capability!r} "
                f"worker;只有 model_id='comfy/local-video' 的 worker 可调 generate_video(video-mode);"
                f"image-mode 应调 generate(),mesh-mode 应调 generate_mesh(),audio-mode 应调 generate_audio()"
            )
        return asyncio.run(self.agenerate_video(
            spec=spec, num_candidates=num_candidates, seed=seed, timeout_s=timeout_s,
        ))

    async def _run_once_video_async(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        params_snapshot: dict[str, Any],
        seed: int,
        timeout_s: float,
    ) -> list[VideoCandidate]:
        """video capability 的一次异步 subprocess 调用 → 1+ VideoCandidate。

        detach-wait 两段式协议(detach-wait change Task 3):
        委托 _run_comfy_prompt(submit run --detach → wait --prompt-id)。
        产物构造走 video path:
        - 从 outputs.video 路径读 video bytes
        - 扩展名 whitelist mp4-only + BMFF strict 5-tuple 校验
        - 不做 worker 内部 in-tree copy
        """
        outputs, returncode, prompt_id = await self._run_comfy_prompt(
            comfy_workflow=comfy_workflow,
            params=params,
            timeout_s=timeout_s,
            context="ComfyAgentWorker.agenerate_video",
        )
        # 三段表守门(video-mode:REQUIRED outputs.video non-empty;无 auxiliary;
        # rejected outputs.images / glb / audio raise)
        self._validate_outputs(outputs, comfy_workflow=comfy_workflow)

        video_paths = outputs.get("video") or []
        candidates: list[VideoCandidate] = []
        for src_str in video_paths:
            src = Path(src_str)
            # F-Plan-4 round-2 path trust-boundary 防护
            if not src.is_file():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: outputs.video path does not exist: {src}"
                )
            if src.is_symlink():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: outputs.video path is a symlink, "
                    f"refusing to follow: {src}"
                )
            self._assert_path_within_comfy_output_root(src, output_kind="video")
            # D8 + round-2 F2 + round-3 PF3 sweep:扩展名 whitelist mp4-only
            ext = src.suffix.lower().lstrip(".")
            if ext not in self._VIDEO_FORMAT_WHITELIST:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: unsupported video format {ext!r}, "
                    f"expected 'mp4' (webm follow-on `comfy-video-webm-adoption`; round-2 F2);"
                    f"file: {src.name}"
                )
            video_head = _read_prefix(src, 16)
            video_size = src.stat().st_size
            # round-2 F4 + round-3 PF2 BMFF strict 5-tuple 校验
            if len(video_head) < 16:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 too short: {len(video_head)} bytes "
                    f"(need >= 16 for minimal BMFF header; file: {src.name})"
                )
            if video_head[4:8] != b"ftyp":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 BMFF header mismatch: "
                    f"offset 4-8 = {video_head[4:8]!r}, expected b'ftyp' "
                    f"(file: {src.name})"
                )
            box_size = int.from_bytes(video_head[0:4], "big")
            if box_size == 1 or box_size < 8 or box_size > video_size:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 BMFF first box_size={box_size} "
                    f"out of range [8, {video_size}] "
                    f"(largesize box_size==1 deferred to follow-on `video-bmff-largesize-support`; "
                    f"round-3 PF2;file: {src.name})"
                )
            major_brand = video_head[8:12]
            if major_brand == b"\x00\x00\x00\x00" or major_brand == b"    ":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 BMFF major_brand is empty / "
                    f"all-zeros / all-spaces: {major_brand!r} (file: {src.name})"
                )
            # ffprobe 解析视频 metadata，失败时静默回退为 None
            duration_seconds, frame_count, width, height, fps = parse_video_metadata(src)
            candidates.append(VideoCandidate(
                data=video_head,
                format="mp4",
                metadata={
                    "comfy_manifest": comfy_workflow,
                    "comfy_params_snapshot": params_snapshot,
                    "comfy_capability": "video",
                    "comfy_original_filename": src.name,
                    "comfy_prompt_id": prompt_id,
                    "comfy_subprocess_run_metadata": {
                        "exit_code": returncode,
                        "project_id": self.project_id,
                        "seed": seed,
                        "model_id": self.model_id,
                    },
                },
                duration_seconds=duration_seconds,
                frame_count=frame_count,
                width=width,
                height=height,
                fps=fps,
                source_path=str(src),
            ))
        return candidates

    @classmethod
    async def aprobe(
        cls,
        scripts_dir: Path,
        python_exe: Path | None,
        timeout_s: float = 30.0,
    ) -> None:
        """async dry-run probe 主面(Step 6: DryRunPass.run async 化后改用此方法)。

        使用 asyncio.create_subprocess_exec 执行 `comfyui_api status`,
        与 _run_once_* 系列方法保持一致。probe 仅确认 status 可达,
        不投递 GPU job,无需包裹 _comfy_submit_lock()。

        校验顺序:scripts_dir 存在 → comfyui_api 子模块存在 →
        `python -m comfyui_api status` 在 timeout_s 内正常退出。
        任何失败均 raise WorkerUnsupportedResponse,含 hint to start ComfyUI
        + check FORGEUE_COMFY_SCRIPTS_DIR。
        """
        scripts_dir = Path(scripts_dir)
        py = Path(python_exe) if python_exe else Path(sys.executable)
        # 文件系统守门:scripts_dir 必须存在
        if not scripts_dir.exists():
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI scripts_dir not found at {scripts_dir!r}; "
                f"set FORGEUE_COMFY_SCRIPTS_DIR or verify path"
            )
        # 文件系统守门:comfyui_api 子模块必须存在
        if not (scripts_dir / "comfyui_api").is_dir():
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI module not found at "
                f"{scripts_dir / 'comfyui_api'!r}; install comfyui_api package "
                f"under scripts_dir"
            )
        # asyncio 子进程:与 _run_once_* 保持一致,不用 subprocess.run
        try:
            proc = await asyncio.create_subprocess_exec(
                str(py), "-m", "comfyui_api", "status",
                cwd=str(scripts_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.aprobe: failed to spawn subprocess "
                f"(python_exe={py!r}): {exc}"
            ) from exc
        try:
            # wait_for 包裹 communicate,确保 timeout_s 内完成
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_s + 5.0,  # 与 _run_once_* 同款 buffer
            )
        except asyncio.TimeoutError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI status probe timed out ({timeout_s}s); "
                f"start ComfyUI via `python -m comfyui_api serve` then retry"
            ) from exc
        finally:
            # probe 子进程 cleanup:沿 _run_once_* —— 未退出则 terminate → kill,
            # 避免 TimeoutError / CancelledError 时残留僵尸进程
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                except asyncio.TimeoutError:
                    proc.kill()
                await proc.wait()
        if proc.returncode != 0:
            stderr_str = (stderr_b or b"").decode("utf-8", errors="replace")
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI status returned exit {proc.returncode}; "
                f"start ComfyUI via `python -m comfyui_api serve` then retry "
                f"(stderr first 500 chars: {stderr_str[:500]!r})"
            )

    @classmethod
    def probe_sync(
        cls,
        scripts_dir: Path,
        python_exe: Path | None,
        timeout_s: float = 30.0,
    ) -> None:
        """sync shim —— 为 probe 脚本等的兼容性保留(Step 6)。
        内部委托给 asyncio.run(cls.aprobe(...))。

        注意:从已运行的 event loop 内(如 arun 中)调用会触发 RuntimeError,
        因此 DryRunPass._check_comfy_reachability 必须直接 await aprobe。
        probe_sync 仅保留给 event loop 外的 probe 脚本 / tests 使用。
        """
        asyncio.run(cls.aprobe(scripts_dir, python_exe, timeout_s))
