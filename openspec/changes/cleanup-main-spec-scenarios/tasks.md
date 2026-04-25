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

- [ ] 3.1 措辞收紧 2 处:
  - `Regression fence per review fix` —— 改为可验证的元规则:"任何被 Codex / adversarial review 修复的 issue 必须在同 commit 引入 ≥1 条 fence test;`tests/unit/test_codex_audit_fixes.py` 是这条规则的执行证据"
  - `Test totals are never hardcoded` —— 改为:"OpenSpec change / docs 引用测试总数时必须以 `pytest -q` 当下输出为准,不在文件正文写死数字(历史快照可标 'YYYY-MM-DD 历史基线')"
- [ ] 3.2 为以下 10 个 Requirement 各补 Scenario:
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
- [ ] 3.3 Scenario 对照:`probes/README.md`、`probes/_output.py`、`probes/smoke/probe_framework.py`、`tests/unit/test_probe_framework.py`、`docs/ai_workflow/validation_matrix.md`
- [ ] 3.4 `openspec validate ... --strict` + `pytest -q`

## 4. provider-routing(16 缺,最大份)

- [ ] 4.1 为以下 16 个 Requirement 各补 Scenario(其中 `Pricing probe defaults to dry-run` [+1] 写 dry-run / --apply 两个):
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
- [ ] 4.2 Scenario 对照:`src/framework/providers/{capability_router,model_registry,litellm_adapter,workers/mesh_worker,_download_async}.py`、`config/models.yaml`、`tests/unit/test_*router*.py` / `test_mesh_*.py` / `test_pricing_*.py`、`src/framework/pricing_probe/`
- [ ] 4.3 `openspec validate ... --strict` + `pytest -q`

## 5. review-engine(8 缺)

- [ ] 5.1 为以下 8 个 Requirement 各补 Scenario:
  - Nine decision enums [Min 1]
  - Five-dimension scoring [Min 1]
  - Confidence threshold governs revise [Min 1]
  - Panel runs in parallel [Min 1]
  - Review usage flows into BudgetTracker [Min 1]
  - Visual-review payload is summarized, not raw bytes [Min 1]
  - SelectExecutor bare-approve semantics [Min 1]
  - Mesh reads review-selected image via verdict priority [Min 1]
- [ ] 5.2 Scenario 对照:`src/framework/review_engine/{judge,chief_judge,report_verdict_emitter,image_prep}.py`、`src/framework/runtime/executors/{select,generate_mesh}.py`、`tests/integration/test_p2_standalone_review.py` / `test_l4_image_to_3d.py`、`tests/unit/test_visual_review_image_compress.py` / `test_review_payload_summarization.py`
- [ ] 5.3 `openspec validate ... --strict` + `pytest -q`

## 6. runtime-core(7 缺)

- [ ] 6.1 为以下 7 个 Requirement 各补 Scenario(其中两条 [+1] 各 2 个):
  - `load_run_metadata` performs three-stage filtering [+1]
  - TransitionEngine is isolated per `arun` [Min 1]
  - Unsupported-response short-circuit at three layers [+1]
  - Premium-API single-attempt contract [Min 1]
  - Budget exceeded synthesizes a Verdict [Min 1]
  - EventBus is loop-aware and thread-safe [Min 1]
  - WebSocket idle-disconnect is leak-free [Min 1]
- [ ] 6.2 Scenario 对照:`src/framework/{artifact_store/repository,runtime/{transition_engine,budget_tracker,failure_mode_map},observability/event_bus,server/ws_server,providers/workers/mesh_worker}.py`、`tests/unit/test_{cascade_cancel,review_budget,event_bus,mesh_no_silent_retry,codex_audit_fixes}.py`、`tests/integration/test_{ws_progress,mesh_failure_visibility}.py`
- [ ] 6.3 `openspec validate ... --strict` + `pytest -q`

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
