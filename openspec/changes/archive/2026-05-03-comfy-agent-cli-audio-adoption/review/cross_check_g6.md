---
change_id: comfy-agent-cli-audio-adoption
stage: S5
evidence_type: implementation_cross_check
contract_refs:
  - design.md
  - tasks.md
  - review/codex_verification_review.md
  - openspec/specs/provider-routing/spec.md
codex_review_ref: review/codex_verification_review.md
plugin_command: "/codex:review --base main"
plugin_task_id: bn2pymr7y
detected_env: claude-code
codex_plugin_available: true
triggered_by: "/forgeue:change-verify (G6 stage cross-check independent verification)"
created_at: 2026-05-03T15:48:00+00:00
disputed_open: 0
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
round: G6
---

# G6 Cross-check — codex_verification_review.md(独立验证)

## A. Decision Summary(冻结于 codex 调用之前)

本轮 G6 cross-check 立场:
- **预期**:本 change 是 audio capability adoption,scope 限制在 `audio_worker.py` /
  `comfy_worker.py` audio 部分 / `generate_audio.py` / `failure_mode_map.py` audio entries
  / `dry_run_pass.py` audio gate / `examples/comfy_local_smoke_audio.json` /
  `probes/provider/probe_comfy_audio.py`。
- **不预期 codex 提到 image / mesh executor / .env.example / forgeue_verify**:这些是
  pre-existing 文件,本 change 没有 modify intent。如果 codex 提到这些,**默认 out-of-scope**
  follow-on,**不阻断本 change archive**。
- **预期 codex 真正可能 catch 的**:audio executor 的 producer attribution 是否正确做
  `comfy_agent_cli` / `comfy/local-audio` 而非误用 `self._worker.name`(因为审计 audit 显
  这是 image/mesh 历史 bug 的同形态风险)。

## B. Findings adjudication

### G6-F1: forgeue_verify Level 2 跑旧 image_pipeline.json — accepted-codex / out-of-scope

**Codex 论据**:`tools/forgeue_verify.py:182-187` 的 Live Comfy verify 仍跑
`examples/image_pipeline.json` + `--comfy-url`,但本补丁(指 v1.6 image change)已让
`framework.run` 忽略该参数 + fall back FakeComfyWorker;且 bundle 没 `comfy/local`
route,所以 Live Comfy verify 是假阳性。

**Claude 立场**:**accepted-codex / out-of-scope**。这是 v1.6 image change 落地时遗留的
verify 工具未同步 bug,与本 audio change 完全无关。本 change 不动 `forgeue_verify.py`。

**Resolution**:`accepted-codex / out-of-scope`;follow-on change
`forgeue-verify-level2-comfy-bundle-update` 处理。

### G6-F2: generate_image.py 290 producer 取 self._worker.name — accepted-codex / out-of-scope

**Codex 论据**:`comfy/local` 分支构造 `ComfyAgentWorker`,但持久化 producer 仍取
`self._worker.name`(注入的 `FakeComfyWorker`)→ 真实 Comfy 生成的图片记录为 `fake_comfy`,
污染 provenance / audit。

**Claude 立场**:**accepted-codex / out-of-scope**。这是 v1.6 image change 历史 bug,
本 audio change 不动 `generate_image.py`。但**本 change 的 audio executor 没踩同 bug**
(独立验证见 `## D`)。

**Resolution**:`accepted-codex / out-of-scope`;follow-on change
`comfy-executor-producer-attribution-fix`(image + mesh 一起修)处理。

### G6-F3: generate_mesh.py 206 同问题 — accepted-codex / out-of-scope

**Codex 论据**:`comfy/local-mesh` 分支命中 `_generate_via_comfy_worker` 后,后续
producer / cost model / metrics 仍 `self._worker.name`(注入 `HunyuanMeshWorker`
when `HUNYUAN_3D_KEY` 在 env)→ 本地 Comfy mesh 产物记录成 Hunyuan/Tripo/Fake。

**Claude 立场**:**accepted-codex / out-of-scope**。Phase 1 mesh change 历史 bug,
本 audio change 不动 `generate_mesh.py`。Audio executor `generate_audio.py:142` 走
正确 attribution(独立验证见 `## D`)。

**Resolution**:`accepted-codex / out-of-scope`;同 G6-F2 合并 follow-on。

### G6-F4: .env.example HUNYUAN_3D_SECRET_ID/KEY/REGION vs HUNYUAN_3D_KEY — accepted-codex / out-of-scope

**Codex 论据**:`.env.example:81-83` 模板列 `HUNYUAN_3D_SECRET_ID/SECRET_KEY/REGION`,
但运行时和 `config/models.yaml` 实读 `HUNYUAN_3D_KEY` → 用户照模板配会拿不到 key。

**Claude 立场**:**accepted-codex / out-of-scope**。Pre-existing env 模板与运行时配置项
对齐 bug,本 audio change 不动 `.env.example`。

**Resolution**:`accepted-codex / out-of-scope`;follow-on change
`env-template-hunyuan-key-alignment` 处理。

## C. disputed_open

**disputed_open: 0**(4 finding 全 accepted-codex / out-of-scope;无 disputed-pending)。

## D. Independent verification(file:line 验证)

### Audio executor 没踩 G6-F2/F3 的 producer attribution bug

`src/framework/runtime/executors/generate_audio.py:140-144`:

```python
producer=ProducerRef(
    run_id=ctx.run.run_id, step_id=ctx.step.step_id,
    provider="comfy_agent_cli" if chosen_model == "comfy/local-audio" else "audio_worker",
    model=chosen_model,
),
```

**验证**:audio executor 显式按 `chosen_model` 分支 attribution,**NOT** `self._worker.name`。
当 comfy/local-audio 路径活跃时:
- `chosen_model = "comfy/local-audio"`(line 106)
- `provider = "comfy_agent_cli"`
- `model = "comfy/local-audio"`

L2 evidence 实跑 `audio_smoke_l2_pass` 落 `_artifacts.json`(`notes/live_smoke_audio_20260503_full.md`):

```json
"producer": {
  "run_id": "audio_smoke_l2_pass",
  "step_id": "step_audio",
  "provider": "comfy_agent_cli",   ← correct
  "model": "comfy/local-audio"      ← correct
}
```

**确认 audio executor 没有 G6-F2/F3 同形态 bug**。

### G6-F2/F3 image/mesh executor producer attribution bug 真实存在

`src/framework/runtime/executors/generate_image.py:155, 209, 236`:

```python
provider=("litellm" if use_api_path else (self._worker.name if self._worker else "fake")),
```

`src/framework/runtime/executors/generate_mesh.py:265, 308, 315`:

```python
provider=self._worker.name,
...
model=self._worker.name,
```

**验证**:image / mesh executor 真实有 G6-F2/F3 bug;但本 audio change 不动这两个文件
(`git diff main..HEAD -- src/framework/runtime/executors/generate_image.py
src/framework/runtime/executors/generate_mesh.py` 应为 empty diff)。

### G6-F1/F4 静态文件存在性

- `tools/forgeue_verify.py` Level 2 部分:本 change 未 modify
- `.env.example`:本 change 未 modify(`git status` confirms)

## E. Follow-on 注册

| Finding | Follow-on change | Priority |
| --- | --- | --- |
| G6-F1 | `forgeue-verify-level2-comfy-bundle-update` | medium(假阳性 verify) |
| G6-F2 + G6-F3 | `comfy-executor-producer-attribution-fix`(image + mesh 同修) | medium(provenance audit) |
| G6-F4 | `env-template-hunyuan-key-alignment` | low(用户配错时静默 fallback) |

本 change archive 不阻断;follow-on 由用户后续 `/opsx:propose` 单独立项。

## F. Verdict

**G6 cross-check disputed_open: 0**;4 finding 全 out-of-scope follow-on;本 change
archive 通过 G6 验证。
