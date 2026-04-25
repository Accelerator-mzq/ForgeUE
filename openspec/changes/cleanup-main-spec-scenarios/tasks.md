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
- [x] 1.4 跑 `python -m pytest -q` —— 848 passed 不变(本 task 是 doc-only,不影响测试)

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
  - **Budget exceeded synthesizes a Verdict** —— 方案 A:把"合成 `budget_exceeded` Verdict 并通过 TransitionEngine 路由"的描述改为按真实终止链路写 —— `BudgetTracker.assert_within(...)` 抛 `BudgetExceeded(RuntimeError)` → `Orchestrator` catch → 写 `run.metrics["termination_reason"]` = `"budget_exceeded(cap=<cap>, spent=<spent>)"` + `last_failure_mode="budget_exceeded"` + `failure_event.decision="human_review_required"`(`Decision` enum 真实成员,非虚构 `budget_exceeded`)→ `run.status=RunStatus.failed` → 返回 `_StepOutcome(terminate=True, next_step_id=None)`;路径覆盖 fresh-execution(`orchestrator.py:566-580`)与 fresh-process resume cache-hit cost replay(`orchestrator.py:428-435`)。Run 不得静默退出。**不**继续保留主 spec 原误写的"合成 Verdict"+"通过 TransitionEngine 路由";**不**写 `Decision` enum 中不存在的 `budget_exceeded` / `abort` 枚举值
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

- [ ] 7.1 为以下 8 个 Requirement 各补 Scenario(其中 Evidence [+1] 写 success-append / crash-no-half 两个):
  - Dual-mode bridge, manifest_only shipped [Min 1]
  - Three-file deliverable [Min 1]
  - UE-side agent supports three domains [Min 1]
  - Naming policy declared per asset [Min 1]
  - Dependencies drive topological order [Min 1]
  - Evidence is append-only and atomic [+1]
  - Bridge never modifies asset content [Min 1]
  - Hardware smoke acceptance [Min 1]
- [ ] 7.2 Scenario 对照:`src/framework/ue_bridge/{manifest_builder,import_plan_builder,permission_policy,evidence}.py`、`ue_scripts/{run_import,evidence_writer,manifest_reader,a1_run}.py`、`tests/integration/test_p4_ue_manifest_only.py`
- [ ] 7.3 `openspec validate ... --strict` + `pytest -q`

## 8. workflow-orchestrator(5 缺)

- [ ] 8.1 为以下 5 个 Requirement 各补 Scenario:
  - Three RunModes share one scheduler [Min 1]
  - Eleven step types are supported [Min 1]
  - Opt-in DAG concurrency [Min 1]
  - Bundle loading goes through the loader [Min 1]
  - Model reference expansion happens before validation [Min 1]
- [ ] 8.2 Scenario 对照:`src/framework/runtime/{orchestrator,scheduler}.py`、`src/framework/workflows/loader.py`、`src/framework/core/{task,enums}.py`、`tests/integration/test_dag_concurrency.py`、`tests/unit/test_workflow_loader_*.py`
- [ ] 8.3 `openspec validate ... --strict` + `pytest -q`

## 9. Full validation

- [ ] 9.1 `openspec validate cleanup-main-spec-scenarios --strict` —— 期望 PASS(0 ERROR)
- [ ] 9.2 `openspec list` —— 期望本 change tasks 全部勾选,只剩 archive 阶段的 sync-specs row(若有)未勾
- [ ] 9.3 `python -m pytest -q` —— 期望 848 passed,零回归
- [ ] 9.4 跑 `git status --short` 确认改动只在 `openspec/changes/cleanup-main-spec-scenarios/` 范围内,**未**触动 `openspec/specs/` / `src/` / `tests/` / `docs/` / `README.md` / 其他禁止清单文件

## 10. Codex Review Gate

- [ ] 10.1 跑 `openspec validate cleanup-main-spec-scenarios --strict` 输出贴给 Codex 作为 ground truth
- [ ] 10.2 通过 Codex CLI 跑 review,审查 8 份 delta spec 的 Scenario 是否对齐源码 / 测试 / docs,是否有未实装行为 / 措辞过宽
- [ ] 10.3 按 Codex 反馈循环修复(同 add-run-comparison 的 Codex review 模式;最多 3-4 轮收敛)
- [ ] 10.4 Codex Commit Recommendation = "可以提交" 后才进入 Task 11

## 11. Archive cleanup-main-spec-scenarios

- [ ] 11.1 `openspec archive cleanup-main-spec-scenarios -y` —— 默认带 strict validate,**不**用 `--no-validate` / `--skip-specs` 绕过
- [ ] 11.2 archive 应当成功(因为本 change delta 给所有缺失 Scenario 补齐,rebuilt main spec 通过 strict)
- [ ] 11.3 archive 后跑 `openspec validate --specs --strict` —— 期望 8/8 PASS
- [ ] 11.4 archive 后跑 `python -m pytest -q` —— 期望 848 passed

## 12. Return to archive add-run-comparison-baseline-regression

- [ ] 12.1 `openspec archive add-run-comparison-baseline-regression -y` —— 现在应当一次通过(它自己的 delta 早已 strict PASS,卡住的是 main spec rebuild,本 cleanup 修了那条卡点)
- [ ] 12.2 archive 后:`openspec list` 不再含两个 active change;主 spec 含 `add-run-comparison-baseline-regression` 的 ADDED Requirements;`pytest -q` 仍 848 passed
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
