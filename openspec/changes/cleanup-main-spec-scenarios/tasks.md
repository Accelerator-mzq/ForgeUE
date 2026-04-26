# Tasks: cleanup-main-spec-scenarios

> 本 change 是 OpenSpec workflow hygiene fix,目标:8 份主 spec 通过 `openspec validate --specs --strict`,解锁 `add-run-comparison-baseline-regression` archive。**不**修改 ForgeUE 运行时代码 / 测试 / docs 五件套。
>
> 推进节奏:Task 1-8 每份主 spec 各占一 task(逐 spec 推进,每 task 跑 strict validate);Task 9 全量验证;Task 10 Codex review;Task 11 archive cleanup;Task 12 回头 archive `add-run-comparison-baseline-regression`。

---

## 1. artifact-contract(5 缺 Scenario)

- [x] 1.1 把 `openspec/changes/cleanup-main-spec-scenarios/specs/artifact-contract/spec.md` 的 "Plan" 段转为 `## MODIFIED Requirements`,为以下 5 个 Requirement 各补 Scenario:
  - Two-segment artifact type [Min 1] — 1 Scenario
  - Modality-specific metadata is required [+1] — 2 Scenario
  - Lineage is tracked end-to-end [+1] — 2 Scenario
  - Four-layer validation on store entry [+1] — 2 Scenario
  - DAG-safe producer lookup [Min 1] — 1 Scenario
- [x] 1.2 Scenario 内容对照源码:`src/framework/core/artifact.py`(ArtifactType / Modality / PayloadRef / Lineage 字段);测试:`tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict`(lineage selected_by_verdict_id 路径);LLD §5(modality 字段表)
- [x] 1.3 跑 `openspec validate cleanup-main-spec-scenarios --strict` —— Task 1 完成时 artifact-contract delta 已合规,其他 7 份 spec 用 `## Planned Requirement Updates` placeholder 段(不当 delta 解析),validate 不再因 "empty MODIFIED section" 报错
- [x] 1.4 跑 `python -m pytest -q` —— 数量以实测为准;本 task 是 doc-only,不影响测试(`pytest -q` / `pytest --collect-only -q | tail -5` 是真源,见 §3.1 收紧后的 `Test totals are never hardcoded` 描述)

**Task 1 Codex review fix**(2026-04-26 Task 10 review 后落地):Task 10 Codex review 发现 artifact-contract delta 含多处 false claims,本 commit 按 M2 实证验证 + M3.2 修复策略**重写 6 个 Scenario** 与**收紧 3 个 Requirement 描述**:
- **重写 Scenario S1**(Two-segment artifact type)—— 删 `display_name` 反向解析虚构;改写为 `internal` `@property` 单向拼接 + `display_name` 独立 author-declared 字段
- **重写 Scenario S2**(Modality-specific metadata)—— 删"image artifact 缺 width/height 在 metadata layer 被拒"虚构;改写为 executor convention(`generate_mesh.py:139-151` 真实写 metadata,`put` 接受 dict as-is)
- **重写 Scenario S4**(Lineage source_step_ids)—— 修 producer-vs-upstream 错位:`source_step_ids=[ctx.step.step_id]` 是 producer step id,不是 upstream consumed step id;此处是 M2 实证发现 Codex 漏报的第 6 处虚构
- **重写 Scenario S5**(Lineage selected_by_verdict_id)—— 删 mesh executor 设 `selected_by_verdict_id = verdict id` 虚构;改写为 `source_artifact_ids` 承载(`test_l4_image_to_3d.py:351` 真实断言),`selected_by_verdict_id` 标注为 reserved future-use field
- **重写 Scenario S6 / S7**(Four-layer validation)—— 删 store-entry 4 层 gate 虚构;S6 改写为 `put` 真实三步边界(write payload → hash → register),S7 改写为 pipeline-stage layered(DryRunPass / executor / manifest_builder + ExportExecutor.validate_manifest / ue_bridge.inspect)
- **收紧 Requirement 描述**(3 处,标题保留为历史命名):
  - `Two-segment artifact type` —— 删"bidirectional mapping",改为 `modality + shape` 字段 + `internal` 单向拼接 + `display_name` 独立标签;明示无反向 parser
  - `Lineage is tracked end-to-end` —— 明确 `source_artifact_ids` 是 upstream / `source_step_ids` 是 producer step id;`selected_by_verdict_id` 标注为 reserved future-use slot,当前 executors 不填充
  - `Four-layer validation on store entry` —— 改为 layered across pipeline stages 描述,明列 4 个真实校验阶段(dry-run preflight / executor-side / manifest build / ue_bridge.inspect),`put` 真实三步边界声明
- **保留**:Scenario S3(Mesh metadata)+ Scenario S8(DAG-safe producer lookup)+ Requirement 标题全部 5 个 + Requirements 2 / 6 描述
- **不改主 spec**(`openspec/specs/artifact-contract/spec.md` 不动,archive 时由 sync-specs 合并 delta 进主 spec)
- **未勾 Task 10**(Codex review 仍待收敛后再勾;本 commit 是 Task 10.3 修复循环的一轮)

**Task 1 hygiene note**(2026-04-25 方案 E 落地):为保持 active change strict validate **完全 PASS**,Task 2-8 未实施前其对应 Plan 内容**已从 specs/ 移出到 notes/**,完整路径如下:

| Task | Plan 来源(已删) | Plan 现位置(notes/) |
|---|---|---|
| 2 examples-and-acceptance | `specs/examples-and-acceptance/spec.md`(skeleton)| `notes/examples-and-acceptance-plan.md` |
| 3 probe-and-validation | 同上 | `notes/probe-and-validation-plan.md` |
| 4 provider-routing | 同上 | `notes/provider-routing-plan.md` |
| 5 review-engine | 同上 | `notes/review-engine-plan.md` |
| 6 runtime-core | 同上 | `notes/runtime-core-plan.md` |
| 7 ue-export-bridge | 同上 | `notes/ue-export-bridge-plan.md` |
| 8 workflow-orchestrator | 同上 | `notes/workflow-orchestrator-plan.md` |

`openspec/changes/cleanup-main-spec-scenarios/specs/` 现**只**含 `artifact-contract/spec.md`(Task 1 完整实装)。OpenSpec validate 不再因"未实施 spec 缺 delta 段"报错。

**Task 2-8 启动协议**:从对应 `notes/<capability>-plan.md` 读 Plan(每个 Requirement 的标记 / 现状 / Scenario 草案 / 真源参考),在 `specs/<capability>/spec.md` 新建文件并写入正式 `## MODIFIED Requirements` 块(每个 Requirement 复用主 spec 描述 + 追加 `#### Scenario:`)。

## 2. examples-and-acceptance(7 缺,1 [审视])

- [x] 2.1 措辞收紧:`No hardcoded provider model ids` —— 在 delta spec MODIFIED 块中重写 Requirement 描述。**采用方案 A**:硬约束"every bundle under `examples/` SHALL declare model selection via `models_ref`;concrete provider model ids MUST live in `config/models.yaml.models`",同时**保留** schema 已允许的 Step-scoped `preferred_models` / `fallback_models` 逃生口,但限定其条目必须是 `config/models.yaml.models` 已注册的 model id(堵裸字符串 bypass registry 漏洞)。**不**引入 LIVE bundle frontmatter 例外(JSON 没有 frontmatter 概念,且当前 10 份 bundle 实证全部走 `models_ref`,没有 LIVE override 路径需要写契约)。**不**改 Requirement 标题
- [x] 2.2 为以下 7 个 Requirement 各补 Scenario(包括 §2.1 收紧后的那条):
  - Bundle is the end-to-end acceptance artifact [Min 1]
  - UTF-8 bundles go through the loader [Min 1]
  - Alias-based model references [Min 1]
  - No hardcoded provider model ids [审视 + Min 1]
  - Stage-aligned acceptance coverage [Min 1]
  - Live bundles carry premium-API warnings [Min 1]
  - UE hardware smoke is reachable via commandlet [Min 1]
- [x] 2.3 Scenario 对照:`framework/workflows/loader.py`、`tests/integration/test_p[0-4]_*.py`、`examples/*_live.json`、`ue_scripts/a1_run.py`
- [x] 2.4 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 3. probe-and-validation(10 缺,2 [审视])

- [x] 3.1 措辞收紧 2 处,**两条 [审视] 项均采用方案 A**(把流程承诺改为可静态识别的样板):
  - `Regression fence per review fix` —— 方案 A:把 "every Codex / adversarial review fix" 放宽为 "fix 触发 executable behaviour change(runtime / executor / provider adapter / schema / worker code)时" 必须新增或扩展 fence test;documentation-only / doc-drift-only fix 可走 review note / validation note(不强制 test);引用 `tests/unit/test_codex_audit_fixes.py` 的 numbered comment blocks(`# #1` … `# #11`)作为 2026-04-22 Codex 21-condition audit 的历史 evidence pattern;开放 peer fence files(`test_cascade_cancel` / `test_review_budget` / `test_download_async` / `test_event_bus`)作为合法 fence 着陆点。**不**断言"所有未来 review fix 必须新增 test";**不**写 CI gate / 自动 enforcement
  - `Test totals are never hardcoded` —— 方案 A:区分两类文档 ——(a)用户入口文档(`README.md` / `validation_matrix.md` / `openspec/specs/*` / `openspec/changes/*/proposal.md` / `design.md` / `tasks.md`)禁止裸数字写 aggregate test count;(b)长篇叙事文档(`test_spec.md` / `acceptance_report.md` / `CHANGELOG.md`)允许 snapshot count 但每次出现必须带 date stamp(如 `2026-04-25 实测 848 用例` / `2026-04-23 历史基线 549`);真源是 `python -m pytest -q` / `python -m pytest --collect-only -q | tail -5`。**不**扩大到"任何数字都不能出现",只管 aggregate test count(timeouts / fixture counts / retry budgets 不受影响)
- [x] 3.2 为以下 10 个 Requirement 各补 Scenario,合计 11 个 Scenario(`Probe exit code convention` 写 2 个覆盖 all-OK 与 has-fail 两侧):
  - Probe directory layout [Min 1]
  - Probe naming [Min 1]
  - Module-level side-effect ban [Min 1]
  - ASCII output markers [Min 1]
  - Probe exit code convention [+1]
  - Probe output path convention [Min 1]
  - Regression fence per review fix [审视 + Min 1]
  - Critical-boundary objects are real, not mocked [Min 1]
  - Validation stratification into three levels [Min 1]
  - Test totals are never hardcoded [审视 + Min 1]
- [x] 3.3 Scenario 对照:`probes/README.md` §"目录结构"/§"命名约定"/§5 输出路径、`probes/_output.py::probe_output_dir`、`probes/smoke/probe_framework.py`、`tests/unit/test_probe_framework.py`(side-effect / tristate / opt-in fence)、`tests/unit/test_codex_audit_fixes.py`(numbered comment blocks `# #1` … `# #11`)、`tests/unit/test_event_bus.py`(真 asyncio.Queue + call_soon_threadsafe)、`docs/ai_workflow/validation_matrix.md`(三级分层 + 不硬编码总数原文)
- [x] 3.4 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 4. provider-routing(16 缺,最大份)

- [x] 4.1 为以下 16 个 Requirement 各补 Scenario,合计 17 个 Scenario(`Pricing probe defaults to dry-run` [+1] 写 dry-run + `--apply` 两个;**Scenario 7b 采用方案 A**:按真实代码行为写 `--apply` 路径 —— `apply_results_to_yaml(... dry_run=False)` mutate `config/models.yaml`,`pricing_autogen.status: manual` 条目保留不动;**不**写 `--apply` 写 `demo_artifacts/<date>/pricing/<HHMMSS>/` snapshot(实证:cli.py / yaml_writer.py 没有该路径写入逻辑;CLAUDE.md §产物路径约定那条仅为路径**约定**,不是实装产物;notes/provider-routing-plan.md 原 Scenario 草案与代码事实不符,本 delta 已纠偏)。其余 15 个 Requirement 描述与标题保持不变(本 capability 无 [审视] 项):
  - Three-section ModelRegistry is the single source [Min 1]
  - Alias reference expansion in the loader [Min 1]
  - OpenAI-compatible endpoints add zero code [Min 1]
  - Non-OpenAI protocols ship dedicated adapters [Min 1]
  - Capability aliases drive provider selection [Min 1]
  - Route pricing is stashed on every ProviderResult [Min 1]
  - Pricing probe defaults to dry-run [+1]
  - External factual pricing requires a verifiable source [Min 1]
  - URL-rank fallthrough for mesh worker [Min 1]
  - Range-resume integrity [Min 1]
  - Magic-bytes format gate [Min 1]
  - Case-insensitive data: URI [Min 1]
  - tokenhub poll timeout is clamped [Min 1]
  - HTML-body pollution wraps as unsupported [Min 1]
  - Premium-API single-attempt guard [Min 1]
  - Parallel candidates are homogeneous [Min 1]
- [x] 4.2 Scenario 对照:`src/framework/providers/model_registry.py`(三段式 + autogen 校验)、`src/framework/providers/{litellm_adapter,qwen_multimodal_adapter,hunyuan_tokenhub_adapter}.py`(wildcard / prefix supports)、`src/framework/providers/_download_async.py`(206 + Content-Range)、`src/framework/providers/workers/mesh_worker.py`(`_rank_hunyuan_3d_urls` 五桶 / `_build_candidate` magic / `_is_data_uri` RFC2397 / `_atokenhub_poll` clamp / `_apost` no-retry)、`src/framework/workflows/loader.py`(expand_model_refs)、`src/framework/pricing_probe/{cli,yaml_writer}.py`(dry-run + manual-skip)、`config/models.yaml`(三家 OpenAI-compatible provider 实证)、`tests/unit/test_model_registry.py` / `test_router_pricing_stash.py` / `test_pricing_probe_framework.py` / `test_download_async.py` / `test_cn_image_adapters.py` / `test_codex_audit_fixes.py`(audit `# #4` poll clamp / `# #3` HTML body / `# #9` parallel hetero) / `test_mesh_no_silent_retry.py`(三层 fence) / `test_pr3_cleanup_fences.py`(case-insensitive 同款式)
- [x] 4.3 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 5. review-engine(8 缺)

- [x] 5.1 为以下 8 个 Requirement 各补 Scenario(合计 8 个 Scenario);**实证检查发现 2 处主 spec 与代码命名漂移**,**Nine decision enums** 与 **Five-dimension scoring** 两条均采用方案 A 收紧描述以对齐真实代码,**保留 Requirement 标题不变**:
  - **Nine decision enums** —— 方案 A:描述明列 `framework.core.enums.Decision` 当前 10 个成员(`approve` / `approve_one` / `approve_many` / `reject` / `revise` / `retry_same_step` / `fallback_model` / `abort_or_fallback` / `rollback` / `human_review_required`),标题中 "Nine" 注解为历史命名,authoritative 真源为 `Decision` enum 自身。**不**继续保留主 spec 原误写的 `accept` / `escalate_human` / `stop` 这三个代码不存在的成员
  - **Five-dimension scoring** —— 方案 A:字段名改 `scores_by_candidate: dict[str, DimensionScores]`(原误写 `scores_by_dimension`),5 维度名改代码实际 `constraint_fit` / `style_consistency` / `production_readiness` / `technical_validity` / `risk_score`(原误写 `quality` / `consistency` / `ue_compliance` / `aesthetics` / `technical_correctness`),引用 `rubric_templates/*.yaml` 三套 YAML 与之一致
  - 其余 6 条不动描述,仅补 Scenario:
    - Confidence threshold governs revise [Min 1]
    - Panel runs in parallel [Min 1]
    - Review usage flows into BudgetTracker [Min 1]
    - Visual-review payload is summarized, not raw bytes [Min 1]
    - SelectExecutor bare-approve semantics [Min 1]
    - Mesh reads review-selected image via verdict priority [Min 1]
- [x] 5.2 Scenario 对照:`src/framework/core/{enums,review}.py`(Decision enum / DimensionScores / Verdict / ReviewReport)、`src/framework/review_engine/{judge,chief_judge,report_verdict_emitter}.py`(asyncio.gather panel / pass_threshold judge / weighted_score)、`src/framework/review_engine/rubric_templates/*.yaml`(三套 rubric criteria.name 实证)、`src/framework/runtime/executors/{select,generate_mesh}.py`(bare-approve / `_resolve_source_image` 4-pass)、`tests/unit/test_chief_judge_parallel.py` / `test_review_budget.py` / `test_review_payload_summarization.py` / `test_codex_audit_fixes.py`(`# #10` SelectExecutor bare-approve)、`tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict`
- [x] 5.3 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 6. runtime-core(7 缺)

- [x] 6.1 为以下 7 个 Requirement 各补 Scenario,合计 9 个 Scenario(两条 [+1] 各 2 个);**实证检查发现 1 处主 spec 与代码命名漂移**,**Budget exceeded synthesizes a Verdict** 采用方案 A 收紧描述以对齐真实代码,**保留 Requirement 标题不变**:
  - **Budget exceeded synthesizes a Verdict** —— 方案 A:把"合成 `budget_exceeded` Verdict 并通过 TransitionEngine 路由"的描述改为按真实终止链路写 —— `budget_tracker.check()` 返回 `False`(`if not budget_tracker.check():` bool branch)→ `Orchestrator` direct termination(**不**调 `assert_within()`,**不** catch `BudgetExceeded`):
    - **共享 4 字段**(fresh-execution `orchestrator.py:566-580` 与 resume cache-hit `orchestrator.py:428-435` 都写):`run.metrics["termination_reason"]` = `"budget_exceeded(cap=<cap>, spent=<spent>)"` + `run.metrics["last_failure_mode"] = "budget_exceeded"` + `run.status = RunStatus.failed` + 返回 `_StepOutcome(terminate=True, next_step_id=None)`
    - **fresh-execution 额外** append `result.failure_events`,decision tag 为 `"human_review_required"`(`Decision` enum 真实成员,非虚构 `budget_exceeded`)
    - **resume cache-hit 不** append `failure_events`(只写 4 个共享字段;Codex Round 2 修正:Step 6.1 原备注误写两路径 metrics identical)
    - Run 不得静默退出
    - **不**继续保留主 spec 原误写的"合成 Verdict"+"通过 TransitionEngine 路由";**不**写 `Decision` enum 中不存在的 `budget_exceeded` / `abort` 枚举值;`BudgetExceeded` class 与 `assert_within()` 在 `BudgetTracker` API 上存在但 Orchestrator 主路径不使用 —— **本备注 2026-04-26 Codex Round 2 Medium Risk self-consistency 修复**(原 Step 7b 改了 Requirement 主体但未同步本备注链路细节,Round 2 抓出残留)
  - 其余 6 条不动描述,仅补 Scenario:
    - `load_run_metadata` performs three-stage filtering [+1] —— 2 个 Scenario(已知 + 缺 payload / file-blob hash drift)
    - TransitionEngine is isolated per `arun` [Min 1]
    - Unsupported-response short-circuit at three layers [+1] —— 2 个 Scenario(Layer 1 transient_check / Layer 2 router re-raise + Layer 3 executor _should_retry)
    - Premium-API single-attempt contract [Min 1] —— runtime 视角(GenerateMeshExecutor attempts=1 + stderr surface),Task 4 provider-routing 视角的 `Premium-API single-attempt guard` 不重复
    - EventBus is loop-aware and thread-safe [Min 1]
    - WebSocket idle-disconnect is leak-free [Min 1]
- [x] 6.2 Scenario 对照:`src/framework/artifact_store/repository.py`(load_run_metadata 三段式)、`src/framework/runtime/{transition_engine,budget_tracker,failure_mode_map,orchestrator}.py`(cloned_for_run / BudgetExceeded / cap miss 双路径)、`src/framework/runtime/executors/{generate_image,generate_image_edit,generate_structured,generate_mesh}.py`(`_should_retry` 首行 + mesh `attempts=1`)、`src/framework/providers/{_retry_async,capability_router,workers/mesh_worker}.py`(transient_check / 4 处 router re-raise / `_apost` 不包 retry)、`src/framework/observability/event_bus.py`(threading.Lock + call_soon_threadsafe)、`src/framework/server/ws_server.py`(FIRST_COMPLETED race)、`src/framework/run.py:240-264`(stderr `[mesh]` block)、`tests/unit/test_codex_audit_fixes.py`(`# #2` resume / `# #4` clamp / `# #8` cloned / `# #9` parallel / FR-RUNTIME-008/009 fence)、`tests/unit/test_{budget_tracker,event_bus,mesh_no_silent_retry,review_budget}.py`、`tests/integration/test_{ws_progress,mesh_failure_visibility}.py`
- [x] 6.3 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 7. ue-export-bridge(8 缺)

- [x] 7.1 为以下 8 个 Requirement 各补 Scenario,合计 9 个 Scenario(`Evidence is append-only and atomic` [+1] 写 success-append / crash-no-half 两个);**8 个 Requirement 描述与标题保持不变**(本 capability 无 [审视] / 无 doc drift 收紧需要);**Scenario 4 / Scenario 7 已按代码事实纠偏**:
  - **Scenario 4**(Naming policy declared per asset)—— notes/plan 第 28 行原草案 "Asset entry without a declared `naming_policy` fails dry-run validation before any UE-side execution" 与代码事实不符(grep 验证 `dry_run_pass.py` 无 naming_policy 校验逻辑)。本 delta 改用代码事实:`UEOutputTarget.asset_naming_policy: Literal["gdd_mandated", "house_rules", "gdd_preferred_then_house_rules"]`(`src/framework/core/ue.py:20-22`)由 Pydantic 在 `UEOutputTarget.model_validate` 时校验(其他字符串拒绝),`manifest_builder._derive_ue_name(art, kind, policy=target.asset_naming_policy)`(`manifest_builder.py:101 / 113 / 150 / 164`)在每个 asset 的 manifest 构造时用同一 target 的 policy。**不**写"dry-run 拦截"
  - **Scenario 7**(Bridge never modifies asset content)—— notes/plan 第 48 行原草案 "Imported texture file's bytes match source file's bytes" 是 UE-internal byte equality,框架侧无法直接断言(UE 的 `AssetImportTask` 内部处理 `.uasset` 写入)。本 delta 改用框架/UE-script 侧 no-transform 断言:`ExportExecutor` 落 file-backed payload 走 copy 不 transcode,`domain_texture.import_texture_entry` 把源文件路径直接传给 `unreal.AssetImportTask.filename`,引用 `test_p4_ue_scripts_run_import_with_stub_unreal`(line 398-528)stub `unreal` 验证框架 / script 侧不改字节。**不**断言 UE 内部导入后 `.uasset` 字节相等
  - 其余 7 条 Scenario 直接按 §3 计划落地:
    - Dual-mode bridge, manifest_only shipped [Min 1] —— `ImportMode` enum + `execute/` 目录无实装代码
    - Three-file deliverable [Min 1] —— `test_p4_full_pipeline_writes_manifest_plan_and_evidence` 守门
    - UE-side agent supports three domains [Min 1] —— `_OP_HANDLERS` 三键 + 域外 kind 走 skipped
    - Dependencies drive topological order [Min 1] —— `import_plan_builder` `depends_on=[folder_op_id]` + `manifest_reader.topological_ops`
    - Evidence is append-only and atomic [+1] —— success-append / crash-mid-write 两 Scenario(tmp + `tmp.replace` POSIX/NTFS atomic rename)
    - Hardware smoke acceptance [Min 1] —— `a1_run.py` commandlet entry + offline stub + 2026-04-23 a1_demo 历史轨迹
- [x] 7.2 Scenario 对照:`src/framework/core/{enums,ue}.py`(`ImportMode` / `UEOutputTarget` Literal)、`src/framework/ue_bridge/{manifest_builder,import_plan_builder,evidence}.py`(`_derive_ue_name` / `depends_on` / atomic write)、`src/framework/ue_bridge/execute/`(空目录,bridge_execute reserved 实证)、`ue_scripts/{run_import,evidence_writer,manifest_reader,a1_run,domain_texture,domain_mesh,domain_audio}.py`(`_OP_HANDLERS` / append + tmp.replace / commandlet 入口)、`tests/unit/test_ue_bridge.py::test_evidence_writer_appends_atomically` / `::test_plan_builder_adds_create_folder_and_dependencies`、`tests/integration/test_p4_ue_manifest_only.py::test_p4_full_pipeline_writes_manifest_plan_and_evidence` / `::test_p4_ue_scripts_run_import_with_stub_unreal` / `::test_p4_verdict_reject_skips_file_drop`、`docs/acceptance/acceptance_report.md` §6.1(2026-04-23 a1_demo)、`examples/{image_to_3d_pipeline_live,ue_export_pipeline_live}.json`(`asset_naming_policy: house_rules` 实证)
- [x] 7.3 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 8. workflow-orchestrator(5 缺)

- [x] 8.1 为以下 5 个 Requirement 各补 Scenario,合计 5 个 Scenario;**实证检查发现 1 处主 spec 与代码命名漂移**,**Eleven step types are supported** 采用方案 A 收紧描述以对齐真实代码,**保留 Requirement 标题不变**:
  - **Eleven step types are supported** —— 方案 A:描述明列 `framework.core.enums.StepType` 当前 11 个实际成员(`generate` / `transform` / `review` / `select` / `merge` / `validate` / `export` / `import_` 暴露为 `"import"` / `retry` / `branch` / `human_gate`),**不**继续保留主 spec 原误写的 `inspect` / `plan` / `execute` / `custom`(代码不存在),**补上**代码实有的 `merge` / `retry` / `branch` / `human_gate`(原 spec 列表未列);明确 dispatch 通过 `framework.runtime.executors.base.ExecutorRegistry` 用 `(step_type, capability_ref)` 键;声明默认 `framework.run._build_orchestrator` 只为 `generate` / `validate` / `review` / `select` / `export` 与 mock variants 注册 executor,其他 StepType 是保留枚举值,调用方可通过 `ExecutorRegistry.register(...)` 注册自定义 executor;未注册的 `(step_type, capability_ref)` 在 `resolve` 时抛 `KeyError(f"No executor for step_type=... capability_ref=...")`;标题 "Eleven" 保留为历史命名(成员数确实是 11,但权威成员清单以 `StepType` enum 为准)。**notes/plan 第 16 行 "Scheduler.dispatch" 草案已纠偏**:真实 dispatch 路径是 `Orchestrator` 通过 `ExecutorRegistry.resolve`,Scheduler 类只有 `prepare` / `default_next` / `risk_sort` / `runnable_after`,无 `dispatch` 方法
  - 其余 4 条不动描述,仅补 Scenario:
    - Three RunModes share one scheduler [Min 1]
    - Opt-in DAG concurrency [Min 1] —— `task.constraints["parallel_dag"]` 或 `workflow.metadata["parallel_dag"]` 短路 OR
    - Bundle loading goes through the loader [Min 1] —— framework / CLI / integration tests 通过 loader,不延伸到任意用户脚本
    - Model reference expansion happens before validation [Min 1] —— 顺序 `read_text` → `json.loads` → `expand_model_refs` → Pydantic validation;alias miss 在 expansion 阶段抛 `UnknownModelAlias`
- [x] 8.2 Scenario 对照:`src/framework/core/enums.py`(`RunMode` 三成员 / `StepType` 11 成员实证)、`src/framework/runtime/scheduler.py`(单 Scheduler 类无 RunMode import)、`src/framework/runtime/orchestrator.py:157-162`(parallel_dag 短路 OR 双源)、`src/framework/runtime/executors/base.py:54-67`(`ExecutorRegistry.register` / `.resolve` 用 `(step_type, capability_ref)` 键 + 未匹配 KeyError)、`src/framework/run.py:140`(`load_task_bundle` 单一入口)、`src/framework/workflows/loader.py:31-37`(`read_text` UTF-8 → `json.loads` → `expand_model_refs` → Pydantic 顺序)、`tests/integration/test_p[0,2,3]_*.py`(三 RunMode 共享 Scheduler)、`tests/integration/test_dag_concurrency.py`(`test_dag_fans_out_leaves_concurrently` / `test_workflow_metadata_parallel_dag_activates_fanout` / `test_linear_mode_still_sequential`)、`tests/integration/test_example_bundles_smoke.py::test_bundle_loads`、`tests/unit/test_model_registry.py::test_expand_unknown_ref_raises`、CLAUDE.md "Bundle JSON 编码"段
- [x] 8.3 `openspec validate cleanup-main-spec-scenarios --strict` + `pytest -q`(以实测为准,本 task 是 doc-only,不影响测试)

## 9. Full validation

- [x] 9.1 `openspec validate cleanup-main-spec-scenarios --strict` —— PASS(0 ERROR);8 份 capability delta 全部合规
- [x] 9.2 `openspec list` —— cleanup-main-spec-scenarios 显示 27/54 tasks(Task 1-8 capability delta 全部勾选;Task 9 自身 4 checkbox 与 Task 10-12 + Documentation Sync 段待按阶段推进时勾选);active change 状态健康,无 stale entry
- [x] 9.3 `python -m pytest -q` —— 与 cleanup 启动前基线一致,零回归;数量以实测为准(不硬编码,见 §3.1 收紧后的 `Test totals are never hardcoded` 描述)
- [x] 9.4 全量结构检查通过:`git status --short` 干净,`git diff --name-only` 空,改动仅落在 `openspec/changes/cleanup-main-spec-scenarios/` 范围内,**未**触动 `openspec/specs/` / `src/` / `tests/` / `docs/` / `README.md` / 其他禁止清单文件;8 份 delta spec(`artifact-contract` / `examples-and-acceptance` / `probe-and-validation` / `provider-routing` / `review-engine` / `runtime-core` / `ue-export-bridge` / `workflow-orchestrator`)全部存在;7 份 notes plan(对应 Task 2-8 的 plan-as-source-of-truth)全部保留;正式 delta spec 内 stale 文本扫描 0 blocker(动词 / 真实 enum 值 / 显式 drift-callout 反例标记 / ADR-004 行为约定引用 均合规);pre-Codex polish 已落地(commit 305dcd9 修掉 tasks.md 4 处裸数字 `848`,与 §3.1 收紧描述自洽)

## 10. Codex Review Gate

- [x] 10.1 `openspec validate cleanup-main-spec-scenarios --strict` —— PASS(`Change 'cleanup-main-spec-scenarios' is valid`,本地 shell 跑;Codex sandbox 因 policy 拦截 `openspec` CLI(`rejected: blocked by policy`),需本地代跑;Round 3 Codex 明确说"无需改文件,请在允许执行 `openspec` 的本地 shell 中运行 strict validate 把真实输出补到 Task 10.1 所需证据链"——已补,2026-04-26)
- [x] 10.2 通过 Codex CLI(via codex:codex-rescue subagent)跑了 3 轮 review,逐 Scenario / 逐 Requirement 描述 + 源码 / 测试交叉核对(详见下方 review-fix log 各 Round 段);未实装行为 / 措辞过宽全部按方案 A 收紧描述 + 重写 Scenario(artifact-contract / runtime-core)或措辞调整(ue-export-bridge / proposal / design)
- [x] 10.3 三轮收敛,共 3 个修复 commit:**Round 1** 修复 commits 805c7e9 + d65e2ea(7 Blocker + 1 Low Risk + 用户 M2 实证漏报 1 处 = 9 finding),**Round 2** 修复 commit 169fcf2(2 Medium Risk self-consistency),**Round 3** 确认 spec 内容零 finding;在 add-run-comparison 同款 3-4 轮 Codex review 模式中,本 change 用 3 轮收敛
- [x] 10.4 Codex Round 3 **effective Recommendation = "可以进入 Task 10 completion update"**(Codex 形式上写"不建议继续 archive"但理由是其 sandbox policy 拦截 `openspec validate`,**非 spec 内容问题**——其 Suggested Fixes 段明确"无需改文件,本地 shell 跑 strict validate PASS 即可进 Task 10 completion update");本地 strict validate PASS 已补;**Task 11 archive readiness 达成**(但本轮按指令**不**进 Task 11)

**Task 10 review-fix log**(2026-04-26 Codex Round 1 / Round 2 / Round 3 全部完成,§10.1-§10.4 全勾):

- **Round 1 Codex review** (commits 805c7e9 + d65e2ea):
  - Codex Recommendation:**修复后再 review**,7 处 Blocker + 1 处 Low Risk 全部 Confirmed(M2 实证零 false positive,加上用户 grep 漏报 1 处 design.md:124 裸 848,共 9 处 finding)
  - **Step 7a**(commit 805c7e9):artifact-contract delta 6 处 Scenario 重写(S1 / S2 / S4 / S5 / S6 / S7) + 3 处 Requirement 描述收紧(Two-segment / Lineage / Four-layer);保留 S3 / S8 + 5 个 Requirement 标题;详见 §1 Task 1 Codex review fix block
  - **Step 7b**(commit d65e2ea):剩余三类修复
    - **proposal.md / design.md 裸测试总数 4 处**(含 design:124 漏报):全部改为"数量以实测为准"措辞,与 §3.1 收紧后的 `Test totals are never hardcoded` 描述自洽;tasks.md line 55 的 `2026-04-25 实测 848 用例` / `2026-04-23 历史基线 549` 是带 date stamp 的合规样板,保留不动
    - **runtime-core delta `Budget exceeded synthesizes a Verdict`**:Codex Blocker #5 + #6 修复 —— 删 "BudgetExceeded → Orchestrator catch" 虚构链路 + "fresh-execution 与 resume cache-hit metrics identical" 错位断言;改写为真实 `budget_tracker.check() → Orchestrator direct termination` bool-branch 路径;Requirement 描述明列两路径共享 4 个终止字段(`termination_reason` / `last_failure_mode` / `run.status` / 终止 outcome)+ 显式区分 fresh path 额外 append `failure_events`(decision="human_review_required")vs resume cache-hit path 不 append;`BudgetExceeded` class / `assert_within()` 标注为 BudgetTracker API 存在但 Orchestrator 主路径不使用;Requirement 标题保留为历史命名
    - **ue-export-bridge delta Low Risk**:Codex Low Risk 修复 —— 删 "contains only `__init__.py`" 虚构;改为"`execute/` directory is empty (no executor module, not even an `__init__.py`)" + 实证标注(2026-04-26 Bash `ls -la` 与 PowerShell `Get-ChildItem -Force` 双重验证空目录,`Test-Path` 验证 `__init__.py` = False);`bridge_execute` reserved 语义在主 spec Invariants 段保留

- **Round 2 Codex review** (commit 169fcf2):
  - Codex Recommendation:**修复后再 review**;Round 1 finding 全部 confirmed resolved,但发现 **2 处 Medium Risk self-consistency 残留**(Step 7b 改了 Requirement 主体但未同步镜像段)
  - **Step 7c**(commit 169fcf2):
    - **runtime-core/spec.md:3 顶部摘要**:删 "代码实际走 `BudgetExceeded` exception → Orchestrator 直接 terminate 链路";改为 "代码实际走 `budget_tracker.check()` bool branch → Orchestrator direct termination 链路;`BudgetExceeded` class 与 `assert_within()` 在 `BudgetTracker` API 上存在但 Orchestrator 主路径不使用,见 Requirement 主体"
    - **tasks.md:124 Task 6.1 备注**:整段方案 A 描述重写,链路改为 `budget_tracker.check()` 返回 `False`(`if not budget_tracker.check():` bool branch)→ Orchestrator direct termination(**不**调 `assert_within()`,**不** catch `BudgetExceeded`);4 子要点显式列共享 4 字段 / fresh-execution 额外 append / resume cache-hit 不 append(Codex Round 2 修正:Step 6.1 原备注误写两路径 metrics identical)/ 标题保留 + API-存在但不使用注解

- **Round 3 Codex review** (本 commit,Task 10 completion update):
  - Codex 跑通 14m33s(第二次 attempt;首次 `task-mofga4z4-sxgqzm` "Reconnecting 5/5" 偶发 IPC fail 后重发即过,无需重启 daemon)
  - **Codex 确认 Round 1 + Round 2 finding 全部 resolved**:artifact-contract 6 重写 Scenario + 3 收紧描述齐(`artifact-contract/spec.md:3 / 9 / 35 / 51`);runtime-core budget chain top summary + Requirement body 一致(`runtime-core/spec.md:3 / 61 / 67-75`);ue-export-bridge `execute/` 描述准确(`ue-export-bridge/spec.md:13`);proposal/design 无裸 aggregate test count
  - **Codex 内容核对**:Blocker / High / Medium / Low / Missing Docs **全部为零**
  - **Codex 唯一阻塞**:其 sandbox policy 拦截 `openspec validate` 命令(`rejected: blocked by policy`),无法独立 verify strict validate 通过 —— **非 spec 内容问题**
  - **Codex Suggested Fixes**:"无需改文件,请在允许执行 `openspec` 的本地 shell 中运行 strict validate"
  - **本地代跑结果**:`openspec validate cleanup-main-spec-scenarios --strict` 输出 `Change 'cleanup-main-spec-scenarios' is valid`(2026-04-26 Claude Code Bash tool,bypass Codex sandbox policy)
  - **Codex effective Recommendation = "可以进入 Task 10 completion update"**(形式 Recommendation "不建议继续 archive" 是环境 gate,本地 PASS 已消解)

- **未修改**:主 spec(`openspec/specs/`)/ src / tests / docs / 其他禁止清单文件;archive 时由 sync-specs 合并 delta 进主 spec
- **archive 权威版本**:Round 1 / Round 2 / Round 3 收敛后的 delta 描述 + Scenario 是 archive 阶段写入主 spec 的权威版本
- **Task 11 archive readiness 达成**:8 份 delta strict-clean,Codex 三轮 content review 通过,本地 strict validate PASS,测试 0 回归(数量以实测为准);**但本轮按指令不进 Task 11,等下一阶段指令**

## 11. Archive cleanup-main-spec-scenarios

- [ ] 11.1 `openspec archive cleanup-main-spec-scenarios -y` —— 默认带 strict validate,**不**用 `--no-validate` / `--skip-specs` 绕过
- [ ] 11.2 archive 应当成功(因为本 change delta 给所有缺失 Scenario 补齐,rebuilt main spec 通过 strict)
- [ ] 11.3 archive 后跑 `openspec validate --specs --strict` —— 期望 8/8 PASS
- [ ] 11.4 archive 后跑 `python -m pytest -q` —— 期望与 cleanup 启动前基线一致,数量以实测为准(不硬编码)

## 12. Return to archive add-run-comparison-baseline-regression

- [ ] 12.1 `openspec archive add-run-comparison-baseline-regression -y` —— 现在应当一次通过(它自己的 delta 早已 strict PASS,卡住的是 main spec rebuild,本 cleanup 修了那条卡点)
- [ ] 12.2 archive 后:`openspec list` 不再含两个 active change;主 spec 含 `add-run-comparison-baseline-regression` 的 ADDED Requirements;`pytest -q` 数量以实测为准(与 cleanup 启动前基线一致,不硬编码)
- [ ] 12.3 git log 含 cleanup archive + add-run-comparison archive 两个 commit

---

## Documentation Sync

> 本 change 是 hygiene-only,不改 ForgeUE 运行时行为,不引入新 FR / NFR / 用户可见命令。Documentation Sync 范围相应缩小。

- [ ] Check whether openspec/specs/* needs update after archive — **是**(本 change 的核心目的就是更新主 spec;由 archive sync-specs 自动合并)
- [ ] Check whether docs/requirements/SRS.md needs update — **跳过**(无新需求)
- [ ] Check whether docs/design/HLD.md needs update — **跳过**(架构边界未变)
- [ ] Check whether docs/design/LLD.md needs update — **跳过**(接口签名未变)
- [ ] Check whether docs/testing/test_spec.md needs update — **跳过**(无新测试)
- [ ] Check whether docs/acceptance/acceptance_report.md needs update — **跳过**(无新验收项;主 spec strict-clean 不直接对应 FR/NFR 验收)
- [ ] Check whether README.md needs update — **跳过**(用户可见命令未变)
- [ ] Check whether CHANGELOG.md needs update — **评估**(可选加 `[Unreleased].Changed` 一条 "OpenSpec workflow hygiene: 8 main specs now pass strict validation",但不算实质用户可见变更;留 archive 阶段评估)
- [ ] Check whether CLAUDE.md needs update — **跳过**(无新 AI 协作约定)
- [ ] Check whether AGENTS.md needs update — **跳过**(同上)
- [ ] Record skipped docs with reason — 见上述 inline 备注
- [ ] Mark doc drift for human confirmation if sources conflict — Task 1-8 实施时按需记录;预期无 drift(本 change 只补 Scenario,不改 Requirement 标题 / 描述,除 §2.1 / §3.1 显式收紧的 3 条)
