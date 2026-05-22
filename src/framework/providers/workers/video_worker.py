"""Video worker —— text-to-video 生成抽象(L4).

类比 `audio_worker.AudioWorker` 模式:外部 video 生成服务(ComfyUI / 未来 Runway /
Pika / Sora)不适合塞进 LiteLLM 的 chat-completion 协议(返回的是 video bytes 而非
token text),所以独立 Worker 抽象。

实现:
- `FakeVideoWorker` —— 测试用,合成 minimal valid BMFF mp4 bytes(magic `b"ftyp"`
  at offset 4 + 32-byte ftyp box,通过 round-2 F4 + round-3 PF2 BMFF strict
  5-tuple 校验,不依赖第三方 codec)
- 远端 video worker —— 留 follow-on change `video-worker-remote-adoption`
  (本 change scope=ABC + ComfyUI 第一客户;远端协议在 ABC 落地后 follow-on)

ComfyUI video 路径 `ComfyAgentWorker.generate_video` 不实现 ABC `generate_video`
方法(签名一致 — `(*, spec, num_candidates, seed, timeout_s)` keyword-only,但
ComfyAgentWorker 是 `ComfyWorker` ABC 子类,通过 capability dispatch 路由 —
设计 D7 沿 audio Phase 2 同模式)。

生成结果包成 `VideoCandidate`,`GenerateVideoExecutor` 再落成 file-backed
`video.mp4` Artifact(D1 + D8:`shape="mp4"` 与 UE bridge `manifest_builder._KIND_MAP[
("video", "mp4")] = "file_media_source"` 唯一映射对齐;实际编码格式始终 mp4 —
round-2 F2 + round-3 PF3 sweep mp4-only,webm follow-on `comfy-video-webm-adoption`)。

UE 导入侧 `ue_scripts/domain_video.import_video_entry` 沿 D12 `Content/Movies/<run_id>/`
路径分流 + `unreal.FileMediaSourceFactory` 创建 `.uasset`(P4 真机 commandlet 验证待
`tasks.md` §11b)。

Round-3 PF1 prep dependency:`D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs`
已 user-authored 扩展加 `video` 收集 block(VHS_VideoCombine 节点 legacy `gifs` UI key
→ `outputs.video` list);commit 4 `ComfyAgentWorker.generate_video` 实施时直接走
`outputs.video` 沿 image / audio / glb 同款 4-dict 协议。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


# ----------------------------------------------------------------------------
# 异常树(类比 audio_worker AudioWorker* 三层)
# ----------------------------------------------------------------------------


class VideoWorkerError(RuntimeError):
    """Generic video worker failure.

    Optional kwargs `job_id` / `worker` / `model` carry remote-side identifiers
    when known at raise site (per Phase 1 mesh TBD-007 模式)。本 change scope
    远端 video worker 不实装,这些字段为远端 follow-on change 预留。
    """

    def __init__(
        self,
        msg: str,
        *,
        job_id: str | None = None,
        worker: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(msg)
        self.job_id = job_id
        self.worker = worker
        self.model = model


class VideoWorkerTimeout(VideoWorkerError):
    """Video worker exceeded wall-clock budget(subprocess 超时 / 网络超时)。"""


class VideoWorkerUnsupportedResponse(VideoWorkerError):
    """Provider returned a response shape this worker can't consume(e.g.
    outputs.video missing / unsupported file format / BMFF strict header
    mismatch / path trust-boundary 违反)。Distinct from generic
    `VideoWorkerError` so `RetryPolicy` can skip pointless retries — the
    response is deterministic;retrying the same submit burns more GPU time
    for the same unusable output。
    """


# ----------------------------------------------------------------------------
# VideoCandidate dataclass
# ----------------------------------------------------------------------------


# D1 + D8:`shape="mp4"` 与 UE bridge `manifest_builder._KIND_MAP[("video", "mp4")] =
# "file_media_source"` 唯一映射对齐;`format=cand.format`(round-2 F2 + round-3 PF3
# sweep mp4-only)硬编码 `"mp4"`(per round-3 PF4 修订 audio Phase 2 同款模式 — Python
# `@dataclass` 不在 runtime enforce Literal,实际 mp4-only 守门在 worker 层
# `_run_once_video` 扩展名检查 + BMFF strict header validation)。


@dataclass
class VideoCandidate:
    """One video result from a VideoWorker call.

    D8 + round-2 F2 + round-3 PF3 sweep 修订(persistence contract):
    - `data` + `format` 是 file-backed payload 的真实 bytes 与编码格式
    - `format: Literal["mp4"]` mp4-only(webm follow-on `comfy-video-webm-adoption`)
    - `metadata` 仅承载 provenance(5 个 comfy_* keys per D8 single-source 决策);
      **不**重复 `duration_seconds` / `frame_count` / `width` / `height` / `fps` /
      `format` 字段(避免双源冲突)
    - `duration_seconds` / `frame_count` / `width` / `height` / `fps` 顶层字段,
      在本 change scope 始终 `None`(ComfyUI agent CLI `extract_outputs` 不暴露
      video metadata;follow-on `video-metadata-parser` change 加 ffprobe / mutagen
      解析)
    - GenerateVideoExecutor 持久化时:`Artifact(modality="video", shape="mp4")`
      + `Artifact.metadata.format=cand.format`(实际格式信息 — UE
      `unreal.FileMediaSourceFactory` import 时按文件扩展名 dispatch)

    Round-3 PF4 修订:Python `@dataclass` 不在 runtime 强制 `Literal` 类型,实际
    mp4-only enforcement 在 worker 层(沿 audio Phase 2 `tests/unit/test_audio_worker.py
    ::test_audio_candidate_format_whitelist` 同款行为)。
    """

    data: bytes
    format: Literal["mp4"]
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None  # 本 change scope 始终 None
    frame_count: int | None = None  # 本 change scope 始终 None
    width: int | None = None  # 本 change scope 始终 None
    height: int | None = None  # 本 change scope 始终 None
    fps: float | None = None  # 本 change scope 始终 None
    source_path: str | None = None  # FOR-13:大视频由 ArtifactRepository 从文件路径流式落盘


# ----------------------------------------------------------------------------
# VideoWorker ABC
# ----------------------------------------------------------------------------


class VideoWorker(ABC):
    """Adapter surface used by `GenerateVideoExecutor`.

    `generate_video` 签名 keyword-only;**no `prompt: str` 参数** — prompt 在
    `spec["comfy_params"]` 内(per design D7;executor SHALL NOT 解构 / 注入
    prompt key)。未来远端 video worker(Runway / Pika / Sora)同 ABC,实现自己
    的 spec 解析约定(可能直接读 `spec["prompt"]` 或 `spec["runway_*"]`)— 这是
    ABC 通用契约的最大公约数。
    """

    name: str = "video"

    @abstractmethod
    def generate_video(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[VideoCandidate]:
        """Produce *num_candidates* video candidates from *spec*.

        per-candidate loop 在 worker 内部实现(沿 image / mesh / audio worker
        `for i in range(max(1, num_candidates))` 同款模式;executor 调一次即可,
        **不**需要外层 loop)。

        Retry policy 由 caller (executor) 处理 — ABC 不实现 retry loop。
        """

    async def agenerate_video(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[VideoCandidate]:
        """Task 5 async 接口:默认实现用 asyncio.to_thread 包 sync generate_video。
        未来远端 video worker(Runway / Pika / Sora 等)应覆盖此方法实现真正 async I/O;
        本 change scope FakeVideoWorker 继承此默认。"""
        import asyncio
        return await asyncio.to_thread(
            self.generate_video,
            spec=spec,
            num_candidates=num_candidates,
            seed=seed,
            timeout_s=timeout_s,
        )


# ----------------------------------------------------------------------------
# FakeVideoWorker —— deterministic, offline (test fixture)
# ----------------------------------------------------------------------------


def _build_minimal_mp4(payload: bytes = b"forgeue") -> bytes:
    """Synthesise a minimal valid BMFF mp4 stream(32 bytes,通过 round-2 F4 +
    round-3 PF2 BMFF strict 5-tuple 校验)。

    BMFF spec(ISO/IEC 14496-12)minimum ftyp box:
    - box header:[size:4 BE][type:4 ASCII]
    - ftyp box body:[major_brand:4][minor_version:4 BE][compatible_brands:variable]

    Layout(32 bytes total,fits BMFF strict 5-tuple:`len >= 16` + `data[4:8] == b"ftyp"`
    + `box_size in [8, len(data)]` + `box_size != 1` + `major_brand non-empty / non-zero
    / non-spaces`):

    ```
    offset 0-3   : box_size = 32 (0x00000020)
    offset 4-7   : type = "ftyp"
    offset 8-11  : major_brand = "isom"  (ISO Base Media File Format)
    offset 12-15 : minor_version = 0x00000200 (= 512,常见 Wan T2V VHS_VideoCombine 输出值)
    offset 16-31 : compatible_brands = "isom" + "iso2" + "mp41" + "mp42"  (16 bytes)
    ```

    用于 unit test 的 deterministic minimal valid mp4 bytes。**不**依赖第三方 codec。
    *payload* 参数当前不影响 32-byte fixed ftyp;为 API 与 audio 保持一致预留。
    """
    out = bytearray()
    # box_size = 32 (4 bytes BE)
    out.extend(b"\x00\x00\x00\x20")
    # type = "ftyp"
    out.extend(b"ftyp")
    # major_brand = "isom"
    out.extend(b"isom")
    # minor_version = 0x00000200 (512)
    out.extend(b"\x00\x00\x02\x00")
    # compatible_brands(4 brands × 4 bytes = 16 bytes)
    out.extend(b"isom")
    out.extend(b"iso2")
    out.extend(b"mp41")
    out.extend(b"mp42")
    return bytes(out)


@dataclass
class _VideoScript:
    """FakeVideoWorker 测试脚本:可注入预设 candidates / 预设 raise。"""

    candidates: list[VideoCandidate] | None = None
    raise_error: BaseException | None = None


class FakeVideoWorker(VideoWorker):
    """Deterministic fake worker. Synthesises minimal BMFF mp4 when unprogrammed."""

    name: str = "fake_video"

    def __init__(self) -> None:
        self._script: _VideoScript = _VideoScript()
        self.calls: list[dict[str, Any]] = []

    def program(
        self,
        *,
        candidates: list[VideoCandidate] | None = None,
        raise_error: BaseException | None = None,
    ) -> None:
        """Prime next call to return *candidates* or raise *raise_error*。"""
        self._script = _VideoScript(candidates=candidates, raise_error=raise_error)

    def generate_video(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[VideoCandidate]:
        # Record call for assertion
        self.calls.append({
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
        })

        if self._script.raise_error is not None:
            raise self._script.raise_error

        if self._script.candidates is not None:
            return list(self._script.candidates)

        # Default:produce *num_candidates* minimal BMFF mp4 clones
        n = max(1, num_candidates)
        results: list[VideoCandidate] = []
        for i in range(n):
            data = _build_minimal_mp4(payload=f"fake-{i}".encode("utf-8"))
            results.append(VideoCandidate(
                data=data,
                format="mp4",
                metadata={"is_fake": True, "fake_index": i},
                # 5 个 metadata 字段 None defaults — ComfyUI agent CLI 不暴露,本 change scope 始终 None
            ))
        return results
