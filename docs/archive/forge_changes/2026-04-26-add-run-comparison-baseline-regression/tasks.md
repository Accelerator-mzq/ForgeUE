# Tasks: add-run-comparison-baseline-regression

> **当前阶段**(2026-04-25):本 change 实装侧 6 Task 已全部完成并 commit(`a1bf0c4` Models+Loader / `40a85da` Diff Engine / `421dab2` Reporter / `c632743` CLI / `d1c5f84` Fixtures+Integration);Codex Review Gate Task 4/5/6 各两轮 PASS;pytest -q 实测 848 通过,工作树进入 Documentation Sync Gate 修复阶段。下文 checkbox 反映**实装事实**,而非 doc-only 阶段路线图。

---

## 1. Pydantic models

- [x] 1.1 新建 `src/framework/comparison/__init__.py`(仅导出公共类型)与 `models.py`。
- [x] 1.2 实装 `RunComparisonInput` / `ArtifactDiff` / `VerdictDiff` / `MetricDiff` / `StepDiff` / `RunComparisonReport`,字段与 `design.md` §2 一致。
- [x] 1.3 `RunComparisonReport.schema_version = "1"` 作为 JSON 输出版本锁。
- [x] 1.4 单元测试:模型构造 / 字段默认值 / Pydantic 序列化往返(`tests/unit/test_run_comparison_models.py`,实现阶段新建)。

**验证**:`python -m pytest tests/unit/test_run_comparison_models.py -v` — 已建,52 用例通过(实测 collect-only)。

## 2. Loader

- [x] 2.1 实装 `src/framework/comparison/loader.py::resolve_run_dir(artifact_root, run_id, date_bucket=None)` 公开函数(原 task 文本误写私有 `_resolve_run_dir`,实际公开),覆盖三分支(显式 date / 自动遍历 / 多匹配 ambiguous)。
- [x] 2.2 实装 `load_run_snapshot(run_dir, *, include_payload_hash_check: bool = True, strict: bool = True)`,读 `run_summary.json` + `_artifacts.json` + 按需重算 payload 字节 hash;`strict` 参数原 task 文本漏写,实装含此 keyword-only 参数(strict=True 时 payload 缺失 raise `PayloadMissingOnDisk`,strict=False 时记录到 `RunSnapshot.payload_missing_on_disk` 集合)。
- [x] 2.3 定义专属异常:`RunDirNotFound` / `RunDirAmbiguous` / `RunSnapshotCorrupt`;不复用 runtime 侧的 FailureMode(comparison 是纯工具,不进 Run 生命周期)。实装时额外加了 `PayloadMissingOnDisk`(strict 模式 payload 缺失专用),与 design.md §3 一致。
- [x] 2.4 单元测试:`tests/unit/test_run_comparison_loader.py`。覆盖:
  - 显式 date_bucket 命中
  - 不指定 date_bucket + 遍历命中
  - 多日期同 run_id → `RunDirAmbiguous`
  - 空目录 / 缺 `run_summary.json` / 缺 `_artifacts.json`
  - strict=True 时 payload 缺失 raise;strict=False 时返回 `payload_missing_on_disk`

**验证**:`python -m pytest tests/unit/test_run_comparison_loader.py -v` — 已建,50 用例通过(实测 collect-only)。

## 3. Diff engine

- [x] 3.1 实装 `src/framework/comparison/diff_engine.py::compare(input, baseline, candidate) -> RunComparisonReport`。
- [x] 3.2 Step 级并集迭代;artifact_id 字典序;lineage 字段独立 delta 块。
- [x] 3.3 Verdict 级对比只读 `decision` / `confidence` / `selected_candidate_ids` / `rejected_candidate_ids`,**不**重新调 judge。
- [x] 3.4 `summary_counts` 字段统计各 diff kind。**注**:实装为 sparse dict,kind 为 0 的键缺省;reporter 用 `_count(report, key)` 走 `.get(key, 0)`。
- [x] 3.5 单元测试:`tests/unit/test_run_comparison_diff_engine.py`。覆盖:
  - 完全一致 → 全部 `unchanged`,`status_match=True`
  - hash 同 metadata 异 → `metadata_only`
  - hash 异 → `content_changed`
  - baseline 独有 → `missing_in_candidate`
  - Verdict decision 变 → `decision_changed`
  - Verdict selected 集合 delta 正确输出 added / removed

**验证**:`python -m pytest tests/unit/test_run_comparison_diff_engine.py -v` — 已建,69 用例通过(实测 collect-only)。

## 4. Reporter

- [x] 4.1 实装 `src/framework/comparison/reporter.py::write_reports(report, output_dir)`,产出 `comparison_report.json` + `comparison_summary.md`。
- [x] 4.2 Markdown 结构见 `design.md` §5。ASCII-only,不用 emoji(Windows GBK stdout 兼容)。实装含 `_ascii_safe` / `_line_safe` / `_escape_cell` / `_console_safe`(后者在 cli.py)四层 ASCII / CRLF 守门。
- [x] 4.3 JSON 采用 `model_dump_json(indent=2)`,末尾追加单个 `"\n"`。
- [x] 4.4 单元测试:`tests/unit/test_run_comparison_reporter.py`。覆盖:
  - 空 diff(两端完全一致)的 Markdown 渲染
  - 含所有 diff kind 的 Markdown 渲染
  - JSON schema_version 存在且为 "1"

**验证**:`python -m pytest tests/unit/test_run_comparison_reporter.py -v` — 已建,65 用例通过。

## 5. CLI

- [x] 5.1 实装 `src/framework/comparison/cli.py::main(argv=None)` 与 `__main__.py`。
- [x] 5.2 Argparse flags 按 `design.md` §6 列表;`--artifact-root` 默认 `./artifacts`。实装含 11 flag(增加 `--json-only` / `--markdown-only` / `--quiet`,前两者 argparse 互斥组)。
- [x] 5.3 Exit code:0 正常 / 2 定位 schema / 3 strict payload 缺。实装含兜底 1(其他未识别异常)。
- [x] 5.4 单元测试:`tests/unit/test_run_comparison_cli.py`。覆盖:
  - 正常两端 → exit 0 + 产物落盘
  - `--baseline-run` 指向的 run 不存在 → exit 2 + stderr 含 `RunDirNotFound`
  - 多日期匹配 → exit 2 + stderr 含 `RunDirAmbiguous`,提示 `--baseline-date`
- [x] 5.5 Integration 测试:`tests/integration/test_run_comparison_cli.py`。用 pytest fixture 构造两个假 run 目录,跑 CLI,验证 JSON + MD 文件结构。

**验证**:
- `python -m pytest tests/unit/test_run_comparison_cli.py tests/integration/test_run_comparison_cli.py -v` — 59 unit + 4 integration 通过
- 手工:`python -m framework.comparison --baseline-run <id_a> --candidate-run <id_b> --artifact-root ./demo_artifacts/runs/compare_demo`

## 6. Fixtures

- [x] 6.1 决策:实装阶段同时使用 A + B(combo),不互斥 ——
  - A(主路径):`tests/fixtures/comparison/builders.py::build_fixture_pair(root)` 通过真实 Pydantic 类构造确定性 fixture(deterministic on-disk JSON + payload bytes,合成日期 `2000-01-01`),驱动 3 个 integration test(happy / 不污染 demo_artifacts / lineage diff)。
  - B(spec validation gate):`test_offline_real_run_pair_via_framework_run` subprocess 跑 `python -m framework.run --task examples/mock_linear.json` 两次(无 `--live-llm` / `--comfy-url`,自动 FakeAdapter + FakeComfyWorker),再跑 `python -m framework.comparison`,守门 `examples-and-acceptance/spec.md:54` Validation 项。
- [x] 6.2 Fixture 路径放 `tests/fixtures/comparison/`(实装阶段创建),不污染现有 `tests/fixtures/review_images/`。
- [x] 6.3 **禁止**在 fixture 里硬编码当前日期;builder 用合成 `2000-01-01` date bucket + 固定 timestamp,实测 byte-deterministic。

**验证**:fixture 文件在 `git status` 中可见(见 commit `d1c5f84`);**未**污染 `./artifacts` / `./demo_artifacts`(integration test 显式 `--output-dir tmp_path/...` + pre/post 递归快照守门)。

## 7. Docs(OpenSpec 主 spec 同步)

- [ ] 7.1 在 archive 前,把本 change 引入的行为从 delta spec 合并到主 spec:
  - `openspec/specs/runtime-core/spec.md` — 新增 "Run comparison is a read-only consumer" invariant(明确 comparison 不进 Run 生命周期)。
  - `openspec/specs/artifact-contract/spec.md` — 新增 "Artifact byte-hash recomputation" 约定(comparison 可重算并校验)。
  - `openspec/specs/examples-and-acceptance/spec.md` — 新增 "Fixture-generated run directories" 路径约定。
- [x] 7.2 **禁止**在本 change 实现阶段直接改 `openspec/specs/` 主 spec——按 OpenSpec 流程,主 spec 的同步在 `/opsx:archive` 时由 sync-specs 步骤执行。本轮 Documentation Sync Gate 也遵守这条规则,未触动 `openspec/specs/`。

**验证**:`/opsx:archive add-run-comparison-baseline-regression` 触发 delta → main sync 预览;确认增量清单与 §7.1 一致后再落。

## 8. Docs(长期知识库)

- [x] 8.1 已更新 `docs/design/LLD.md` —— 新增 §15 "Run Comparison(`src/framework/comparison/`)" 章节(接口签名级),老 §15-§17 顺延为 §16-§18;§18.3 变更记录加 v1.2 行。
- [x] 8.2 已更新 `docs/testing/test_spec.md` —— §3 单元测试矩阵新增 §3.11 Run Comparison;§4 集成测试场景新增 comparison 行;§10.2 变更记录加新行。
- [x] 8.3 已更新 `docs/acceptance/acceptance_report.md` —— §6 加 §6.8 Run Comparison / Baseline Regression 验收记录;§7 表里 ~~README §7 第 7 项 Run Comparison~~ 占位关闭;§8.1 自动化验收行更新到 848 通过;§9.2 变更记录加 v1.4 行。
- [x] 8.4 **未**把 `design.md` 长文复制进 `docs/`;LLD 新章节只追加接口 / 字段摘要 + 分层边界,详细算法仍引用 `design.md` 与源码。

## 9. Acceptance

- [x] 9.1 Level 0(离线):`python -m pytest -q` 全绿 —— **848 passed** (2026-04-25 实测,基线 549 + Run Comparison 模块 299 新用例 = 52 + 50 + 69 + 65 + 59 + 4)。
- [x] 9.2 Level 0 CLI:`python -m framework.comparison --baseline-run <id_a> --candidate-run <id_b> --artifact-root <fixture_root>` 产出合法 JSON + Markdown(`tests/integration/test_run_comparison_cli.py::test_python_m_framework_comparison_happy_path` 守门)。
- [x] 9.3 Level 1 / 2:**本 change 不新增任何 Level 1 / 2 验证项**(comparison 不需要 key / UE / ComfyUI)。
- [x] 9.4 Windows + macOS + Linux 路径兼容:本机 Windows 实测通过;`_safe_path_segment` / `_console_safe` / `_snapshot_tree` 全部用 POSIX-relative 字符串规范化,跨平台行为一致。**注**:macOS / Linux CI 未建立(对应 acceptance_report TBD-T-001),留 CI 接入或异机验证时收尾。

---

## Documentation Sync

> 本段为 `docs/ai_workflow/README.md` §4.4 要求的 Documentation Sync Gate 检查清单。archive 本 change 之前必须勾选每一项。

- [ ] Check whether openspec/specs/* needs update after archive — **跳过本轮**:tasks.md §7.2 显式禁止实现 / Documentation Sync 阶段改 `openspec/specs/`;主 spec 同步留 `/opsx:archive` 的 sync-specs 步骤执行。
- [x] Check whether docs/requirements/SRS.md needs update — **跳过**:Run Comparison 是开发 / 诊断工具,不引入新 FR / NFR,不改变用户可见功能需求。docs/ai_workflow/README.md §4.2 "不机械同步"。
- [x] Check whether docs/design/HLD.md needs update — **跳过**:LLD §15 已记录模块级设计 + 分层边界,HLD 架构边界(子系统拓扑)未实质变更;Run Comparison 作为 sibling read-only consumer 与既有架构图相容。本轮不扩 HLD,留下次架构整理批量更新。
- [x] Check whether docs/design/LLD.md needs update — **已更新**:见 tasks.md §8.1。新增 §15 + 重编号老 §15-§17 + §18.3 变更记录。
- [x] Check whether docs/testing/test_spec.md needs update — **已更新**:见 tasks.md §8.2。新增 §3.11 + §4 集成行 + §10.2 变更记录。
- [x] Check whether docs/acceptance/acceptance_report.md needs update — **已更新**:见 tasks.md §8.3。新增 §6.8 + 关闭 §7 表 Run Comparison 占位 + §8.1 测试总数 549 → 848 + §9.2 变更记录。
- [x] Check whether README.md needs update — **已更新**:§"后续扩展" 第 7 项 Run Comparison 从"`observability/run_comparison.py` 待补"改为"已实装",指向 `python -m framework.comparison`,记录默认产物 `comparison_report.json` / `comparison_summary.md`。
- [x] Check whether CHANGELOG.md needs update — **已更新**:`[Unreleased].Added` 新增 Run Comparison 模块条目(models / loader / diff_engine / reporter / cli / __main__ + CLI 入口 + 离线 fixture + integration coverage)+ deferred follow-up `lazy-artifact-store-package-exports`。
- [x] Check whether CLAUDE.md needs update — **跳过**:无新 AI 协作约定;本 change 是 OpenSpec 工作流的具体应用,不修改工作流本身;CLI `python -m framework.comparison` 是用户可见命令(已记入 README),不属于 AI 协作核心高频命令。
- [x] Check whether AGENTS.md needs update — **跳过**:与 CLAUDE.md 同步规则(`AGENTS.md:3` 显式声明镜像);CLAUDE.md 既然不动,AGENTS.md 也保持原状。
- [x] Record skipped docs with reason — **已记录**:本段每个 "跳过本轮" / "跳过" 行均含原因。`openspec/specs/*` 跳过原因独立(留 archive 阶段),其他 4 份(SRS / HLD / CLAUDE / AGENTS)按 docs/ai_workflow/README.md §4.2 "不机械同步" 原则评估后跳过。
- [x] Mark doc drift for human confirmation if sources conflict — Documentation Sync Gate 阶段(2026-04-25)发现的 drift 分两类:

  **类别 A — 本轮已修(在白名单内)**:
  1. `tasks.md §4.1` 原写 `comparison_report.md` → 已对齐为 `comparison_summary.md`(实装常量 `reporter.MARKDOWN_FILENAME`)。
  2. `tasks.md §1.4 / §2.4 / §3.5` 验证段 per-file 用例数 32 / 96 / 43 → 已对齐为实测 52 / 50 / 69(`pytest --collect-only`)。
  3. `tasks.md §2.1` `_resolve_run_dir`(私有名)→ 已对齐为 `resolve_run_dir`(实装公开名,loader.py:110)。
  4. `tasks.md §2.2` `load_run_snapshot` 签名漏 `strict` → 已补 `strict: bool = True` keyword-only。
  5. `tasks.md` 顶部 doc-only 阶段措辞 → 已更新为当前阶段(实装已完成,Documentation Sync Gate 修复中)。
  6. `docs/testing/test_spec.md §3.11` per-file 用例数 32 / 96 / 43 → 已对齐 52 / 50 / 69;§24 / §66 / §386 / §387 / §458 / §462 历史基线数字 549 / ≤15s / ≤18s 等 → 已加 "历史基线 (2026-04-23)" 标注或更新到当前实测 848 / ~28s。
  7. `docs/acceptance/acceptance_report.md §49 / §704 / §719` 残留 549 → 已加历史基线标注 / 同步当前 848;§6.8 / §8.1 per-file 用例数 → 已对齐 52 / 50 / 69。
  8. `README.md §10 / §286 / §310` 长期残留 "143 条测试" → 已改为不硬编码,引用 `pytest -q` 实测。

  **类别 B — 本轮 Documentation Sync Gate 不在白名单,留 archive / sync-specs 阶段处理**:
  9. `openspec/changes/add-run-comparison-baseline-regression/proposal.md:61` 仍写 `--baseline <id_a> --candidate <id_b>` + `comparison_report.md` —— 实装是 `--baseline-run` / `--candidate-run` + `comparison_summary.md`。
  10. `openspec/changes/add-run-comparison-baseline-regression/design.md:37 / :131 / :176` 仍写 `comparison_report.md`(§5 Markdown 段 + 目录树)+ `hash_bytes`(实装是 `framework.artifact_store.hashing.hash_payload`)。
  11. `openspec/changes/add-run-comparison-baseline-regression/specs/runtime-core/spec.md:17` THEN 子句仍写 `comparison_report.md`,与 reporter `MARKDOWN_FILENAME` 不一致。

  类别 B 共 3 文件 / 5 处。**当前代码事实**:CLI 用 `--baseline-run` / `--candidate-run`;Markdown 产物名是 `comparison_summary.md`;hash 复用走 `hash_payload`。这些 drift 留 `/opsx:archive` 触发 sync-specs 阶段一并处理,本轮 Documentation Sync Gate 严格守"不动 proposal / design / openspec/specs/"白名单边界。

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
