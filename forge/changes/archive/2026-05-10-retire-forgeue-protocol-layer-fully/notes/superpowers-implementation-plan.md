# Retire ForgeUE Protocol Layer Fully Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 整 retire ForgeUE-specific 协议层(9 命令 / 8 工具 / 2 sister skill / 3 协议文档 / 部分 spec Requirement),切换到 OpenSpec(contract anchor)+ Superpowers(evidence 流)+ codex CLI(opt-in via convention)三层精简栈。

**Architecture:** 不动 `src/framework/*` 业务代码、不动 `docs/{requirements,design,testing,acceptance}/` 五件套(test_spec.md 仅加 Level 2 章节)、不动 `openspec/specs/` 8 capability(只 REMOVED/MODIFIED 协议层 Requirements)、不动 `openspec/changes/archive/` 24 changes evidence(D-ArchivedReplayCompat)、不动 `openspec/backlog/` 目录(D3 信息容器,只砍 fence 守门)。**保留** `.claude/skills/subagent-driven-discipline/`(D11 generic universal SKILL)。

**Tech Stack:** Python 3.12+ stdlib only(本 change 不动 `src/framework/`)、Git(`git rm` / `git mv` / `git commit`)、OpenSpec CLI(`openspec validate --strict` / `openspec archive` / `openspec sync`)、PowerShell + ripgrep(Windows + Git-Bash 环境)。

**Source of Truth Hierarchy:**
- delta specs(`openspec/changes/retire-forgeue-protocol-layer-fully/specs/**/spec.md`) = behavior contract source of truth
- design.md = architecture constraint(D1-D11 binding)
- tasks.md = high-level phase reference(P0-P9 mapping)

**Subagent Model Tier Reference**(沿 D11 保留的 SKILL `subagent-driven-discipline` §1):

| Task | OpenSpec Phase | Subtype | Implementer model | Reviewer model |
|---|---|---|---|---|
| Task 1 | P0 baseline | §1.7.1 mechanical | direct(no subagent;controller 自跑 pytest + openspec validate) | N/A |
| Task 2 | P1 retire commands + skills | §1.1.1 mechanical | haiku | spec_review: haiku / code_quality: haiku |
| Task 3 | P2 retire tools + grep-driven cleanup | §1.1.2 pattern + §1.1.3 multi-file | **sonnet** | spec_review: haiku / code_quality: **sonnet**(MANDATORY 沿 §1.3.4) |
| Task 4 | P3 retire docs + Level 2 文档化 | §1.5.2 doc rewrite | **sonnet** | spec_review: sonnet(§1.2.4 acceptance criteria)/ code_quality: haiku |
| Task 5 | P4 verify backlog preservation | §1.7.1 mechanical verify | direct(controller) | N/A |
| Task 6 | P5 三大文件精简 | §1.5.2 + §1.5.4 architecture doc | **sonnet**(每个文件单独 dispatch;P5.A/B/C 各 1 implementer)| spec_review: sonnet / code_quality: **sonnet** |
| Task 7 | P6 verify follow-on preservation | §1.7.1 mechanical verify | direct(controller) | N/A |
| Task 8 | P7 pytest baseline 0 fail | §1.6.1 / §1.6.2 | direct → 若 fail 升 **sonnet**(§1.6.2) | N/A |
| Task 9 | P8 retrospective + archive | §1.5.4 architecture doc | **sonnet**(retrospective writeup) | final_reviewer: sonnet |
| Task 10 | P9 optional CHANGELOG | §1.5.1 mechanical | direct or haiku | N/A |

---

## Task 1: P0 — Baseline + scope freeze

**Files:**
- Read: `openspec/changes/retire-forgeue-protocol-layer-fully/proposal.md`
- Read: `openspec/changes/retire-forgeue-protocol-layer-fully/design.md`
- Read: `openspec/changes/retire-forgeue-protocol-layer-fully/tasks.md`
- Read: `openspec/changes/retire-forgeue-protocol-layer-fully/specs/examples-and-acceptance/spec.md`
- Read: `openspec/changes/retire-forgeue-protocol-layer-fully/specs/probe-and-validation/spec.md`
- Read: `openspec/changes/retire-forgeue-protocol-layer-fully/notes/codex_adversarial_review_review_round1.md`

**Subagent dispatch:** **None — direct controller execution**(纯 verification step,无 implementation)。

- [ ] **Step 1: Run pytest baseline**

Run: `python -m pytest -q 2>&1 | tail -20`
Expected output: 包含 `failed` 行,显示 2 个 pre-existing fail:
- `tests/unit/test_followon_registry.py::TestActiveMdSchema::test_active_md_known_workflow_protocol_entries_present`
- `tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type`

Record the PASS / FAIL count for later P7 comparison。

- [ ] **Step 2: Run openspec validate strict**

Run: `openspec validate retire-forgeue-protocol-layer-fully --strict 2>&1`
Expected: `Change 'retire-forgeue-protocol-layer-fully' is valid`(round 1 codex writeback 后已 PASS)

- [ ] **Step 3: Verify round 1 codex writeback inline complete**

Run: `cat openspec/changes/retire-forgeue-protocol-layer-fully/notes/codex_adversarial_review_round_counter.txt`
Expected: `1`

Run: `ls openspec/changes/retire-forgeue-protocol-layer-fully/notes/codex_adversarial_review_review_round1.md`
Expected: file exists

- [ ] **Step 4: Verify design.md Round 1 Codex Writeback section + D11 present**

Run: `grep -c "## Round 1 Codex Adversarial Review Writeback" openspec/changes/retire-forgeue-protocol-layer-fully/design.md`
Expected: `1`

Run: `grep -c "### D11:" openspec/changes/retire-forgeue-protocol-layer-fully/design.md`
Expected: `1`

- [ ] **Step 5: Verify proposal.md modify list extended**

Run: `grep -E "AGENTS.md|README.md" openspec/changes/retire-forgeue-protocol-layer-fully/proposal.md | head -5`
Expected: 至少 3 行匹配(Affected files modify list 含 AGENTS.md + README.md)

**No commit for P0**(verification only, no file changes)。

---

## Task 2: P1 — Retire 9 个 `/forgeue:change-*` 命令 + 2 sister skill(保留 subagent-driven-discipline)

**Files:**
- Delete: `.claude/commands/forgeue/change-status.md`
- Delete: `.claude/commands/forgeue/change-plan.md`
- Delete: `.claude/commands/forgeue/change-apply.md`
- Delete: `.claude/commands/forgeue/change-apply-subagent.md`
- Delete: `.claude/commands/forgeue/change-apply-direct.md`
- Delete: `.claude/commands/forgeue/change-debug.md`
- Delete: `.claude/commands/forgeue/change-verify.md`
- Delete: `.claude/commands/forgeue/change-review.md`
- Delete: `.claude/commands/forgeue/change-doc-sync.md`
- Delete: `.claude/commands/forgeue/change-finish.md`
- Delete (recursive): `.claude/skills/forgeue-integrated-change-workflow/`
- Delete (recursive): `.claude/skills/forgeue-doc-sync-gate/`
- **PRESERVE**: `.claude/skills/subagent-driven-discipline/` (D11 generic SKILL)

**Subagent dispatch:** Implementer = `haiku`(mechanical git rm,沿 §1.1.1)。Reviewers:spec_review = `haiku`(§1.2.1 string matching),code_quality = `haiku`(§1.3.1 style)。

- [ ] **Step 1: Verify command files exist (pre-condition)**

Run: `ls .claude/commands/forgeue/`
Expected: 10 .md files(change-status, change-plan, change-apply, change-apply-subagent, change-apply-direct, change-debug, change-verify, change-review, change-doc-sync, change-finish)

Run: `ls .claude/skills/`
Expected: 3 skill 目录(forgeue-integrated-change-workflow, forgeue-doc-sync-gate, subagent-driven-discipline)

- [ ] **Step 2: Git rm 9 commands + 2 sister skills (preserve subagent-driven-discipline)**

```bash
git rm .claude/commands/forgeue/change-status.md \
       .claude/commands/forgeue/change-plan.md \
       .claude/commands/forgeue/change-apply.md \
       .claude/commands/forgeue/change-apply-subagent.md \
       .claude/commands/forgeue/change-apply-direct.md \
       .claude/commands/forgeue/change-debug.md \
       .claude/commands/forgeue/change-verify.md \
       .claude/commands/forgeue/change-review.md \
       .claude/commands/forgeue/change-doc-sync.md \
       .claude/commands/forgeue/change-finish.md

git rm -r .claude/skills/forgeue-integrated-change-workflow/
git rm -r .claude/skills/forgeue-doc-sync-gate/
```

Expected: `rm '.claude/commands/forgeue/change-status.md'` ... 12 删除行。

- [ ] **Step 3: Verify forgeue/ command directory empty (and remove if so)**

Run: `ls .claude/commands/forgeue/ 2>&1`
Expected: empty 或 `cannot access ... No such file or directory`(若 ls 返回空 + 目录是空 → 自然存在 `.git/index` 上但 working tree 已 empty 是 ok 的;`git rm` 不删空目录)

If non-empty after Step 2: investigate (are there any .md files we missed?)。

- [ ] **Step 4: Verify subagent-driven-discipline preserved (D11)**

Run: `ls .claude/skills/subagent-driven-discipline/SKILL.md`
Expected: file exists(NOT deleted)

Run: `head -15 .claude/skills/subagent-driven-discipline/SKILL.md | grep -E "name:|description:|compatibility:"`
Expected: `name: subagent-driven-discipline` + description 含 `Universal controller-side discipline`

- [ ] **Step 5: Verify 2 sister skills deleted**

Run: `ls .claude/skills/ 2>&1`
Expected: 只剩 `subagent-driven-discipline/`(forgeue-integrated-change-workflow / forgeue-doc-sync-gate 不再出现)

- [ ] **Step 6: Commit P1 retire**

```bash
git add .claude/commands/forgeue .claude/skills/forgeue-integrated-change-workflow .claude/skills/forgeue-doc-sync-gate
git commit -m "$(cat <<'EOF'
retire(forgeue): P1 retire 9 commands + 2 sister skills (preserve subagent-driven-discipline generic SKILL)

- Delete 9 .claude/commands/forgeue/change-*.md (change-status / change-plan / change-apply / change-apply-subagent / change-apply-direct / change-debug / change-verify / change-review / change-doc-sync / change-finish)
- Delete .claude/skills/forgeue-integrated-change-workflow/
- Delete .claude/skills/forgeue-doc-sync-gate/
- Preserve .claude/skills/subagent-driven-discipline/ (round 1 codex P1-1 partial-dispute → accepted-claude; sister to superpowers:subagent-driven-development; generic universal subagent discipline)

Refs: openspec/changes/retire-forgeue-protocol-layer-fully/{proposal,design,tasks}.md P1; D11 SKILL keep policy

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected commit message starts with `retire(forgeue): P1 ...` and includes Co-Authored-By。

---

## Task 3: P2 — Retire 8 tools + grep-driven 测试 / fixture cleanup

**Files:**
- Delete: `tools/forgeue_finish_gate.py`
- Delete: `tools/forgeue_change_state.py`
- Delete: `tools/forgeue_verify.py`
- Delete: `tools/forgeue_doc_sync_check.py`
- Delete: `tools/forgeue_subagent_budget.py`
- Delete: `tools/forgeue_skill_cascade_check.py`
- Delete: `tools/forgeue_enum_cross_ref_check.py`
- Delete: `tools/forgeue_env_detect.py`
- Conditional delete: `tools/_common.py`(only if exclusively used by retired tools)
- Delete (17 files): `tests/unit/test_forgeue_*.py` + `tests/unit/test_skill_cascade_check.py`
- Delete (recursive): `tests/fixtures/forgeue_workflow/`

**Subagent dispatch:** Implementer = **sonnet**(§1.1.3 multi-file integration + §1.1.2 pattern matching;case-by-case judgment about which tests are retire-related)。Reviewers:spec_review = haiku(§1.2.1 verify retired files actually removed),code_quality = **sonnet** MANDATORY(§1.3.4 runtime correctness — 是否漏删导致 import error)。

- [ ] **Step 1: Run baseline grep to confirm scope (pre-condition)**

Run:
```bash
rg -l "forgeue_finish_gate|forgeue_verify|forgeue_change_state|forgeue_doc_sync|forgeue_subagent_budget|forgeue_skill_cascade|forgeue_enum_cross_ref|forgeue_env_detect|/forgeue:change|forgeue_workflow" tests/ 2>/dev/null | sort
```
Expected: 17+ test files + 1+ fixture files。Record full list as ground truth for Step 5 verification。

- [ ] **Step 2: Git rm 8 tools**

```bash
git rm tools/forgeue_finish_gate.py \
       tools/forgeue_change_state.py \
       tools/forgeue_verify.py \
       tools/forgeue_doc_sync_check.py \
       tools/forgeue_subagent_budget.py \
       tools/forgeue_skill_cascade_check.py \
       tools/forgeue_enum_cross_ref_check.py \
       tools/forgeue_env_detect.py
```

Expected: 8 删除行。

- [ ] **Step 3: Git rm 17 retired test files**

```bash
git rm tests/unit/test_forgeue_finish_gate.py \
       tests/unit/test_forgeue_change_state.py \
       tests/unit/test_forgeue_verify.py \
       tests/unit/test_forgeue_doc_sync_check.py \
       tests/unit/test_forgeue_subagent_budget.py \
       tests/unit/test_forgeue_enum_cross_ref_check.py \
       tests/unit/test_forgeue_env_detect.py \
       tests/unit/test_forgeue_codex_review_no_skill_files.py \
       tests/unit/test_forgeue_cross_check_format.py \
       tests/unit/test_forgeue_no_duplicated_tdd_skill.py \
       tests/unit/test_forgeue_skill_markdown.py \
       tests/unit/test_forgeue_workflow_ascii_markers.py \
       tests/unit/test_forgeue_workflow_no_hardcoded_test_count.py \
       tests/unit/test_forgeue_workflow_no_paid_default.py \
       tests/unit/test_forgeue_workflow_plugin_invocation.py \
       tests/unit/test_forgeue_writeback_detection.py \
       tests/unit/test_forgeue_command_markdown.py \
       tests/unit/test_skill_cascade_check.py \
       tests/unit/test_followon_registry.py
```

Expected: 19 删除行(实际仓库存在量略不同;若某文件不存在 `git rm` 报错 — 此时移除该行重跑或单独跑 `ls` 确认)。

注意:此 step 在 implementer subagent 内完成时,subagent **必须**先跑一次 `ls tests/unit/test_forgeue_*.py tests/unit/test_skill_cascade_check.py tests/unit/test_followon_registry.py 2>&1` 列实际存在文件,只对存在的跑 `git rm`。

- [ ] **Step 4: Git rm fixtures directory**

```bash
git rm -r tests/fixtures/forgeue_workflow/
```

Expected: 5+ 删除行(`__init__.py` + `builders.py` + 3 个 `fake_change_*/README.md` + `__pycache__`)。

- [ ] **Step 5: Conditional `tools/_common.py` cleanup**

Run: `rg -l "from tools._common|tools/_common|tools\._common" tools/ tests/ 2>/dev/null`
Expected output: list of files referencing `_common`。

If output is **empty** OR **only references retire 工具**(已删):
```bash
git rm tools/_common.py
```
Else: skip — `_common.py` 有非 retire 工具引用,本 change 不删(留作生态层共享 helper)。

- [ ] **Step 6: Final residue grep verification**

Run:
```bash
rg -l "forgeue_finish_gate|forgeue_verify|forgeue_change_state|forgeue_doc_sync|forgeue_subagent_budget|forgeue_skill_cascade|forgeue_enum_cross_ref|forgeue_env_detect|/forgeue:change|forgeue_workflow" tests/ 2>/dev/null
```
Expected: empty(or only intentional preservation,需 implementer subagent 解释)。

Run:
```bash
rg --files tools/ | rg "forgeue"
```
Expected: empty(`tools/forgeue_*` 全删)。

- [ ] **Step 7: Verify pytest collection passes (no import error)**

Run: `python -m pytest --collect-only -q tests/unit/ 2>&1 | tail -10`
Expected: collection 完成无 `ImportError` / `ModuleNotFoundError`(可能仍有 P0 baseline 中的 2 pre-existing fail,因为它们的 fence test files 已 P2 整删 → 这些 fail 自动消失)。

If collection has `ImportError` referencing `tools.forgeue_*`: 漏删了某个引用文件,回到 Step 6 grep 结果,补 git rm。

- [ ] **Step 8: Commit P2 retire**

```bash
git add tools tests
git commit -m "$(cat <<'EOF'
retire(forgeue): P2 retire 8 tools + grep-driven 17 tests + 5 fixtures (round 1 codex P1-3 accept)

- Delete 8 tools/forgeue_*.py (forgeue_finish_gate / forgeue_change_state / forgeue_verify / forgeue_doc_sync_check / forgeue_subagent_budget / forgeue_skill_cascade_check / forgeue_enum_cross_ref_check / forgeue_env_detect)
- Delete 17+ tests/unit/test_forgeue_*.py + test_skill_cascade_check.py + test_followon_registry.py (grep-driven cleanup)
- Delete tests/fixtures/forgeue_workflow/ (5 files: __init__.py + builders.py + 3 fake_change_*/README.md)
- tools/_common.py: kept|deleted (depending on Step 5 grep result)

Refs: openspec/changes/retire-forgeue-protocol-layer-fully/{proposal,design,tasks}.md P2 (round 1 codex P1-3 grep-driven cleanup expansion)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: P3 — Retire 3 协议文档 + Level 2 验证文档化

**Files:**
- Delete: `docs/ai_workflow/forgeue_integrated_ai_workflow.md`
- Delete: `docs/ai_workflow/forgeue_quickstart.md`
- Modify: `docs/ai_workflow/README.md`(删 Documentation Sync Gate 段 + ForgeUE Integrated AI Change Workflow 引用段)
- Modify: `docs/ai_workflow/validation_matrix.md`(若引用 `forgeue_verify.py` Level 2 路径)
- Modify: `docs/testing/test_spec.md`(加 Level 2 ComfyUI 验证章节;round 1 codex P1-5 升必做)

**Subagent dispatch:** Implementer = **sonnet**(§1.5.2 doc rewrite — semantic 重写 Level 2 章节 + §1.5.4 architecture doc — 删 Documentation Sync Gate 整段)。Reviewers:spec_review = sonnet(§1.2.4 acceptance criteria — verify Level 2 章节包含 4 capability 完整命令矩阵 + 警告段),code_quality = haiku(§1.3.1 style — markdown 格式)。

- [ ] **Step 1: Verify retire 文档存在 (pre-condition)**

Run: `ls docs/ai_workflow/forgeue_integrated_ai_workflow.md docs/ai_workflow/forgeue_quickstart.md docs/ai_workflow/README.md docs/ai_workflow/validation_matrix.md docs/testing/test_spec.md 2>&1`
Expected: 5 个文件全在(forgeue_integrated_ai_workflow.md / forgeue_quickstart.md / README.md / validation_matrix.md / test_spec.md)。

- [ ] **Step 2: Git rm 2 协议文档**

```bash
git rm docs/ai_workflow/forgeue_integrated_ai_workflow.md \
       docs/ai_workflow/forgeue_quickstart.md
```
Expected: 2 删除行。

- [ ] **Step 3: Edit `docs/ai_workflow/README.md` 段删**

Read current file: `head -100 docs/ai_workflow/README.md`(看 sections 列表)。

Find sections to delete using grep: `grep -n "^## \|^### " docs/ai_workflow/README.md`

Delete sections matching:
1. **"Documentation Sync Gate"** 整段头 + 内容 + §4.3 提示词 + 应用列表
2. **"ForgeUE Integrated AI Change Workflow"** 引用段(如果存在,通常指向已删的 `forgeue_integrated_ai_workflow.md`)

Use Edit tool with old_string = entire section block(from `## Documentation Sync Gate` heading to next `^## ` heading-1)。

Verify after edit:
```bash
grep -c "Documentation Sync Gate" docs/ai_workflow/README.md
```
Expected: `0`(整段删除)

```bash
grep -c "forgeue_integrated_ai_workflow" docs/ai_workflow/README.md
```
Expected: `0`

- [ ] **Step 4: Edit `docs/ai_workflow/validation_matrix.md` (if forgeue_verify.py reference)**

Run: `grep -n "forgeue_verify" docs/ai_workflow/validation_matrix.md 2>&1`

If matches found: replace each `forgeue_verify.py` Level 2 reference with user 手工命令矩阵:
```markdown
**Level 2 ComfyUI 验证(自 retire-forgeue-protocol-layer-fully 起,2026-05-10)**:user 手工跑 `python -m framework.run --task examples/comfy_local_smoke{,_mesh,_audio,_video}.json --live-llm --run-id <id>`。详见 `docs/testing/test_spec.md` Level 2 章节。**禁止** `--comfy-url` flag(silently FakeComfyWorker fallback);**禁止** 走 LiteLLM wildcard 的 bundle(silently FakeComfyWorker fallback,verification 变 false-positive PASS)。
```

If no matches: skip this step。

- [ ] **Step 5: Edit `docs/testing/test_spec.md` Level 2 章节(round 1 codex P1-5)**

Read current file: `grep -n "^## \|^### " docs/testing/test_spec.md | head -30`

Find Level 2 verification section(if exists)or insert new section after Level 1 / before Level 3。

New Level 2 章节内容(insert via Edit tool):

```markdown
## Level 2 — ComfyUI 真机验证(user 手工)

> **自 OpenSpec change `retire-forgeue-protocol-layer-fully`(2026-05-10)起**:Level 2 ComfyUI 验证由 user 手工跑命令矩阵;`tools/forgeue_verify.py` wrapper 已 retire。沿 `openspec/specs/probe-and-validation/spec.md` MODIFIED Requirement 工具无关 contract:**`comfy/local*` 虚拟模型 id + 禁止 `--comfy-url` flag + 禁止 LiteLLM wildcard fallback**。

### 4 Capability 命令矩阵

**前置(双终端工作流,沿 `CLAUDE.md` ComfyUI 接入段)**:
- 终端 1:`python -m factory_v3 serve` 启 ComfyUI(detached, ~30-90s 冷启动;用户自管)
- 终端 2:export env + 跑 ForgeUE

**通用 env**:
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
# FORGEUE_COMFY_PYTHON_EXE 留空 → sys.executable
# FORGEUE_COMFY_LIFECYCLE 留空 → "none"
```

| Capability | Bundle path | 额外 env | 命令 |
|---|---|---|---|
| **Image** | `examples/comfy_local_smoke.json` | (无) | `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>` |
| **Mesh** | `examples/comfy_local_smoke_mesh.json` | `FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input` | `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>` |
| **Audio** | `examples/comfy_local_smoke_audio.json` | (无) | `python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>` |
| **Video** | `examples/comfy_local_smoke_video.json` | (无) | `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>` |

### 警告:false-positive PASS 防范

- **禁止传 `--comfy-url` flag**:silently 被 `framework.run` 忽略,fallback 到 `FakeComfyWorker`(deprecated by `comfy-agent-cli-adoption` v1.6,2026-05-02 archived)。
- **禁止用走 LiteLLM wildcard 的 bundle**:silently fallback 到 `FakeComfyWorker`,verification 变 false-positive PASS(没真跑 ComfyUI subprocess)。
- **检查方法**:bundle `provider_policy.models_ref` 必须解析至 `comfy/local` / `comfy/local-mesh` / `comfy/local-audio` / `comfy/local-video` 之一(`config/models.yaml` aliases 定义);若用 `qwen/*` / `hunyuan/*` 之类 alias → 走 LiteLLMAdapter wildcard → silently fallback FakeComfyWorker。
```

Verify after edit:
```bash
grep -c "Level 2 — ComfyUI" docs/testing/test_spec.md
```
Expected: `1`

```bash
grep -c "comfy_local_smoke_video.json" docs/testing/test_spec.md
```
Expected: `1`(4 capability 全在)

- [ ] **Step 6: Commit P3 retire + Level 2 文档化**

```bash
git add docs/ai_workflow/forgeue_integrated_ai_workflow.md \
        docs/ai_workflow/forgeue_quickstart.md \
        docs/ai_workflow/README.md \
        docs/ai_workflow/validation_matrix.md \
        docs/testing/test_spec.md
git commit -m "$(cat <<'EOF'
retire(forgeue): P3 retire 3 协议文档 + Level 2 验证 docs/testing/test_spec.md 文档化(round 1 codex P1-5 accept)

- Delete docs/ai_workflow/forgeue_integrated_ai_workflow.md
- Delete docs/ai_workflow/forgeue_quickstart.md
- Edit docs/ai_workflow/README.md: 删 Documentation Sync Gate 段 + ForgeUE Integrated AI Change Workflow 引用段
- Edit docs/ai_workflow/validation_matrix.md: 改 forgeue_verify.py Level 2 引用为 user 手工命令矩阵 (if applicable)
- Edit docs/testing/test_spec.md: 新加 Level 2 — ComfyUI 真机验证章节(4 capability 命令矩阵 + false-positive PASS 防范警告)

Refs: openspec/changes/retire-forgeue-protocol-layer-fully/{proposal,design,tasks}.md P3 + P3.5; round 1 codex P1-5 升必做

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: P4 — Verify `openspec/backlog/` 目录保留 + fence 已随 P2 自然消失

**Files:** (no edits — verification only)
- Verify exists: `openspec/backlog/active.md`
- Verify exists: `openspec/backlog/archived.md`
- Verify exists: `openspec/backlog/README.md`
- Verify removed: `tools/forgeue_finish_gate.py`(已 P2 删除)
- Verify exists: 5 archived tombstones(`enhance-workflow-automation-v2-fence-hardening` / `fix-finish-gate-section-regex-for-p-prefixed` / `fix-openspec-validate-archived-change-support` / `fix-video-export-path-split-d12-violation` / `fix-run-import-skipped-filter-permission-only`)

**Subagent dispatch:** None — direct controller execution(verification only)。

- [ ] **Step 1: Verify backlog directory preserved**

```bash
ls openspec/backlog/
```
Expected: `active.md`, `archived.md`, `README.md`(D3 目录保留)

- [ ] **Step 2: Verify finish_gate retire (no fences left)**

```bash
ls tools/forgeue_finish_gate.py 2>&1
```
Expected: `cannot access ... No such file or directory`(P2 已删)

- [ ] **Step 3: Verify 5 archived tombstones exist**

```bash
grep -c "^### \`" openspec/backlog/archived.md
```
Expected: `5`(5 个 `### \`<followon-id>\`` H3 entry)

```bash
grep -E "^### \`(enhance-workflow-automation-v2-fence-hardening|fix-finish-gate-section-regex-for-p-prefixed|fix-openspec-validate-archived-change-support|fix-video-export-path-split-d12-violation|fix-run-import-skipped-filter-permission-only)\`" openspec/backlog/archived.md | wc -l
```
Expected: `5`(5 个 expected ID 全在)

- [ ] **Step 4: Verify SRS §7.3 cross-link (if present)**

```bash
grep -n "openspec/backlog/active.md" docs/requirements/SRS.md | head -3
```
Expected: 至少 1 行匹配(若 SRS 有 cross-link header note 至 active.md)。若无,skip(双源 cross-link 是 documented optional)。

**No commit for P4**(verification only)。

---

## Task 6: P5 — CLAUDE.md / AGENTS.md / README.md 三大段精简(round 1 codex P1-2 accept)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `README.md`

**Subagent dispatch:** Implementer = **sonnet**(§1.5.2 doc rewrite + §1.5.4 architecture doc rewrite — judgment-heavy 哪行删 / 哪行保留 / 如何精简到 ≤30 行 + 如何措辞 codex convention)。**3 个文件分 3 个 implementer dispatch**(P5.A CLAUDE.md / P5.B AGENTS.md / P5.C README.md),避免单 subagent context 过载。Reviewers:spec_review = sonnet(§1.2.3 cross-phase reasoning — 跨 3 文件一致性),code_quality = **sonnet** MANDATORY(§1.3.4 runtime correctness — 漏删可能引发 stale reference)。

### 6.A — CLAUDE.md 精简

- [ ] **Step 6.A.1: Read current CLAUDE.md ForgeUE protocol sections**

Run: `grep -n "^## " CLAUDE.md | head -20`
Expected: 多个 `##` headings,其中 ForgeUE 协议层段:
- `## OpenSpec 工作流(2026-04-24 启用)`
- `## Follow-on Backlog Registry(自 centralize 启用,2026-05-07)`
- `## ForgeUE Integrated AI Change Workflow(2026-04-27 启用)`
- `## 决策权下放(自 enhance-workflow-automation change 起,ADR-010)`
- `## Documentation Sync Gate(摘要)`

Find exact line ranges for each section(start = section heading line, end = next `^## ` line - 1)。

- [ ] **Step 6.A.2: Plan replacement content**

Replacement should be **≤ 30 lines total**(沿 D6 + tasks.md 6.7 verification),含:
1. **OpenSpec 用法**(5-10 行):非平凡走 `/opsx:propose`;小 bugfix 直接改;实施只在 active change scope。
2. **Superpowers 流程**(5-10 行):brainstorming → writing-plans → subagent-driven-development → requesting-code-review → verification-before-completion。
3. **Codex CLI convention**(3-5 行):**Convention**:重要 design 阶段先跑 `/codex:adversarial-review`(catch latent design smell);final review 跑 `/codex:review --base main`(catch cross-archive mixed-scope)。
4. **Backlog pointer**(3-5 行):`openspec/backlog/active.md` 作信息容器 + 双源 cross-link SRS §7.3 + 无 fence 守门 user 自由维护。

- [ ] **Step 6.A.3: Edit CLAUDE.md (delete 5 sections + insert simplified workflow section)**

Use Edit tool to delete each section by `old_string` matching exact heading + entire body to next `^## ` heading。

Then Edit tool insert simplified `## 工作流` section(content from Step 6.A.2 plan)。

- [ ] **Step 6.A.4: Verify CLAUDE.md ForgeUE protocol sections gone + ≤30 lines**

```bash
grep -E "^## (OpenSpec 工作流|Follow-on Backlog Registry|ForgeUE Integrated AI Change Workflow|决策权下放|Documentation Sync Gate)" CLAUDE.md
```
Expected: empty(全删)

```bash
sed -n '/^## 工作流/,/^## /p' CLAUDE.md | wc -l
```
Expected: ≤ 30 lines(沿 D6 + tasks.md 6.7)

### 6.B — AGENTS.md 精简

- [ ] **Step 6.B.1: Read current AGENTS.md protocol references**

Run: `grep -n "/forgeue:change\|forgeue_finish_gate\|forgeue_skill_cascade_check\|12-key frontmatter\|Documentation Sync Gate\|forgeue_integrated_ai_workflow\|forgeue_quickstart\|cross-check\|4 类 DRIFT" AGENTS.md`
Expected: 多个 line:number matches。

- [ ] **Step 6.B.2: Edit AGENTS.md (delete forgeue protocol references)**

Delete sections / lines containing:
1. `/forgeue:change-*` 9 命令矩阵(L212-274 大段)
2. `forgeue_finish_gate` / `forgeue_skill_cascade_check` 等 8 工具引用
3. `12-key frontmatter` / `Documentation Sync Gate` / `cross-check` / `4 类 DRIFT taxonomy`
4. `forgeue_integrated_ai_workflow.md` / `forgeue_quickstart.md` 文档引用

- [ ] **Step 6.B.3: Add codex convention to AGENTS.md**

Insert after the OpenSpec workflow description(if exists)or at appropriate workflow section:
```markdown
**Convention**:重要 design 阶段先跑 `/codex:adversarial-review`(catch latent design smell);final review 跑 `/codex:review --base main`(catch cross-archive mixed-scope)。沿 OpenSpec change `retire-forgeue-protocol-layer-fully`(2026-05-10)。
```

确保 Codex / Cursor / Aider agent onboarding 与 Claude 一致(同 CLAUDE.md 6.A.2 plan 第 3 项)。

- [ ] **Step 6.B.4: Verify AGENTS.md cleanup**

```bash
grep -E "/forgeue:change|forgeue_finish_gate|forgeue_skill_cascade_check|12-key frontmatter|Documentation Sync Gate|forgeue_integrated_ai_workflow|forgeue_quickstart" AGENTS.md
```
Expected: empty(全删)

```bash
grep -c "/codex:adversarial-review" AGENTS.md
```
Expected: ≥ 1(convention 加成功)

### 6.C — README.md 精简

- [ ] **Step 6.C.1: Read current README.md protocol references**

Run: `grep -n "/forgeue:change\|Documentation Sync Gate\|forgeue_integrated\|OpenSpec 工作流" README.md | head -30`
Expected: 多 line:number matches(L360-391 9 命令矩阵)。

- [ ] **Step 6.C.2: Edit README.md (delete protocol references)**

Delete sections / lines containing:
1. `/forgeue:change-*` 9 命令矩阵(L360-391)
2. Documentation Sync Gate 引用
3. `forgeue_integrated_ai_workflow.md` 引用

- [ ] **Step 6.C.3: Update README.md workflow description**

替换为:OpenSpec `/opsx:propose` + Superpowers + codex CLI opt-in convention(类似 CLAUDE.md 6.A.2 plan 但更对外简化)。

- [ ] **Step 6.C.4: Verify README.md cleanup**

```bash
grep -E "/forgeue:change|Documentation Sync Gate|forgeue_integrated_ai_workflow" README.md
```
Expected: empty

### 6.D — Final residue grep verification

- [ ] **Step 6.D.1: Run residue grep across all 4 user-facing docs**

```bash
rg "forgeue_finish_gate|forgeue_verify|forgeue_change_state|forgeue_doc_sync|forgeue_subagent_budget|forgeue_skill_cascade|forgeue_enum_cross_ref|forgeue_env_detect|/forgeue:change|12-key frontmatter|Documentation Sync Gate|forgeue_integrated_ai_workflow|forgeue_quickstart" CLAUDE.md AGENTS.md README.md docs/ai_workflow/README.md 2>&1 | head -20
```
Expected: empty(全砍干净;若有 archived/historical references 在 archived 目录是允许的)

- [ ] **Step 6.D.2: Commit P5 三大文件精简**

```bash
git add CLAUDE.md AGENTS.md README.md
git commit -m "$(cat <<'EOF'
retire(forgeue): P5 CLAUDE.md / AGENTS.md / README.md 三大段精简 + 加 codex convention(round 1 codex P1-2 accept)

- CLAUDE.md: 删 5 段 ForgeUE 协议引用(OpenSpec 工作流 / Follow-on Backlog Registry / ForgeUE Integrated AI Change Workflow / 决策权下放 / Documentation Sync Gate);精简为 ≤30 行新 ## 工作流 段(OpenSpec 用法 + Superpowers 流程 + codex convention + backlog pointer)
- AGENTS.md: 删 9 命令矩阵 + 8 工具引用 + 12-key frontmatter / Documentation Sync Gate / cross-check / 4 类 DRIFT 协议引用 + forgeue_integrated_ai_workflow / forgeue_quickstart 文档引用;加 codex convention 一行
- README.md: 删 9 命令矩阵(L360-391)+ Documentation Sync Gate / OpenSpec 工作流引用;更新工作流描述

Refs: openspec/changes/retire-forgeue-protocol-layer-fully/{proposal,design,tasks}.md P5; round 1 codex P1-2 accept

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: P6 — Verify 13 active workflow-protocol follow-on 不动(自然演化)

**Files:** (no edits — verification only)
- Verify: `openspec/backlog/active.md` 13 workflow-protocol entries unchanged
- Verify: 6 capability-boundary entries unchanged
- Verify: 9 requirements-tbd-pointer entries unchanged

**Subagent dispatch:** None — direct controller execution(verification only)。

- [ ] **Step 1: Verify 13 workflow-protocol follow-on present**

```bash
grep -E "^### \`(enhance-workflow-automation-handoff-persistence|add-forgeue-brainstorm-stage|enhance-workflow-automation-finishing-branch|enhance-workflow-automation-final-review-fence-strictness|analyze-superpowers-skills-openspec-integration-gaps|fix-cross-check-format-test-enum-extension|fix-finish-gate-completed-cancel-uses-baseline-entries|fix-finish-gate-followon-regex-allow-tbd-uppercase|fix-finish-gate-tombstone-empty-cancel-tag-bypass|fix-finish-gate-archived-md-protected-field-deletion|fix-enum-cross-ref-check-windows-gbk-print|audit-archived-subagent-budget-true-cost-vs-discipline-tier|fix-pretest-pre-existing-fence-baseline-drift)\`" openspec/backlog/active.md | wc -l
```
Expected: `13`

- [ ] **Step 2: Verify 6 capability-boundary entries present**

```bash
grep -E "^### \`(audio-metadata-parser|video-metadata-parser|comfy-video-webm-adoption|comfy-video-v2v-adoption|comfy-video-image-sequence-adoption|video-bmff-largesize-support)\`" openspec/backlog/active.md | wc -l
```
Expected: `6`

- [ ] **Step 3: Verify 9 requirements-tbd-pointer entries present**

```bash
grep -E "^### \`TBD-00[1-9]\`|^### \`TBD-01[0-3]\`" openspec/backlog/active.md | wc -l
```
Expected: `9`(沿 SRS §7.3 双源 cross-link)

- [ ] **Step 4: Verify total 28+ entries**

```bash
grep -c "^### \`" openspec/backlog/active.md
```
Expected: ≥ 28(13 workflow-protocol + 6 capability-boundary + 9 requirements-tbd-pointer = 28;round 1 codex 后可能略多)

**No commit for P6**(verification only)。

---

## Task 8: P7 — 全套 pytest baseline 0 fail

**Files:** (no edits unless fail investigation requires)

**Subagent dispatch:** Direct controller execution for Step 1-2;若 Step 3 发现 non-retire-related fail 升 **sonnet** subagent(§1.6.2 reproduce + identify root cause)。

- [ ] **Step 1: Run full pytest suite**

```bash
python -m pytest -q 2>&1 | tail -30
```
Expected:
- 之前 P0 baseline 中的 2 pre-existing fail(`test_active_md_known_workflow_protocol_entries_present` + `test_real_cross_check_files_have_evidence_type`)在 P2 retire 后 **自动消失**(fence test files 已 P2 整删,pytest 不再 collect)。
- 总 fail 数 == 0(0 failed in summary)。

If `failed: 0` → PASS,go to Step 4。

- [ ] **Step 2: Investigate any non-retire-related fails (if any)**

If pytest fail count > 0 in Step 1:

Run: `python -m pytest -q 2>&1 | grep "FAILED"`
Expected: list of failing test names。

For each failing test:
1. Read the test file
2. Identify failure cause(import error / fixture missing / assertion fail)
3. Classify:
   - **retire-residual**(test still references retire 工具 / 命令)→ go to Step 3
   - **non-retire-related**(本 retire 之前已存在的 latent issue)→ defer to follow-on(沿 follow-on `fix-pretest-pre-existing-fence-baseline-drift` cleanup)

- [ ] **Step 3: Fix retire-residual fails (if any)**

If retire-residual found:
1. `git rm <residual_test_file>`(若整删 + commit)
2. 或 Edit 修复 stale reference(若部分保留)
3. Re-run `python -m pytest -q`
4. Verify fail count = 0

- [ ] **Step 4: (Optional) Commit P7 baseline cleanup**

If Step 3 produced any commits:
```bash
git commit -m "fix(forgeue): P7 baseline cleanup retire-residual test fails"
```

If Step 1 directly PASS: no commit needed for P7。

---

## Task 9: P8 — Retrospective + archive

**Files:**
- Create: `openspec/changes/retire-forgeue-protocol-layer-fully/notes/retrospective.md`
- (Optional)Create: codex final review evidence(if `/codex:review --base main` is run)
- Modify: `openspec/specs/examples-and-acceptance/spec.md`(via `openspec sync`)
- Modify: `openspec/specs/probe-and-validation/spec.md`(via `openspec sync`)

**Subagent dispatch:** Implementer = **sonnet**(§1.5.4 architecture doc rewrite — retrospective 写 architecture-level reflection)。Final reviewer = sonnet(§1.7.2 cross-check evidence vs spec)。

- [ ] **Step 1: Write retrospective.md**

Create `openspec/changes/retire-forgeue-protocol-layer-fully/notes/retrospective.md` (free-form, no 12-key frontmatter):

```markdown
# Retrospective — `retire-forgeue-protocol-layer-fully`

## 实施统计

- **实际 LOC delete**: <count from `git log --shortstat <P0-commit>..HEAD`>(对比 design.md 估计 ~9500)
- **实际 commit 数**: <count, expect 6-8>(P1 / P2 / P3 / P5 / P7-optional / P8 各一,共 ~6 commits)
- **Phase 执行顺序**: P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8
- **Subagent dispatch 总数**: <count from per-task evidence file count or budget log>

## Codex review 调用记录(round 1 codex P2 writeback;design.md D4 mitigation 强制)

- **codex_design_review**: run(2026-05-10);output: `notes/codex_adversarial_review_review_round1.md`;6 finding(5 P1 + 1 P2);verdict: needs-attention → 全 inline writeback,disputed_open=0
- **codex_final_review**: <run | explicitly skipped with reason>(P9.2 optional `/codex:review --base main`)

## 新工作流 dogfood 反馈

- 走 OpenSpec `/opsx:propose` + Superpowers `writing-plans` + `subagent-driven-development` 是否顺畅?<填写实际反馈>
- Friction points:<列举 friction,如:writing-plans 把 OpenSpec artifacts 作 input 是否流畅、subagent 之间如何 handoff、phase 间 review checkpoint 是否过密 / 过疏>
- Time spent per phase:<填写时间分布,for 后续 calibration>

## Round 1 codex writeback 总结

| Finding | Codex priority | Verify | Resolution | 落地 commit / writeback location |
|---|---|---|---|---|
| P1-1 SKILL 删 vs 保留 | high | confirmed real,但 codex 误读 SKILL 性质 | accepted-claude(partial-dispute) | design.md D11 + tasks.md P1.13 + proposal.md What Changes |
| P1-2 AGENTS.md / README.md scope | high | confirmed real | accepted-codex | proposal.md Impact + tasks.md P5 |
| P1-3 测试清单 17+5 漏 | high | confirmed real | accepted-codex | tasks.md P2 grep-driven |
| P1-4 capability-boundary requirement 孤立 | high | confirmed real | accepted-codex | specs/examples-and-acceptance/spec.md REMOVED→MODIFIED |
| P1-5 Level 2 subprocess contract 过早删 | high | confirmed real | accepted-codex | specs/probe-and-validation/spec.md REMOVED→MODIFIED + tasks.md P3.5 升必做 |
| P2 codex hook silent skip | medium | confirmed real | accepted-codex | design.md D4 mitigation + tasks.md P8.1 retrospective record |

**disputed_open**: 0

## 后续 follow-on(本 change 后可能新发现的 retire 残留)

- <填写实际新发现的 retire 残留,如 docs/ 中漏改的引用、tests/ 中漏删的 stale fixture、其他 sister skill 的 hard-wire>
- <若无新发现,写"无 — 本 retire scope 完整覆盖,沿 round 1 codex P1-3 grep-driven cleanup 已 grep 残留 0">
```

After writing,verify:
```bash
test -f openspec/changes/retire-forgeue-protocol-layer-fully/notes/retrospective.md
grep -c "## Codex review 调用记录" openspec/changes/retire-forgeue-protocol-layer-fully/notes/retrospective.md
```
Expected: file exists, `1` match。

- [ ] **Step 2: (Optional) Run final codex review**

If user opt-in:
```bash
node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" review --base main
```
Background dispatch via `Bash(run_in_background: true)`。

If output is reviewed and no new BLOCKER:update retrospective.md `codex_final_review` field to `run(<date>); 0 BLOCKER`。

If skipped:update retrospective.md `codex_final_review` field to `explicitly skipped: <≥30 字 reason>`。

- [ ] **Step 3: Run openspec validate strict (final pre-archive)**

```bash
openspec validate retire-forgeue-protocol-layer-fully --strict 2>&1
```
Expected: `Change 'retire-forgeue-protocol-layer-fully' is valid`

- [ ] **Step 4: Archive change**

```bash
# Note: assuming /opsx:archive command or openspec archive CLI
openspec archive retire-forgeue-protocol-layer-fully 2>&1
```
Expected: `openspec/changes/<date>-retire-forgeue-protocol-layer-fully/` 创建成功(`<date>` = 2026-05-XX,运行日期)

- [ ] **Step 5: Run openspec sync (apply spec deltas)**

```bash
openspec sync 2>&1
```
Expected: 主 spec(`openspec/specs/examples-and-acceptance/spec.md` + `openspec/specs/probe-and-validation/spec.md`)更新,REMOVED 30 段从主 spec 删除,MODIFIED 2 段在主 spec 应用最新内容。

Verify:
```bash
grep -c "Centralized follow-on backlog registry" openspec/specs/examples-and-acceptance/spec.md
```
Expected: `1`(MODIFIED 后保留最小 schema 段)

```bash
grep -c "forgeue_finish_gate.py" openspec/specs/examples-and-acceptance/spec.md
```
Expected: `0`(REMOVED 段全删)

```bash
grep -c "forgeue_verify.py" openspec/specs/probe-and-validation/spec.md
```
Expected: `0`(原 Requirement 名含 `forgeue_verify.py`,MODIFIED 后改成工具无关版)

- [ ] **Step 6: Commit P8 archive + sync**

```bash
git add openspec/changes openspec/specs
git commit -m "$(cat <<'EOF'
archive(forgeue): retire-forgeue-protocol-layer-fully → archive/<date>(round 1 codex 6 finding accepted + writeback inline)

- Move openspec/changes/retire-forgeue-protocol-layer-fully/ → openspec/changes/archive/<date>-retire-forgeue-protocol-layer-fully/
- Sync REMOVED 30 段 + MODIFIED 2 段 to openspec/specs/examples-and-acceptance/spec.md + openspec/specs/probe-and-validation/spec.md
- Notes/retrospective.md captures: 实施统计 + codex review 调用记录(round 1 + final optional)+ 新工作流 dogfood 反馈 + round 1 codex writeback 总结(disputed_open=0)

Refs: openspec/changes/retire-forgeue-protocol-layer-fully/{proposal,design,tasks}.md P8; round 1 codex 6 finding 5 accepted-codex + 1 accepted-claude

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: P9 — Optional CHANGELOG / residue sweep(本 change scope 外)

**Files:**
- (Optional)Modify: `CHANGELOG.md`
- (Optional)Sweep: residue references to `forgeue_integrated_ai_workflow.md` etc. in CLAUDE.md/AGENTS.md/README.md(P5 已做 Step 6.D residue grep,P9 是 backstop)

**Subagent dispatch:** None or haiku(§1.5.1 mechanical doc sync if CHANGELOG entry simple)。

- [ ] **Step 1: (Optional) Add CHANGELOG entry**

If user prefers maintaining CHANGELOG.md:

Edit `CHANGELOG.md`,add entry under most recent date heading:

```markdown
## [2026-05-XX] — retire-forgeue-protocol-layer-fully

- **BREAKING** retire 9 个 `/forgeue:change-*` 命令 + 2 sister skill + 8 个 `tools/forgeue_*.py` 工具 + 3 协议文档 + 部分 spec Requirement(31 个 REMOVED + 2 个 MODIFIED across `examples-and-acceptance` + `probe-and-validation` spec)
- 切换到 OpenSpec(contract anchor)+ Superpowers(evidence 流)+ codex CLI(opt-in via convention)三层精简栈
- 保留 `.claude/skills/subagent-driven-discipline/`(D11 generic universal SKILL)+ `openspec/backlog/`(信息容器,无 fence)+ archived 24 changes(D-ArchivedReplayCompat)
- Round 1 codex adversarial review 6 finding 全 inline writeback(5 accepted-codex + 1 accepted-claude partial-dispute)
- 量级:LOC delete <实际数>;文件 delete ~50+
```

- [ ] **Step 2: (Optional) Final residue sweep**

```bash
rg "forgeue_integrated_ai_workflow|forgeue_quickstart" --type md 2>&1 | grep -v "openspec/changes/archive" | head -10
```
Expected: empty(若有 stale reference 在非 archived 目录,sweep 修)

- [ ] **Step 3: (Optional) Commit P9 sweep**

```bash
git add CHANGELOG.md
git commit -m "docs(forgeue): P9 CHANGELOG entry for retire-forgeue-protocol-layer-fully(optional)"
```

> **Note**: P9 is optional. 可在本 change 内跑 / 也可拆独立 follow-on `cleanup-retire-residue` 执行。

---

## Self-Review Checklist

(Run mentally before declaring plan complete)

### 1. Spec coverage

| Spec section | Plan task |
|---|---|
| proposal.md What Changes — retire 9 commands | Task 2 (P1) |
| proposal.md What Changes — retire 2 sister skills | Task 2 (P1) |
| proposal.md What Changes — retire 8 tools | Task 3 (P2) |
| proposal.md What Changes — retire 3 docs | Task 4 (P3) |
| proposal.md What Changes — protocol mechanisms retire | Tasks 2/3/4 (随 9 命令 / 8 工具 / 12-key frontmatter retire 自然消失) |
| proposal.md What Changes — backlog 守门 fence retire | Task 5 (P4 verify) |
| proposal.md What Changes — CLAUDE.md / AGENTS.md / README.md slim | Task 6 (P5) |
| proposal.md Capabilities — examples-and-acceptance MODIFIED | Task 9 (P8 sync 应用 MODIFIED) |
| proposal.md Capabilities — probe-and-validation MODIFIED | Task 9 (P8 sync 应用 MODIFIED) |
| proposal.md Impact — AGENTS.md/README.md/test_spec.md modify | Tasks 4 (P3 test_spec.md) + 6 (P5 AGENTS/README) |
| design.md D1 走 Superpowers 不走自家 9 命令 | 整 plan 走 Superpowers,本 plan 自身证明 |
| design.md D2 archived 不动 | Task 5 (P4) verify, Task 9 (P8 sync) 不影响 archived |
| design.md D3 backlog 目录保留 | Task 5 (P4) |
| design.md D4 codex hook opt-in convention | Task 6 (P5 6.A.2 + 6.B.3 加 convention) |
| design.md D5 13 follow-on 自然演化 | Task 7 (P6 verify) |
| design.md D6 CLAUDE.md ≤30 行 | Task 6 (P5 6.A.4 verify) |
| design.md D7 examples-and-acceptance REMOVED 30 段 | Task 9 (P8 sync) |
| design.md D8 probe-and-validation REMOVED→MODIFIED | Task 9 (P8 sync) |
| design.md D9 Phase 划分 P0-P8 | Tasks 1-9 1:1 mapping |
| design.md D10 sunk cost accept | retrospective.md(Task 9) |
| design.md D11 SKILL 保留 | Task 2 (P1 6.B 步骤 4 verify preserve) |
| tasks.md P0-P9 各 phase | Tasks 1-10 完整 mapping |

**No gaps**: 所有 spec section 都有对应 task。

### 2. Placeholder scan

- ✅ 无 "TBD" / "TODO" / "implement later" / "fill in details"
- ✅ 无 "Add appropriate error handling" / "add validation" / "handle edge cases"
- ✅ 无 "Write tests for the above"(without actual test code)
- ✅ 无 "Similar to Task N"(各 task 内容独立)
- ✅ 各 step 有 exact 命令 + expected output
- ✅ 各 file 引用都是 exact path

### 3. Type consistency

- ✅ Phase 命名 P0-P9 跨 task 一致
- ✅ Subagent dispatch model tier 沿 sister skill `subagent-driven-discipline` §1 表统一引用
- ✅ Round 1 codex writeback 6 finding 引用 P1-1 ~ P1-5 + P2 命名跨 task / retrospective 一致
- ✅ Spec delta REMOVED / MODIFIED 边界跨 task 9 / proposal / design 一致

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-10-retire-forgeue-protocol-layer-fully.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Fresh subagent per task + two-stage review(spec_review + code_quality_review per task)
- Model tier per Task 1-10 表(haiku for P1/P7 mechanical;sonnet for P2/P3/P5/P8 judgment-heavy + code_quality runtime correctness reviewer)

**If Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- Batch execution with checkpoints between phases(P1 → P2 → P3 → P5 → P7 → P8 = 6 checkpoints)
