# Plan: ue-export-bridge — Task 7 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 7 实装清单。Task 7 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/ue-export-bridge/spec.md` 的 `## MODIFIED Requirements` 块。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### Dual-mode bridge, manifest_only shipped
- 标记:[Min 1]
- 现状:主 spec line 27;manifest_only 已上线,bridge_execute 模式预留(TBD-001 / ADR-008)
- Scenario 草案:"Production runs use `manifest_only`; `bridge_execute` mode is reserved and not invoked by current pipeline"
- 真源:`src/framework/ue_bridge/`、`docs/acceptance/acceptance_report.md` §7 TBD-001

### Three-file deliverable
- 标记:[Min 1]
- 现状:主 spec line 31;UEAssetManifest + UEImportPlan + Evidence
- Scenario 草案:"Bridge writes `manifest.json` + `import_plan.json` + `evidence.json` for each successful export"
- 真源:`src/framework/ue_bridge/{manifest_builder,import_plan_builder,evidence}.py`、`tests/integration/test_p4_ue_manifest_only.py`

### UE-side agent supports three domains
- 标记:[Min 1]
- 现状:主 spec line 35;Texture / StaticMesh / Material 三域
- Scenario 草案:"`ue_scripts/run_import.py` dispatches Texture / StaticMesh / Material entries to their respective Python domain handlers"
- 真源:`ue_scripts/run_import.py`、`tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal`

### Naming policy declared per asset
- 标记:[Min 1]
- 现状:主 spec line 39
- Scenario 草案:"Asset entry without a declared `naming_policy` fails dry-run validation before any UE-side execution"
- 真源:`src/framework/ue_bridge/permission_policy.py`、`src/framework/runtime/dry_run_pass.py`

### Dependencies drive topological order
- 标记:[Min 1]
- 现状:主 spec line 43
- Scenario 草案:"Material entry depending on a Texture entry is imported after the Texture, per topological sort over `depends_on`"
- 真源:`src/framework/ue_bridge/import_plan_builder.py`、`tests/integration/test_p4_ue_manifest_only.py`

### Evidence is append-only and atomic
- 标记:[+1]
- 现状:主 spec line 47
- Scenario 草案:
  - "Successful import appends exactly one entry to `evidence.json` via atomic write"
  - "Crash mid-import leaves no half-written `evidence.json` record (atomic-rename guarantee)"
- 真源:`src/framework/ue_bridge/evidence.py`、`ue_scripts/evidence_writer.py`

### Bridge never modifies asset content
- 标记:[Min 1]
- 现状:主 spec line 61
- Scenario 草案:"Imported texture file's bytes match source file's bytes; bridge does not transcode or mutate the asset"
- 真源:`ue_scripts/run_import.py`(domain handlers)、`tests/integration/test_p4_ue_manifest_only.py`

### Hardware smoke acceptance
- 标记:[Min 1]
- 现状:主 spec line 65;A1 真机 commandlet
- Scenario 草案:"`ue_scripts/a1_run.py` succeeds against UE 5.x stub editor under `tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal`; A1 真机 commandlet 通过(2026-04-23 a1_demo)"
- 真源:`ue_scripts/a1_run.py`、`docs/acceptance/acceptance_report.md` §6.1
