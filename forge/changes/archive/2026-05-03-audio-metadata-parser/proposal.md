# Proposal — audio-metadata-parser

## Why

`AudioCandidate.duration_seconds` 和 `sample_rate` 字段在
`comfy-agent-cli-audio-adoption`(2026-05-03)中**永远 None**(D10 决策:本 change
scope 不引入 audio metadata parser)。结果:

- L2 evidence 的 `(d) duration ±10% 校验`项无法做(`tasks.md §11.4 (d) DEFERRED`)
- UE 侧 import_audio 后 audio asset metadata 缺 duration / sample rate 字段
- run comparison 无法对比 audio 时长 / 采样率
- audit 报告 audio asset 元数据不全

Codex G6/G11 review 没直接 catch 这个,但 D10 显式承诺 follow-on `audio-metadata-parser`
解决。本 change 兑现承诺。

## What Changes

- **NEW**:`src/framework/providers/workers/audio_metadata.py` — stdlib-only audio
  metadata parser
  - `parse_audio_metadata(data: bytes, fmt: Literal["flac","mp3","wav"]) -> tuple[duration_seconds | None, sample_rate | None]`
    dispatch entry
  - `_parse_flac` — FLAC STREAMINFO block 解析(magic + last_block + type 0 + 34-byte
    body;sample_rate 20 bits + total_samples 36 bits → duration = total_samples / sample_rate)
  - `_parse_wav` — RIFF / WAVE / fmt chunk + data chunk size → sample_rate +
    duration = data_size / byte_rate
  - `_parse_mp3` — ID3v2 preamble skip + first MPEG frame header sync + version /
    rate_idx 表查 sample_rate(duration MVP best-effort,Xing/LAME header 不实施
    → 返 None)
  - 所有 parse 失败 silent fallback `(None, None)`(不阻断 audio Artifact 落盘)
- **MODIFIED**:`src/framework/providers/workers/comfy_worker.py::_run_once_audio`
  在 magic bytes 校验后 + AudioCandidate 构造前 call
  `parse_audio_metadata(audio_bytes, ext)`,fill 两字段
- **NEW fence**:`tests/unit/test_audio_metadata.py`(8 fence)
  - `test_parse_flac_extracts_sample_rate_and_duration`(positive: 44100 Hz × 5s)
  - `test_parse_flac_invalid_magic_returns_none`(safety: silent fallback)
  - `test_parse_wav_extracts_sample_rate_and_duration`(positive: 22050 Hz × 1s)
  - `test_parse_wav_invalid_returns_none`
  - `test_parse_mp3_extracts_sample_rate_for_mpeg1`(positive: 44100 Hz, duration None)
  - `test_parse_mp3_with_id3v2_preamble_skipped`(skip ID3v2 → reach frame header)
  - `test_parse_audio_metadata_unknown_format_returns_none`(safety: unknown fmt)
  - `test_parse_audio_metadata_truncated_input_returns_none`(safety: short input)

## Impact

- **Breaking**:无(`AudioCandidate.duration_seconds` / `sample_rate` 已是
  `Optional[float|int]`,从 None 变为 some 真实值是"扩展", caller 当前不依赖
  None 默认)
- **Affected specs**:`artifact-contract` +1 ADDED Requirement(audio metadata 三键
  实际填值规则)
- **Affected code**:1 新 module + `comfy_worker.py:_run_once_audio` 一处 call
  (~5 行)
- **Affected tests**:8 新 fence
- **L0 baseline**:1315 → 1323(+8 fence)
- **L2 verified**:`audio_smoke_meta_l2_v3` 真实 ComfyUI Stable Audio Open 输出
  FLAC,parser 提取 `duration_seconds=10.031s`(within ±10% of bundle declared
  10.0s)+ `sample_rate=44100 Hz`(Stable Audio Open default)+ size 1.17 MB
  落地

## Out of scope

- MP3 duration:不做精算(Xing/LAME VBR header 解析复杂);MVP 返 None。Future
  follow-on 可加。
- AAC / OGG / Opus:三 capability 仅接受 flac/mp3/wav whitelist(per audio adoption
  D10),其他格式不在本 change scope。
- duration ±10% 一致性校验(原 tasks §11.4 (d)):本 change 提供了 metadata 字段,
  consistency 校验作为 evidence note 写到 `notes/`(本 change 不内嵌生产 fence,
  避免 tooling lock real-FLAC 真实 duration 与 bundle declared 之间的 ε 容差)。

## References

- 起源:[archive/2026-05-03-comfy-agent-cli-audio-adoption/design.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/design.md) D10
- AudioCandidate 字段:[src/framework/providers/workers/audio_worker.py](src/framework/providers/workers/audio_worker.py)
- L2 evidence 计划:`notes/live_smoke_audio_metadata_20260504.md`
