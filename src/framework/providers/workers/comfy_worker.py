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

四个暴露的类:
- ComfyWorker     : ABC adapter surface(GenerateImageExecutor 使用)
- FakeComfyWorker : 确定性 scripted/synth adapter(离线测试)
- ComfyAgentWorker: 真实 adapter,通过 asyncio.create_subprocess_exec 启动子进程

生产流程:
  GenerateImageExecutor._should_use_worker_path 检测 model=='comfy/local'
  → 构建 ComfyAgentWorker(scripts_dir=env, run_id, project_id, artifacts_dir=ctx.run_dir)
  → 调用 worker.agenerate(spec={comfy_workflow, comfy_params, comfy_lifecycle},
    num_candidates, seed, timeout_s)
  → asyncio.create_subprocess_exec(sys.executable, "-m", "comfyui_api", "run",
    "--workflow", X, "--params", json.dumps(P), "--project", project_id,
    "--lifecycle", "none", "--timeout", str(timeout_s), cwd=scripts_dir)
  → 解析 stdout JSON,复制 outputs.images 到 artifacts_dir/comfy/,
    构建 list[ImageCandidate]

并发安全:comfy-submission 串行锁(_comfy_submit_lock())确保同一 event loop 内
同时只有 1 个 comfy subprocess 在运行。per-loop WeakKeyDictionary 防止跨 loop
RuntimeError(asyncio.Lock 绑定到首次 waiter 的 loop,模块级单一 Lock 跨 loop 会炸)。

Cancel 语义:async 主面下 CancelledError 可以在 await 点到达 _run_once_async*,
finally 块执行 proc.terminate() + proc.kill() 清理。后续 Task 4 会加 /interrupt
server-side abort。
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

# Mesh capability(OpenSpec change comfy-agent-cli-mesh-audio-video-adoption Phase 1):
# generate_mesh 返回 MeshCandidate(从 mesh_worker module 复用 dataclass,
# 不扩字段 — provenance 走 metadata dict per design D5)。
from framework.providers.workers.audio_worker import AudioCandidate
from framework.providers.workers.mesh_worker import MeshCandidate
from framework.providers.workers.video_worker import VideoCandidate

# 模块级 logger(R2-F4 fix:auxiliary outputs.images SHALL emit INFO via 此 logger,
# fence 用 caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker") 抓)
_COMFY_LOGGER = logging.getLogger("framework.providers.workers.comfy_worker")


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
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """异步主面(TBD-010 Task 3):FakeComfyWorker 的 async 版本直接委托给 generate 逻辑。
        Fake worker 不真正启动子进程,无需 asyncio.create_subprocess_exec。"""
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
        if "comfy_workflow" in spec:
            if not isinstance(spec["comfy_workflow"], str) or not spec["comfy_workflow"]:
                raise WorkerUnsupportedResponse(
                    "FakeComfyWorker.generate: spec.comfy_workflow must be a "
                    "non-empty string"
                )
            if "comfy_params" in spec and not isinstance(spec["comfy_params"], dict):
                raise WorkerUnsupportedResponse(
                    "FakeComfyWorker.generate: spec.comfy_params must be a dict"
                )
            lifecycle = spec.get("comfy_lifecycle", "none")
            # Task 10:FakeComfyWorker 同步解锁 — 接受四个合法值,集合外才 raise。
            _FAKE_VALID_LIFECYCLES = {
                "none", "ensure_running", "ensure_release", "self_managed_session",
            }
            if lifecycle not in _FAKE_VALID_LIFECYCLES:
                raise WorkerUnsupportedResponse(
                    f"FakeComfyWorker.generate: spec.comfy_lifecycle={lifecycle!r} 不合法; "
                    f"合法值为 {sorted(_FAKE_VALID_LIFECYCLES)}。"
                )
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


# ----------------------------------------------------------------------------
# Real worker — invoke `python -m comfyui_api` as subprocess.
# ----------------------------------------------------------------------------


# Failure-mode discriminators (round 2 spec D5 + round 3 P2 sync probe).
_UNSUPPORTED_ERROR_MARKERS = (
    "Missing required param",
    "value out of range",
    "value_not_in_list",
)


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
        _VALID_LIFECYCLES = {"none", "ensure_running", "ensure_release", "self_managed_session"}
        if default_lifecycle not in _VALID_LIFECYCLES:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.__init__: 不支持的 default_lifecycle={default_lifecycle!r}; "
                f"合法值为 {sorted(_VALID_LIFECYCLES)}。"
            )
        # D1: capability dispatch via model_id 推断;unknown id raise(不静默 fallback)。
        # F-Plan-R3-A round-3 修订:audio capability 已加(comfy/local-audio);
        # Phase 3 D6 修订:video capability 已加(comfy/local-video) — TBD-009 全 3 phase closed。
        capability = self._CAPABILITY_BY_MODEL_ID.get(model_id)
        if capability is None:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.__init__: unsupported model_id={model_id!r}, "
                f"expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)} "
                f"(all TBD-009 phases closed: image / mesh / audio / video)"
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
        if env_output_root:
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
        if lifecycle != "none":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate: spec.comfy_lifecycle must be "
                f"'none' in this change scope (got {lifecycle!r}); "
                f"see SRS TBD-010 for executor-async-rewrite"
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

        submit→poll 段整体在 async with _comfy_submit_lock(): 内,
        确保同一 loop 内同时只有 1 个 comfy subprocess 运行。
        超时时 raise WorkerTimeout;cleanup 走 terminate → kill。
        后续 Task 4 会在 finally 前加 _abort_comfy_prompt(server-side /interrupt)。
        """
        cmd = [
            str(self.python_exe), "-m", "comfyui_api", "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
        ]
        async with _comfy_submit_lock():
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.scripts_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Task 4 测试钩子:保存当前 proc 供 cancel 后检查 returncode
                self._last_proc = proc
            except FileNotFoundError as exc:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: failed to spawn subprocess "
                    f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                    f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
                ) from exc
            try:
                raw_out, raw_err = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_s + _SUBPROC_BUFFER_S,
                )
            except asyncio.TimeoutError as exc:
                raise WorkerTimeout(
                    f"ComfyAgentWorker subprocess wall-clock exceeded "
                    f"{timeout_s + _SUBPROC_BUFFER_S}s (CLI internal timeout was {timeout_s}s)"
                ) from exc
            finally:
                # Task 4:先 POST /interrupt 停服务端 GPU job,再 terminate CLI 子进程
                if proc.returncode is None:
                    await self._abort_comfy_prompt()
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                    except asyncio.TimeoutError:
                        proc.kill()
                    await proc.wait()

        # stdout/stderr 转 UTF-8 文本(沿 G11 R1 fix:errors="replace")
        stdout_text = raw_out.decode("utf-8", errors="replace").strip() if raw_out else ""
        stderr_text = raw_err.decode("utf-8", errors="replace").strip() if raw_err else ""

        # 把 returncode 绑定到变量,便于像 CompletedProcess 一样复用
        returncode = proc.returncode

        # Parse stdout JSON; map failures per spec D5 table.
        stdout = stdout_text
        if not stdout:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: empty stdout (exit code {returncode}; "
                f"stderr first 500 chars: {stderr_text[:500]!r})"
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout is not valid JSON "
                f"(exit code {returncode}; first 500 chars: {stdout[:500]!r})"
            ) from exc

        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout JSON is not a dict (got {type(data).__name__})"
            )
        if not data.get("ok"):
            error_msg = str(data.get("error", ""))
            if "TimeoutError" in error_msg:
                raise WorkerTimeout(
                    f"ComfyAgentWorker: ComfyUI reported TimeoutError: {error_msg}"
                )
            for marker in _UNSUPPORTED_ERROR_MARKERS:
                if marker in error_msg:
                    raise WorkerUnsupportedResponse(
                        f"ComfyAgentWorker: deterministic param error: {error_msg}"
                    )
            raise WorkerError(
                f"ComfyAgentWorker: comfyui_api returned ok=false "
                f"(exit {returncode}, error: {error_msg})"
            )

        if "outputs" not in data or not isinstance(data["outputs"], dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout JSON missing 'outputs' field or "
                f"not a dict (got {data.get('outputs')!r})"
            )
        outputs = data["outputs"]
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
            # `comfy_output_root` before read_bytes — defense-in-depth
            self._assert_path_within_comfy_output_root(src, output_kind="images")
            dst = comfy_subdir / src.name
            shutil.copy2(src, dst)
            data = dst.read_bytes()
            # G11 R2 fix: validate PNG magic bytes (8-byte signature
            # 89 50 4E 47 0D 0A 1A 0A). image-generation path must reject
            # non-PNG bytes — a workflow producing JPG/WEBP/etc. should be
            # treated as deterministic mismatch (caller declared image
            # capability with implicit PNG expectation per ImageCandidate
            # mime_type default). Future change can broaden the magic
            # allowlist to JPEG/WEBP if needed.
            if data[:8] != b"\x89PNG\r\n\x1a\n":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images file {src.name!r} is "
                    f"not a valid PNG (first 8 bytes {data[:8]!r}); "
                    f"image-generation path requires PNG magic bytes"
                )
            candidates.append(ImageCandidate(
                data=data,
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
                },
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

    async def _abort_comfy_prompt(self) -> None:
        """cancel 路径 best-effort:POST /interrupt 停服务端正在跑的 prompt。

        comfyui_api cancel(无 --prompt-id)即 POST http://127.0.0.1:8188/interrupt。
        在 Task 3 的 comfy-submission 锁内调用 → 中断的必是本 worker 的 prompt。
        失败只 warning,不抛(主路径已在 cancel 流程中,abort 仅 best-effort)。
        等待超时 _ABORT_TIMEOUT_S 秒后放弃,不阻塞后续 terminate。
        """
        ap = None
        try:
            ap = await asyncio.create_subprocess_exec(
                str(self.python_exe), "-m", "comfyui_api", "cancel",
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
        if lifecycle != "none":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: spec.comfy_lifecycle must be "
                f"'none' in this change scope (got {lifecycle!r}); see SRS TBD-010"
            )
        image_param_key = spec.get("comfy_image_param_key") or "input_image"
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

        submit→poll 段整体在 async with _comfy_submit_lock(): 内,
        确保同一 loop 内同时只有 1 个 comfy subprocess 运行。
        产物构造走 mesh path:
        - 从 outputs.glb 路径读 GLB bytes 到 MeshCandidate.data
        - 不做 worker 内部 in-tree copy(由 ArtifactRepository.put 自动落 in-tree)
        - GLB magic bytes 校验(b"glTF" prefix)
        - metadata 含 comfy_manifest / comfy_params_snapshot / comfy_capability / ...
        """
        cmd = [
            str(self.python_exe), "-m", "comfyui_api", "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
        ]
        async with _comfy_submit_lock():
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.scripts_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Task 4 测试钩子:保存当前 proc 供 cancel 后检查 returncode
                self._last_proc = proc
            except FileNotFoundError as exc:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_mesh: failed to spawn subprocess "
                    f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                    f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
                ) from exc
            try:
                raw_out, raw_err = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_s + _SUBPROC_BUFFER_S,
                )
            except asyncio.TimeoutError as exc:
                raise WorkerTimeout(
                    f"ComfyAgentWorker.agenerate_mesh subprocess wall-clock exceeded "
                    f"{timeout_s + _SUBPROC_BUFFER_S}s (CLI internal timeout was {timeout_s}s)"
                ) from exc
            finally:
                # Task 4:先 POST /interrupt 停服务端 GPU job,再 terminate CLI 子进程
                if proc.returncode is None:
                    await self._abort_comfy_prompt()
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                    except asyncio.TimeoutError:
                        proc.kill()
                    await proc.wait()

        stdout_text = raw_out.decode("utf-8", errors="replace").strip() if raw_out else ""
        stderr_text = raw_err.decode("utf-8", errors="replace").strip() if raw_err else ""
        returncode = proc.returncode

        stdout = stdout_text
        if not stdout:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: empty stdout (exit code {returncode}; "
                f"stderr first 500 chars: {stderr_text[:500]!r})"
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: stdout is not valid JSON "
                f"(exit code {returncode}; first 500 chars: {stdout[:500]!r})"
            ) from exc
        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: stdout JSON is not a dict (got {type(data).__name__})"
            )
        if not data.get("ok"):
            error_msg = str(data.get("error", ""))
            if "TimeoutError" in error_msg:
                raise WorkerTimeout(
                    f"ComfyAgentWorker.agenerate_mesh: ComfyUI reported TimeoutError: {error_msg}"
                )
            for marker in _UNSUPPORTED_ERROR_MARKERS:
                if marker in error_msg:
                    raise WorkerUnsupportedResponse(
                        f"ComfyAgentWorker.agenerate_mesh: deterministic param error: {error_msg}"
                    )
            raise WorkerError(
                f"ComfyAgentWorker.agenerate_mesh: comfyui_api returned ok=false "
                f"(exit {returncode}, error: {error_msg})"
            )
        if "outputs" not in data or not isinstance(data["outputs"], dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_mesh: stdout JSON missing 'outputs' field or "
                f"not a dict (got {data.get('outputs')!r})"
            )
        outputs = data["outputs"]
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
            # `comfy_output_root` before read_bytes
            self._assert_path_within_comfy_output_root(src, output_kind="glb")
            glb_bytes = src.read_bytes()
            # GLB magic bytes 校验:`b"glTF"`(4-byte signature for binary glTF)
            if glb_bytes[:4] != b"glTF":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.generate_mesh: outputs.glb file {src.name!r} is "
                    f"not a valid GLB (first 4 bytes {glb_bytes[:4]!r}); "
                    f"mesh-generation path requires glTF binary magic bytes"
                )
            candidates.append(MeshCandidate(
                data=glb_bytes,
                format="glb",
                mime_type="model/gltf-binary",
                metadata={
                    "comfy_manifest": comfy_workflow,
                    "comfy_params_snapshot": params_snapshot,
                    "comfy_capability": "mesh",
                    "comfy_original_filename": src.name,
                    # round 5 D10:input 文件在 ComfyUI 自家 input/ 目录(by FORGEUE_COMFY_INPUT_DIR);
                    # 本 worker 不知道 dir 绝对路径(由 executor 传 filename only),所以 metadata 里
                    # 只记 filename;executor 会另外补 comfy_input_dir(round 5 D10 修订)。
                    "comfy_input_filename": source_image_filename,
                    "comfy_project_id": self.project_id,
                    "source": "comfy_agent_cli",
                    "seed": seed,
                },
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
        if lifecycle != "none":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: spec.comfy_lifecycle must be "
                f"'none' in this change scope (got {lifecycle!r}); see SRS TBD-010"
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

        submit→poll 段整体在 async with _comfy_submit_lock(): 内,
        确保同一 loop 内同时只有 1 个 comfy subprocess 运行。
        产物构造走 audio path:
        - 从 outputs.audio 路径读 audio bytes
        - 扩展名 whitelist + magic bytes 二次校验(F5 round-1)
        - 不做 worker 内部 in-tree copy(由 ArtifactRepository.put 自动落 in-tree)
        """
        cmd = [
            str(self.python_exe), "-m", "comfyui_api", "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
        ]
        async with _comfy_submit_lock():
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.scripts_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Task 4 测试钩子:保存当前 proc 供 cancel 后检查 returncode
                self._last_proc = proc
            except FileNotFoundError as exc:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_audio: failed to spawn subprocess "
                    f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                    f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
                ) from exc
            try:
                raw_out, raw_err = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_s + _SUBPROC_BUFFER_S,
                )
            except asyncio.TimeoutError as exc:
                raise WorkerTimeout(
                    f"ComfyAgentWorker.agenerate_audio subprocess wall-clock exceeded "
                    f"{timeout_s + _SUBPROC_BUFFER_S}s (CLI internal timeout was {timeout_s}s)"
                ) from exc
            finally:
                # Task 4:先 POST /interrupt 停服务端 GPU job,再 terminate CLI 子进程
                if proc.returncode is None:
                    await self._abort_comfy_prompt()
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                    except asyncio.TimeoutError:
                        proc.kill()
                    await proc.wait()

        stdout_text = raw_out.decode("utf-8", errors="replace").strip() if raw_out else ""
        stderr_text = raw_err.decode("utf-8", errors="replace").strip() if raw_err else ""
        returncode = proc.returncode

        stdout = stdout_text
        if not stdout:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: empty stdout (exit code {returncode}; "
                f"stderr first 500 chars: {stderr_text[:500]!r})"
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: stdout is not valid JSON "
                f"(exit code {returncode}; first 500 chars: {stdout[:500]!r})"
            ) from exc
        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: stdout JSON is not a dict (got {type(data).__name__})"
            )
        if not data.get("ok"):
            error_msg = str(data.get("error", ""))
            if "TimeoutError" in error_msg:
                raise WorkerTimeout(
                    f"ComfyAgentWorker.agenerate_audio: ComfyUI reported TimeoutError: {error_msg}"
                )
            for marker in _UNSUPPORTED_ERROR_MARKERS:
                if marker in error_msg:
                    raise WorkerUnsupportedResponse(
                        f"ComfyAgentWorker.agenerate_audio: deterministic param error: {error_msg}"
                    )
            raise WorkerError(
                f"ComfyAgentWorker.agenerate_audio: comfyui_api returned ok=false "
                f"(exit {returncode}, error: {error_msg})"
            )
        if "outputs" not in data or not isinstance(data["outputs"], dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_audio: stdout JSON missing 'outputs' field or "
                f"not a dict (got {data.get('outputs')!r})"
            )
        outputs = data["outputs"]
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
            audio_bytes = src.read_bytes()
            # F5 round-1 mandatory magic bytes 二次校验
            magic_ok = (
                (ext == "flac" and audio_bytes[:4] == b"fLaC")
                or (ext == "mp3" and (
                    audio_bytes[:3] == b"ID3"
                    or audio_bytes[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2")
                ))
                or (ext == "wav" and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE")
            )
            if not magic_ok:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_audio: audio format mismatch "
                    f"(file: {src.name}; extension={ext!r}; magic bytes={audio_bytes[:12].hex()}) — "
                    f"扩展名与 payload bytes 不一致;F5 round-1 二次校验拒绝"
                )
            from framework.providers.workers.audio_metadata import parse_audio_metadata
            duration_seconds, sample_rate = parse_audio_metadata(audio_bytes, ext)
            candidates.append(AudioCandidate(
                data=audio_bytes,
                format=ext,  # type: ignore[arg-type]
                metadata={
                    "comfy_manifest": comfy_workflow,
                    "comfy_params_snapshot": params_snapshot,
                    "comfy_capability": "audio",
                    "comfy_original_filename": src.name,
                    "comfy_subprocess_run_metadata": {
                        "exit_code": returncode,
                        "project_id": self.project_id,
                        "seed": seed,
                        "model_id": self.model_id,
                    },
                },
                duration_seconds=duration_seconds,
                sample_rate=sample_rate,
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
        if lifecycle != "none":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: spec.comfy_lifecycle must be "
                f"'none' in this change scope (got {lifecycle!r}); see SRS TBD-010"
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

        submit→poll 段整体在 async with _comfy_submit_lock(): 内,
        确保同一 loop 内同时只有 1 个 comfy subprocess 运行。
        产物构造走 video path:
        - 从 outputs.video 路径读 video bytes
        - 扩展名 whitelist mp4-only + BMFF strict 5-tuple 校验
        - 不做 worker 内部 in-tree copy
        """
        cmd = [
            str(self.python_exe), "-m", "comfyui_api", "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
        ]
        async with _comfy_submit_lock():
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.scripts_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Task 4 测试钩子:保存当前 proc 供 cancel 后检查 returncode
                self._last_proc = proc
            except FileNotFoundError as exc:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: failed to spawn subprocess "
                    f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                    f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
                ) from exc
            try:
                raw_out, raw_err = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_s + _SUBPROC_BUFFER_S,
                )
            except asyncio.TimeoutError as exc:
                raise WorkerTimeout(
                    f"ComfyAgentWorker.agenerate_video subprocess wall-clock exceeded "
                    f"{timeout_s + _SUBPROC_BUFFER_S}s (CLI internal timeout was {timeout_s}s)"
                ) from exc
            finally:
                # Task 4:先 POST /interrupt 停服务端 GPU job,再 terminate CLI 子进程
                if proc.returncode is None:
                    await self._abort_comfy_prompt()
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
                    except asyncio.TimeoutError:
                        proc.kill()
                    await proc.wait()

        stdout_text = raw_out.decode("utf-8", errors="replace").strip() if raw_out else ""
        stderr_text = raw_err.decode("utf-8", errors="replace").strip() if raw_err else ""
        returncode = proc.returncode

        stdout = stdout_text
        if not stdout:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: empty stdout (exit code {returncode}; "
                f"stderr first 500 chars: {stderr_text[:500]!r})"
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: stdout is not valid JSON "
                f"(exit code {returncode}; first 500 chars: {stdout[:500]!r})"
            ) from exc
        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: stdout JSON is not a dict (got {type(data).__name__})"
            )
        if not data.get("ok"):
            error_msg = str(data.get("error", ""))
            if "TimeoutError" in error_msg:
                raise WorkerTimeout(
                    f"ComfyAgentWorker.agenerate_video: ComfyUI reported TimeoutError: {error_msg}"
                )
            for marker in _UNSUPPORTED_ERROR_MARKERS:
                if marker in error_msg:
                    raise WorkerUnsupportedResponse(
                        f"ComfyAgentWorker.agenerate_video: deterministic param error: {error_msg}"
                    )
            raise WorkerError(
                f"ComfyAgentWorker.agenerate_video: comfyui_api returned ok=false "
                f"(exit {returncode}, error: {error_msg})"
            )
        if "outputs" not in data or not isinstance(data["outputs"], dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.agenerate_video: stdout JSON missing 'outputs' field or "
                f"not a dict (got {data.get('outputs')!r})"
            )
        outputs = data["outputs"]
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
            video_bytes = src.read_bytes()
            # round-2 F4 + round-3 PF2 BMFF strict 5-tuple 校验
            if len(video_bytes) < 16:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 too short: {len(video_bytes)} bytes "
                    f"(need >= 16 for minimal BMFF header; file: {src.name})"
                )
            if video_bytes[4:8] != b"ftyp":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 BMFF header mismatch: "
                    f"offset 4-8 = {video_bytes[4:8]!r}, expected b'ftyp' "
                    f"(file: {src.name})"
                )
            box_size = int.from_bytes(video_bytes[0:4], "big")
            if box_size == 1 or box_size < 8 or box_size > len(video_bytes):
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 BMFF first box_size={box_size} "
                    f"out of range [8, {len(video_bytes)}] "
                    f"(largesize box_size==1 deferred to follow-on `video-bmff-largesize-support`; "
                    f"round-3 PF2;file: {src.name})"
                )
            major_brand = video_bytes[8:12]
            if major_brand == b"\x00\x00\x00\x00" or major_brand == b"    ":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.agenerate_video: mp4 BMFF major_brand is empty / "
                    f"all-zeros / all-spaces: {major_brand!r} (file: {src.name})"
                )
            # D8 + D1:VideoCandidate format 硬编码 "mp4";5 个 video metadata 字段恒为 None
            candidates.append(VideoCandidate(
                data=video_bytes,
                format="mp4",
                metadata={
                    "comfy_manifest": comfy_workflow,
                    "comfy_params_snapshot": params_snapshot,
                    "comfy_capability": "video",
                    "comfy_original_filename": src.name,
                    "comfy_subprocess_run_metadata": {
                        "exit_code": returncode,
                        "project_id": self.project_id,
                        "seed": seed,
                        "model_id": self.model_id,
                    },
                },
                duration_seconds=None,
                frame_count=None,
                width=None,
                height=None,
                fps=None,
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
                f"start ComfyUI via `python -m factory_v3 serve` then retry (note: `comfyui_api` CLI does NOT have a `serve` subcommand; use sister CLI `factory_v3 serve` from same scripts/ dir)"
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
                f"start ComfyUI via `python -m factory_v3 serve` then retry (note: `comfyui_api` CLI does NOT have a `serve` subcommand; use sister CLI `factory_v3 serve` from same scripts/ dir) "
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
