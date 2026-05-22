---
change_id: retire-parallel-and-worktree-fully
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md#1
  - tasks.md#2
  - tasks.md#3
  - tasks.md#4
  - tasks.md#5
  - tasks.md#6
  - tasks.md#7
  - tasks.md#8
  - tasks.md#9
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round1.md
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - opsx:propose
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-06T10:26:44Z
created_at: 2026-05-06T10:26:44Z
---

# retire-parallel-and-worktree-fully Micro Tasks

> Bite-sized 实施步骤(每 step 2-5 min);沿 `superpowers:executing-plans` 节奏。每 phase commit 一次。每 step 含**明确文件路径 + 命令 + 期望输出**。

---

## Task P0 — Baseline(锚点 `tasks.md#1`)

**Files:**
- Create: `openspec/changes/retire-parallel-and-worktree-fully/verification/baseline.md`

### Step P0.1: 记录 git HEAD + pytest baseline

- [ ] **P0.1.1**:实测 pytest collect 数

```bash
python -m pytest -q --collect-only 2>&1 | tail -3
```

期望输出格式:
```
======== <N> tests collected in <T>s ========
```
记 `<N>` 为 baseline pytest 数(预期 549,实测确认)。

- [ ] **P0.1.2**:记 git HEAD SHA

```bash
git rev-parse HEAD
```

期望:`0d697fc...`(本 change 启动前的 commit)。

- [ ] **P0.1.3**:写 `verification/baseline.md` 含上述 2 数据 + 12-key audit frontmatter(`stage: S2` / `evidence_type: baseline`)

### Step P0.2: 验证 4 archived change finish_gate replay PASS

- [ ] **P0.2.0**:**前置校验 4 archive 目录确实存在**(沿 codex round 1 F2 inline writeback)

```bash
ls openspec/changes/archive/ | grep -E "runtime-enforcement|executable-enforcement|consent-gate|ledger-binding"
```

期望(4 行):
```
2026-05-05-enhance-workflow-automation-executable-enforcement
2026-05-05-enhance-workflow-automation-runtime-enforcement
2026-05-06-enhance-workflow-automation-ledger-binding
2026-05-06-restore-superpowers-worktree-consent-gate
```

注意:**runtime-enforcement 实际归档日期是 2026-05-05**(非 2026-05-04;codex round 1 F2 finding 揭示 tasks.md 原写错)

- [ ] **P0.2.1**:run finish_gate on 4 archived changes(**id 不带 `archive/` 前缀**,沿 `tools/_common.py:484-496 change_path()` 仅匹配 `archive entry.name.endswith(change_id)`)

```bash
python tools/forgeue_finish_gate.py --change 2026-05-05-enhance-workflow-automation-runtime-enforcement --json --dry-run 2>&1 | python -c "import sys, json; d = json.loads(sys.stdin.read()); print('runtime-enforcement:', 'PASS' if d.get('all_checks_passed') else 'FAIL')"
python tools/forgeue_finish_gate.py --change 2026-05-05-enhance-workflow-automation-executable-enforcement --json --dry-run 2>&1 | python -c "import sys, json; d = json.loads(sys.stdin.read()); print('executable-enforcement:', 'PASS' if d.get('all_checks_passed') else 'FAIL')"
python tools/forgeue_finish_gate.py --change 2026-05-06-restore-superpowers-worktree-consent-gate --json --dry-run 2>&1 | python -c "import sys, json; d = json.loads(sys.stdin.read()); print('restore-consent-gate:', 'PASS' if d.get('all_checks_passed') else 'FAIL')"
python tools/forgeue_finish_gate.py --change 2026-05-06-enhance-workflow-automation-ledger-binding --json --dry-run 2>&1 | python -c "import sys, json; d = json.loads(sys.stdin.read()); print('ledger-binding:', 'PASS' if d.get('all_checks_passed') else 'FAIL')"
```

期望:4 行全 `PASS`(若有 FAIL → 立即 user_required + 暂停本 change,沿 fence #1 / fence #2)

- [ ] **P0.2.2**:把 4 archived replay PASS 记到 `verification/baseline.md`

### Step P0.3: Commit baseline

- [ ] **P0.3.1**:commit

```bash
git add openspec/changes/retire-parallel-and-worktree-fully/verification/baseline.md
git commit -m "feat(forgeue): retire-parallel-worktree P0 — baseline (pytest <N> + 4 archived replay PASS)"
```

期望:1 file changed,baseline.md 创建。

---

## Task P1 — 测试 imports 清理 + fence 测试删除(锚点 `tasks.md#2`;reorder Option B step 1)

> **Reorder rationale**(P0 实施 writeback,2026-05-06):原 P1=file delete / P2=fence edit / P3=test edit 顺序会让 P1 commit 之后 `pytest --collect-only` fail(`tests/unit/test_forgeue_finish_gate.py:3411` 模块级 import `_forgeue_ledger_crypto` 在 crypto 文件被删后崩溃)。reorder 为 P1=test edit / P2=production edit / P3=file delete,每 commit 后 pytest collect 都过,git bisect 友好。

**Files:**
- Modify: `tests/unit/test_forgeue_finish_gate.py`(删除 module-level import + 30+ fence tests + v3_fence_evidence_setup fixture)
- Modify or Delete: `tests/integration/test_v2_e2e_synthetic_change.py`(本 P1 仅 Edit 删除模块级 import 防 collect fail;整文件 git rm 在 P3)
- Modify: `tests/unit/test_forgeue_change_state.py`(删 5th DRIFT type case)

### Step P1.1: test_forgeue_finish_gate.py 部分删除

- [ ] **P1.1.1** 删除 module-level `_forgeue_ledger_crypto` import + sys.path 操作(line 3407-3411)

通过 Read 找到准确位置 → Edit 删除整段(line 3405-3411 的 import block + 任何相邻 comment marker)

```bash
# 验证删除后无残留
grep -n "_forgeue_ledger_crypto\|_ledger_crypto_test" tests/unit/test_forgeue_finish_gate.py
```

期望:无输出(或仅 fence 测试函数体内引用,Step P1.1.2-P1.1.6 内随测试一起删除)

- [ ] **P1.1.2** 删除 `test_check_dispatch_ledger_*` 测试组(v1/v2/v3 全分支)

通过 `grep -nE "def test_check_dispatch_ledger" tests/unit/test_forgeue_finish_gate.py` 找位置 → Edit 逐函数删除(从 `def test_xxx` 到下一 `def test_` 或 fixture / class 结束)

- [ ] **P1.1.3** 删除 `test_check_worktree_*` 测试组(`test_check_worktree_path` + `test_check_worktree_consent_outcome` + `test_check_worktree_mode_consistency`)

- [ ] **P1.1.4** 删除 `test_check_ledger_*` 测试组(`test_check_ledger_terminal_proof` + `test_check_ledger_forgery_resistance_consistency`)

- [ ] **P1.1.5** 删除 `test_check_archived_replay_path_*` 测试组

- [ ] **P1.1.6** 删除 `test_check_runtime_enforcement_protocol_version_validity_*` 测试组

- [ ] **P1.1.7** 删除 `v3_fence_evidence_setup` fixture(line 3414+ 的 `@pytest.fixture` block,依赖 `_ledger_crypto_test`)

- [ ] **P1.1.8** 保留 ADR-010 advisory + ADR-011 v1 advisory 测试(skill_cascade / round_fix_continuity / task_granularity / autonomy_boundary)

- [ ] **P1.1.9** 验证文件仍可 collect:

```bash
python -m pytest tests/unit/test_forgeue_finish_gate.py --collect-only -q 2>&1 | tail -3
```

期望:能 collect(无 SyntaxError / ModuleNotFoundError);剩余 case 数 = 原 case 数 - <删除数>。记录基线 case 数 + 删除后 case 数。

### Step P1.2: test_v2_e2e_synthetic_change.py 处理(本 P1 仅 Edit 防 collect fail)

- [ ] **P1.2.1** 检测 v2 path 占比

```bash
grep -c "v2_protocol\|dispatch_ledger\|HMAC\|forgery_resistance\|protocol_version.*v2\|protocol_version.*v3" tests/integration/test_v2_e2e_synthetic_change.py
total=$(grep -c "^def test_" tests/integration/test_v2_e2e_synthetic_change.py)
echo "v2-related lines / total def test_: <count> / $total"
```

实测占比记录到 `verification/p1_v2e2e_analysis.md`(或先记到本 micro_task 注释中)。

- [ ] **P1.2.2** 检查 module-level imports 是否引用待删 tools

```bash
grep -nE "^from tools\.|^import.*forgeue_dispatch_ledger|^import.*_forgeue_ledger_crypto|^import.*forgeue_preflight_wrapper" tests/integration/test_v2_e2e_synthetic_change.py
```

若有 module-level import 引用待删 tools → Edit 删除该 import(防 collect fail)。
若无(本 change P0 实测显示 imports 仅 stdlib + pytest)→ 跳过 P1.2.2 / P1.2.3。

- [ ] **P1.2.3** 若 P1.2.1 占比 > 80% → P3 阶段整 `git rm`(本 P1 阶段无需动);若 ≤ 80% → 在本 P1 阶段 Edit 删除 v2 path 测试 case

### Step P1.3: test_forgeue_change_state.py 部分删除(5th DRIFT type case)

- [ ] **P1.3.1** 找 5th DRIFT case

```bash
grep -nE "test_.*archived_replay_path|test_.*5th_drift_type|test_.*detect_drift_archived" tests/unit/test_forgeue_change_state.py
```

- [ ] **P1.3.2** Edit 删除该 case;保留 4 类 DRIFT 测试

### Step P1.4: 全 pytest collect 验证 + commit

- [ ] **P1.4.1** 全 pytest collect 验证(P1 commit 前 critical check)

```bash
python -m pytest --collect-only -q 2>&1 | tail -3
```

期望:`<M> tests collected`(`<M>` = P0 baseline 1746 - 本 P1 删除测试 case 数;无 ImportError / ModuleNotFoundError)。

若 collect fail → 本 P1 阶段未把所有依赖 retired tool 的 module-level import 清理干净 → 继续 Edit 修复直到 collect pass。

- [ ] **P1.4.2** 全 pytest 实测(可选;collect-only 已是 critical gate)

```bash
python -m pytest -q 2>&1 | tail -5
```

期望:`<M> passed`(P0 - 本 P1 删除 case 数)。

- [ ] **P1.4.3** commit

```bash
git add tests/
git commit -m "feat(forgeue): retire-parallel-worktree P1 — 测试 imports 清理 + fence 测试删除(pytest collect 1746 → <M>;reorder Option B step 1)"
```

---

## Task P2 — finish_gate + change_state 内部 fence/helper/常量删除(锚点 `tasks.md#3`;reorder Option B step 2)

**Files:**
- Modify: `tools/forgeue_finish_gate.py`(删 7 fence + 2 helper + 3 常量 + dispatch loop 分支 + 加 `_is_archived_replay_path` helper + 改写 dispatch matrix)
- Modify: `tools/forgeue_change_state.py`(删 5th DRIFT type detector + worktree drift)

### Step P2.1: 删除 7 fence 函数

每个 fence 通过 `Edit` tool 找 `def <fence_name>(...)` 函数体 + 整个删除(到下一个 `def ` 或文件末尾)。

- [ ] **P2.1.1** 删 `_check_dispatch_ledger`(v1/v2/v3 全分支整函数)
- [ ] **P2.1.2** 删 `_check_ledger_terminal_proof`
- [ ] **P2.1.3** 删 `_check_ledger_forgery_resistance_consistency`
- [ ] **P2.1.4** 删 `_check_archived_replay_path_boundary`
- [ ] **P2.1.5** 删 `_check_worktree_path`
- [ ] **P2.1.6** 删 `_check_worktree_consent_outcome`
- [ ] **P2.1.7** 删 `_check_worktree_mode_consistency`
- [ ] **P2.1.8** 删 `_check_runtime_enforcement_protocol_version_validity`

每删一个验证:

```bash
grep -n "def _check_dispatch_ledger" tools/forgeue_finish_gate.py
```

期望:无输出(函数已删除)。

### Step P2.2: 删除 helper 函数

- [ ] **P2.2.1** 删 `_runtime_enforcement_v3_active`(若存在)
- [ ] **P2.2.2** 删 `_runtime_enforcement_v2_active`(若存在)

### Step P2.3: 简化常量

- [ ] **P2.3.1** `_VALID_PROTOCOL_VERSIONS = frozenset({"v1"})`(原含 v2/v3)

```bash
grep -n "_VALID_PROTOCOL_VERSIONS" tools/forgeue_finish_gate.py
```

期望:仅 1 行,值 `frozenset({"v1"})`。

- [ ] **P2.3.2** 删除 `_AUDIT_CONSISTENCY_MAP` 整常量
- [ ] **P2.3.3** 删除 `_WORKTREE_REQUIRED_COMMANDS` 整常量(ADR-013 已 retire 为空 frozenset 但仍占行)

### Step P2.4: 改写 dispatch matrix(沿 D-ActiveVsArchivedReplayBoundary 物理路径分支)

- [ ] **P2.4.1** 加 helper `_is_archived_replay_path(evidence_path: Path) -> bool`

定义:判断 evidence 是否物理在 `openspec/changes/archive/` 子树。可通过 `archive_dir(repo)` 与 `evidence_path` 的 `os.path.commonpath` 比较 / 或 string-prefix check。

```python
def _is_archived_replay_path(evidence_path: Path, repo_root: Path) -> bool:
    """判断 evidence 物理路径是否在 openspec/changes/archive/ 子树(D-ActiveVsArchivedReplayBoundary)"""
    try:
        rel = evidence_path.resolve().relative_to(repo_root.resolve())
        return rel.parts[:3] == ("openspec", "changes", "archive")
    except (ValueError, OSError):
        return False
```

- [ ] **P2.4.2** 改写 `_runtime_enforcement_active` 主路由(沿 D-ActiveVsArchivedReplayBoundary 7-row 表):

```python
def _runtime_enforcement_active(frontmatter: dict, evidence_path: Path, repo_root: Path) -> str:
    """返回 '' / 'v1' / BLOCKER reason"""
    pv = frontmatter.get("runtime_enforcement_protocol_version")
    is_archived = _is_archived_replay_path(evidence_path, repo_root)
    
    if pv is None or pv == "":  # absent
        return ""  # skip all fence (legacy)
    if pv == "v1":
        return "v1"  # 走 v1 advisory fence
    # v2 / v3 / unknown
    if is_archived:
        return ""  # archived path: legacy pass-through (D-ArchivedReplayCompat)
    # active path with present-but-invalid value: BLOCKER
    raise UnknownProtocolVersionError(f"unknown_protocol_version: active evidence {evidence_path} has runtime_enforcement_protocol_version: {pv!r} (must be absent / 'v1')")
```

- [ ] **P2.4.3** 删除 dispatch loop 中 v2 fence 路由分支(原 `if _runtime_enforcement_v2_active(frontmatter): _check_dispatch_ledger(...)` 等)

- [ ] **P2.4.4** 删除 dispatch loop 中 v3 fence 路由分支(原 v3 strict schema + chain HMAC verify 等)

- [ ] **P2.4.5** 加 dispatch loop 错误处理:`UnknownProtocolVersionError` 转为 BLOCKER(沿 active path BLOCKER 语义)

### Step P2.5: change_state 删除

- [ ] **P2.5.1** 删 `detect_drift_archived_replay_path` 函数(整函数)

```bash
grep -n "def detect_drift_archived_replay_path" tools/forgeue_change_state.py
```

期望:无输出。

- [ ] **P2.5.2** 删 worktree drift detection(若存在 `detect_drift_worktree_*` 函数)
- [ ] **P2.5.3** DRIFT taxonomy enum 改回 4 类

通过 `grep "DRIFT_TYPE\|drift_type\|_DRIFT_TYPES" tools/forgeue_change_state.py` 找当前 enum 声明 → `Edit` 改回:

```python
_DRIFT_TYPES = frozenset({
    "evidence_introduces_decision_not_in_contract",
    "evidence_references_missing_anchor",
    "evidence_contradicts_contract",
    "evidence_exposes_contract_gap",
})  # 4 类(原 5 类含 evidence_in_archived_replay_path,本 change retire 后回到 4 类)
```

### Step P2.6: import smoke check

- [ ] **P2.6.1** verify import 不抛异常

```bash
python -c "from tools import forgeue_finish_gate, forgeue_change_state; print('ok')"
```

期望:`ok`(无 ImportError / NameError / SyntaxError)。

若失败 → `Edit` 修复 → 重测。

### Step P2.7: Commit

- [ ] **P2.7.1**:`git diff --stat tools/forgeue_finish_gate.py tools/forgeue_change_state.py`

期望:2 文件 modified,删除行数 > 添加行数(净删除)。

- [ ] **P2.7.2**:commit

```bash
git add tools/forgeue_finish_gate.py tools/forgeue_change_state.py
git commit -m "feat(forgeue): retire-parallel-worktree P2 — finish_gate (7 fence + 2 helper + 3 常量 + dispatch loop v2/v3 分支) + change_state (5th DRIFT type + worktree drift) 删除"
```

---

## Task P3 — 工具/命令/skill/测试文件 git rm + grep audit + pytest 对账(锚点 `tasks.md#4`;reorder Option B step 3)

**Files:** 7 文件 + 1 整目录 `git rm`(P0 实测 LOC,总 ~4578)

P1 commit 后(测试 imports 已清理)+ P2 commit 后(production code 不再 import 待删 tools)→ P3 安全 git rm,无 collect / runtime 失败风险。

### Step P3.1: 删除 W1 wrapper

- [ ] **P3.1.1** 验证 LOC + 删除前依赖检查

```bash
wc -l tools/forgeue_preflight_wrapper.py
```
期望:615 lines(P0 实测确认)。

```bash
grep -rn "forgeue_preflight_wrapper" tools/ tests/ src/ 2>&1 | grep -v "^.*\.md:"
```
期望:无 `tools/` / `src/` import 残留(P2 已清理 production code references);`tests/` 残留 OK 因 P3.5 一起删除测试文件。

- [ ] **P3.1.2** `git rm tools/forgeue_preflight_wrapper.py`

### Step P3.2: 删除 W3 ledger 工具

- [ ] **P3.2.1** 验证 LOC

```bash
wc -l tools/forgeue_dispatch_ledger.py
```
期望:353 lines(P0 实测确认;non-v3 升级估)。

- [ ] **P3.2.2** `git rm tools/forgeue_dispatch_ledger.py`

### Step P3.3: 删除 ledger-binding internal helper

- [ ] **P3.3.1** 验证 LOC + 依赖检查

```bash
wc -l tools/_forgeue_ledger_crypto.py
grep -rn "_forgeue_ledger_crypto\|_ledger_crypto" tools/ tests/ src/ 2>&1 | grep -v "^.*\.md:"
```
期望:507 lines(P0 实测);grep 无 `tools/` / `src/` import 残留(P1 删了 test_forgeue_finish_gate.py module-level import + P2 删了 _check_dispatch_ledger 内 import)。

- [ ] **P3.3.2** `git rm tools/_forgeue_ledger_crypto.py`

### Step P3.4: 删除 parallel 命令模板

- [ ] **P3.4.1** 验证 LOC

```bash
wc -l .claude/commands/forgeue/change-apply-parallel.md
```
期望:433 lines。

- [ ] **P3.4.2** `git rm .claude/commands/forgeue/change-apply-parallel.md`

### Step P3.5: ~~删除 sister skill 整目录~~ **SKIP**(沿 D-SisterSkillRewrite P3 writeback,2026-05-06)

> **Skip rationale**(user push back 2026-05-06):sister skill 主体(§1 scenario taxonomy / §2 cheap-model reliability / §3-main cross-scenario discipline / §4 failure recovery / §6-§9 meta)与 worktree/parallel **完全无关**。整删是 over-retire(沿 D-BackboneSkillRewrite 同款 pattern)。改为 **inside-file rewrite in P4**(删 retire-related 段保留主体 + 命令模板 MANDATORY → OPTIONAL invoke)。

- [ ] **P3.5.1 SKIPPED** sister skill 不在 P3 file-level 删除 scope
- [ ] **P3.5.2 SKIPPED** sister skill 不在 P3 file-level 删除 scope

### Step P3.6: 删除测试文件

- [ ] **P3.6.1** `git rm tests/unit/test_dispatch_ledger.py`(W3 + ledger-binding v3 测试,1021 LOC)

```bash
ls tests/unit/test_dispatch_ledger.py
git rm tests/unit/test_dispatch_ledger.py
```

- [ ] **P3.6.2** `git rm tests/unit/test_preflight_wrapper.py`(W1 wrapper 测试,902 LOC;P0 实测确认 `forgeue_` 前缀名错)

```bash
ls tests/unit/test_preflight_wrapper.py
git rm tests/unit/test_preflight_wrapper.py
```

- [ ] **P3.6.3** 跳过 `test_forgeue_ledger_crypto.py`(P0 实测确认不存在;沿 codex round 1 F4 + P0 writeback)

- [ ] **P3.6.4** P1.2.3 决定:若 P1 实测 `test_v2_e2e_synthetic_change.py` v2 path > 80% → 此处 `git rm tests/integration/test_v2_e2e_synthetic_change.py`;否则 P1 已 partial Edit 删除 v2 case,本步跳过

### Step P3.7: grep audit `tests/`

- [ ] **P3.7.1** grep audit retire 关键字

```bash
grep -rnE 'dispatch_ledger|_forgeue_ledger_crypto|forgeue_preflight_wrapper|change-apply-parallel|ledger_forgery_resistance|HMAC.*chain|ledger_line_count|ledger_final_hmac|worktree_consent_outcome|worktree_mode|task_files_actual|preflight.*receipt' tests/ 2>&1 | head -30
```

期望:全空(允许残留:archived 历史 fixture / 注释中的 retire 描述)。每行 hit 必须分类。

### Step P3.8: pytest 全跑 + baseline 对账

- [ ] **P3.8.1** 完整 pytest

```bash
python -m pytest -q 2>&1 | tail -5
```

期望:`<M> passed in <T>s`(`<M>` = P0 baseline 1746 - P1 删除 - P3 删除 case 数)。

- [ ] **P3.8.2** baseline 对账:写 `verification/p3_pytest_summary.md`

含字段:
- P0 baseline:1746
- P1 删除:`<P1_deleted>`(从 P1.4.1 collect-only diff)
- P3 删除:`<P3_deleted>`(整 `git rm test_dispatch_ledger.py 1021 LOC + test_preflight_wrapper.py 902 LOC` 内的 case 数,可通过 git diff --cached --stat 实测;P3.6.4 若整删 v2 e2e 加上 case 数)
- P3 实测 pytest:`<M>`
- diff 应等:`P0 - P1_deleted - P3_deleted = M`

- [ ] **P3.8.3** 若 diff 不等 expected → 写 `verification/p3_baseline_diff.md` + Edit 修

### Step P3.9: 验证 git status + commit

- [ ] **P3.9.1** `git status`

期望:删除 7 个文件 + 1 整目录(`-r` flag 后 SKILL.md);无 untracked。

- [ ] **P3.9.2** 实测删除总 LOC

```bash
git diff --cached --stat | tail -5
```
期望:总删除行数 ~4578(P0 实测累计:615 + 353 + 507 + 433 + 747 + 1021 + 902 = 4578)。

- [ ] **P3.9.3** commit

```bash
git commit -m "feat(forgeue): retire-parallel-worktree P3 — 工具/命令/skill/测试文件 git rm(7 文件 + 1 目录,~4578 LOC)+ pytest 1746 → <M>(diff: -<deleted>)"
```

---

## Task P4 — 命令模板编辑(锚点 `tasks.md#5`)

**Files:**
- Modify: `.claude/commands/forgeue/change-apply-subagent.md`
- Modify: `.claude/commands/forgeue/change-apply-direct.md`
- Modify: `.claude/commands/forgeue/change-apply.md`(若残留)
- Check: `.claude/commands/forgeue/change-{finish,verify,doc-sync,status,plan,debug,review}.md`

### Step P4.1: change-apply-subagent.md 删除 sections

- [ ] **P4.1.1** 删除 `## Preflight Worktree` 整 section(从 `## Preflight Worktree` 标题到下一 `## ` 标题之前)
- [ ] **P4.1.2** 删除 `## Preflight Subagent Discipline` 整 section
- [ ] **P4.1.3** 删除 v2/v3 frontmatter 字段说明:

通过 grep 找 frontmatter 字段定义段:
```bash
grep -nE "worktree_path|worktree_consent_outcome|worktree_mode|worktree_receipt_path|dispatch_ledger_path|task_files_actual|degraded_to|degradation_reason|pre_dispatch_metadata|ledger_forgery_resistance|ledger_line_count|ledger_final_hmac" .claude/commands/forgeue/change-apply-subagent.md
```

逐行 Edit 删除(保留 v1 only 字段说明)。

- [ ] **P4.1.4** 删除 Step 10a stdout 解析逻辑(`[LEDGER] line_count=<N> final_hmac=<hex>` 行解析)

```bash
grep -n "LEDGER\|ledger_line_count\|final_hmac" .claude/commands/forgeue/change-apply-subagent.md
```

逐行 Edit 删除。

- [ ] **P4.1.5** 删除 ledger append step

```bash
grep -n "forgeue_dispatch_ledger\|append_ledger\|ledger.append" .claude/commands/forgeue/change-apply-subagent.md
```

逐行 Edit 删除。

- [ ] **P4.1.6** verify only v1 frontmatter:

```bash
grep -nE "frontmatter MUST|^- runtime_enforcement_protocol_version" .claude/commands/forgeue/change-apply-subagent.md
```

期望:列出 v1 字段(`runtime_enforcement_protocol_version: v1` + `skill_cascade_audit` + `subagent_continuity` + `task_granularity` + ADR-010 baseline 字段)。

### Step P4.2: change-apply-direct.md 删除 Preflight Worktree

- [ ] **P4.2.1** 检查是否含 `## Preflight Worktree`

```bash
grep -n "## Preflight Worktree" .claude/commands/forgeue/change-apply-direct.md
```

若有 → Edit 删除整 section;若无 → 跳过。

### Step P4.3: change-apply.md 检查 + 清理

- [ ] **P4.3.1** check

```bash
grep -nE "worktree|dispatch_ledger|change-apply-parallel|subagent-driven-discipline" .claude/commands/forgeue/change-apply.md
```

若有 hit → Edit 清理(deprecated stub 同步);若无 → 跳过。

### Step P4.4: 其他 change-* 命令 sweep

- [ ] **P4.4.1** sweep grep

```bash
grep -lnE "worktree_consent_outcome|worktree_mode|dispatch_ledger_path|ledger_forgery_resistance|ledger_line_count|ledger_final_hmac|change-apply-parallel|subagent-driven-discipline" .claude/commands/forgeue/*.md 2>&1
```

期望:仅本 change scope 内 5 文件 hit;若发现 `change-finish.md` / `change-verify.md` 等含 hit → Edit 清理。

### Step P4.4x: 改写 sister skill `.claude/skills/subagent-driven-discipline/SKILL.md`(沿 D-SisterSkillRewrite P3 writeback;2026-05-06 user push back 修正)

**File:**
- Modify: `.claude/skills/subagent-driven-discipline/SKILL.md`(747 LOC,~150-300 LOC retire-related delete)

- [ ] **P4.4x.1** 删 §3 ADR-013 default narrative(line 224 area `## Working Directory(main repo cwd — ADR-013 default)` 整段 + 相邻 worktree consent policy 引用)

通过 `grep -n "ADR-013\|main repo cwd\|worktree_consent" .claude/skills/subagent-driven-discipline/SKILL.md` 找位置。

- [ ] **P4.4x.2** 删 §1 / §3 内 Trigger Type 2 = parallel scenario subtype 行(grep `Trigger Type 2\|parallel.*scenario` 查找)

- [ ] **P4.4x.3** 删 §5 Case Studies 内 explicit ADR-011/012/013 / W1/W2/W3 / parallel dispatch 历史 case;若整 case 全 retire 相关 → 整 case 段删除;若 case 含其他 retire 无关 lessons → 仅 prune retire-related 段

- [ ] **P4.4x.4** **保留**(verify 不动):§1 主体(scenario taxonomy 除 parallel subtype)/ §2 全(cheap-model reliability)/ §3 主体(cwd verify / cross-verify / cost framework — 通用基础设施)/ §4 全(failure recovery)/ §6 全(pattern catalog)/ §7-§9 全(meta)

- [ ] **P4.4x.5** 实测改写后 retire hit 数

```bash
grep -cE 'change-apply-parallel|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already|worktree_consent_outcome|worktree_mode|forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|HMAC|dispatching-parallel-agents|ADR-011|ADR-012|ADR-013' .claude/skills/subagent-driven-discipline/SKILL.md
```

期望:`0`(允许 historical narrative 在 §5 Case Studies 段提及历史 retire — narrative-only,不影响 active controller 协议)

- [ ] **P4.4x.6** 实测 line 数变化:`wc -l .claude/skills/subagent-driven-discipline/SKILL.md`(期望 747 → ~450-600 LOC)

### Step P4.5: 改写 backbone skill `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(沿 codex round 1 F1 inline writeback + design.md `D-BackboneSkillRewrite`)

**File:**
- Modify: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(363 LOC,~45+ retire hit)

- [ ] **P4.5.1** 实测当前 retire hit 数(基线)

```bash
grep -cE 'change-apply-parallel|subagent-driven-discipline|worktree_consent_outcome|worktree_mode|ledger_forgery_resistance|task_files_actual|forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|HMAC|dispatching-parallel-agents|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already' \
  .claude/skills/forgeue-integrated-change-workflow/SKILL.md
```

期望:~45+ 行(P4.5 编辑前基线)。

- [ ] **P4.5.2** 删除 `change-apply-parallel` 引用(line 47 dispatching-parallel-agents matrix entry / line 102 命令矩阵 / line 142 wrapper invocation post-condition / 142 parallel post-cond)

通过 `grep -n "change-apply-parallel" .claude/skills/forgeue-integrated-change-workflow/SKILL.md` 找位置 → Edit 逐行删除(整 matrix row 或整 list item)

- [ ] **P4.5.3** 删除 sister skill `subagent-driven-discipline` 引用(line 202 Layer 2 wiring / line 240 v2.3 update 段)

- [ ] **P4.5.4** 删除 W1 / W2 / W3 wrapper / dispatch ledger 段(line 120 deprecated wrapper / line 129 W1 segment / line 149 W3 segment / line 171 `_check_file_overlap_actual` / line 184 `pre_dispatch_metadata` / `ledger_forgery_resistance` advisory)

- [ ] **P4.5.5** 删除 ADR-013 5 D-decision 整段(line 81-93 outcome × mode 表 / line 212-216 D-RestoreConsentGate + D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant + D-ParallelDeclineFallback + D-WrapperDeprecate / line 220-238 表 + 内容 / line 240 sister skill v2.3)

- [ ] **P4.5.6** v1 advisory baseline 保留:

通过 `grep -n "v1\|skill_cascade\|round_fix_continuity\|task_granularity" .claude/skills/forgeue-integrated-change-workflow/SKILL.md` 验证保留 v1 baseline 段。

- [ ] **P4.5.7** 实测改写后 retire hit 数 → 0

```bash
grep -cE 'change-apply-parallel|subagent-driven-discipline|worktree_consent_outcome|worktree_mode|ledger_forgery_resistance|task_files_actual|forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|HMAC|dispatching-parallel-agents|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already' \
  .claude/skills/forgeue-integrated-change-workflow/SKILL.md
```

期望:`0`(若 > 0 → 漏改,继续 Edit;允许 retrospective narrative 在 `### History` 段提及 retire 历史,但默认 0)

- [ ] **P4.5.8** 实测 line 数变化:`wc -l .claude/skills/forgeue-integrated-change-workflow/SKILL.md`

期望:从 363 LOC 减少至 ~250-280 LOC(精简后)。

### Step P4.6: Commit

- [ ] **P4.6.1**:commit(含 backbone skill 改写)

```bash
git add .claude/commands/forgeue/ .claude/skills/forgeue-integrated-change-workflow/SKILL.md
git commit -m "feat(forgeue): retire-parallel-worktree P4 — 命令模板退回 v1 frontmatter only + backbone skill 整改(retire hit <baseline> → 0;LOC 363 → <new>)"
```

---

## Task P5 — Verify(锚点 `tasks.md#6`)

**Files:**
- Create: `verification/p5_archived_replay.md`
- Create: `verification/codex_verification_review_round1.md`
- Create: `verification/verify_report.md`

### Step P5.1: Level 0 — 静态校验

- [ ] **P5.1.1** finish_gate on 本 change(预期不 PASS — evidence 还没全集成)

```bash
python tools/forgeue_finish_gate.py --change retire-parallel-and-worktree-fully --json 2>&1 | python -m json.tool | head -30
```

期望:输出 JSON 含 `evidence_complete: false`(P7 才完整)。

- [ ] **P5.1.2** archived 4 change replay 不引入新失败模式(D-ArchivedReplayCompat 修正 criterion;沿 P0 baseline writeback `verification/baseline.md` P0.2.1 — 不再要求"全 PASS",改要求"blocker total 31 → 29 + 不引入新 blocker type")

```bash
# 实测 blocker 分布对照 P0 baseline
for archived in 2026-05-05-enhance-workflow-automation-runtime-enforcement \
                2026-05-05-enhance-workflow-automation-executable-enforcement \
                2026-05-06-restore-superpowers-worktree-consent-gate \
                2026-05-06-enhance-workflow-automation-ledger-binding; do
  python tools/forgeue_finish_gate.py --change $archived --json 2>&1 | python -c "
import sys, json
d = json.loads(sys.stdin.read())
b_types = {}
for b in d.get('blockers', []):
    t = b.get('type', '?')
    b_types[t] = b_types.get(t, 0) + 1
print('$archived blocker types:', b_types)
"
done
```

**期望对账表**(P0 baseline 31 → P5 retire 后 29):

| Archive | tasks_unchecked | openspec_validate_failed | round_fix_continuity_v2 | dispatch_ledger_violation | 期望总 |
|---------|---|---|---|---|---|
| runtime-enforcement | 11 | 1 | 0 | 0 | 12 |
| executable-enforcement | 14 | 1 | 0 | 0 | 15 |
| restore-consent-gate | 0 | 1 | **0**(从 1 消失) | **0**(从 1 消失) | 1 |
| ledger-binding | 0 | 1 | 0 | 0 | 1 |
| **总** | **25** | **4** | **0** | **0** | **29** |

若 P5 实测 blocker 不符(任何新 blocker type 出现 / `tasks_unchecked` 数变 / `openspec_validate_failed` 数变 / 2 个 v2 fence blocker 没消失)→ DRIFT type 3 阻断 archive。

期望:4 行全 `PASS`(若有 FAIL → critical blocker → user_required + 阻断 archive)。

- [ ] **P5.1.3** 写 `verification/p5_archived_replay.md`(12-key audit frontmatter + 4 archived PASS 表)

### Step P5.2: Level 1 — pytest

- [ ] **P5.2.1** 完整 pytest 全跑

```bash
python -m pytest -q 2>&1 | tail -5
```

期望:与 P3 实测数一致(`<M> passed`),无新 fail / error。

### Step P5.3: Level 2 — codex /codex:review --base main

- [ ] **P5.3.1** invoke

```bash
node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" review --base main "retire-parallel-and-worktree-fully change verification — focus on retire 漏物 (grep audit 实测覆盖) + archived 4 change replay PASS + pytest baseline 对账"
```

(走 `Bash run_in_background: true`;capture job id)

- [ ] **P5.3.2** poll codex:status,等 done

- [ ] **P5.3.3** 落 `verification/codex_verification_review_round1.md`(12-key audit frontmatter)

### Step P5.4: grep audit retire scope 全清

- [ ] **P5.4.1** sweep src/ + tools/ + tests/

```bash
grep -rnE 'forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto' src/ tools/ tests/ 2>&1 | head -20
```

期望:全空(若有 hit → 漏物,Edit 清理)

- [ ] **P5.4.2** sweep .claude/

```bash
grep -rnE 'change-apply-parallel|subagent-driven-discipline' .claude/ 2>&1 | head -20
```

期望:全空(允许 archived 引用,但 .claude/ 是 active 目录,应全清)

- [ ] **P5.4.3** sweep tools/ + .claude/ for v2/v3 字段

```bash
grep -rnE 'worktree_consent_outcome|worktree_mode|task_files_actual|ledger_forgery_resistance|ledger_line_count|ledger_final_hmac' tools/ .claude/ 2>&1 | head -20
```

期望:全空(允许 archived 4 change 内残留,在 archive/ 路径)

### Step P5.5: 落 verify_report.md + commit

- [ ] **P5.5.1** 写 `verification/verify_report.md`(12-key audit frontmatter + L0/L1/L2 全结果 + grep audit 全清确认)

- [ ] **P5.5.2**:commit

```bash
git add openspec/changes/retire-parallel-and-worktree-fully/verification/
git commit -m "feat(forgeue): retire-parallel-worktree P5 — verify(L0+L1+L2 PASS + 4 archived replay PASS + grep audit 全清)"
```

---

## Task P6 — Doc Sync Gate(锚点 `tasks.md#7`)

**Files:**
- Create: `verification/doc_sync_check.md`
- Create: `verification/doc_sync_report.md`
- Modify: 10+ docs(SRS / acceptance_report / test_spec / README / CLAUDE / AGENTS / ai_workflow / CHANGELOG)

### Step P6.1: 静态扫

- [ ] **P6.1.1** run forgeue_doc_sync_check

```bash
python tools/forgeue_doc_sync_check.py --change retire-parallel-and-worktree-fully --json 2>&1 | python -m json.tool | head -50
```

落 `verification/doc_sync_check.md`。

### Step P6.2: 逐文档 audit + Edit

- [ ] **P6.2.a** `docs/requirements/SRS.md` ADR table 更新

通过 `grep -n "ADR-011\|ADR-012\|ADR-013\|ledger-binding" docs/requirements/SRS.md` 找 ADR table 位置 → Edit 改 `[Active]` 为 `[Retired]` + 加 `Superseded by retire-parallel-and-worktree-fully (2026-05-XX archived)`(具体日期 P8 archive 时回填)

- [ ] **P6.2.b** `docs/acceptance/acceptance_report.md` ADR table 同步 SRS

- [ ] **P6.2.c** `docs/testing/test_spec.md` 删除 ledger / worktree fence 测试索引

```bash
grep -nE "test_check_dispatch_ledger|test_check_worktree|test_check_ledger|test_check_archived_replay" docs/testing/test_spec.md
```

逐行 Edit 删除。

- [ ] **P6.2.d** `docs/ai_workflow/README.md` §4 + §6 更新

`grep -n "change-apply-parallel\|forgeue_dispatch_ledger\|forgeue_preflight_wrapper" docs/ai_workflow/README.md` → Edit。

- [ ] **P6.2.e** `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.6 + §C.7-C.10 整段删除

通过 Read + Edit 删除整 section(从 §B.6 / §C.7 / §C.8 / §C.9 / §C.10 标题到下一 § 标题前)。

- [ ] **P6.2.f** `docs/ai_workflow/forgeue_quickstart.md` 残留 Preflight 提及清理

```bash
grep -n "Preflight" docs/ai_workflow/forgeue_quickstart.md
```

- [ ] **P6.2.g** `README.md` v3 cryptographic ledger binding section 删除

```bash
grep -n "v3 [Cc]ryptographic\|HMAC\|ledger_forgery_resistance" README.md
```

逐 section Edit 删除(沿 commit `4b2e366` 反向)。

- [ ] **P6.2.h** `CHANGELOG.md` 加 retire entry(沿 ledger-binding 同款 entry 风格)

在 `## [Unreleased]` 段下加:
```markdown
- **Retire** ADR-011 + ADR-012 + ADR-013 + ledger-binding 全部 ForgeUE-level worktree / parallel dispatch / dispatch ledger / sister skill 强制层(~3000-4000 LOC delete + ~30-50 测试 case 删除 + ~12-15 文档 stale residue 清理);行为退回 ADR-010 advisory baseline + Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate(`retire-parallel-and-worktree-fully` 2026-05-XX archived)
```

- [ ] **P6.2.i** `CLAUDE.md` 大段编辑

通过 Read 找 `## ForgeUE Integrated AI Change Workflow` 段:
- 12 字段表 → 删除 v2/v3 行,保留 v1 单字段(`runtime_enforcement_protocol_version: v1`)
- ADR-013 update 段 → 整段删除
- v3 字段段 → 整段删除(沿 design.md `D-CapabilityDeltaScope`)
- dispatch matrix 描述 → 简化为 2 档(absent → skip,v1 → advisory,unknown → legacy pass-through)

- [ ] **P6.2.j** `AGENTS.md` 同步 `CLAUDE.md`(diff 后保持一致)

### Step P6.3: 二次扫 + 分类

- [ ] **P6.3.1** D-DocResidueSweep grep audit(沿 codex round 1 F1 inline writeback 扩展 keyword + scope)

```bash
# 注意:沿 ForgeUE Windows-禁用-/tmp 约束(CLAUDE.md 全局规则 — Git-Bash 翻译到 C: 系统 temp),改用 demo_artifacts/
mkdir -p demo_artifacts/$(date +%Y-%m-%d)/adhoc/p6_grep_audit/
grep -rniE 'worktree|dispatch_ledger|forgeue_finish_gate|forgeue_preflight_wrapper|change-apply-parallel|ledger_forgery_resistance|HMAC.*chain|HMAC|ledger_line_count|ledger_final_hmac|cryptographic.*ledger|ADR-011|ADR-012|ADR-013|ledger-binding|runtime_enforcement_protocol_version.*v[23]|worktree_consent_outcome|worktree_mode|task_files_actual|preflight.*receipt|subagent-driven-discipline|dispatching-parallel-agents|_forgeue_ledger_crypto|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already' \
  .claude/skills/ .claude/commands/ docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md 2>&1 | tee demo_artifacts/$(date +%Y-%m-%d)/adhoc/p6_grep_audit/grep_audit.txt | wc -l
```

**沿 codex round 1 F1 inline writeback,扩展 scope**:`.claude/skills/`(backbone skill 入口)+ `.claude/commands/`(命令模板)纳入 grep audit,**不仅 docs/**。

每 hit 分类:
- 描述本 change retire 行为(allowed,例:CHANGELOG retire entry / SRS `[Retired]`标记)
- archived 4 change 引用(allowed,在 archived 归档路径文档)
- historical narrative(allowed,SRS ADR table)
- **active stale residue**(必须删,本 change scope)

- [ ] **P6.3.2** 写 `verification/doc_sync_report.md`(12-key audit + grep audit 完整分类清单 + 残留 hit 数)

### Step P6.4: Commit

- [ ] **P6.4.1**:commit

```bash
git add docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md openspec/changes/retire-parallel-and-worktree-fully/verification/
git commit -m "docs(forgeue): retire-parallel-worktree P6 — doc-sync(10+ 文档 stale residue 清理 + ADR table retire 标记 + grep audit 分类清单)"
```

---

## Task P7 — Retrospective + Cross-check(锚点 `tasks.md#8`)

**Files:**
- Create: `notes/retrospective.md`
- Create: `notes/review_cross_check.md`
- Create: `verification/finish_gate_report.md`

### Step P7.1: 写 retrospective

- [ ] **P7.1.1** `notes/retrospective.md`(12-key audit frontmatter + 以下子 section):

  - **实施过程 lessons learned**:P1-P6 实施中遇到的阻力 / 设计假设是否 hold
  - **retire 漏物清单**:P5/P6 grep audit 漏的项目(本 round writeback)
  - **工程量实测对账**:
    - 预估 ~3000-4000 LOC,实测 `<actual-LOC>`(P1.8.2 + P2.7.1 + P3 实测累加)
    - 预估 ~30-50 测试 case 删除,实测 `<actual-cases>`(P3.5.1)
    - 预估 ~12-15 文档 stale residue,实测 `<actual-docs>`(P6.3.1)
  - **4-round codex review 实测 round 数**:预估 2-3 round,实测 `<actual-rounds>`

### Step P7.2: 写 review_cross_check

- [ ] **P7.2.1** `notes/review_cross_check.md`(沿 ForgeUE cross-check A/B/C/D 模板):

  - **`## A. Decision Summary`** — 复用 `review/design_cross_check.md ## A` 段(本 round 立场)
  - **`## B. Per-finding Response`**:
    - 列 P5 codex `/codex:review --base main` 全 finding
    - 每 finding 标 Resolution(`aligned` / `accepted-codex` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`)
    - 配 `evidence_link` 指向具体修改 commit SHA
  - **`## C. Disputed Count`**:`disputed_open: <count>`(MUST == 0 沿 finish_gate fence)
  - **`## D. Independent file:line Verification`**:
    - 对每条 codex finding 独立 grep / Read 验证 file:line 真实存在
    - 不把 codex claim 当结论(沿 memory `feedback_verify_external_reviews`)

### Step P7.3: finish_gate report

- [ ] **P7.3.1** `python tools/forgeue_finish_gate.py --change retire-parallel-and-worktree-fully --json` 落 `verification/finish_gate_report.md`(12-key audit + 4 runtime enforcement v1 fence 分支输出)

### Step P7.4: Commit

- [ ] **P7.4.1**:commit

```bash
git add openspec/changes/retire-parallel-and-worktree-fully/notes/ openspec/changes/retire-parallel-and-worktree-fully/verification/finish_gate_report.md
git commit -m "feat(forgeue): retire-parallel-worktree P7 — retrospective + cross-check(disputed_open=0;ready-to-ship)"
```

---

## Task P8 — Finish Gate + Archive(锚点 `tasks.md#9`)

**Files:**
- Modify: `openspec/changes/retire-parallel-and-worktree-fully/` → `openspec/changes/archive/2026-05-XX-retire-parallel-and-worktree-fully/`
- Modify: `MEMORY.md`

### Step P8.1: finish_gate 全 PASS

- [ ] **P8.1.1**:run

```bash
python tools/forgeue_finish_gate.py --change retire-parallel-and-worktree-fully --json 2>&1 | python -m json.tool
```

期望(全字段 true / 0):
- `evidence_complete: true`
- `frontmatter_aligned: true`
- `cross_check_disputed_open: 0`
- `writeback_truth: true`
- `tasks_unchecked: 0`
- `all_checks_passed: true`

- [ ] **P8.1.2** `openspec validate retire-parallel-and-worktree-fully --strict`

期望:`Change 'retire-parallel-and-worktree-fully' is valid`。

### Step P8.2: User explicit auth(fence #1 不可逆)

- [ ] **P8.2.1**:用 `AskUserQuestion` 请求 archive change + push origin dev?

```
"finish_gate 全 PASS + openspec validate strict PASS;ready-to-ship。
执行 archive change(沿 ForgeUE 归档原则) + push origin dev?"
options: [archive_only, archive_and_push, abort_for_review]
```

- [ ] **P8.2.2**:等用户确认后才走下面 step;若 abort → 写 `notes/p8_abort_reason.md`

### Step P8.3: Archive change(用户授权后)

- [ ] **P8.3.1** date 命名

```bash
TODAY=$(date -u +%Y-%m-%d)
echo "Archive target: openspec/changes/archive/${TODAY}-retire-parallel-and-worktree-fully"
```

- [ ] **P8.3.2** mv

```bash
mv openspec/changes/retire-parallel-and-worktree-fully \
   openspec/changes/archive/${TODAY}-retire-parallel-and-worktree-fully
```

- [ ] **P8.3.3** SRS / acceptance_report ADR table 回填具体 archived 日期

(P6.2.a / P6.2.b 中 `<2026-05-XX archived>` 占位 → 真实 `<TODAY>`;通过 Edit replace_all)

- [ ] **P8.3.4** commit archive

```bash
git add openspec/changes/ docs/requirements/SRS.md docs/acceptance/acceptance_report.md
git commit -m "feat(forgeue): ship retire-parallel-and-worktree-fully (squash merge)"
```

### Step P8.4: Push(用户授权后)

- [ ] **P8.4.1**:`git push origin dev`(若 P8.2 选 archive_and_push)

### Step P8.5: MEMORY.md update

- [ ] **P8.5.a** 删除 entry `[retire-parallel-and-worktree-fully change planned (B option)]` link(planning entry,本 change shipped 后 obsolete)

- [ ] **P8.5.b** 加新 entry `[retire-parallel-and-worktree-fully shipped 2026-05-XX]`(描述完成状态 + 实际 LOC 删除数 + 测试 case 删除数 + 文档清理数)

写新 memory file `memory/project_retire_parallel_worktree_shipped.md`(12-key memory frontmatter)+ 在 `MEMORY.md` index 加链接

- [ ] **P8.5.c** entry `[ADR-013 Restore Superpowers Worktree Consent Gate shipped 2026-05-06]` 标 `[Superseded by retire-parallel-and-worktree-fully]`(保留 traceability)

- [ ] **P8.5.d** entry `[v3 Cryptographic Ledger Binding shipped 2026-05-06]` 标 `[Superseded by retire-parallel-and-worktree-fully]`

- [ ] **P8.5.e** entry `[Runtime enforcement change shipped 2026-05-05]` 标 `[Superseded by retire-parallel-and-worktree-fully]`(traceability chain 完整)

### Step P8.6: 最终 commit + push

- [ ] **P8.6.1**:commit

```bash
git add C:/Users/mzq/.claude/projects/D--ClaudeProject-ForgeUE-claude/memory/
git commit -m "chore(memory): retire-parallel-worktree shipped — MEMORY.md superseded chain update"
```

- [ ] **P8.6.2**:`git push origin dev`(若 P8.4 已 push 则跳过此 push)

---

## Self-Review

**1. Spec coverage check**(对 specs/examples-and-acceptance/spec.md REMOVED Requirements):

- [ ] Preflight Worktree runtime enforcement → Task P2.1.5/6/7 + P4.1.1
- [ ] Implementation parallel dispatch via `/forgeue:change-apply-parallel` → Task P1.4
- [ ] Preflight wrapper receipt JSON contract → Task P1.1
- [ ] Dispatch ledger append-only contract → Task P1.2 + P2.1.1
- [ ] Parallel dispatch actual file overlap detection → Task P1.4(隐含;parallel 命令模板整删)
- [ ] v2 e2e integration test fixture → Task P3.2
- [ ] Runtime enforcement protocol version v2 migration → Task P2.3.1 + P2.4
- [ ] HMAC key lifecycle for v3 cryptographic ledger binding → Task P1.3
- [ ] v3 ledger schema with HMAC chain → Task P1.2(整文件删除后 schema 自然 retire)
- [ ] v3 fence dispatch matrix and HMAC chain verification → Task P2.1.2-4 + P2.4
- [ ] ledger_forgery_resistance frontmatter field upgrade → Task P2.1.3 + P4.1.3
- [ ] v3 ledger terminal proof → Task P2.1.2 + P4.1.4
- [ ] v3 ledger strict 11-field schema validation → Task P1.2(整文件删除)
- [ ] Runtime enforcement protocol_version validity gate → Task P2.1.8 + P2.4
- [ ] Archived replay path boundary → Task P2.1.4 + P2.5.1

**MODIFIED Requirements**:
- [ ] Round 2+ fix subagent continuity → 无独立 micro_task(`_check_round_fix_continuity` v1 advisory 行为已是当前实装;本 change retire v2/v3 cross-check 部分,但 v1 行为不变)→ Task P2.1.1 删 `_check_dispatch_ledger` 时连带 cross-check 逻辑删除即可

**2. Placeholder scan**:无 TBD / TODO 残留(本文件全文 grep 通过)。

**3. Type consistency**:`_VALID_PROTOCOL_VERSIONS`(P2.3.1)+ `_DRIFT_TYPES`(P2.5.3)+ `_runtime_enforcement_active`(P2.4.1)— 命名一致。

---

## Open Questions(已 inherit 自 execution_plan.md)

1. `tests/unit/test_forgeue_preflight_wrapper.py` / `test_forgeue_ledger_crypto.py` 存在性 → P1.7.1/2 micro task 含 existence check。
2. `tests/integration/test_v2_e2e_synthetic_change.py` 整删 vs 部分删 → P3.2.1 实测后决定。
3. `runtime_enforcement_protocol_version v1` 命名 → 保留 `v1`(本 change 内不改)。
4. `CLAUDE.md` 12 字段表保留 v1 单行 vs 整删表 → P6.2.i micro task 显式说明保留 v1 单字段。
