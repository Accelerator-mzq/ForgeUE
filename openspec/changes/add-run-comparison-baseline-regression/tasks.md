# Tasks: add-run-comparison-baseline-regression

> 本轮(阶段 3)**只创建文档,不实现代码**。以下任务清单是未来实现阶段的路线图;每条任务应独立可执行与可验证,完成后打钩。

---

## 1. Pydantic models

- [ ] 1.1 新建 `src/framework/comparison/__init__.py`(仅导出公共类型)与 `models.py`。
- [ ] 1.2 实装 `RunComparisonInput` / `ArtifactDiff` / `VerdictDiff` / `MetricDiff` / `StepDiff` / `RunComparisonReport`,字段与 `design.md` §2 一致。
- [ ] 1.3 `RunComparisonReport.schema_version = "1"` 作为 JSON 输出版本锁。
- [ ] 1.4 单元测试:模型构造 / 字段默认值 / Pydantic 序列化往返(`tests/unit/test_run_comparison_models.py`,实现阶段新建)。

**验证**:`python -m pytest tests/unit/test_run_comparison_models.py -v`(新文件,当前不存在)。

## 2. Loader

- [ ] 2.1 实装 `src/framework/comparison/loader.py::_resolve_run_dir`,覆盖三分支(显式 date / 自动遍历 / 多匹配 ambiguous)。
- [ ] 2.2 实装 `load_run_snapshot(run_dir, *, include_payload_hash_check)`,读 `run_summary.json` + `_artifacts.json` + 按需重算 payload 字节 hash。
- [ ] 2.3 定义专属异常:`RunDirNotFound` / `RunDirAmbiguous` / `RunSnapshotCorrupt`;不复用 runtime 侧的 FailureMode(comparison 是纯工具,不进 Run 生命周期)。
- [ ] 2.4 单元测试:`tests/unit/test_run_comparison_loader.py`。覆盖:
  - 显式 date_bucket 命中
  - 不指定 date_bucket + 遍历命中
  - 多日期同 run_id → `RunDirAmbiguous`
  - 空目录 / 缺 `run_summary.json` / 缺 `_artifacts.json`
  - strict=True 时 payload 缺失 raise;strict=False 时返回 `payload_missing_on_disk`

**验证**:`python -m pytest tests/unit/test_run_comparison_loader.py -v`(新文件)。

## 3. Diff engine

- [ ] 3.1 实装 `src/framework/comparison/diff_engine.py::compare(input, baseline, candidate) -> RunComparisonReport`。
- [ ] 3.2 Step 级并集迭代;artifact_id 字典序;lineage 字段独立 delta 块。
- [ ] 3.3 Verdict 级对比只读 `decision` / `confidence` / `selected_candidate_ids` / `rejected_candidate_ids`,**不**重新调 judge。
- [ ] 3.4 `summary_counts` 字段统计各 diff kind。
- [ ] 3.5 单元测试:`tests/unit/test_run_comparison_diff_engine.py`。覆盖:
  - 完全一致 → 全部 `unchanged`,`status_match=True`
  - hash 同 metadata 异 → `metadata_only`
  - hash 异 → `content_changed`
  - baseline 独有 → `missing_in_candidate`
  - Verdict decision 变 → `decision_changed`
  - Verdict selected 集合 delta 正确输出 added / removed

**验证**:`python -m pytest tests/unit/test_run_comparison_diff_engine.py -v`(新文件)。

## 4. Reporter

- [ ] 4.1 实装 `src/framework/comparison/reporter.py::write_reports(report, output_dir)`,产出 `comparison_report.json` + `comparison_report.md`。
- [ ] 4.2 Markdown 结构见 `design.md` §5。ASCII-only,不用 emoji(Windows GBK stdout 兼容)。
- [ ] 4.3 JSON 采用 `model_dump_json(indent=2)`。
- [ ] 4.4 单元测试:`tests/unit/test_run_comparison_reporter.py`。覆盖:
  - 空 diff(两端完全一致)的 Markdown 渲染
  - 含所有 diff kind 的 Markdown 渲染
  - JSON schema_version 存在且为 "1"

**验证**:`python -m pytest tests/unit/test_run_comparison_reporter.py -v`(新文件)。

## 5. CLI

- [ ] 5.1 实装 `src/framework/comparison/cli.py::main(argv=None)` 与 `__main__.py`。
- [ ] 5.2 Argparse flags 按 `design.md` §6 列表;`--artifact-root` 默认 `./artifacts`。
- [ ] 5.3 Exit code:0 正常 / 2 定位 schema / 3 strict payload 缺。
- [ ] 5.4 单元测试:`tests/unit/test_run_comparison_cli.py`。覆盖:
  - 正常两端 → exit 0 + 产物落盘
  - `--baseline` 不存在 → exit 2 + stderr 含 `RunDirNotFound`
  - 多日期匹配 → exit 2 + stderr 含 `RunDirAmbiguous`,提示 `--baseline-date`
- [ ] 5.5 Integration 测试:`tests/integration/test_run_comparison_cli.py`。用 pytest fixture 构造两个假 run 目录,跑 CLI,验证 JSON + MD 文件结构。

**验证**:
- `python -m pytest tests/unit/test_run_comparison_cli.py tests/integration/test_run_comparison_cli.py -v`
- 手工:`python -m framework.comparison --baseline <id_a> --candidate <id_b> --artifact-root ./demo_artifacts/runs/compare_demo`

## 6. Fixtures

- [ ] 6.1 决策:fixture 两个假 run 目录的方案(两选一)——
  - A:pytest fixture 手写静态 `run_summary.json` + `_artifacts.json` + 占位 payload(快,但人造)
  - B:fixture 跑两次 `examples/mock_linear.json` 经 `FakeAdapter` 产生两份真实 artifact 目录(慢但真实)
  - 默认推荐 A(单测快);B 作为 integration 单条覆盖即可。
- [ ] 6.2 Fixture 路径放 `tests/fixtures/comparison/`(目前不存在目录,实现阶段创建),不污染现有 `tests/fixtures/review_images/`。
- [ ] 6.3 **禁止**在 fixture 里硬编码当前日期;fixture 自己 freezegun 或用相对日期子目录。

**验证**:fixture 文件在 `git status` 中可见;不污染 `./artifacts` / `./demo_artifacts`。

## 7. Docs(OpenSpec 主 spec 同步)

- [ ] 7.1 在 archive 前,把本 change 引入的行为从 delta spec 合并到主 spec:
  - `openspec/specs/runtime-core/spec.md` — 新增 "Run comparison is a read-only consumer" invariant(明确 comparison 不进 Run 生命周期)。
  - `openspec/specs/artifact-contract/spec.md` — 新增 "Artifact byte-hash recomputation" 约定(comparison 可重算并校验)。
  - `openspec/specs/examples-and-acceptance/spec.md` — 新增 "Fixture-generated run directories" 路径约定。
- [ ] 7.2 **禁止**在本 change 实现阶段直接改 `openspec/specs/` 主 spec——按 OpenSpec 流程,主 spec 的同步在 `/opsx:archive` 时由 sync-specs 步骤执行。

**验证**:`/opsx:archive add-run-comparison-baseline-regression` 触发 delta → main sync 预览;确认增量清单与 §7.1 一致后再落。

## 8. Docs(长期知识库)

- [ ] 8.1 评估是否更新 `docs/design/LLD.md`:若 comparison 产出成为稳定 API,需在 LLD 新增 §"Run Comparison" 章节(接口签名级)。
- [ ] 8.2 评估是否更新 `docs/testing/test_spec.md`:新增 comparison 相关 unit + integration 测试文件索引。
- [ ] 8.3 评估是否更新 `docs/acceptance/acceptance_report.md`:如果 comparison 关掉了既有 TBD 项,需更新验收矩阵;否则跳过并在 Documentation Sync 段记录原因。
- [ ] 8.4 **不要**把 `design.md` 长文复制进 `docs/`;只追加接口 / 字段摘要。

## 9. Acceptance

- [ ] 9.1 Level 0(离线):`python -m pytest -q` 全绿(数量以实测为准,不硬编码)。
- [ ] 9.2 Level 0 CLI:`python -m framework.comparison --baseline <id_a> --candidate <id_b> --artifact-root <fixture_root>` 产出合法 JSON + Markdown。
- [ ] 9.3 Level 1 / 2:**本 change 不新增任何 Level 1 / 2 验证项**(comparison 不需要 key / UE / ComfyUI)。
- [ ] 9.4 Windows + macOS + Linux 路径兼容通过(CI 若未建立,至少本机 Windows 过)。

---

## Documentation Sync

> 本段为 `docs/ai_workflow/README.md` §4.4 要求的 Documentation Sync Gate 检查清单。archive 本 change 之前必须勾选每一项。

- [ ] Check whether openspec/specs/* needs update after archive
- [ ] Check whether docs/requirements/SRS.md needs update
- [ ] Check whether docs/design/HLD.md needs update
- [ ] Check whether docs/design/LLD.md needs update
- [ ] Check whether docs/testing/test_spec.md needs update
- [ ] Check whether docs/acceptance/acceptance_report.md needs update
- [ ] Check whether README.md needs update
- [ ] Check whether CHANGELOG.md needs update
- [ ] Check whether CLAUDE.md needs update
- [ ] Check whether AGENTS.md needs update
- [ ] Record skipped docs with reason
- [ ] Mark doc drift for human confirmation if sources conflict

---

## Deferred Follow-ups

> 本段记录在本 change 范围内**有意推迟**的工作项。Archive 本 change **之后**应单独创建对应的 OpenSpec change 跟进。本段不阻塞 archive。

### `lazy-artifact-store-package-exports`

**产生原因**(Task 5 CLI 实装时发现):

- `framework.comparison.loader` 在模块顶层 `from framework.artifact_store.hashing import hash_payload`(loader 的 hash 重算职责必须依赖该 helper)。
- Python 子模块 import 必须先执行父包 `__init__.py`,这是语言层语义,不可绕过。
- 当前 `framework/artifact_store/__init__.py` 在顶层 eager-import `repository` / `payload_backends` / `lineage` / `variant_tracker`,作为公共 API 表面。
- 因此任何 import `framework.comparison.loader`(以及依赖它的 `framework.comparison.cli`)的进程,都会在 `sys.modules` 里出现 `framework.artifact_store.repository` 与 `framework.artifact_store.payload_backends`,**即使** loader / CLI 源码从未直接调用这些模块。

**当前 Task 5 的裁决**:

- 接受这个 transitive-import 事实,与 Task 2 loader fence 对齐 —— `tests/unit/test_run_comparison_loader.py` 与 `tests/unit/test_run_comparison_cli.py` 的 import-fence 测试都**不**把 `repository` / `payload_backends` 列入禁止清单,只锁 9 个执行链路前缀(runtime / providers / review_engine / ue_bridge / workflows / observability / server / schemas / pricing_probe)。
- 在 `src/framework/comparison/cli.py` 顶部 docstring 与 `tests/unit/test_run_comparison_cli.py::TestCliImportFence` docstring 显式记录这个 carve-out 与原因。
- **不**修改 `framework/artifact_store/__init__.py`;**不**修改任何 artifact_store 既有文件;**不**在本 change 里悄悄重构跨子系统的包结构。
- CLI 源码层仍守门"DIRECTLY import or call write-side APIs",禁止直接调用 `ArtifactRepository.put` / `load_run_metadata` / 任何 payload backend 写操作 / `CheckpointStore` 写路径。

**为什么不在当前 change 中修**:

- 改 `framework/artifact_store/__init__.py` 为 PEP 562 lazy export 是**跨子系统**改动 —— 该包被 runtime / providers / review_engine / ue_bridge 等多处调用方 import,行为变化范围远超 comparison。
- 本 change(`add-run-comparison-baseline-regression`)的 proposal.md "Modules NOT affected" 显式承诺**不动** `artifact_store`。在实施阶段擅自改它会越界。
- comparison 模块对 `repository` / `payload_backends` 的源码依赖为零;transitive 加载只影响 fence 测试的禁止清单宽度,**不**影响运行时正确性。延迟到独立 change 处理是合理的工程取舍。

**未来处理**:

在 `add-run-comparison-baseline-regression` archive 之后,单独创建 OpenSpec change:

```
lazy-artifact-store-package-exports
```

该 change 评估并(若可行)实施以下改动:

- 把 `framework/artifact_store/__init__.py` 顶层的 `repository` / `payload_backends` / `lineage` / `variant_tracker` eager-import 改为 PEP 562 `__getattr__` lazy export(参考 `framework/comparison/__init__.py` 现有做法)。
- 更新 Task 2 loader fence、Task 5 CLI fence 测试的禁止清单,把 `framework.artifact_store.repository` / `framework.artifact_store.payload_backends` 重新加回禁止项。
- 评估对 runtime / providers / review_engine / ue_bridge 等 artifact_store 公共 API 调用方的影响(它们目前依赖顶层符号即时可用,改 lazy 后需要确认无回归)。
- 跑全套 ForgeUE 测试矩阵确认无回归。

本 change(`add-run-comparison-baseline-regression`)**不**预先创建该 follow-up change 的 proposal / spec,只在本段记录入口。
