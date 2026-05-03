---
change_id: comfy-agent-cli-audio-adoption
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - design.md
  - tasks.md
  - verification/verify_report.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
codex_plugin_available: true
triggered_by: "/forgeue:change-verify (G6 stage hook /codex:review --base main)"
created_at: 2026-05-03T15:25:00+00:00
plugin_command: "/codex:review --base main"
plugin_task_id: bn2pymr7y
---

# Codex Verification Review (G6) — verbatim output

`/codex:review --base main` 执行结果(plugin task `bn2pymr7y`,2026-05-03 23:25)。
Verdict 段总结 + 4 条 finding(P2/P2/P2/P3)。

## Verbatim codex output

```text
# Codex Review

Target: branch diff against main

补丁中的运行时 provenance 和验证工具存在会误导验收/审计的缺陷,且 env 模板与实际配置项不一致。
虽然核心执行路径大多可运行,但这些问题会让新增 Comfy/Hunyuan 能力被错误验证或错误记录。

Full review comments:

- [P2] 让 live Comfy 验证真正跑 CLI 路径 — D:/ClaudeProject/ForgeUE_claude/tools/forgeue_verify.py:182-187
  当设置 `FORGEUE_VERIFY_LIVE_COMFY=1` 时,这个 Level 2 步骤仍运行旧的 `examples/image_pipeline.json`
  并传 `--comfy-url`;但本补丁里的 `framework.run` 已经忽略该参数并回退到 `FakeComfyWorker`,
  而该 bundle 的 image step 也没有 `comfy/local` route,所以报告会显示 Comfy 验证通过但完全
  没有执行新的 `ComfyAgentWorker` CLI 路径。请改为运行新增的 `examples/comfy_local_smoke*.json`
  (并依赖 `FORGEUE_COMFY_*` env)。

- [P2] 记录真实的 Comfy 图像 producer — D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/executors/generate_image.py:290-290
  在 `comfy/local` 分支里会临时构造 `ComfyAgentWorker`,但后续 artifact producer 和 metrics
  仍从 `self._worker.name` 取值;在 `framework.run` 中这个字段现在总是注入的 `FakeComfyWorker`,
  因此真实本地 ComfyUI 生成的图片会被记录成 `fake_comfy`,影响 provenance、审计和 comparison
  报告。请把实际 worker/provider 名称随该分支结果一起传给持久化逻辑。

- [P2] 避免本地 Comfy mesh 被标成远端 worker — D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/executors/generate_mesh.py:206-206
  当 `prepared_routes` 命中 `comfy/local-mesh` 时,实际执行的是 `_generate_via_comfy_worker`,
  但该分支成功后下面的 artifact producer、cost model 和 metrics 仍使用注入的 `self._worker.name`;
  如果环境里有 `HUNYUAN_3D_KEY`,`framework.run` 会注入 `HunyuanMeshWorker`,导致本地 Comfy
  产物被记录成 Hunyuan/Tripo/Fake mesh。请在 Comfy 分支显式设置 `provider/model/worker`
  为 `comfy_agent_cli` / `comfy/local-mesh`。

- [P3] 在 env 模板中提供运行时实际读取的 Hunyuan 3D key — D:/ClaudeProject/ForgeUE_claude/.env.example:81-83
  复制这个模板后用户只会看到 `HUNYUAN_3D_SECRET_ID/SECRET_KEY/REGION`,但运行时和
  `config/models.yaml` 实际读取的是 `HUNYUAN_3D_KEY`;按模板配置会导致 Hunyuan 3D 路由
  拿不到 key,进而回退到 Tripo/Fake 或在 provider auth 处失败。请补充/改成
  `HUNYUAN_3D_KEY=...`,或同步修改运行时代码读取这些 Secret 字段。
```

## Findings table

| Finding | File:line | Severity | Scope of this change |
| --- | --- | --- | --- |
| G6-F1 forgeue_verify Level 2 跑旧 image_pipeline.json + --comfy-url | tools/forgeue_verify.py:182-187 | P2 | **out-of-scope**(pre-existing tool bug) |
| G6-F2 generate_image.py:290 Comfy 分支 producer 取 `self._worker.name` | src/framework/runtime/executors/generate_image.py:155, 209, 236 | P2 | **out-of-scope**(pre-existing image change bug) |
| G6-F3 generate_mesh.py:206 Comfy mesh 分支 producer 取 `self._worker.name` | src/framework/runtime/executors/generate_mesh.py:265, 308, 315 | P2 | **out-of-scope**(pre-existing mesh change bug) |
| G6-F4 .env.example HUNYUAN_3D_SECRET_ID/KEY/REGION vs 运行时实读 HUNYUAN_3D_KEY | .env.example:81-83 | P3 | **out-of-scope**(pre-existing env template) |

## Resolution preview (full Resolution in `cross_check_g6.md`)

**4 finding 全部 out-of-scope**:本 change 是 audio capability adoption,不动 image
executor / mesh executor / .env.example 模板 / forgeue_verify。Audio executor
`generate_audio.py:142` 已正确做 producer attribution(`provider="comfy_agent_cli"
if chosen_model == "comfy/local-audio"`),与 G6-F2/F3 image/mesh 历史 bug
形成对照(独立验证 file:line 见 `cross_check_g6.md ## D`)。

**Follow-on 建议**:
- G6-F1 → follow-on `forgeue-verify-level2-comfy-bundle-update`
- G6-F2/F3 → follow-on `comfy-executor-producer-attribution-fix`(image+mesh 一起修)
- G6-F4 → follow-on `env-template-hunyuan-key-alignment`

本 change archive 不阻断(out-of-scope finding 不该 block 本 change)。

## References

- Cross-check + independent verification:`cross_check_g6.md`
- Verbatim raw output:`C:/Users/mzq/AppData/Local/Temp/claude/.../tasks/bn2pymr7y.output`
