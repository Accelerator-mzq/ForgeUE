# Proposal — comfy-agent-cli-path-containment-hardening

## Why

兑现 OpenSpec change `comfy-agent-cli-audio-adoption` G11-F2 codex finding 之
follow-on commitment(R7-C `disputed-permanent-drift / accepted-claude` 立场约定的
hardening 方向)。三处 `_run_once*`(image:558 / mesh:877 / audio:1093)读 ComfyUI
subprocess 返回的 output paths 时,只验 `is_file()` + `is_symlink()` + extension
whitelist + magic bytes,**没有 path containment** —— 即 stdout JSON 内的路径只要
能 resolve 成存在的文件、不是 symlink、且头几字节 magic 合法,bytes 就被读入。

威胁面:buggy / compromised ComfyUI subprocess 返回 ComfyUI install tree 之外的
路径(典型场景:节点 bug 导致 path traversal `..` 段被误用,或者第三方 custom
node 输出位置异常)。

## What Changes

- **MODIFIED**:`src/framework/providers/workers/comfy_worker.py` `ComfyAgentWorker.__init__`
  加 `comfy_output_root: Path` 字段,resolution order:
  1. `FORGEUE_COMFY_OUTPUT_ROOT` env var(显式,推荐 production)
  2. `scripts_dir.parent`(heuristic — 真实 ComfyUI install `D:/AI/ComfyUI/scripts`
     parent = `D:/AI/ComfyUI`,outputs 实际在 `D:/AI/ComfyUI/outputs/main/...` 都
     在该根下;tests `tmp_path/scripts.parent = tmp_path` 同样 cover fake outputs)
- **NEW helper**:`ComfyAgentWorker._assert_path_within_comfy_output_root(src, output_kind)`
  — `Path.resolve().is_relative_to(comfy_output_root)` 校验,raise
  `WorkerUnsupportedResponse` if outside
- **MODIFIED**:三处 `_run_once*` 在 magic bytes 校验之前(`read_bytes()` 之前)加
  `self._assert_path_within_comfy_output_root(src, output_kind=...)`:
  - image:`comfy_worker.py:558-` 之后,`shutil.copy2` 之前(防 copy `/etc/secrets`)
  - mesh:`comfy_worker.py:877-` 之后,`src.read_bytes()` 之前
  - audio:`comfy_worker.py:1093-` 之后,`src.read_bytes()` 之前
- **NEW fence**(3):
  - `tests/unit/test_comfy_subprocess.py` 加
    `test_image_outputs_path_outside_comfy_output_root_raises_unsupported_response`
  - `tests/unit/test_comfy_subprocess.py` 加
    `test_mesh_outputs_path_outside_comfy_output_root_raises_unsupported_response`
  - `tests/unit/test_comfy_subprocess_audio.py` 加
    `test_audio_outputs_path_outside_comfy_output_root_raises_unsupported_response`
- **L2 verified**(2026-05-04):`audio_smoke_path_containment_l2` 真实跑通
  1.17 MB FLAC(real ComfyUI outputs 在 `D:/AI/ComfyUI/outputs/main/...`,heuristic
  root `D:/AI/ComfyUI` 容纳 — containment check passes 真实生产路径)

## Impact

- **Breaking**:理论上是 — buggy / compromised CLI 返回 D 盘外路径现在 raise
  而非静默落 Artifact。实际生产无 incident(这是 hardening 非修复)
- **Affected specs**:`provider-routing` +1 ADDED Requirement(三 capability 同步
  containment)
- **Affected code**:`comfy_worker.py` 一文件 ~30 行(+1 helper + 3 调用站点)
- **Affected tests**:3 新 fence + helper docstring update
- **L0 baseline**:1310 → 1313(+3 fence)
- **L2**:audio live smoke FULL PASS verified(`live_smoke_audio_20260504_path_containment.md`
  evidence)

## References

- 起源:[archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_adversarial_review.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_adversarial_review.md) G11-F2
- R7-C `disputed-permanent-drift` follow-on commitment:[archive/2026-05-03-comfy-agent-cli-audio-adoption/design.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/design.md) `## Reasoning Notes — F-Plan-R7-C / G11-F2`
- audio executor reference template(已无 path containment,现 follow-on 同步加):[src/framework/runtime/executors/generate_audio.py](src/framework/runtime/executors/generate_audio.py)
