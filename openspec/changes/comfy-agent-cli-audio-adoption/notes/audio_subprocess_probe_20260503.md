# Audio Subprocess Probe — 2026-05-03

> S2→S3 阻塞 probe(per cross-check F4 resolution + design.md OQ-1/2/3 resolve)。
> 沿 Phase 1 round 5 D10 教训:外部 ComfyUI 协议未验证不上 S3。

## 环境

- ForgeUE 仓库:`d:/ClaudeProject/ForgeUE_claude`
- ComfyUI scripts dir:`D:/AI/ComfyUI/scripts`(✅ 存在,与 CLAUDE.md `FORGEUE_COMFY_SCRIPTS_DIR` 一致)
- ComfyUI 服务状态(`python -m comfyui_api status`):`{"ok": true, "online": false}` — **agent CLI 可用,但 server 离线**(用户自管,本 probe 限制为不需要 server 的 subcommand:`list` / `params` + 源码静态阅读)
- agent CLI 子命令(`python -m comfyui_api -h`):`{list, params, run, batch, status, cancel}` — 与 CLAUDE.md 描述一致

## OQ-1 — `outputs.audio` 真实字段名

**结论**:✅ **`outputs.audio` 是正确字段名,string list of absolute paths**。

**证据来源**:`D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs`,line 186-249:

```python
def extract_outputs(history_entry: dict, root: Path | None = None) -> dict:
    """
    Returns
    -------
    dict
        ``images`` — list of absolute path strings for PNG/image outputs.
        ``audio``  — list of absolute path strings for audio outputs.
        ``glb``    — list of absolute path strings for .glb mesh outputs.
        ``raw``    — the full ``outputs`` dict for advanced use.
    """
    outputs: dict = history_entry.get("outputs", {})
    images = []
    audio = []
    glb = []
    for _node_id, node_out in outputs.items():
        for img in node_out.get("images", []): ... images.append(path)
        for aud in node_out.get("audio", []): ... audio.append(path)
        for item in <glb extraction>: ... glb.append(...)
    return {"images": images, "audio": audio, "glb": glb, "raw": outputs}
```

**关键事实**:
1. `outputs.images` / `outputs.audio` / `outputs.glb` 三个 key **always present**(empty list if not produced),NOT 只在产出时出现
2. agent CLI 在 `run` 子命令的 stdout JSON 顶层(envelope)里包含 `outputs: {images: [...], audio: [...], glb: [...], raw: <full>}`(line 353 `"outputs": outputs`)
3. ComfyUI history entry 的 **真实 per-node audio output 列表** 在 `outputs.raw.<node_id>.audio` 里

**对 spec / 4-dict 的影响**:
- `_REQUIRED_OUTPUT_KEY["audio"] = "audio"` ✅ 正确(non-empty 检查)
- `_REJECTED_OUTPUT_KEYS_BY_CAP["audio"] = {"images", "glb", "video"}` ✅ 正确(非空检查 — `images` / `glb` 即使始终 present 也是 `[]`,只有非空才 raise)
- ⚠️ `outputs.video` key 在 `extract_outputs` **不存在**(只 extract `images` / `audio` / `glb` 三种);若未来 ComfyUI 加 video 节点,需要 agent CLI 端先扩 `extract_outputs`,本 change `_REJECTED_OUTPUT_KEYS_BY_CAP["audio"]` 包含 `"video"` 是 forward-compat 保险,即使该 key 现在不存在,`outputs.get("video", [])` 返 `[]` 不会触发 reject(safe)

## OQ-2 — `outputs.audio` list 长度与 num_candidates 关系

**结论**:**单 subprocess invocation 通常产 `len(outputs.audio) == 1`(单 SaveAudioMP3 节点),`num_candidates > 1` 通过多次 subprocess 实现**(沿 Phase 1 mesh `_run_mesh_subprocess` per-candidate loop 模式)。

**证据**:
1. ACE-Step manifest:1 个 SaveAudioMP3 节点(`audio_ace_step_1_t2a_instrumentals.json` `params.filename_prefix.patches[0].node_class == "SaveAudioMP3"`)
2. Stable Audio manifest:1 个 SaveAudioMP3 节点(同上,`audio_stable_audio_example.json`)
3. ComfyUI KSampler `batch_size` 默认 1;两个 manifest 都没有 `batch_size` 暴露为 param,所以单次跑出 1 个 audio file
4. extract_outputs 收集所有 `_node_id` 下的 audio outputs,如果 manifest 有多个 SaveAudio 节点理论上能产多个,但本 change 选定的两个 manifest 都是单节点

**对 spec 的影响**:
- `provider-routing/spec.md` Step 5「Return list[AudioCandidate] of length matching len(outputs.audio)」✅ 正确
- `generate_audio` 内部 `for path in outputs.audio` 循环正确处理任意 length(0 / 1 / N)
- num_candidates > 1 实现(F-Plan-R5-A round-5 plan 修订:loop 归属由 executor-side 改为 worker-side,与 F-Plan-3 round-2 plan + spec/provider-routing Step 6 收敛后的 contract 对齐):**`ComfyAgentWorker.generate_audio` 内部** per-candidate loop `for i in range(max(1, num_candidates)): call_seed = (seed or 0) + i; ... results.extend(self._run_once_audio(...))`(对照 image / mesh worker `comfy_worker.py:427` / `:689`);`GenerateAudioExecutor._generate_via_comfy_worker` 调一次 `worker.generate_audio(spec=spec, num_candidates=num, ...)` 即可,**不**需要外层 loop。事实保留:单 SaveAudioMP3 节点 1 file per subprocess run(per probe);worker 内部 N 次 subprocess 聚合 candidates。

## OQ-3 — `duration_seconds` / `sample_rate` 暴露形式

**结论**:**ComfyUI agent CLI `extract_outputs` 不暴露 audio metadata(duration / sample_rate)**;只返回路径列表。

**证据**:
- `runner.py:209-249` `extract_outputs` 只 collect path strings 到 `audio` list,**不提取** per-audio metadata
- `outputs.raw.<node_id>.audio[i]` 在 ComfyUI history entry 里 **可能** 含 metadata(per node implementation),但 ForgeUE 通过 `outputs.audio`(扁平化路径 list)读时丢失
- agent CLI envelope 顶层 **没有** `outputs.metadata.audio` 字段(我之前 spec 写错了路径)

**对 spec 的影响**:
- `provider-routing/spec.md` line 118「if ComfyUI agent CLI stdout JSON exposes these (e.g. via `outputs.metadata.audio` field) the worker reads them」**字段名错误**,需 writeback:
  - 改为「`AudioCandidate.duration_seconds` / `sample_rate` 总是 None(本 change scope);未来若需要,follow-on `audio-metadata-parser` change 加 stdlib `wave` / `aifc` / mutagen 解析」
  - 或者:从 `outputs.raw.<node_id>.audio[i]` per-node 字典里挖(若节点实现暴露;不稳定,不推荐 S2 锁定)
- 决策:**本 change 不暴露 duration / sample_rate**,顶层字段保留为 `| None = None` 但 `_run_subprocess_and_validate` 不尝试解析;`AudioCandidate(duration_seconds=None, sample_rate=None)` 是 always-correct;follow-on change 加 metadata parser
- `Artifact.metadata.duration_seconds` 也对应 None;UE `import_audio` 不依赖此字段(`unreal.SoundFactory` 自己解析 audio header,per spec D10 reasoning)

## 副产物 — Stable Audio params schema 实测

`python -m comfyui_api params --workflow Audio_Workflows/audio_stable_audio_example` 输出(摘):

```json
{
  "params": {
    "text": {"type": "string", "required": true, "patches": [{"node_id": "6", "field": "text"}]},
    "negative_prompt": {"type": "string", "default": "", "patches": [{"node_id": "7", "field": "text"}]},
    "duration_seconds": {"type": "float", "default": 47.6, "range": [5.0, 120.0], "patches": [{"node_class": "EmptyLatentAudio", "field": "seconds"}]},
    "seed": {"type": "int", "default": 840755638734093, "patches": [{"node_class": "KSampler", "field": "seed"}]},
    "steps": {"type": "int", "default": 50, "range": [10, 100], "patches": [{"node_class": "KSampler", "field": "steps"}]},
    "filename_prefix": {"type": "string", "default": "audio/ComfyUI", "patches": [{"node_class": "SaveAudioMP3", "field": "filename_prefix"}]}
  }
}
```

**`text` 是唯一 required field**;其它 5 个有 default。本 change `examples/comfy_local_smoke_audio.json` `comfy_params` 必须含 `text`,其它 OPTIONAL(若 OPTIONAL 给则覆盖 default)。

## 文件输出格式 — FLAC vs MP3 抉择

**SaveAudioMP3 节点名 vs `outputs.primary: audio/flac`**:manifest declares flac,但节点名是 MP3 — 这是 ComfyUI 节点命名遗留(SaveAudio* 节点系统化默认 mp3 编码,但 ComfyUI 现行版本 SaveAudioMP3 node 实际可输出 FLAC 取决于 node 参数)。

无 server 时无法实际跑 `run` 验证扩展名;但 extract_outputs 不限制扩展名,仅按节点 emit 的路径填 list。**结论**:文件扩展名(.flac / .mp3 / .wav)由 ComfyUI 节点实际写出决定,ForgeUE 在 worker 端检测扩展名(D10 决策正确,但 magic bytes gate F5 必须加,因 SaveAudioMP3 节点名暗示可能写 mp3 内容到 .flac 扩展名 — 需要 magic bytes 二次校验防止 ext-content 错配)。

## 后续 implementation 阶段未解决项

1. **真跑 `python -m comfyui_api run`**:用户启 server(`python -m factory_v3 serve`)+ Stable Audio Open 模型权重已下载(首次 ~2GB HuggingFace 拉)后,跑一次 minimal smoke 拿 stdout JSON 完整样例,验证:
   - `extract_outputs` 实测 `outputs.audio` 路径列表是绝对路径还是相对 `D:/AI/ComfyUI/outputs/main/<date>/<project>/`(看 line 31 `COMFYUI_OUTPUT_ROOT`)
   - 文件扩展名实际是 `.flac` / `.mp3` / `.wav` 哪一个
   - magic bytes 是 `b"fLaC"` / `b"ID3"` / `b"\xff\xfb"` / `b"RIFF"` 哪一个
2. **OQ-2 multi-candidate 实测**(F-Plan-R5-A round-5 plan 修订):目前 spec 推 **`ComfyAgentWorker.generate_audio` 内部** per-candidate loop(对照 image / mesh worker 模式);若 `num_candidates=1` 在 L2 evidence 期间足够,multi-candidate 验证可推迟到 follow-on
3. **OQ-3 metadata parser**:本 change scope=不解析,留 follow-on `audio-metadata-parser`

## 影响 cross-check 的 round-2 修订

`review/codex_design_review.md` F4 medium finding `accepted-codex` 已确认;writeback action items:

- `provider-routing/spec.md` line 118 改「outputs.metadata.audio」→「(本 change scope 不解析 duration / sample_rate;set None;follow-on `audio-metadata-parser` 加)」
- `design.md` D5 D10 OQ-3 同步:duration / sample_rate 顶层字段 `| None = None`,worker **不**尝试 parse(去掉「best-effort 从 ComfyUI agent CLI stdout JSON metadata 字段读」描述)
- `tasks.md` §4.2 实装段:`AudioCandidate(..., duration_seconds=None, sample_rate=None)` 固定值(don't probe metadata)

无需 round-2 design 大改 — `_REQUIRED_OUTPUT_KEY` / `_REJECTED_OUTPUT_KEYS_BY_CAP` 都正确。
