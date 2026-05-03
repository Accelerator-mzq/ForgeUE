"""Audio worker —— text-to-audio 生成抽象(L4).

类比 `mesh_worker.MeshWorker` 模式:外部 audio 生成服务(ComfyUI / 未来 AudioCraft)
不适合塞进 LiteLLM 的 chat-completion 协议(返回的是 audio bytes 而非 token text),
所以独立 Worker 抽象。

实现:
- `FakeAudioWorker` —— 测试用,合成 minimal valid FLAC bytes(magic `fLaC` +
  STREAMINFO + 单 frame,~100 bytes,不依赖第三方 codec)
- 远端 AudioCraft worker —— 留 follow-on change `audio-worker-audiocraft-adoption`
  (本 change scope=ABC + ComfyUI 第一客户;远端协议在 ABC 落地后 follow-on)

ComfyUI audio 路径 `ComfyAgentWorker.generate_audio` 不实现 ABC `generate_audio`
方法(签名一致 — `(*, spec, num_candidates, seed, timeout_s)` keyword-only,但
ComfyAgentWorker 是 `ComfyWorker` ABC 子类,通过 capability dispatch 路由 —
设计 D7 / R3-A round-3 修订)。

生成结果包成 `AudioCandidate`,`GenerateAudioExecutor` 再落成 file-backed
`audio.waveform` Artifact(F-Plan-R6-A round-6 修订:`shape="waveform"` 与
UE bridge `manifest_builder._KIND_MAP[("audio", "waveform")] = "sound_wave"`
唯一映射对齐;实际编码格式 flac/mp3/wav 保留在 `Artifact.metadata.format`)。

UE 导入侧 `ue_scripts/domain_audio.import_audio_entry` 已就绪
(SRS FR-UE-003 P4 真机验证 2026-04-23)。
"""
from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


# ----------------------------------------------------------------------------
# 异常树(类比 mesh_worker MeshWorker* 三层)
# ----------------------------------------------------------------------------


class AudioWorkerError(RuntimeError):
    """Generic audio worker failure.

    Optional kwargs `job_id` / `worker` / `model` carry remote-side identifiers
    when known at raise site (per Phase 1 mesh TBD-007 模式)。本 change scope
    远端 audio worker 不实装,这些字段为远端 follow-on change 预留。
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


class AudioWorkerTimeout(AudioWorkerError):
    """Audio worker exceeded wall-clock budget(subprocess 超时 / 网络超时)。"""


class AudioWorkerUnsupportedResponse(AudioWorkerError):
    """Provider returned a response shape this worker can't consume(e.g.
    outputs.audio missing / unsupported file format / magic bytes mismatch /
    path trust-boundary 违反)。Distinct from generic `AudioWorkerError` so
    `RetryPolicy` can skip pointless retries — the response is deterministic;
    retrying the same submit burns more GPU time for the same unusable output。
    """


# ----------------------------------------------------------------------------
# AudioCandidate dataclass
# ----------------------------------------------------------------------------


# F-Plan-R6-A round-6 plan 修订:`shape="waveform"` 与 UE bridge
# `manifest_builder._KIND_MAP[("audio", "waveform")] = "sound_wave"` 唯一映射对齐;
# `format=cand.format`(flac/mp3/wav)保留在 `metadata.format` 顶层字段(per
# F3 round-1 single-source decision + F-Plan-R7-A round-7 修订:metadata 仅放
# provenance 5 个 comfy_* keys,`duration_seconds` / `sample_rate` 顶层 None always)。


@dataclass
class AudioCandidate:
    """One audio result from an AudioWorker call.

    F-Plan-R6-A round-6 修订(persistence contract):
    - `data` + `format` 是 file-backed payload 的真实 bytes 与编码格式
    - `metadata` 仅承载 provenance(5 个 comfy_* keys per F-Plan-R7-A round-7
      single-source 修订);**不**重复 `duration_seconds` / `sample_rate` /
      `format_detected` 字段(避免双源冲突)
    - `duration_seconds` / `sample_rate` 顶层字段,在本 change scope 始终 `None`
      (ComfyUI agent CLI `extract_outputs` 不暴露 audio metadata;follow-on
      `audio-metadata-parser` change 加 mutagen / stdlib `wave` 解析)
    - GenerateAudioExecutor 持久化时:`Artifact(modality="audio", shape="waveform")`
      + `Artifact.metadata.format=cand.format`(实际格式信息 — UE
      `unreal.SoundFactory` import 时按文件扩展名 dispatch)
    """

    data: bytes
    format: Literal["flac", "mp3", "wav"]
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None  # 本 change scope 始终 None
    sample_rate: int | None = None  # 本 change scope 始终 None


# ----------------------------------------------------------------------------
# AudioWorker ABC
# ----------------------------------------------------------------------------


class AudioWorker(ABC):
    """Adapter surface used by `GenerateAudioExecutor`.

    `generate_audio` 签名 keyword-only;**no `prompt: str` 参数** — prompt 在
    `spec["comfy_params"]` 内(per design D7 / D8;executor SHALL NOT 解构 / 注入
    prompt key)。未来远端 AudioCraft worker 同 ABC,实现自己的 spec 解析约定
    (可能直接读 `spec["prompt"]` 或 `spec["audiocraft_*"]`)— 这是 ABC 通用契约
    的最大公约数。
    """

    name: str = "audio"

    @abstractmethod
    def generate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
        """Produce *num_candidates* audio candidates from *spec*.

        per-candidate loop 在 worker 内部实现(F-Plan-3 round-2 plan + F-Plan-R5-A
        round-5 修订:对照 image / mesh worker `comfy_worker.py:427` / `:689` 模式;
        executor 调一次即可,**不**需要外层 loop)。
        """


# ----------------------------------------------------------------------------
# FakeAudioWorker —— deterministic, offline (test fixture)
# ----------------------------------------------------------------------------


def _build_minimal_flac(payload: bytes = b"forgeue") -> bytes:
    """Synthesise a minimal valid FLAC stream(~50-100 bytes)。

    FLAC spec(RFC 9639):
    - Magic:`b"fLaC"`(4 bytes)
    - METADATA_BLOCK STREAMINFO(34 bytes payload + 4 bytes header):
      - block header: last-block flag(1 bit) + block type(7 bits)+ length(24 bits)
      - block body(34 bytes):min/max block size(uint16 each)+ min/max frame size
        (uint24 each)+ sample_rate(20 bits)+ channels(3 bits)+ bps(5 bits)+
        total_samples(36 bits)+ md5_signature(16 bytes)
    - 一个 minimal frame(无 audio 实质内容,只占位让 unreal.SoundFactory 解析头)

    用于 unit test 的 deterministic minimal valid FLAC bytes。**不**依赖第三方 codec。
    """
    # Magic
    out = bytearray(b"fLaC")

    # STREAMINFO METADATA_BLOCK header:last-block=1 + type=0(STREAMINFO)+ length=34
    # 0x80 = 10000000 = last-block flag set + block type 0
    # length 34 = 0x000022
    out.extend(b"\x80\x00\x00\x22")

    # STREAMINFO body(34 bytes):
    # min_block_size = 4096 (0x1000)
    # max_block_size = 4096 (0x1000)
    # min_frame_size = 0 (24-bit)
    # max_frame_size = 0 (24-bit)
    # sample_rate (20 bits) = 44100 = 0xAC44 → packed
    # channels - 1 (3 bits) = 1 (=stereo - 1)
    # bps - 1 (5 bits) = 15 (=16 bps - 1)
    # total_samples (36 bits) = 0
    # md5_signature (128 bits) = zeros
    streaminfo = bytearray()
    streaminfo.extend(struct.pack(">H", 4096))  # min block size
    streaminfo.extend(struct.pack(">H", 4096))  # max block size
    streaminfo.extend(b"\x00\x00\x00")  # min frame size (24-bit)
    streaminfo.extend(b"\x00\x00\x00")  # max frame size (24-bit)
    # sample_rate (20 bits=44100) + channels (3 bits=1) + bps (5 bits=15) + total_samples (36 bits=0)
    # 44100 = 0x00AC44 → 20 bits
    # packed bytes:
    #   byte 0:high 8 bits of sample_rate                     = 0x0A (从 44100>>12)
    #   byte 1:next 8 bits                                     = 0xC4 (44100>>4 & 0xff)
    #   byte 2:low 4 bits sample_rate + channels(3)+ bps_high(1) = 0x42
    #   byte 3:bps_low(4) + total_samples_high(4)              = 0xF0
    #   byte 4-7:total_samples low 32 bits                      = 0
    sr = 44100
    streaminfo.append((sr >> 12) & 0xFF)
    streaminfo.append((sr >> 4) & 0xFF)
    # bottom 4 bits of sr | channels-1 (3 bits=1) << 1 | bps-1 high bit (1 bit=0 since 15=01111 high=0)
    b2 = ((sr & 0x0F) << 4) | (1 << 1) | 0
    streaminfo.append(b2)
    # bps-1 low 4 bits = 15 & 0x0F = 15 = 0xF;total_samples high 4 bits = 0
    streaminfo.append(0xF0)
    streaminfo.extend(b"\x00\x00\x00\x00")  # total_samples low 32 bits
    streaminfo.extend(b"\x00" * 16)  # md5_signature

    out.extend(streaminfo)

    # Optional minimal frame(0xFF 0xF8 sync + dummy)— 非严格必要,只为非空 stream
    # 让 stdlib `wave` / `aifc` 不会读 0-byte 报 EOF
    if payload:
        out.extend(b"\xff\xf8")
        out.extend(payload[:8])  # ≤ 8 bytes payload identifier
    return bytes(out)


@dataclass
class _AudioScript:
    """FakeAudioWorker 测试脚本:可注入预设 candidates / 预设 raise。"""

    candidates: list[AudioCandidate] | None = None
    raise_error: BaseException | None = None


class FakeAudioWorker(AudioWorker):
    """Deterministic fake worker. Synthesises minimal FLAC when unprogrammed."""

    name: str = "fake_audio"

    def __init__(self) -> None:
        self._script: _AudioScript = _AudioScript()
        self.calls: list[dict[str, Any]] = []

    def program(
        self,
        *,
        candidates: list[AudioCandidate] | None = None,
        raise_error: BaseException | None = None,
    ) -> None:
        """Prime next call to return *candidates* or raise *raise_error*。"""
        self._script = _AudioScript(candidates=candidates, raise_error=raise_error)

    def generate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
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

        # Default:produce *num_candidates* minimal FLAC clones
        n = max(1, num_candidates)
        results: list[AudioCandidate] = []
        for i in range(n):
            data = _build_minimal_flac(payload=f"fake-{i}".encode("utf-8"))
            results.append(AudioCandidate(
                data=data,
                format="flac",
                metadata={
                    "is_fake": True,
                    "fake_index": i,
                    "fake_seed": (seed or 0) + i,
                },
                duration_seconds=None,  # 本 change scope 始终 None
                sample_rate=None,  # 本 change scope 始终 None
            ))
        return results
