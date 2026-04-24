# Change Proposal: add-run-comparison-baseline-regression

## Why ForgeUE needs this

ForgeUE 已经围绕 Run / Artifact / ReviewReport / Verdict / Provider / examples / tests 建立了完整的运行时链路,但**没有**在 Run 粒度上横向比较两次执行的工具:

- 换模型别名后,想知道 `text_cheap` 切到更便宜 provider 对 UE 资产结构化输出的稳定性影响,只能靠人工 diff `run_summary.json`。
- 改 review policy / rubric 后,想验证"同一输入、不同 policy"的 Verdict 走向是否符合预期,缺少自动化工具。
- 真实 provider(Qwen / Hunyuan / GLM)上线 / 降级时,需要 baseline 对照回归,防止 silent regression。
- `README.md` §"后续扩展" 第 7 项已占位 "Run Comparison / 基线回归 — `observability/run_comparison.py` 待补",长期未落。

该能力**只读消费**已有 artifact 产物,不需要先改 UE、ComfyUI 或真实 provider,适合作为 ForgeUE OpenSpec 工作流的首个试点 change。

## What this change solves

- 提供一个**只读**工具,读取同一仓库下 baseline run 目录与 candidate run 目录,逐项对比并产出 `comparison_report.json` + 可读 Markdown summary。
- 对比维度覆盖 Run 级状态、Artifact hash / metadata / lineage、ReviewReport / Verdict、BudgetTracker 指标。
- 明确标记差异来源:content_changed / metadata_only / missing_in_baseline / missing_in_candidate / status_mismatch / verdict_mismatch / cost_delta。
- 可被 pytest fixture 驱动,不依赖真实 provider。

## What this change explicitly does NOT solve

- **不改**现有 Run 执行链路(Orchestrator / Scheduler / TransitionEngine / Executors 全部不动)。
- **不改** Artifact / Checkpoint / ReviewReport / Verdict 的 schema。
- **不做**实时对比:两端 Run 都必须已经完成落盘。
- **不做** content-semantic 比较(图像相似度、mesh 几何差异由 `review-engine` 承担);comparison 止于 hash + 元数据 + Verdict 语义。
- **不做** Run 合并、选优、人工审核协议(这些归 `review-engine` / 未来 `human-review` change)。
- **不做** CI 集成:CLI 返回 exit code,但是否卡 PR 由调用方决定。
- **不**先实现 `bridge_execute` 模式的额外对比维度(ADR-001 / ADR-008 下 `bridge_execute` 仍为未启用);本 change 只对 `manifest_only` 产物做对比。

## Modules affected

**本轮只写文档,不碰代码**。未来实现阶段会影响:

- **新增**(规划中,本轮不创建):`src/framework/comparison/`(models / loader / diff_engine / reporter / cli)
- **不动**(硬约束):`src/framework/core/` / `runtime/` / `providers/` / `review_engine/` / `artifact_store/` / `ue_bridge/` / `observability/` / `schemas/` / `workflows/` / `pricing_probe/` / `server/`
- **不动**:所有 `tests/` 与 `examples/` 现有文件(未来实现时会新增 fixture + 新测试,但不改已有)
- **不动**:`ue_scripts/` / `probes/` / `config/models.yaml`

## Modules NOT affected

- Provider routing 与 ModelRegistry(参见 `openspec/specs/provider-routing/spec.md`)——comparison 读取已落盘的 `chosen_model` 即可,不参与路由决策。
- UE Export Bridge(参见 `openspec/specs/ue-export-bridge/spec.md`)——对比时把 `UEAssetManifest` / `UEImportPlan` / `Evidence` 当作普通 Artifact 文件处理,不调用 UE 侧脚本。
- Review engine 运行时逻辑(参见 `openspec/specs/review-engine/spec.md`)——comparison 读取已产出的 `ReviewReport` / `Verdict` JSON,不重新调 judge。
- Probe 约定(参见 `openspec/specs/probe-and-validation/spec.md`)——comparison 走纯 framework CLI 路径,不走 probe。

## Why doc-only in this round

首轮试点目标是验证 OpenSpec 工作流本身(proposal → design → tasks → delta spec → Documentation Sync Gate),因此只产出文档 artifact。实现阶段将另起 session,按 `tasks.md` 顺序推进,每个 task 独立可验证。

## Success criteria (doc-only phase)

- [x] `openspec/changes/add-run-comparison-baseline-regression/` 目录下 6 份文档就位。
- [x] delta spec 只描述增量行为,不复制阶段 2 主 spec 全文。
- [x] `tasks.md` 末尾含 Documentation Sync Gate 章节,10+2 个 checkbox 与 `docs/ai_workflow/README.md` §4.4 模板一致。
- [x] `design.md` 以 `src/framework/` 实际 layout 为准,不凭印象写目录。
- [x] 本轮未改动任何禁止目录(`git diff --name-only` 只出现 change 自己的路径)。

## Success criteria (future implementation phase, 非本轮范围)

- CLI `python -m framework.comparison --baseline <id_a> --candidate <id_b>` 跑通离线 fixture,产出 `comparison_report.json` + `comparison_report.md`。
- 至少一条 integration 测试用 fixture 两个 run 目录覆盖:`status_match` / `artifact_content_changed` / `verdict_mismatch` / `missing_in_candidate` 四类差异。
- 不依赖 `.env` 或任何 provider key 即可全量跑完。
- 新增测试数**不**硬编码进文档;以 `python -m pytest -q` 实测为准。

## References

- 阶段 2 主 spec:`openspec/specs/runtime-core/spec.md`(Run 生命周期 + Checkpoint)、`openspec/specs/artifact-contract/spec.md`(Artifact + `_artifacts.json` 跨进程持久化)、`openspec/specs/examples-and-acceptance/spec.md`(bundle 作为 acceptance artifact)。
- SRS:`docs/requirements/SRS.md` §3.2 FR-LC-006/007(跨进程 metadata 持久化)、§3.6 FR-STORE-005(Lineage)、§3.10 FR-COST-009(parallel_candidates 同质性)。
- 入口占位:`README.md` §"后续扩展" 第 7 项 "Run Comparison / 基线回归"。
