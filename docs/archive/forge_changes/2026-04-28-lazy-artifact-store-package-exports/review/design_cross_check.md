---
change_id: lazy-artifact-store-package-exports
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/artifact-contract/spec.md
codex_review_ref: review/codex_design_review.md
plugin_command: "/codex:adversarial-review --background (companion script bash invocation, codex-companion.mjs)"
plugin_task_id: "thread 019dcf19-1266-7720-9340-7c04d75eb68b / turn 019dcf19-15ec-7453-815d-823d1b75e0c1 (Claude task id bnwyv3npv)"
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-04-27T21:17:02+08:00
resolved_at: 2026-04-27T21:42:00+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: null
writeback_commit: ea05260d3107b9c1a7851db9ca0096e54c1bfc73
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 cross-check 由 /forgeue:change-plan S2→S3 codex design hook 触发。
  ## A. Decision Summary 段冻结于 codex 调用之前(2026-04-27 21:17),Claude 不允许在看完 codex review 后回填本段(协议自我保护 R6)。
  Codex 返 3 finding(2 high + 1 medium),Claude 独立 file:line 验证全部 verified=true,无虚构 claim;3 项均 accepted-codex,通过 commit ea05260d 回写到 design.md / tasks.md / proposal.md / specs/artifact-contract/spec.md(F1 sub-package consumer carve-out;F2 subprocess PYTHONPATH+__file__ 守门;F3 __dir__ 函数 + spec 4th Scenario + 新 fence)。disputed_open 收尾为 0,aligned_with_contract: true。
---

# S2→S3 Design Cross-check: lazy-artifact-store-package-exports

## A. Claude's Decision Summary (frozen before codex run, 2026-04-27 21:17 +08:00)

> 本段为 Claude 在调 `/codex:adversarial-review` 之**前**对 contract 三件套(proposal / design / tasks / spec)关键设计决策的立场冻结。Claude 不允许在看完 codex review 后回填本段。

### 关键设计决策

- **D-LazyTemplate**:`src/framework/artifact_store/__init__.py` 改 PEP 562 `__getattr__` lazy export 模板,沿用同 repo `src/framework/comparison/__init__.py:50-95` 的现成实现 —— frozenset 名称分组 + `__getattr__` 中 `from framework.artifact_store import <submodule>` + `globals()[name] = value` write-back cache + `if TYPE_CHECKING:` 块辅助 mypy。`design.md` §Decisions Decision 1。

- **D-EagerHashing**:`hashing` 子模块保持 eager(`from framework.artifact_store.hashing import hash_inputs, hash_payload`),仅 `repository` / `payload_backends` / `lineage` / `variant_tracker` 走 lazy。理由:`hashing.py` ~50 行零依赖,任何 caller(包括 read-only `comparison.loader`)都用得到,延迟收益接近 0。`design.md` §Decisions Decision 2。

- **D-CallsiteZeroChange**:30+ 个既有 callsite(`from framework.artifact_store import ArtifactRepository, get_backend_registry` 等)零修改,通过 `__all__` 9-name 列表 byte-identical 保留 + PEP 562 透明转发实现兼容。`design.md` §Goals 第 3 条 + Non-Goals 第 2 条。

- **D-FenceScope**:fence test `test_no_callsite_uses_submodule_path`(`tests/unit/test_artifact_store_lazy_imports.py` 3.1.3)主动**排除** `src/framework/artifact_store/**` 包内部 + 排除 change 目录自身;fence 的目标是**包外** callers,不是 intra-package import 结构。这是 contract 精度细节,21:14 的最终扫查发现自己的 design.md Risk A 原文"已 grep 全 repo,0 个匹配"措辞过宽,21:15 已修为"排除包内部后 0 个匹配"。`design.md` §Risks A + tasks.md §3.1.3。

- **D-SpecModified**:`openspec/specs/artifact-contract/spec.md` 加 1 个 ADDED Requirement「Package import surface is lazy-load by default」+ 3 个 Scenario(read-only consumer 不污染 / 首次访问加载并 cache / 30+ 既有 callsite 透明兼容)。把约束从测试 fence 提升到 spec 级合约,避免未来再有 read-only consumer 出现时 fence 又被人为放宽。`design.md` §Decisions Decision 3。

- **D-NewFenceTriple**:新增 fence 文件 `tests/unit/test_artifact_store_lazy_imports.py` 含 3 个测试 —— (a) subprocess 启动后 `sys.modules` 干净 / (b) 首次属性访问加载 submodule 并 cache(getattr 两次返回同一 object) / (c) 包外无 submodule path callsite。3.1.1 + 3.1.2 用 subprocess 是为了避开同一 pytest session 内其他测试已加载 `repository` 等模块的 `sys.modules` 污染。`tasks.md` §3.1.1-3.1.3。

- **D-FenceTighten**:既有 `tests/unit/test_run_comparison_loader.py::TestImportFence` + `tests/unit/test_run_comparison_cli.py::TestCliImportFence` 的禁止清单加回 `framework.artifact_store.repository` / `payload_backends` / `lineage` / `variant_tracker`(原 Task 5 carve-out 撤销),同时删 `comparison/cli.py` + 测试 docstring 中"transitive load 不可避免"段落,改为指向新 spec Requirement。`tasks.md` §4.1-4.4。

- **D-ScopeTight**:不动任何 `artifact_store/` 子模块文件(`hashing.py` / `repository.py` / `payload_backends/*` / `lineage.py` / `variant_tracker.py` 全部不动),不改 `runtime/` / `providers/` / `review_engine/` / `ue_bridge/` / `workflows/` / `observability/` 任何 callsite,不改 schema,不引入新依赖。Migration Plan 5 步走;Rollback 一句 `git revert` 一步回滚(零 schema + 零 callsite + 公共 API 不变)。`design.md` §Non-Goals + §Migration Plan + §Rollback。

### 已知风险与缓解(冻结于此刻)

- **Risk A**:包外 callsite 通过 `framework.artifact_store.repository.X` 子模块路径访问 → grep 实测排除包内部后 0 个匹配;新 fence 守门
- **Risk B**:`mypy` / `pyright` 静态分析在 lazy 模式下丢失类型 → `if TYPE_CHECKING:` 块导入 lazy 符号(`framework/comparison/__init__.py:30-48` 已验证此 pattern 在本 repo `mypy` 配置下不产生类型 noise)
- **Risk C**:循环依赖产生 `AttributeError` → 实测依赖图 `hashing`(零依赖)→ `payload_backends`(依赖 `hashing`)→ `repository`(依赖 `hashing` + `payload_backends`)→ `lineage`(零内部依赖)→ `variant_tracker`(零内部依赖),无 cycle
- **Risk D**:PEP 562 在 IDE 跳转 / 补全 / `dir()` 中不可见 → `__all__` 显式列出 + `if TYPE_CHECKING:` 让静态跳转可工作;运行时 `dir()` 缺 lazy 符号是 PEP 562 已知 trade-off,本 repo `comparison` 已验证可接受
- **Risk E**:全套测试矩阵某处隐式依赖 transitive load → Level 0 `pytest -q` 必须 baseline+3 全绿 + Level 1 P0/P3 离线冒烟 + mypy 三级 verify 守门

### 已知 contract 自查项(冻结于此刻,作为本次 cross-check 的 Claude 起点状态)

- design.md Risk A 21:15 已修(原"0 个匹配"→ 新"排除包内部后 0 个匹配")
- tasks.md 3.1.3 21:15 已修(加 fence 排除 `src/framework/artifact_store/**` 与 change 目录)
- proposal.md / design.md / spec.md / tasks.md `openspec validate --strict` 21:16 PASS

### Claude 自评的 contract 弱点(诚实声明,作为 codex 重点对照入口)

- spec.md 3 个 Scenario 是否覆盖足够多 PEP 562 边界:`hasattr()` / `getattr(default)` / `dir()` 行为 / sub-interpreter 语义 —— 未覆盖
- tasks 5.5 mypy 检查命令仅扫 6 个高频文件,未跑全 `src/` —— 是否漏掉 lazy 模式下的隐藏类型推断回归
- spec.md ADDED Requirement 是否足以反向**禁止**未来再出现 eager re-export(只声明 SHALL NOT 加载,但没说"不得加新 eager re-export 行")—— 反向禁令缺失
- 文档 sync gate 只覆盖 10 文档列表,但 `openspec/changes/archive/2026-04-26-add-run-comparison-baseline-regression/tasks.md §"Deferred Follow-ups"` 自己引用了本 change name —— 是否需要在归档时同步指明"已落地"

## B. Cross-check Matrix

| ID | Claude's choice (from ## A) | Codex's verdict | Codex's reasoning(摘要 + 引用) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| **F1 D-FenceScope** (high) | tasks 3.1.3 fence 排除"`src/framework/artifact_store/**` 包内部 + change 目录"两类 → "0 包外匹配"(Risk A) | dispute (high blocker) | `tests/unit/test_payload_backends.py:9` 顶层 + `:84` function-local 直接 `from framework.artifact_store.payload_backends import (...)` 与 `... import file_backend`,会让 fence 在现有树上自撞失败 | **accepted-codex** | design.md callsite 表加第 4 行(sub-package 内部 backend 类合法 consumer)+ Risk A 文字加排除项;tasks 3.1.4 fence exclude list 加 `tests/unit/test_payload_backends.py` 与 `*.pyc` / `__pycache__/` 路径,并在测试代码里写明每条排除原因(commit ea05260d) |
| **F2 D-SubprocessPath** (high) | tasks 3.1.1/3.1.2 用 subprocess 启动干净进程跑 `import framework.artifact_store`(隐含假设 sys.path 干净 = sys.modules 干净) | dispute (high blocker) | `tests/conftest.py:24-31` 只把 `src/` 加到 pytest **主进程** sys.path,fresh `subprocess.run([sys.executable, ...])` 不继承该 mutation;fresh checkout / xdist worker / 旧 editable install 任一情况下,要么 `ModuleNotFoundError`,要么误命中已安装包而非 working tree | **accepted-codex** | tasks 3.1.0 新增 `_run_clean_subprocess` 助手,resolve `_REPO_ROOT.parents[2]` + 注入 `PYTHONPATH=<src>` env;3.1.1 / 3.1.2 / 3.1.3(新)子进程脚本顶部 assert `framework.artifact_store.__file__` 落在 working-tree `src/` 下;commit ea05260d |
| **F3 D-DirInspect** (medium) | Risk D 接受 "`dir()` lazy 后看不到未访问符号" 为 PEP 562 已知 trade-off,不补救 | dispute (medium) | PEP 562 `__getattr__` alone 不影响 `__dir__`;eager 时 `dir()` / `inspect.getmembers()` 见全 9 个公共符号,lazy 后未访问前缺失,违 design.md "公共 API 表面零变化" 承诺;影响 plugin 自动发现 / Sphinx autodoc / REPL 交互 | **accepted-codex** | design.md Decision 1 模板加 `__dir__` 函数返回 `sorted(set(__all__) \| set(globals()))` + Risk D 改为"实现 `__dir__` 守门 introspection 契约";tasks 2.4 加实现步骤;spec.md 新增第 4 个 Scenario "dir() and inspect.getmembers() see the full public API surface even before any lazy symbol has been accessed";tasks 3.1.3 新 fence `test_dir_returns_full_public_api_surface_before_any_lazy_access`;proposal.md What Changes 同步;commit ea05260d |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。Codex 3 项发现全部独立 file:line 验证 verified=true,全部 accepted-codex 通过 commit `ea05260d` 回写到 contract 三件套 + spec delta。无 `disputed-pending` / `disputed-blocker` / `disputed-permanent-drift` 项。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 对 codex 3 条 finding 逐条独立验证 file:line evidence(2026-04-27 21:25-21:35,**不**直接采信 codex 措辞):

| ID | Codex claim 引用 | Claude verify 步骤 | 结论 |
|---|---|---|---|
| **F1** | `tests/unit/test_payload_backends.py:9` 顶层 import + `:84` function-local | Read tool 实读 line 1-20 + line 75-95:确认 line 9 = `from framework.artifact_store.payload_backends import (` + line 84 = `from framework.artifact_store.payload_backends import file_backend` | **verified=true** — 真实 contract drift。我 design.md Risk A "0 个包外匹配" 漏数。`BlobBackend` / `FileBackend` / `InlineBackend` 不在 `framework/artifact_store/__init__.py::__all__`,该测试是合法 sub-package consumer |
| **F2** | `tests/conftest.py:24-31` 只 mutate 主进程 sys.path,subprocess 不继承 | Read tool 实读 conftest.py 全文 1-63:确认 line 27-31 是 `_REPO_ROOT = Path(__file__).resolve().parents[1]` + `for _p in (_SRC, _REPO_ROOT): if str(_p) not in sys.path: sys.path.insert(0, str(_p))`,典型 conftest pattern,只对主进程生效 | **verified=true** — Python subprocess 语义本就如此,`subprocess.run([sys.executable, "-c", ...])` 启 fresh interpreter,完全不读 parent 的 sys.path mutation。tasks 3.1.1/3.1.2 没说怎么处理这个,真 bug |
| **F3** | `framework/comparison/__init__.py:74-95` 也未实现 `__dir__`,我 follow 这个 reference 也会有相同盲区 | Read tool 实读 comparison/__init__.py 73-122:确认仅有 `__getattr__` 函数 + `__all__` 列表,无 `__dir__` 定义 | **verified=true** — reference 实现确实没补 `__dir__`。PEP 562(Python 3.7+)明确支持模块级 `__dir__`,与 `__getattr__` 独立。我 design.md Risk D 措辞"接受 trade-off" 把契约缺口当 feature 显然不对 |

**全部 verified = true**,无 codex 虚构 claim,无 partial 项。

### D.2 修复完整性(commit ea05260d)

| Finding | Contract 修改文件 | 行数变化 | 内容 |
|---|---|---|---|
| F1 | `design.md` callsite table + Risk A | +12 / -3 | 表加第 4 行(sub-package 内部 backend 类)+ Risk A 文字增补 |
| F1 | `tasks.md` 3.1.3 → 3.1.4 + exclude list | +5 / -1 | exclude (a)(b)(c)(d) 四类 + 显式说明 sub-package consumer 不是 fence target |
| F2 | `tasks.md` 3.1.0 + 3.1.1 + 3.1.2 + 3.1.3 | +新增 3.1.0 / 各 step 重写 | `_run_clean_subprocess` helper 注入 PYTHONPATH;每个子进程脚本 assert `__file__` 落 working-tree |
| F3 | `design.md` Decision 1 template + Risk D | +18 / -1 | `__dir__` 函数 docstring + 实现 + Risk D 改为"实现 mitigation" |
| F3 | `tasks.md` 2.4 新增 + 5.1 测试基线 +1 | +2 | 实现 `__dir__` step + fence 数 3→4 |
| F3 | `specs/artifact-contract/spec.md` 4th Scenario | +6 | dir + inspect.getmembers 守门 |
| F3 | `tasks.md` 3.1.3 new fence | +1 | `test_dir_returns_full_public_api_surface_before_any_lazy_access` |
| F3 | `proposal.md` What Changes bullet 5 | +1 | `__dir__` 实施承诺 |

**Verify 步骤**:`openspec validate lazy-artifact-store-package-exports --strict` 实测 PASS(2026-04-27 21:40);commit ea05260d `git show --stat` 实测 5 files / +355 -0 lines,与 frontmatter `writeback_commit` 引用一致。

### D.3 协议自我保护合规

- `## A` 段于 2026-04-27 21:17 +08:00 冻结(commit 之前、调 codex 之前)
- 21:18-21:30 调 codex `/codex:adversarial-review --background`(task `bnwyv3npv`,`bxs6igl8` 因 shell quote 失败重提)
- 21:30 codex 输出落本地 `tasks/bnwyv3npv.output`,3 finding 返回
- 21:32 Claude 在 `## A` 之外的位置(本段 + ## B/C/D)写入回应,**未**回填 `## A`(R6 防 anchoring bias 合规)

### D.4 进 S3 前置

- `disputed_open: 0` ✓
- 全部 finding 已通过 commit ea05260d 真实 writeback 到 contract ✓
- frontmatter `aligned_with_contract: true`(post-writeback)✓
- frontmatter `writeback_commit: ea05260d3107b9c1a7851db9ca0096e54c1bfc73`(实 hash,可 `git show` 验证)✓
- `openspec validate lazy-artifact-store-package-exports --strict` PASS ✓
- 可继续 Step 7(Superpowers `writing-plans` skill 输出 `execution/`)+ Step 8(`forgeue_change_state.py --writeback-check`)→ S3 转移
