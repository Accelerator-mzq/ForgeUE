# Plan: workflow-orchestrator — Task 8 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 8 实装清单。Task 8 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/workflow-orchestrator/spec.md` 的 `## MODIFIED Requirements` 块。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### Three RunModes share one scheduler
- 标记:[Min 1]
- 现状:主 spec line 26;`basic_llm` / `production` / `standalone_review` 共享同一 Scheduler
- Scenario 草案:"`basic_llm` and `standalone_review` runs reuse the same `Scheduler` class; no per-mode scheduler subclass exists"
- 真源:`src/framework/runtime/scheduler.py`、`src/framework/core/enums.py::RunMode`、`tests/integration/test_p[0,2]_*.py`

### Eleven step types are supported
- 标记:[Min 1]
- 现状:主 spec line 30;11 种 StepType
- Scenario 草案:"All 11 `StepType` enum values round-trip through `Scheduler.dispatch` to their corresponding executor without `KeyError`"
- 真源:`src/framework/core/enums.py::StepType`、`src/framework/runtime/executors/`、`src/framework/runtime/scheduler.py`

### Opt-in DAG concurrency
- 标记:[Min 1]
- 现状:主 spec line 44;`parallel_dag=True` opt-in
- Scenario 草案:"Bundle with `parallel_dag=True` fans out ready siblings concurrently; bundle without flag executes them sequentially per scheduling plan"
- 真源:`src/framework/runtime/orchestrator.py::arun`、`tests/integration/test_dag_concurrency.py`、LLD §16.1

### Bundle loading goes through the loader
- 标记:[Min 1]
- 现状:主 spec line 58;CLAUDE.md "Bundle JSON 编码"段
- Scenario 草案:"Direct `json.load(open(<bundle>))` in framework code is forbidden; `framework.workflows.loader.load_task_bundle` is the single supported entry point (handles UTF-8 / GBK boundary)"
- 真源:`src/framework/workflows/loader.py`、`tests/unit/test_workflow_loader_*.py`(若有)、`CLAUDE.md` "Bundle JSON 编码"段

### Model reference expansion happens before validation
- 标记:[Min 1]
- 现状:主 spec line 62;loader 先展开 `models_ref` 再跑 schema validation
- Scenario 草案:"Bundle with `provider_policy.models_ref='text_cheap'` expands to `prepared_routes` before `Task` schema validation runs; alias misses fail at expansion, not at schema check"
- 真源:`src/framework/workflows/loader.py`、`config/models.yaml`
