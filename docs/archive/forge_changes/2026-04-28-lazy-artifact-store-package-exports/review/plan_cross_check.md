---
change_id: lazy-artifact-store-package-exports
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - design.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - review/codex_plan_review.md
  - review/design_cross_check.md
codex_review_ref: review/codex_plan_review.md
plugin_command: "/codex:adversarial-review --background (companion script bash invocation, codex-companion.mjs)"
plugin_task_id: "thread 019dcf33-2cd2-7542-bc87-370e727a8a39 / turn 019dcf33-311a-7d73-a538-be49e41ef53c (Claude task id bpgwettqx)"
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-04-27T21:46:42+08:00
resolved_at: 2026-04-27T22:05:00+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: null
writeback_commit: 5ce16c144f30e01b6531b21b8b8d89b043db6d34
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 plan_cross_check 由 /forgeue:change-apply S3→S4-S5 codex plan hook 触发。
  ## A. Decision Summary 段冻结于 codex 调用之前(2026-04-27 21:46 +08:00),Claude
  不允许在看完 codex review 后回填本段(协议 R6 防 anchoring bias)。Codex 返 4 finding
  (1 high + 3 medium),Claude 独立 file:line 验证 4/4 verified=true 无虚构 claim;4 项
  全部 accepted-codex 通过 commit 5ce16c14 真实回写到 spec.md / design.md / tasks.md /
  execution_plan.md / micro_tasks.md 5 文件。codex P5 (__dir__ globals 边界) + P6
  (binary file skip) 由 codex 主动判定 not blocker(__dir__ 通过 __all__ 已含 lazy
  名;Path.rglob('*.py') 只读 .py 文件不会碰 binary)。disputed_open 收尾为 0。
---

# S3 Plan Cross-check: lazy-artifact-store-package-exports

## A. Claude's Decision Summary (frozen before codex run, 2026-04-27 21:46 +08:00)

> 本段为 Claude 在调 `/codex:adversarial-review` 之**前**对 plan 两件套(execution_plan.md / micro_tasks.md)关键计划决策的立场冻结。Claude 不允许在看完 codex review 后回填本段。

### 关键计划决策

- **D-FileStructure**:5 文件编辑列表 — 1 production rewrite(`src/framework/artifact_store/__init__.py`)+ 1 new test file(`tests/unit/test_artifact_store_lazy_imports.py` ~140 行)+ 2 modify test files(`tests/unit/test_run_comparison_loader.py` + `cli.py` 各动 forbidden_prefixes 列表 + class docstring)+ 1 modify production docstring(`src/framework/comparison/cli.py` 顶 docstring)。`execution_plan.md` 文件结构表 + `micro_tasks.md` G2/G3/G4 commit 块。

- **D-CommitGranularity**:7 个 task group → 4 个生产 commit(G2 / G3 / G4 / G6)+ G1/G5/G7 零 LOC 验证 commit(G7 evidence 文件可单独 commit)。每 commit 单一 concern,便于 `git bisect` 隔离回归来源。`micro_tasks.md` 每 group 末尾 commit step + 含完整 `Co-Authored-By` trailer。

- **D-CommitOrder**:G2(production lazy `__init__.py`)→ G3(new fences)→ G4(tighten existing fences)。**故意不走严格 TDD red-first**:G2 commit 单独时测试包仍绿(eager → lazy 透明转发,30+ callsites + 既有 fence 都 PASS);G3 commit 加 4 fence 守 spec 4 个 Scenario(此时 lazy 已生效,fence 直接 green-on-arrival);G4 紧 fence 是后置清理,与 G2 顺序无关但放后面减少 G2 commit 内噪声。理由:fence 是 spec contract 的镜像,不是 G2 的 driving test;严格 TDD red-first 在结构性 refactor(eager → lazy,行为零变化)中是 ceremonial 而非有用。**自评:此点是 codex 大概率会挑战的决策**。

- **D-FenceCarveOut**:G3 `test_no_callsite_uses_submodule_path` fence 排除 4 类路径(`src/framework/artifact_store/**` 包内部 / `tests/unit/test_payload_backends.py` sub-package consumer / 本 change 目录 / `*.pyc` + `__pycache__/`),每条排除原因写进测试代码 inline 注释;`micro_tasks.md` G3 Step 3.1 fence 实现块 + G3 self-doc 部分有解释。

- **D-SubprocessHelper**:`_run_clean_subprocess(script: str)` 助手 — `_REPO_ROOT = Path(__file__).resolve().parents[2]` + `_SRC = _REPO_ROOT / "src"` + `env = {**os.environ, "PYTHONPATH": str(_SRC) + os.pathsep + os.environ.get("PYTHONPATH", "")}` + `subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True, timeout=30)` + 返 `json.loads(stdout)`。**`os.pathsep` 跨平台兼容**(Windows `;` / Unix `:`);**`timeout=30`** 防 future regression 卡 subprocess。

- **D-DirImpl**:`__dir__` 函数返 `sorted(set(__all__) | set(globals()))` —— `list[str]` 类型(PEP 562 protocol)。`micro_tasks.md` G2 Step 2.1 production code 块 line 76-77 + `execution_plan.md` Risks 段第 5 条已 lock 类型 + 实现签名。

- **D-FenceTestNames**:4 个 fence test function 名 lock —— `test_import_artifact_store_does_not_pull_repository_or_payload_backends` / `test_first_access_of_lazy_symbol_loads_submodule_and_caches` / `test_dir_returns_full_public_api_surface_before_any_lazy_access` / `test_no_callsite_uses_submodule_path`。每个对应 spec.md 1 个 Scenario(S1/S2/S4/S3)。

- **D-VerifyMatrix**:G5 验证三层 — Level 0 full `pytest -q`(baseline+4)+ Level 0 narrow 9 个 artifact_store-touching suite(unit + integration P0-P4)+ Level 1 P0/P3 offline `framework.run` + targeted mypy 6 个高频文件。**未跑** Level 2 (`--live-llm`):lazy export 与 LLM 调用无关,不 burn API quota。

- **D-DocSyncMatrix**(预测,subject to runtime confirm):per-doc 决策预测 — `test_spec.md` REQUIRED / `acceptance_report.md` REQUIRED / `CHANGELOG.md` REQUIRED / 其余 7 文档 SKIP。`micro_tasks.md` Step 6.2-6.11 每 doc 给 SKIP 时记录原因;`forgeue_doc_sync_check.py` 静态扫结果会 override 此预测,本 plan 不强压。

- **D-FinishGateOrder**:G7 顺序 — verify(Level 0/1/2 编排)→ review(Superpowers + codex)→ blocker writeback(若有)→ finish gate(12-key + cross-check + writeback truthfulness + tasks.md `[x]` + strict validate)→ archive(sync-specs)。**G7.3 blocker writeback 显式说明可能 force return 到 G2/G3/G4** —— plan 不假设 review 必绿。

### 自评的 plan 弱点(诚实声明,作为 codex 重点对照入口)

- **W1 D-CommitOrder 故意非 TDD red-first**:G2 production 先于 G3 fence,严格 TDD discipline 看会被批"先实现再写测试"。我认为 spec contract 已 lock fence 行为,fence 是 spec 镜像不是设计驱动。**预期 codex 挑战此选择;我准备好 disputed-pending 然后写 reason ≥ 50 字论证 disputed-permanent-drift**(若 codex 给出强论据再 accepted-codex 翻转)
- **W2 micro_tasks G3 Step 3.1 fence 用 `subprocess.run + inline ; -c "<long script>"`**:script 内多语句用 `;` 串联,fail 时 traceback 难定位;替代方案是写小辅助 .py 文件 `tests/unit/_lazy_fence_subprocess.py` 然后 `python <helper> --mode=test1`。**自评易读性差,但与 `_run_clean_subprocess` 助手解耦的代价是 fence 文件 self-contained 性下降**
- **W3 G6 DocSync 决策矩阵是预测**:实际 `forgeue_doc_sync_check.py` 输出可能 reclassify 某文档为 [REQUIRED];例如 LLD §5 若引用 `__init__.py` eager 行,则 `tasks.md#6.5` 从 SKIP 翻为 REQUIRED。预测准确度 ~70%
- **W4 micro_tasks 含中文注释 + commit message 中英混排**:ForgeUE memory `feedback_ascii_only_in_adhoc_scripts` 反面 — 用户偏好中文沟通技术名词留英文,但 inline test code 注释用英文更安全(GBK 终端打印中文 traceback 崩);我目前 fence test 文件注释是英文,但 `micro_tasks.md` 自身有中文。两者是不同 layer,**预期 codex 不会挑这条**,但记一下
- **W5 plan 未覆盖 `__dir__` 性能影响**:`inspect.getmembers()` 触发全 lazy 一次性 materialization 时,会加载 `repository.py`(链式拉 `lineage` / `payload_backends`)+ `payload_backends/{base,inline,file,blob}.py` —— 一次 ~7-8 个模块。对外部插件框架(如 hypothetical Sphinx autodoc)是 O(N) 一次性成本,未必接受。`design.md` Risk D 把这点描述为"correct PEP 562 behavior, not a regression",但**未给数值** —— 预期 codex 不挑这条(还在 acceptable 边界),记一下

### 已知 plan 自查项(冻结于此刻)

- `execution/execution_plan.md` 21 个 `tasks.md#X.Y` 锚点引用,与 tasks.md 实际 task item ID 1:1 对应(forgeue_change_state.py --writeback-check DRIFT type 2 实测通过,exit 0 / drifts: [])
- `execution/micro_tasks.md` 7 Task block 头每个引用 1+ tasks.md 锚点
- 21:50 strict validate PASS / state: S3
- `git log --oneline -3` 显示 commit `ea05260d`(P0 contract scaffold + S2 writeback)+ `6318b93`(S2→S3 evidence)已 land;HEAD 干净 / 无 staged

## B. Cross-check Matrix

| ID | Claude's choice (from ## A) | Codex's verdict | Codex's reasoning(摘要 + 引用) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| **F1 D-PerSymbolLazy** (high) | spec.md scenario 2 写"first attribute access loads the corresponding submodule";Claude 默认这是合 design value 的强约束 | dispute (high blocker) | spec.md:5 + 17-21 文本要求 4 submodule "loaded only when their exported symbols are accessed";但 `repository.py:24-29` 顶层 import lineage / payload_backends.base / variant_tracker → 访问任一 write-side symbol 必 cluster-materialize ~7-8 个 submodule;fence 3.1.2 只测 repository in sys.modules,不测 cluster 其余三者保持 absent → fence 可绿但 spec 已违 | **accepted-codex** | spec.md Requirement 文本 "loaded only when..." 改为 "MAY be loaded as a coupled cluster..."(诚实 cluster 行为);spec.md Scenario 2 重命名"...loads the directly-targeted submodule plus its intra-package cluster" + 显式承认 lineage / payload_backends / variant_tracker 一同出现 in sys.modules;design.md Decision 2 加"接受的 cluster materialization 副作用"段;tasks.md 3.1.2 加 note "intentionally only asserts repository in sys.modules, not absence of others";commit 5ce16c14 |
| **F2 D-CommitOrder** (medium) | G2 production → G3 fence 顺序;新 fence green-on-arrival 是 acceptable for 结构性 refactor(W1 自评弱点) | dispute (medium) | green-on-arrival 测试不能证伪 PYTHONPATH/import-location 错误;新 sys.modules contract fence 应该 red-first 至少跑过一次 against eager baseline | **accepted-codex** | micro_tasks.md G2 加 Step 2.0 G2 pre-step "Capture red baseline":先 stage fence 文件 → 跑 against eager `__init__.py` → 期 FAIL → 落 evidence/tdd_red_baseline.md(12-key + `evidence_type: tdd_log`)→ revert fence 文件 → 进 Step 2.1 production change。commit history 仍 G2 → G3,但红基线证据证 fence 不是 green-on-arrival 假绿。commit 5ce16c14 |
| **F3 D-FileBoundary** (medium) | execution_plan File Structure 5 文件硬边界;G6 commits stage docs/ + CHANGELOG + evidence/ | dispute (medium) | 5 文件边界与 G6/G7 stage 命令自相矛盾;boundary check gate 严格执行会判 G6 全部违规,或 G6 跑会违 plan 自身 boundary | **accepted-codex** | execution_plan.md File Structure 表拆 2 表:**Implementation files (production scope, 5 files)** = 边界检查目标 + **Authorized auxiliary files (DocSync + evidence scope)** = exempt allow-list 列出 docs/test_spec.md / docs/acceptance_report.md / CHANGELOG.md / `evidence/` / `review/` / `execution/`。Scope Check 段加 2-bucket 说明。commit 5ce16c14 |
| **F4 D-FenceCount** (medium) | execution_plan Architecture 行 "three new fence tests" + 同 plan +4 budget 预算 + tasks.md G6.6 "3 new fences" + micro_tasks 实造 4 fence | dispute (medium) | "3 vs 4" 不一致跨多文件;根因 = S2 codex F3 加 `__dir__` fence 时未同步 G6.6;test_spec / acceptance baseline 更新会沿用错误 3 数 | **accepted-codex** | execution_plan.md Architecture "Three new fence tests" → "**Four** new fence tests... S2 codex F3 added the `__dir__` fence as the 4th";tasks.md 6.6 "3 new fences" → "**4 new fences**" + 4 个 fence 函数名全列;commit 5ce16c14 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。Codex 4 项发现全部独立 file:line 验证 verified=true,全部 accepted-codex 通过 commit `5ce16c14` 回写到 spec.md / design.md / tasks.md / execution_plan.md / micro_tasks.md。无 `disputed-pending` / `disputed-blocker` / `disputed-permanent-drift` 项。

Codex 主动判 P5(`__dir__` globals 边界)与 P6(binary file `UnicodeDecodeError`)not blocker:
- P5 verdict:`__dir__` 返 `sorted(set(__all__) | set(globals()))`,`__all__` 已含 9 个 lazy 名,即使 globals 未 cache 任何 lazy 符号,`set` 并集仍含全 9 个 → dir 输出正确。Claude 同意。
- P6 verdict:fence 3.1.4 用 `Path.rglob("*.py")` + `text = path.read_text(encoding="utf-8")`,只读 `.py` 文件,不会碰 fixture 下的 `*.png` / `*.glb` binary → 无 `UnicodeDecodeError` 风险。Claude 同意。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 对 codex 4 项发现逐条独立验证 file:line evidence(2026-04-27 21:55-22:00,**不**直接采信 codex 措辞):

| ID | Codex claim 引用 | Claude verify 步骤 | 结论 |
|---|---|---|---|
| **F1** | `spec.md:5,17-21` Requirement + Scenario 2 文本 vs `src/framework/artifact_store/repository.py:24-29` 顶层 import | Read tool 实读 spec.md Requirement 段:确认文本 "These four submodules SHALL be loaded **only when** a caller actually accesses one of their exported symbols";Read tool 实读 repository.py:24-29 line by line:确认 24=`from framework.artifact_store.lineage import LineageIndex` / 25-28=`from framework.artifact_store.payload_backends.base import (...)` / 29=`from framework.artifact_store.variant_tracker import VariantTracker`;trace Python import 协议:`__getattr__("ArtifactRepository")` → load `repository` → `repository.py:24-29` cascade load `lineage` + `payload_backends` 包 init + 内部 `inline_backend` / `file_backend` / `blob_backend` + `variant_tracker` ≈ 7-8 模块同进 sys.modules | **verified=true** — 真实 spec/reality mismatch。spec 文本 over-promised,违 design value 实际无 impact(comparison.loader 永不访问 write-side symbol 所以 cluster 永不材化),但 contract 文本与 fence test 内部标准不自洽 |
| **F2** | `micro_tasks.md:291-306` Step 3.2 实文 "expect 4 PASS" + ## A W1 自评 | Read tool 实读 micro_tasks Step 3.2 段:确认实文是 "Run new fences and expect PASS" 而非 "expect FAIL then implement";自评 ## A W1 已 flag 此点,Claude 已知该选择存争议 | **verified=true** — green-on-arrival 真实存在;codex 给的 mitigation(red-baseline 捕获 + revert)成本 ~5 分钟 + 1 次 evidence 落盘,远低于 PYTHONPATH 错误漏过的代价 |
| **F3** | `execution_plan.md:43-53` File Structure 段 + G6 commit 命令 stage docs/ + CHANGELOG + evidence/ | Read tool 实读 execution_plan.md Scope Check 段(实文 "Implementation crosses one production module + three test modules + one production docstring. All changes ride one PR")+ G6 Step 6.13 commit 命令(`git add docs/ CHANGELOG.md openspec/changes/...evidence/`);确认两段表述自相矛盾 | **verified=true** — 真实自相矛盾;cleanest fix = 拆 2 表声明 production scope vs auxiliary scope |
| **F4** | `execution_plan.md:33-35` "three new fence tests" vs `tasks.md` G6.6 "3 new fences" vs `micro_tasks.md` 实造 4 fence | grep 实测:execution_plan Architecture 行 "Three new fence tests";同 plan G3 task group map "+4 (test count: baseline → baseline+4)";tasks.md G6.6 实文 "3 new fences";micro_tasks Step 3.1 fence test code 含 4 个 `def test_*` 函数。3 vs 4 跨 3 文件不一致 | **verified=true** — 根因清晰:S2 codex F3 加 `__dir__` fence 时只更新了 spec.md / design.md / tasks.md 2.4 + 3.1.3,**漏更** tasks.md G6.6 与 execution_plan.md Architecture 行 |

**全部 verified = true**,无 codex 虚构 claim,无 partial 项。Codex P5/P6 的 self-judged not-blocker Claude 验证后接受。

### D.2 修复完整性(commit 5ce16c14)

| Finding | Contract / Evidence 修改文件 | 行数变化 | 内容 |
|---|---|---|---|
| F1 | `specs/artifact-contract/spec.md` Requirement + Scenario 2 | +6 / -3 | 文本由 "loaded only when..." → "MAY be loaded as a coupled cluster..." + Scenario 2 改名 + 显式承认 cluster |
| F1 | `design.md` Decision 2 末尾 | +5 / 0 | 新增 "接受的 cluster materialization 副作用" 段,记 repository.py:24-29 cascade + 与 design value 相容性 |
| F1 | `tasks.md` 3.1.2 末尾 | +1 / 0 | Note "intentionally only asserts repository in sys.modules, not absence of others" |
| F2 | `execution/micro_tasks.md` G2 Step 2.0 新增 | +新增 ~25 行 | G2 pre-step "Capture red baseline":stage fence → run against eager → expect FAIL → 落 `evidence/tdd_red_baseline.md` → revert fence → 进 Step 2.1 |
| F3 | `execution/execution_plan.md` Scope Check + File Structure | +2 表 / -1 表 | 拆 "Implementation files (production scope, 5 files)" + "Authorized auxiliary files (DocSync + evidence scope)";Scope Check 段加 2-bucket 说明 |
| F4 | `execution/execution_plan.md` Architecture 行 | +1 / -1 | "Three new fence tests" → "**Four** new fence tests... S2 codex F3 added the `__dir__` fence as the 4th" |
| F4 | `tasks.md` G6.6 | +1 / -1 | "3 new fences" → "**4 new fences**" + 4 个 fence 函数名全列 |

**Verify 步骤**:`openspec validate lazy-artifact-store-package-exports --strict` 实测 PASS(2026-04-27 22:05);`forgeue_change_state.py --writeback-check` 实测 exit 0 / drifts: [];commit 5ce16c14 `git show --stat` 实测 5 files / +55 -10 lines,与 frontmatter `writeback_commit` 引用一致。

### D.3 协议自我保护合规

- `## A` 段于 2026-04-27 21:46 +08:00 冻结(commit 之前、调 codex 之前)
- 21:48-21:54 调 codex `/codex:adversarial-review --background`(task `bpgwettqx`,thread `019dcf33-2cd2-7542-bc87-370e727a8a39`)
- 21:54 codex 输出落本地 `tasks/bpgwettqx.output`,4 finding 返回(1 high + 3 medium)
- 21:55-22:00 Claude 在 `## A` 之外的位置(本段 + ## B/C/D)写入回应,**未**回填 `## A`(R6 防 anchoring bias 合规)
- 22:00-22:05 commit 5ce16c14 落 5 文件 writeback;22:05 写本 ## B/C/D + frontmatter `writeback_commit`

### D.4 进 S4-S5 前置

- `disputed_open: 0` ✓
- 全部 finding 已通过 commit 5ce16c14 真实 writeback 到 contract + evidence ✓
- frontmatter `aligned_with_contract: true`(post-writeback)✓
- frontmatter `writeback_commit: 5ce16c144f30e01b6531b21b8b8d89b043db6d34`(实 hash,可 `git rev-parse --verify`)✓
- `openspec validate lazy-artifact-store-package-exports --strict` PASS ✓
- `forgeue_change_state.py --writeback-check` exit 0 / drifts: [] ✓
- 可继续 Step 7(Superpowers `executing-plans` + TDD auto-trigger)+ Step 8(越界检测 git diff vs design.md modules)+ Step 9(writeback-check)→ S4→S5 转移
