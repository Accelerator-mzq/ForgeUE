# Design: add-run-comparison-baseline-regression

本 design 假设实现阶段**另起 session**,按 `tasks.md` 顺序推进。本文件描述**应该实现成什么样**,不含任何可执行代码。

---

## 1. 目录 layout(以当前 `src/framework/` 为准)

当前仓库 src layout(2026-04-24 实测):

```
src/framework/
├── __init__.py
├── py.typed
├── run.py                       # CLI 入口
├── core/                        # Task / Run / Artifact / Review / UE / Policies schema
├── artifact_store/              # repository.py / payload_backends / lineage / variant_tracker / hashing
├── runtime/                     # orchestrator / scheduler / transition_engine / dry_run_pass / checkpoint_store / budget_tracker / failure_mode_map + executors/
├── providers/                   # adapters + capability_router + model_registry + workers/
├── review_engine/               # judge / chief_judge / report_verdict_emitter / rubric_loader / image_prep + rubric_templates/
├── schemas/                     # 业务 schema 注册
├── ue_bridge/                   # manifest_builder / import_plan_builder / permission_policy / evidence + inspect/ plan/ execute/
├── observability/               # EventBus / secrets / OTel tracing / compactor
├── server/ws_server.py          # WS 进度推送
├── pricing_probe/               # CLI 工具
└── workflows/loader.py          # load_task_bundle + 模板占位
```

**新增位置**:`src/framework/comparison/`,与 `observability/` / `pricing_probe/` / `ue_bridge/` 同级,作为**独立工具模块**——**不**嵌入 `runtime/` 或 `observability/`。这样 comparison 只做只读消费,不污染执行链路。

```
src/framework/comparison/       (规划,实现阶段创建)
├── __init__.py
├── models.py                   # Pydantic:RunComparisonInput / Report / ArtifactDiff / VerdictDiff / MetricDiff / StepDiff
├── loader.py                   # 读 <artifact_root>/<date>/<run_id>/ 下 run_summary.json + _artifacts.json + 各 artifact
├── diff_engine.py              # 逐 Step / 逐 Artifact / 逐 Verdict 对比,返回 structured diff
├── reporter.py                 # Report → comparison_report.json + comparison_summary.md
└── cli.py                      # python -m framework.comparison 入口
```

注意:
- `src/framework/comparison/__main__.py` 规划用 `cli.main()`,使 `python -m framework.comparison` 可直接跑。
- **不会**新增 `observability/run_comparison.py`——README "后续扩展" 第 7 项原占位在 observability 下是早期提法,现应放在独立 `comparison/` 子包,职责更清。

## 2. Pydantic 模型

全部放 `src/framework/comparison/models.py`,基于 Pydantic v2(与 `src/framework/core/` 一致)。

### 2.1 `RunComparisonInput`

```
baseline_run_id: str
candidate_run_id: str
artifact_root: Path              # 默认 ./artifacts;可由 CLI --artifact-root 覆盖
baseline_date_bucket: Optional[str]   # YYYY-MM-DD;省略时在 artifact_root 下遍历找
candidate_date_bucket: Optional[str]
strict: bool = True              # True 时 artifact 缺失 / 后端不存在算 failure;False 时降级为 warning
include_payload_hash_check: bool = True
```

### 2.2 `ArtifactDiff`

```
artifact_id: str
kind: Literal["unchanged", "content_changed", "metadata_only", "missing_in_baseline", "missing_in_candidate", "payload_missing_on_disk"]
baseline_hash: Optional[str]
candidate_hash: Optional[str]
metadata_delta: dict[str, tuple[Any, Any]]   # 字段名 → (baseline, candidate)
lineage_delta: Optional[dict[str, tuple[Any, Any]]]
note: Optional[str]              # 例如 "payload backend exists()==False in baseline"
```

### 2.3 `VerdictDiff`

```
step_id: str
kind: Literal["unchanged", "decision_changed", "confidence_changed", "selected_candidates_changed", "missing_in_baseline", "missing_in_candidate"]
baseline_decision: Optional[str]
candidate_decision: Optional[str]
baseline_confidence: Optional[float]
candidate_confidence: Optional[float]
selected_delta: Optional[dict[str, list[str]]]   # {"added": [...], "removed": [...]}
```

### 2.4 `MetricDiff`

```
metric: str                      # cost_usd / prompt_tokens / completion_tokens / total_tokens / wall_clock_s
scope: Literal["run", "step"]
step_id: Optional[str]
baseline_value: Optional[float]
candidate_value: Optional[float]
delta: Optional[float]
delta_pct: Optional[float]
```

### 2.5 `StepDiff`

```
step_id: str
status_baseline: str             # succeeded / failed / skipped / ...
status_candidate: str
chosen_model_baseline: Optional[str]
chosen_model_candidate: Optional[str]
artifact_diffs: list[ArtifactDiff]
verdict_diffs: list[VerdictDiff]
metric_diffs: list[MetricDiff]
```

### 2.6 `RunComparisonReport`

```
input: RunComparisonInput
baseline_run_meta: dict          # 来自 run_summary.json 截断
candidate_run_meta: dict
status_match: bool
step_diffs: list[StepDiff]
run_level_metric_diffs: list[MetricDiff]
summary_counts: dict[str, int]   # unchanged / content_changed / decision_changed / missing / ...
generated_at: datetime
schema_version: str              # "1"
```

## 3. Loader 设计

`src/framework/comparison/loader.py` 负责**只读**访问 `<artifact_root>/<YYYY-MM-DD>/<run_id>/` 目录。

关键实现点:

- **不**走 `ArtifactRepository.put()` / `load_run_metadata()` 的写路径;只读 `_artifacts.json` 纯文件 + 重算 payload hash 做一致性校验(默认开启,可 `--no-hash-check` 关)。
- 调用 `framework.artifact_store.hashing.hash_payload` 重算 payload 字节哈希——**引用**现有 hashing module,不复制算法。
- `_resolve_run_dir(artifact_root, run_id, date_bucket)`:
  1. 若 `date_bucket` 显式给出 → 直接 `<artifact_root>/<date_bucket>/<run_id>/`
  2. 否则遍历 `artifact_root` 下所有日期分桶,找匹配 `<run_id>/` 目录
  3. 多个匹配(不同日期的同 run_id)→ raise `RunDirAmbiguous`,提示用户显式指定 `--baseline-date` / `--candidate-date`
  4. 无匹配 → raise `RunDirNotFound`
- 缺失文件处理:
  - `run_summary.json` 缺 → raise(两端都必须有,否则无法对比)
  - `_artifacts.json` 缺 → raise
  - 具体 artifact payload 文件缺 → 根据 `strict` 决定 raise 或降级为 `ArtifactDiff.kind="payload_missing_on_disk"`
- Windows 路径兼容:全部 `pathlib.Path`,不拼字符串;`artifact_root` 接受正 / 反斜线(Path 原生兼容)。

## 4. Diff engine 设计

`src/framework/comparison/diff_engine.py` 纯函数,无副作用,无网络,无磁盘写。

算法骨架:

```
compare(input: RunComparisonInput, baseline: RunSnapshot, candidate: RunSnapshot) -> RunComparisonReport
```

逐层对比:

1. **Run 级**:status / 总 cost / 总 tokens / wall_clock_s → `run_level_metric_diffs`;status_mismatch 独立布尔字段。
2. **Step 级**:以 `step_id` 并集迭代。
   - baseline 独有 → `status_candidate="missing"`,其 artifacts 全部 `missing_in_candidate`。
   - candidate 独有 → 对称处理。
   - 双端都有 → 逐项对比 status / chosen_model / artifacts / verdicts / metrics。
3. **Artifact 级**:以 `artifact_id` 并集迭代,key 来自 `_artifacts.json`。
   - hash 不同 → `content_changed`
   - hash 同但 metadata 不同 → `metadata_only`(标出具体字段 delta)
   - Lineage 字段变化(`source_artifact_ids` / `selected_by_verdict_id` / `variant_group_id` 等)独立摘录成 `lineage_delta`
4. **Verdict 级**:对每个 review step 读 `ReviewReport` + `Verdict` artifact JSON 体,对比 `decision` / `confidence` / `selected_candidate_ids` / `rejected_candidate_ids`。**不**重新调 judge。
5. **Metric 级**:按 `openspec/specs/runtime-core/spec.md` Requirement "Cost is persisted before Checkpoint" 的约定,baseline / candidate 的 `cp.metrics["cost_usd"]` 必然已经落盘;diff engine 直接对比字段。

避开的陷阱:
- **不**在 diff 结果里放原始 payload 字节——Report 只含 hash 和 metadata,防止报告文件炸大。
- **不**保证 diff 顺序稳定等于插入顺序——按 step_id / artifact_id 字典序排序,方便人工 diff。

## 5. Reporter 设计

`src/framework/comparison/reporter.py` 把 `RunComparisonReport` 渲染为两份输出:

- **JSON**:`comparison_report.json`,Pydantic `model_dump_json(indent=2)`,用于程序化消费。
- **Markdown**:`comparison_summary.md`,结构:
  ```
  # Run Comparison: baseline=<id_a> vs candidate=<id_b>
  ## Summary
  ## Run-level metrics
  ## Step diffs
    ### step_<id>
      - status / chosen_model
      - Artifact diffs
      - Verdict diffs
      - Metric diffs
  ## Missing / Anomalies
  ```

两份都落到调用方指定的 `--output-dir`,默认 `./demo_artifacts/<YYYY-MM-DD>/comparison/<baseline_id>__vs__<candidate_id>/<HHMMSS>/`,与 `probes/_output.py::probe_output_dir` 模式对齐(但放 comparison 子树,不污染 probes/)。

ASCII 输出原则同 `probes/README.md` §5:报告内文不用 emoji,避免 Windows GBK stdout 崩。

## 6. CLI 入口

`src/framework/comparison/cli.py` + `__main__.py`:

```
python -m framework.comparison \
    --baseline-run <run_id_a> \
    --candidate-run <run_id_b> \
    [--artifact-root ./artifacts] \
    [--baseline-date YYYY-MM-DD] \
    [--candidate-date YYYY-MM-DD] \
    [--output-dir <path>] \
    [--non-strict] \
    [--no-hash-check] \
    [--json-only | --markdown-only] \
    [--quiet]
```

注:`--non-strict` 为单向开关(默认 strict);`--json-only` / `--markdown-only` 互斥(argparse mutually-exclusive group);`--quiet` 抑制人类可读 summary,只输出产物路径。

exit code:
- 0 = 两端都跑通对比,无论差异多少
- 2 = Run 目录定位失败 / 文件结构破损(schema 错误)
- 3 = strict 模式下 artifact payload 缺失

**不**默认把 "任何差异 → 非零 exit" 写死,因为"有差异"是 comparison 的正常产出,不是错误。CI 如果想卡 PR,自己消费 `comparison_report.json` 的 `summary_counts` 字段决定。

## 7. 不依赖真实 provider

对比全部基于**已经落盘的 artifact 文件**,不调用任何 LLM / Worker / UE。

测试策略:

- **单元测试**:纯 fixture 字典构造 `ArtifactDiff` / `VerdictDiff`,测 diff engine 边界条件。
- **集成测试**:pytest fixture 预生成两个假 run 目录(可以直接写静态 JSON 到 `tmp_path`,或用现有 `FakeAdapter` + `examples/mock_linear.json` 真跑两次得到两份产物;后者更真实但稍慢)。两种方案在实现阶段二选一,实现任务会单独评估。

## 8. 与阶段 2 主 spec 的依赖

本 change 的 delta spec **引用而不重写** 阶段 2 主 spec:

- `openspec/changes/add-run-comparison-baseline-regression/specs/runtime-core/spec.md` — ADDED:CLI 与只读载入契约,基于 `openspec/specs/runtime-core/spec.md` "Checkpoint persistence survives cross-process resume" + "Cost is persisted before Checkpoint" 两条 Requirement,把它们作为 comparison 可读取的既有事实。
- `openspec/changes/add-run-comparison-baseline-regression/specs/artifact-contract/spec.md` — ADDED:artifact hash 重算规则与 Lineage delta 定义,基于 `openspec/specs/artifact-contract/spec.md` 的 `_artifacts.json` 持久化 + 四层校验 + hashing。
- `openspec/changes/add-run-comparison-baseline-regression/specs/examples-and-acceptance/spec.md` — ADDED:两个 fixture run 的生成策略,基于 `openspec/specs/examples-and-acceptance/spec.md` 的 bundle-as-acceptance-artifact。

**不**创建针对 `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` 的 delta spec,因为 comparison 不改变这些 capability 的行为。

## 9. Windows 路径兼容

- `pathlib.Path`(不拼字符串)。
- `artifact_root` 默认当前工作目录下 `./artifacts`,接受绝对路径。
- 所有 fixture 产物落 `tmp_path`(pytest)或 `./demo_artifacts/<date>/comparison/`(CLI 默认),避免 `/tmp/...`。
- `pathlib.Path.relative_to()` 用法注意跨盘符 raise,comparison 内部路径统一走 Path 对象,不做字符串 relative 运算。

## 10. 非目标与边界兜底

- **不**接管 Run 的执行:baseline / candidate 都必须**已经结束**(即 `run_summary.json` 含 `status` 字段),否则 loader raise。
- **不**做图像 / mesh 的感知级相似度;仅 hash + 元数据。
- **不**做 cross-repo 对比;`artifact_root` 必须在同一文件系统。
- **不**引入新 Step type;**不**改 Orchestrator / Scheduler;**不**改 FailureModeMap;**不**新增 FR。
- 如果未来需要"图像内容近似度",应单独开 change,接入 `review-engine` 的 visual judge path,**不**在本模块内膨胀。
