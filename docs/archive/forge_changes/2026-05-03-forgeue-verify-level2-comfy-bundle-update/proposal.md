# Proposal — forgeue-verify-level2-comfy-bundle-update

## Why

`tools/forgeue_verify.py:174-189` 的 Level 2 `live-comfy-pipeline` 步骤跑过时
bundle:
- `examples/image_pipeline.json`(无 `comfy/local` route → 落 wildcard router → 不
  走 ComfyAgentWorker subprocess CLI 路径)
- 传 `--comfy-url http://127.0.0.1:8188`(已 deprecated;`framework.run` 静默忽略 +
  fall back FakeComfyWorker)

结果:`FORGEUE_VERIFY_LIVE_COMFY=1` 显示 "Comfy 验证通过" 但**完全没碰** v1.6 起的
新 ComfyUI agent CLI 路径 → **假阳性 verify**。

Codex G6-F1 finding(`comfy-agent-cli-audio-adoption` 2026-05-03)catch 此 drift。

## What Changes

- **MODIFIED**:`tools/forgeue_verify.py:174-189` — 把单个 `live-comfy-pipeline` 步骤
  替换为三个 ComfyUI Level 2 steps,各自 opt-in 不同 env var,各自跑对应 capability bundle:
  - `live-comfy-image`(env `FORGEUE_VERIFY_LIVE_COMFY`)→ `examples/comfy_local_smoke.json`
  - `live-comfy-mesh`(env `FORGEUE_VERIFY_LIVE_COMFY_MESH`)→ `examples/comfy_local_smoke_mesh.json`
  - `live-comfy-audio`(env `FORGEUE_VERIFY_LIVE_COMFY_AUDIO`)→ `examples/comfy_local_smoke_audio.json`
- **MODIFIED**:`tools/forgeue_verify.py` 顶部 docstring — Level 2 env var 列表加
  `_COMFY_MESH` / `_COMFY_AUDIO`,加 `FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_INPUT_DIR`
  环境依赖说明

## Impact

- **Breaking 兼容性**:`FORGEUE_VERIFY_LIVE_COMFY=1` 行为变了:
  - 旧:跑 `image_pipeline.json` + `--comfy-url`(假阳性)
  - 新:跑 `comfy_local_smoke.json`(真实 ComfyAgentWorker CLI 路径,需 ComfyUI server
    + `FORGEUE_COMFY_SCRIPTS_DIR`)
  - 用户旧 CI/dev 跑 `FORGEUE_VERIFY_LIVE_COMFY=1` 不带 ComfyUI server / env →
    现在 fail 而非假 PASS(更诚实)
- **Affected specs**:`probe-and-validation` +1 ADDED Requirement(锁住 Level 2 env
  var 矩阵 + bundle 名映射)
- **Affected code**:`tools/forgeue_verify.py` 一文件,~40 行
- **Affected tests**:无新 fence(行为正确性 fix;现有 `test_forgeue_verify` 在 dry-run
  模式下不受影响)
- **L0 baseline**:不变(Level 0/1 无影响)

## References

- 起源:[archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_verification_review.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_verification_review.md) G6-F1
- v1.6 ComfyUI agent CLI:[archive/2026-05-02-comfy-agent-cli-adoption/](../archive/2026-05-02-comfy-agent-cli-adoption/)
- Phase 1 mesh:[archive/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/](../archive/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/)
- Phase 2 audio:[archive/2026-05-03-comfy-agent-cli-audio-adoption/](../archive/2026-05-03-comfy-agent-cli-audio-adoption/)
