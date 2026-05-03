# Design — audio-metadata-parser

## 1. Context

`comfy-agent-cli-audio-adoption` D10 把 audio metadata 解析推给 follow-on,本 change
落实。审计 / run comparison / UE import_audio 都希望拿到真实 duration_seconds +
sample_rate,不是 None。

## 2. Decisions

**D1**:**stdlib-only**(无 mutagen / pydub / soundfile / audioop 等第三方依赖)。
理由:
- audio 三 capability 仅接受 flac/mp3/wav 三 format(per audio adoption D10 whitelist),
  format 范围有限,stdlib parse 足够
- 避免 dependency 引入(NFR-MAINT)
- 解析 FLAC STREAMINFO / WAV fmt / MP3 frame header 都是文档化的固定 byte layouts,
  150 行 stdlib 代码可覆盖

**D2**:**FLAC 完整 + WAV 完整 + MP3 简化**:
- FLAC + WAV 两 format 在 binary 头 fixed-size 字段,duration / sample_rate 直接计算
- MP3 sample_rate 易得(first frame header 4 bytes),但 duration 需要 frame count
  + bitrate(VBR)或 Xing/LAME VBR header 解析,复杂度高于本 change scope
- MP3 duration 返 None(已记入 proposal.md "Out of scope");caller 知 None = unknown
- MP3 sample_rate 是真实需求(audit + UE)

**D3**:**Silent fallback**:解析失败(magic mismatch / 截短输入 / unknown format
/ struct.error)→ `(None, None)`。理由:
- audio Artifact 已通过前置 magic bytes 校验(`_run_once_audio`),不会真实进入
  parser 无效输入(除非 ComfyUI 输出极其异常)
- 不阻断 audio Artifact 落盘 — duration / sample_rate None 是预期 fallback,与
  pre-fix 行为一致

**D4**:**位置**:`src/framework/providers/workers/audio_metadata.py` 独立 module。
理由:
- 与 `audio_worker.py`(ABC + dataclass)分离 — parser 是纯 byte logic 不依赖
  AudioWorker / AudioCandidate
- 与 `comfy_worker.py`(ComfyAgentWorker)分离 — parser 也可被 future remote
  AudioCraft worker 复用
- helper module 不需要 expose `__init__.py` __all__(internal,worker 直接 import)

**D5**:**调用点**:`ComfyAgentWorker._run_once_audio` 在 magic bytes 校验后 +
AudioCandidate 构造前。理由:
- magic bytes 已 verify ext 与 payload bytes 一致(F5 round-1 mandatory),parser
  不需要重做格式检测
- AudioCandidate 构造时直接拿 parsed values 填 duration_seconds / sample_rate

## 3. Risk

- **Real Stable Audio Open FLAC**:已 L2 verified(2026-05-04 `audio_smoke_meta_l2_v3`
  真跑通,parser 提取 `duration=10.031s` / `rate=44100 Hz` 与 bundle declared 10s
  对齐 ±0.5%;1.17 MB FLAC 落地)
- **MP3 sync byte 不全**:`comfy-agent-cli-audio-adoption` magic bytes 校验有
  4 个 MPEG frame sync prefix(`FF FB / FA / F3 / F2`)— 这 4 个对应 MPEG-1 / MPEG-2
  / MPEG-2.5 layer III no-CRC + with-CRC 的常见组合;我的 parser 接受任何
  `(b1 & 0xE0) == 0xE0` 的 sync(更宽容)
- **Edge cases**:WAV non-canonical chunk order(LIST INFO before fmt 等)→ parser
  give up duration 但保 sample_rate;MP3 没 ID3v2 + 直接 frame header → 也支持

## 4. Migration

无。新填 metadata 不破 existing Artifact records;新 run 后 metadata 字段从 None
变为 some real value(non-breaking 字段 type 已是 `Optional`)。

## 5. Scope discipline

本 change 加 1 module + 1 调用站点 + 8 fence + 1 evidence note。**不**改:
- AudioWorker ABC / AudioCandidate dataclass(字段已支持 Optional)
- audio executor `generate_audio.py`(executor 透传 candidate.duration_seconds /
  sample_rate 到 Artifact.metadata,字段 path 不变)
- bundle JSON / examples
- UE bridge

## 6. References

- 起源:`archive/2026-05-03-comfy-agent-cli-audio-adoption` D10 + tasks §11.4 (d)
  duration 校验 deferred
- L2 evidence:`notes/live_smoke_audio_metadata_20260504.md`(本 change 内)
- Stable Audio Open output format:FLAC 16-bit 44.1 kHz stereo(实测 verified)
