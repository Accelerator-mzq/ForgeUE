# Design — comfy-worker-seed-setdefault-bug-fix

## 1. Context

`ComfyAgentWorker` 三处 capability(image / mesh / audio)的 per-candidate 循环都用
`params_for_call.setdefault("seed", call_seed)` 注入 seed:

| Capability | File:line | Status |
| --- | --- | --- |
| image  | `src/framework/providers/workers/comfy_worker.py:442` | **bug 在**(本 change scope) |
| mesh   | `src/framework/providers/workers/comfy_worker.py:703` | **bug 在**(本 change scope) |
| audio  | `src/framework/providers/workers/comfy_worker.py:912` | 已 fix(`comfy-agent-cli-audio-adoption` 2026-05-03 G11-F3 closed)|

Bug 触发条件:caller 在 `comfy_params` 内显式填了 `seed`(canonical bundles 三处都填了:
[examples/comfy_local_smoke.json](examples/comfy_local_smoke.json) /
[examples/comfy_local_smoke_mesh.json](examples/comfy_local_smoke_mesh.json) /
[examples/comfy_local_smoke_audio.json](examples/comfy_local_smoke_audio.json)
`step.config.spec.comfy_params.seed`)+ `num_candidates > 1`。`setdefault` 不覆盖已存在的
key → 所有 candidate 拿同一 seed,但 metadata 仍记录递增 seed。

dormant on `num_candidates=1`(默认),活跃在多 candidate 路径(future PR / 自定义 bundle)。

## 2. Decisions

**D1**:Audio change 已用「直接覆盖」模式([commit 7fee63f](https://github.com/Accelerator-mzq/ForgeUE/commit/7fee63f)):
```python
params_for_call["seed"] = call_seed   # NOT setdefault
```
本 change 把 image / mesh 同步到此模式。三处一致是必要的(否则 audit 时三 capability
seed 行为分叉)。

**D2**:不改 metadata `seed` 字段(executor/worker `seed=call_seed` 已正确);只改
`params_for_call` 注入逻辑。

**D3**:fence 模式 mirror audio 已落地的
[`test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`](tests/unit/test_comfy_subprocess_audio.py)
(检查 subprocess `--params` JSON 实际收到的 seed 序列 == [base, base+1, base+2])。

## 3. Risk

无。`num_candidates=1` 默认行为不变(setdefault 与覆盖等价 since key 不存在前是 None)。
等等 — caller 在 `comfy_params` 内填了 `seed: 42` 时,改前 → 用 42;改后 → 用 call_seed。
这是行为变化(num_candidates=1 + comfy_params has seed → 行为从「caller seed wins」
变成「per-candidate seed wins」)。

**Decision**:这是 bug fix,不是 breaking。理由:caller 把 seed 同时写在 `step.seed`
顶层 + `comfy_params.seed` 是冗余写法,canonical 路径是顶层 `step.seed` + per-candidate
偏移。`comfy_params.seed` 字段当前在 manifest schema 里仅是 ComfyUI 节点参数透传,不
应该 override executor 层 seed 偏移逻辑。修复后语义 = "顶层 seed 总是 wins,comfy_params
内可写但被覆盖"。

## 4. Migration

- 任何 caller 依赖 "comfy_params.seed override 顶层 seed" 行为:**升级后 break**(none
  已知;canonical bundles 写两处但同值 42,无所谓覆盖)
- `examples/comfy_local_smoke*.json` 三 bundle:删 `comfy_params.seed`(冗余)— 可选
  cleanup,本 change 不动 bundle(讲 contract clean,bundle 写 seed 不 break;只是不再
  生效)

## 5. Scope discipline

本 change 只动 `comfy_worker.py:442` + `:703` + 2 fence。**不**动 audio executor /
audio worker / examples / docs(audio 已修;bundle cleanup 是 cosmetic 不必)。

## 6. References

- 起源:[comfy-agent-cli-audio-adoption review/codex_adversarial_review.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_adversarial_review.md) G11-F3
- 已 fix 模板:[src/framework/providers/workers/comfy_worker.py:912](src/framework/providers/workers/comfy_worker.py#L912)(audio)
- fence 模板:[tests/unit/test_comfy_subprocess_audio.py](tests/unit/test_comfy_subprocess_audio.py)
  `test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`
