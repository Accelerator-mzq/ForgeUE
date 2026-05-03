---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_design_review.md
plugin_command: "/codex:adversarial-review --background \"design review for comfy-agent-cli-mesh-audio-video-adoption (S2 contract): mesh-only Phase 1 split, capability dispatch via model id, ADR-007 boundary, table-driven _validate_outputs, MeshCandidate metadata\""
plugin_task_id: bd0ufs9r6
detected_env: claude-code
triggered_by: "/forgeue:change-plan (interactive Claude Code session, S2→S3 transition)"
codex_plugin_available: true
created_at: 2026-05-03T13:05:55+08:00
resolved_at: 2026-05-03T13:35:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (4 findings accepted-codex; pending writeback commits — see ## B Resolution column)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 cross-check 在调用 codex /codex:adversarial-review 之前冻结 `## A. Decision Summary` 段,
  以避免 Claude 看完 codex finding 后回填 ## A(协议自我保护)。
  ## B / C / D 在 codex review 落盘后 由 Claude 续写。
  contract_refs 含 4 个 spec delta 文件以确保 codex 同时审 design + 全部 spec deltas。
---

# S2→S3 Design Cross-check: comfy-agent-cli-mesh-audio-video-adoption

## A. Claude's Decision Summary (frozen before codex run, 2026-05-03 13:05 +08:00)

> 本 change 起草时 Claude 的关键判断(冻结于此刻);Claude 不允许在看完 codex review 后回填本段。
> 列出每条决策的具体引用 file:line + 可被质疑的脆弱点(self-criticism),便于 codex / 后续 reviewer 直接对照。

- **D1 — Capability dispatch via model id**(design.md §Decisions D1):`_CAPABILITY_BY_MODEL_ID` 表把 `comfy/local` → `image`、`comfy/local-mesh` → `mesh`,bundle 不引入 `outputs_kind` 字段。**脆弱点**:若 ComfyUI 同一 manifest 既能产 image 又能产 mesh(例如 `02_mini_textured_3d_hunyuan` 同时输出 PNG preview + GLB),capability 由 alias 决定就会 raise on unexpected outputs.images;design D2 守门规则把这种「workflow 顺带产 preview」一并 raise。是否过于严苛?是否应允许 mesh-mode 容忍 outputs.images 作为辅助 preview?

- **D2 — `_validate_outputs` 表驱动单点**(design.md §Decisions D2):`_EXPECTED_OUTPUT_KEY` + `_ALL_OUTPUT_KEYS` 表驱动,switch by `_capability`。**脆弱点**:`_ALL_OUTPUT_KEYS = {"images", "glb", "audio", "video"}` 在 Phase 1 写死,若未来 ComfyUI 暴露新 output key(如 `outputs.video_frames` / `outputs.gif`)会被「any non-expected non-empty」规则拦下,但这种「未知输出」是 raise 还是放行?未明确。本 change 默认 raise(fail-fast),但 follow-on change 接 audio / video 时会扩 `_ALL_OUTPUT_KEYS` 集合,扩之前 ComfyUI 暴露的新 key 会被错误归类为「unexpected」。

- **D3 — Scope split mesh-only**(design.md §Decisions D3):本 change 实际 scope = mesh-only;audio / video 拆 follow-on change(`comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption`);umbrella change name(`comfy-agent-cli-mesh-audio-video-adoption`)保留作为 split 决策的归档入口。**脆弱点**:OpenSpec 实践通常 change name 应反映实际 scope;保留 umbrella name 是反惯例。是否应重命名为 `comfy-agent-cli-mesh-adoption` 更干净?保留 umbrella 是不是给后续 reviewer 制造误导(以为本 change 接了三路)?

- **D4 — ADR-007 边界形式化**(design.md §Decisions D4):本地 ComfyUI mesh `cost_usd=0` → 标准 retry;远端 Hunyuan3D `cost_usd>0` → 严格 no-silent-retry;`route.pricing.input_cost_per_call >= $0.10` 作为「贵族 API」量化判定阈值。**脆弱点**:$0.10 阈值是基于 ADR-007 原文 `~$0.20-1/job` 倒推的,无独立 source;如果 LLM 大模型 per-call cost ≈ $0.05 但确实贵,这个阈值会漏判。是否应该用 `cost_usd > 0 && per_job_user_perceived_cost ≥ N` 的更复杂判定,还是接受 $0.10 这个 round number?另:provider-routing spec 把这条新条款表达为「is_premium(route)」语义,但目前 `BudgetTracker` 没有对应方法,实施阶段需要新增,design 是否应预先列出方法签名?

- **D5 — `MeshCandidate` 不扩字段**(design.md §Decisions D5):mesh 元信息走 `PayloadRef.metadata: dict`;`comfy_manifest` / `comfy_params_snapshot` / `comfy_capability` 三 key。**脆弱点**:`MeshCandidate` 现有字段(`format` / `vertex_count` / `face_count`)由 ComfyUI 输出 metadata 填,但 ComfyUI agent CLI stdout 是否暴露 vertex/face count 在 design 阶段未知(列为 Open Question Q7,推到 tasks §1.5 探明)。如果不暴露,这些字段填 `None`,对下游消费(UE 侧 import 验收 / review_mesh visual)是否有破坏?

- **D6 — Live smoke manifest 名 deferred**(design.md §Decisions D6):tasks §1.2 实施阶段动态确认 manifest 名。**脆弱点**:如果 ComfyUI scripts/ 实际无 mesh manifest 暴露(只有 image),整个本 change 实施 abort。Risks 段提到了这个降级路径,但 design 未给出 abort 后的 fallback 决策(是否回退到「ComfyUI 长期 image-only,mesh 全走 Hunyuan3D」?如果是,SRS §7.3 TBD-009 行需要怎么改?)

- **D-Capabilities-Section**(proposal.md `## Capabilities`):`New Capabilities` 写「无(Phase 1)」+ 加了非标准的 `### Conditional New Capabilities(Phase 2/3,split 决策依赖)` 段。**脆弱点**:OpenSpec 标准模板 `## Capabilities` 只有 `### New Capabilities` 和 `### Modified Capabilities` 两个子段,`### Conditional New Capabilities` 不在标准内,可能让 `openspec validate --strict` 误读或忽略;实测 strict validate PASS,但 spec 解析器可能只看前两个标准段而对 conditional 段视而不见。

- **D-Spec-MODIFIED-Coverage**(specs/provider-routing/spec.md):本 change 给 `ComfyAgentWorker.__init__` 加了 `model_id` 参数(签名修改),但我**只用了 ADDED Requirements**(`ComfyAgentWorker dispatches by capability inferred from model id` 等),没有 MODIFIED 已有的 image-change Requirement(`ComfyUI worker invokes the agent CLI via subprocess`,该 Requirement 写明了构造参数清单);也没有 MODIFIED `Bundle declaring comfy_workflow + comfy_params resolves through ComfyAgentWorker via worker dispatch` Scenario 中的 worker 构造调用。**这是潜在 D-Spec-MODIFY-Missing**:image-change 已有 Requirement 的 worker 构造签名清单 (`scripts_dir, python_exe, default_lifecycle, run_id, project_id, artifacts_dir`) 现在不完整(缺 `model_id`);理论上应该 MODIFY 已有 Requirement 而不是只 ADD 新的。

- **D-Tasks-CommitOrder**(tasks.md §5/§6):examples bundle(commit 4)先于 fence test(commit 5)。image change 的实践是 fence test 先于 examples,因为 fence 守门 examples loader。**脆弱点**:本 change commit 4 加 bundle 时,fence 还未加(commit 5 才加),如果 bundle 的 `prepared_routes` 解析 / loader 行为有问题,commit 4 head 跑 baseline 549 可能红灯。是否应该把 §5 (examples) 移到 §6 (fence) 之后?

- **D-DryRun-Probe-Extension**(tasks.md §4.5):dry-run 探活把 model id gate 扩为 `model in {"comfy/local", "comfy/local-mesh"}`,复用 `probe_sync`。**脆弱点**:probe 本身和 capability 无关(只测 `comfyui_api status`),但 `ComfyAgentWorker.probe_sync` 当前签名是否需要 `model_id` 参数?如果不需要,本 change 不动 probe;如果未来 audio / video follow-on 加入,probe 也无需扩,只 gate list 变。design 未明确这一点。

- **D-AudioWorker-Coupling-Avoidance**(design.md §Goals / §D3 reasoning):audio follow-on change 标 blocked-on TBD-002,理由是「避免在 ComfyUI audio path 上承担通用 audio worker 契约设计责任」。**脆弱点**:这个 reasoning 是否过度保守?TBD-002 长期未启动,如果用户只想接 ComfyUI audio path 而暂时不需要 AudioCraft 等其它 audio provider,等 TBD-002 反而是过度阻塞。是否应在本 change 内给出「ComfyUI audio first,通用 audio worker 契约在 ComfyUI audio path 上诞生」的备选路径?

## B. Cross-check Matrix

| ID | Claude's choice | Codex's verdict | Codex reasoning(摘要 + file:line) | Resolution | 修复操作(待落盘 + commit) |
|---|---|---|---|---|---|
| **B1 D5 — `MeshCandidate.payload` 不存在** | design D5 + spec/artifact-contract:mesh provenance 走 `MeshCandidate.payload.metadata` + `PayloadRef(kind="file", file=..., metadata=...)` | dispute (high) | `MeshCandidate` 仅有 `data/format/mime_type/poly_count/has_uv/has_rig/metadata`(`mesh_worker.py:64-74`),**无 payload 字段**;`PayloadRef` 仅有 `kind/inline_value/file_path/blob_key/size_bytes`(`artifact.py:12-19`),**无 file 也无 metadata**;`ArtifactRepository.put` 把 candidate bytes 重写到 `<artifact_root>/<run_id>/<artifact_id><suffix>`(`repository.py:73-77`),不直接注册 `artifacts_dir/comfy/<original_filename>` | **accepted-codex** | (1) design D5 重写:provenance 走 `MeshCandidate.metadata["worker_metadata"]`,沿用现有 `ArtifactRepository.put` 持久化路径(它内部用 hash 做 idempotent 写,与 image change 模式一致);文件名约定从「保留 ComfyUI 原文件名」改为「`ArtifactRepository` 自动用 `<artifact_id><suffix>` 命名」;(2) spec/artifact-contract 整段重写:`PayloadRef(kind="file", file=..., metadata=...)` → 改为「`MeshCandidate(data=<bytes>, metadata={...})`,由 `GenerateMeshExecutor` 调 `repo.put(...)` 持久化」;(3) tasks §3.6 同步重写;(4) 删 `Mesh PayloadRef metadata records ComfyUI manifest provenance` Requirement,新加 `Mesh Artifact metadata records ComfyUI manifest provenance` 语义对应改 |
| **B2 — Mesh executor 强依赖 source_image,本 change 未定义 ComfyUI mesh 的 source 语义** | tasks §4.3 `_generate_via_comfy_worker` 只调 `worker.generate(spec=...)`,bundle 只声明 `comfy_workflow / comfy_params / mesh_local`,无上游 image | dispute (high) | `GenerateMeshExecutor.execute` 在 line 67 无条件 `_resolve_source_image(ctx)`,line 90 把 `source_image_bytes=source_bytes` 传给 worker;`MeshWorker.generate` ABC 签名要求 `source_image_bytes: bytes`(`mesh_worker.py:86`);本 change spec 未提任何 source image binding,standalone mesh smoke 会在 `_resolve_source_image` raise | **accepted-codex** | (1) design 加 D7「Comfy mesh source image semantics」决策:本 change 选 **image-to-mesh 路径**(沿用 image change 已有的 image step + DAG 上游模式,等价于 `examples/image_to_3d_pipeline.json`),理由:Hunyuan / Tripo3D mesh worker 已是 image-to-mesh,ComfyUI mesh 沿用同模式可保 lineage 一致 + executor 不分裂;(2) spec/examples-and-acceptance 重写:bundle 必须含上游 image step + DAG 依赖;`comfy_params` 注入约定:source image bytes 由 executor 写入 in-tree input 文件后,把文件路径塞进 `comfy_params["image_path"]`(具体 key 名待 §1.2 + §1.3 探明);(3) spec/provider-routing `GenerateMeshExecutor dispatches comfy/local-mesh ...` Requirement 加「source_image 与现有 mesh worker 同语义」段;(4) tasks §1.2-§1.5 加「确认选定 manifest 是 image-to-mesh 类(接受 input image 参数)」;§4.2 `_generate_via_comfy_worker` 加 `source_image_bytes` 参数;§4.3 `_should_use_comfy_worker_path` 在 `_resolve_source_image` **之后**判定(沿用现有 execute 流程顺序);§5.1 example bundle 加上游 image step;(5) MeshWorker ABC 是否需要扩(允许 source_image_bytes 是 None 走 standalone)留作 follow-on,本 change 不动 ABC 签名 |
| **B3 D4 — ADR-007 premium 判定字段不存在** | design D4 + spec/provider-routing:`route.pricing.input_cost_per_call >= $0.10` + 提议 `BudgetTracker.is_premium(route)` API | dispute (high) | 现有 mesh pricing schema 用 `per_task_usd`(`config/models.yaml:30, 310`);`estimate_mesh_call_cost_usd` 只读 `per_task_usd`(`budget_tracker.py:211-232`);Hunyuan mesh `pricing.per_task_usd: 0.25`;按我 spec 字段实现,远端 Hunyuan3D 不会匹配 premium → ADR-007 边界错误放松 → 双扣费风险回归(正是 ADR-007 起源的 bug) | **accepted-codex** | (1) design D4 重写:premium mesh 判定改为现有字段 `pricing.per_task_usd > 0`(简单 + 与 `estimate_mesh_call_cost_usd` 字段统一);**本 change 不引入** `BudgetTracker.is_premium` 新 API(避免新增表面);spec 描述改为「mesh 路径 `pricing.per_task_usd > 0` 即 premium,走 ADR-007 strict no-silent-retry;`per_task_usd is None or == 0` 视作本地 / 无成本路径,走标准 retry」;(2) spec/provider-routing `Local ComfyUI mesh worker is NOT a premium API` Requirement 重写;Scenario `Local ComfyUI mesh worker_timeout retries via FailureModeMap` / `Remote hunyuan/mesh-generation still refuses silent retry per ADR-007` 同步修;(3) tasks §6.5 fence 名加 `test_mesh_premium_judged_by_per_task_usd_field` + `test_local_comfy_mesh_per_task_usd_None_treated_as_non_premium` |
| **B4 D2 — mesh-mode 严格拒绝 `outputs.images` 可能让全部 manifest 不可用** | design D2 + spec/provider-routing `_validate_outputs`:mesh-mode 拒绝 non-empty `outputs.images / audio / video` | dispute (medium) | image change 归档 spec line 157 明确 `02_mini_textured_3d_hunyuan` 同时产 PNG preview + GLB;design D6 把 manifest 选择推到实施阶段,S2 无证据存在 `outputs.glb` only 的 mesh manifest;若所有 mesh manifest 都带 preview,Phase 1 全部不可落地;实施到 §1.2 `comfyui_api list` 才能发现,abort 风险高 | **accepted-codex** | (1) design D2 重写:mesh-mode 守门改为「**必须** `outputs.glb` non-empty;`outputs.images` non-empty **允许** 视为 auxiliary preview(忽略,不构造 ImageCandidate);`outputs.audio / video` non-empty raise」;表驱动改为「expected REQUIRED key + optional auxiliary key set + rejected key set」三段;(2) spec/provider-routing `ComfyAgentWorker output validation is capability-aware` Requirement 重写表;Scenario `Mesh-mode worker rejects unexpected non-empty outputs.images` → 改为 `Mesh-mode worker accepts non-empty outputs.images as auxiliary preview (ignored)`,加新 Scenario `Mesh-mode worker logs auxiliary outputs.images count for diagnostics`;(3) tasks §3.1 `_ALL_OUTPUT_KEYS` 概念改为 `_REQUIRED_OUTPUT_KEY` + `_AUXILIARY_OUTPUT_KEYS_BY_CAP` + `_REJECTED_OUTPUT_KEYS_BY_CAP` 三表;§6.2 fence 改:`test_mesh_mode_accepts_non_empty_outputs_images_as_auxiliary` 替代 `test_mesh_mode_rejects_unexpected_outputs_images`;(4) audio / video follow-on 同模式约定可在本 change design 末尾加一句「auxiliary 兼容路径同样适用 audio / video capability」 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。4 项 finding 全部 `accepted-codex`,无 `disputed-pending` / `disputed-permanent-drift` 项。

但 contract 回写工作量为 4 高 / 1 中级,预估涉及:
- design.md:D2 / D4 / D5 重写 + 新加 D7 source image 决策 + Risks 段更新
- specs/provider-routing/spec.md:3 个 Requirement 部分重写 + 多个 Scenario 修
- specs/artifact-contract/spec.md:整段重写(去掉 PayloadRef.metadata / file 字段引用,改用 `MeshCandidate.metadata` + `ArtifactRepository.put`)
- specs/examples-and-acceptance/spec.md:加上游 image step 约定 + Scenario 重写
- specs/probe-and-validation/spec.md:fence 名调整(B4 / B3 同步)
- tasks.md:§1.2 / §3.1 / §3.6 / §4.2-4.3 / §5.1 / §6.2-6.5 多处修
- proposal.md:Phase 1 mesh 描述更新(image-to-mesh 路径 + provenance metadata 路径)

writeback 完成后必须重跑 `openspec validate --strict` + `forgeue_change_state.py --writeback-check`,确认 exit 0 才能进 S3。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 对 codex 提的 4 项 finding 逐条独立验证 file:line evidence(2026-05-03 13:25-13:30):

| ID | Codex claim 引用 | Claude verify 命令 + 结果 | 结论 |
|---|---|---|---|
| **B1** | `MeshCandidate` 无 `payload` 字段;`PayloadRef` 无 `file` / `metadata` 字段 | 实测 `Read src/framework/core/artifact.py:12-29` 显示 `PayloadRef` 字段 = `{kind, inline_value, file_path, blob_key, size_bytes}`,**无 file 也无 metadata**;实测 `Read src/framework/providers/workers/mesh_worker.py:64-74` 显示 `MeshCandidate` 字段 = `{data, format, mime_type, poly_count, has_uv, has_rig, metadata}`,**无 payload** | **真实 contract drift,我的 spec 引用了不存在的字段** |
| **B2** | `GenerateMeshExecutor.execute` 无条件 `_resolve_source_image`;`MeshWorker.generate` 要 `source_image_bytes` | 实测 `Bash grep -n "_resolve_source_image\|def execute\|source_image" src/framework/runtime/executors/generate_mesh.py` 显示 line 60 `def execute`,line 67 `source_bytes, source_image_artifact_id = _resolve_source_image(ctx)`(无 if 守门),line 90 `source_image_bytes=source_bytes` 传 worker;实测 `mesh_worker.py:86` ABC 签名 `source_image_bytes: bytes` 是 keyword-only required | **真实 architectural conflict,我的 design / spec / tasks 完全没回答 source image 问题** |
| **B3** | mesh pricing 用 `per_task_usd`,Hunyuan `per_task_usd: 0.25`;我 spec 用不存在的 `input_cost_per_call` | 实测 `Bash grep -n "per_task_usd\|input_cost\|estimate_mesh\|is_premium" src/framework/runtime/budget_tracker.py` 显示 line 211 `def estimate_mesh_call_cost_usd`,line 230 `per_task = (route_pricing or {}).get("per_task_usd")`;实测 `config/models.yaml:310` `per_task_usd: 0.25`(Hunyuan mesh);全文件 grep 无 `input_cost_per_call` 字段 | **真实 schema mismatch,按我 spec 字段实现会让 ADR-007 边界判定永远 False(input_cost_per_call 永远 None),premium 判定全失效** |
| **B4** | image change 归档 spec 已写明 `02_mini_textured_3d_hunyuan` 同时产 PNG + GLB | 实测 `Bash grep "02_mini_textured_3d_hunyuan" archive/2026-05-02-comfy-agent-cli-adoption/specs/provider-routing/spec.md` 命中 line 157 `(a manifest that produces both a PNG preview and a GLB)` | **真实历史证据,我 design D2 守门会把这种"workflow 顺带产 preview"误归类为 unexpected** |

### D.2 Codex 行为可信度

- Codex 在 read-only sandbox 跑(系统拒了 `git status` / `git diff` 第一次,第二次加 `-NoProfile` 才过),所以未能直接落盘 `codex_design_review.md`(本文件由 Claude 代行 verbatim 复制 + 加 frontmatter,见 `codex_design_review.md` frontmatter `note` 段)
- Codex 主动 grep 了 `MeshCandidate` / `PayloadRef` / `ArtifactRepository` / `per_task_usd` 等关键 schema,evidence 引用全部 file:line 化,不是泛泛而谈
- Codex 未提的潜在问题(Claude 自查):**没找到额外 high finding**,但 D-Spec-MODIFIED-Coverage(我自己 ## A 列的 vulnerable 点之一,即 image-change 已有 Requirement 列了 ComfyAgentWorker 构造签名,我加 model_id 参数本应 MODIFY 已有 Requirement)codex 没提 — 这一项作为 P 5 残留 vulnerable,会在 writeback 阶段顺带处理(spec/provider-routing 加 MODIFIED 段或 ADDED Requirement 显式说明「image-change Requirement constructor signature 扩展」)

### D.3 Resolution 的 contract-bound 性

按 forgeue-integrated-ai-workflow 协议「evidence 不能取代 contract」:4 项 accepted-codex 全部需要回写到 design / specs / tasks(已在 ## B Resolution 列详细列出修复操作);**writeback 完成前不允许进入 S3**。当前 `drift_decision: written-back-to-design+specs+tasks`,`writeback_commit: pending` — 真实 commit hash 在系统回写后填入。
