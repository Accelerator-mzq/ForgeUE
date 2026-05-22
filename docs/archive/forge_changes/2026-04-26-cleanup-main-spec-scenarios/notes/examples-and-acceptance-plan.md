# Plan: examples-and-acceptance — Task 2 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 2 实装清单。Task 2 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/examples-and-acceptance/spec.md` 的 `## MODIFIED Requirements` 块,其中 `No hardcoded provider model ids` 同时收紧措辞(LIVE bundle 显式覆盖路径合法例外)。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### Bundle is the end-to-end acceptance artifact
- 标记:[Min 1]
- 现状:主 spec line 39;`examples/*.json` 是 ForgeUE 的端到端验收 artifact
- Scenario 草案:"`examples/mock_linear.json` runs the full P0 pipeline end-to-end"
- 真源参考:`tests/integration/test_p0_mock_linear.py`、`examples/mock_linear.json`

### UTF-8 bundles go through the loader
- 标记:[Min 1]
- 现状:主 spec line 43;bundle 含 UTF-8(全角引号等),必须经 `load_task_bundle` 而非 `json.load(open(...))`
- Scenario 草案:"Bundle with full-width quotes loads via `load_task_bundle` without UnicodeDecodeError on Windows GBK"
- 真源参考:`src/framework/workflows/loader.py`、`tests/unit/test_workflow_loader_*.py`

### Alias-based model references
- 标记:[Min 1]
- 现状:主 spec line 47;bundle 用 `models_ref: "<alias>"`,loader 展开为 prepared_routes
- Scenario 草案:"Bundle with `models_ref=text_cheap` expands to provider routes via ModelRegistry"
- 真源参考:`src/framework/workflows/loader.py`、`config/models.yaml`

### No hardcoded provider model ids
- 标记:[审视 + Min 1]
- 现状:主 spec line 51;**措辞过宽**,LIVE bundle(如 `image_to_3d_pipeline_live.json`)显式声明 model id 是合法例外
- 措辞收紧:从"No hardcoded provider model ids"改为限定语义:"production bundles MUST use `models_ref`;LIVE bundles MAY declare explicit `provider_policy` overrides via frontmatter,显式声明视为白名单例外"
- Scenario 草案:"Production bundle without `models_ref` and without LIVE override fails alias check"
- 真源参考:`examples/*.json`(`mock_linear` / `character_extract` 等用 ref;`*_live.json` 用 override)、`src/framework/workflows/loader.py`

### Stage-aligned acceptance coverage
- 标记:[Min 1]
- 现状:主 spec line 65;P0-P4 每阶段都有专属 integration test
- Scenario 草案:"Each P0-P4 stage has a dedicated `test_p[0-4]_*.py` integration test"
- 真源参考:`tests/integration/test_p{0,1,2,3,4}_*.py`、`docs/testing/test_spec.md` §4.1

### Live bundles carry premium-API warnings
- 标记:[Min 1]
- 现状:主 spec line 69;LIVE bundle(贵族 API)需带显式警示,默认 fail-closed without `--live-llm`
- Scenario 草案:"`image_to_3d_pipeline_live.json` fails closed when run without `--live-llm`"
- 真源参考:`examples/*_live.json`、`src/framework/run.py::main`

### UE hardware smoke is reachable via commandlet
- 标记:[Min 1]
- 现状:主 spec line 73;UE 真机 smoke 通过 commandlet 路径(0 GUI 依赖)
- Scenario 草案:"`ue_scripts/a1_run.py` launches UE 5.x commandlet and writes `Generated/` assets without GUI"
- 真源参考:`ue_scripts/a1_run.py`、`docs/acceptance/acceptance_report.md` §6.1
