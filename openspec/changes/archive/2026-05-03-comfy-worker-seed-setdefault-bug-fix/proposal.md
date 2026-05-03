# Proposal — comfy-worker-seed-setdefault-bug-fix

## Why

`ComfyAgentWorker` 三处 capability(image / mesh / audio)的 per-candidate loop 都用
`params_for_call.setdefault("seed", call_seed)` 注入 seed,但当 caller 在
`comfy_params` 显式填了 seed(canonical bundles 都填了:
[examples/comfy_local_smoke.json](examples/comfy_local_smoke.json) /
[examples/comfy_local_smoke_mesh.json](examples/comfy_local_smoke_mesh.json) /
[examples/comfy_local_smoke_audio.json](examples/comfy_local_smoke_audio.json) `step.config.spec.comfy_params.seed`)
时,`setdefault` 不覆盖 → `num_candidates>1` 所有 candidate 拿同 seed,但 metadata
报告递增 seed → **重复 candidate + 误导 provenance**。

Codex G11 finding F3(`comfy-agent-cli-audio-adoption` 2026-05-03 plan_task `b86swn4sj`)
catch 此 bug。Audio change scope 内已修(audio worker line 912 `setdefault → 直接覆盖`
+ fence `test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`),
但 image (line 442) / mesh (line 703) **同模式 bug 未修**(scope discipline 留
follow-on)。

本 change scope = image + mesh 同 fix + 配套 fence(audio 已在
`comfy-agent-cli-audio-adoption` 修过),让三 capability `seed` 行为一致。

## What Changes

- **MODIFIED**:`src/framework/providers/workers/comfy_worker.py:442`(image generate
  loop)`setdefault("seed", call_seed)` → `params_for_call["seed"] = call_seed`
- **MODIFIED**:`src/framework/providers/workers/comfy_worker.py:703`(mesh generate
  loop)同样改
- **NEW fence**:`tests/unit/test_comfy_subprocess.py` 加 `test_generate_per_candidate_seed_overrides_comfy_params_seed`(image-mode,镜像 audio fence 模式)
- **NEW fence**:`tests/unit/test_comfy_subprocess.py` 加 `test_generate_mesh_per_candidate_seed_overrides_comfy_params_seed`(mesh-mode,镜像 audio fence 模式)

dormant bug only when `num_candidates>1`(canonical bundles 默认 `num_candidates=1`
所以生产暂未触发);但 production audit / provenance 角度,seed metadata 必须真实
反映 actual seed used。

## Impact

- **Breaking**:无(`num_candidates=1` 默认行为不变;`num_candidates>1` 时行为更正
  确,与 metadata 一致)
- **Affected specs**:无 spec 变更(本 change 是行为正确性 fix,不改 contract)
- **Affected code**:`comfy_worker.py:442` (image) + `:703` (mesh);其他文件不动
- **Affected tests**:`tests/unit/test_comfy_subprocess.py` 加 2 fence
- **L0 baseline**:1294 → 1296(预计 +2 fence)

## References

- 起源:[comfy-agent-cli-audio-adoption review/codex_adversarial_review.md](../comfy-agent-cli-audio-adoption/review/codex_adversarial_review.md)
  G11-F3 finding
- 镜像 fence 模式:[tests/unit/test_comfy_subprocess_audio.py](../../../tests/unit/test_comfy_subprocess_audio.py)
  `test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`(已存在)
- audio 同 fix commit:`comfy-agent-cli-audio-adoption` archive 链
