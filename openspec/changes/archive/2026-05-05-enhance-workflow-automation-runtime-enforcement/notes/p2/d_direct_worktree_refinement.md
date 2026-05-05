# D-DirectWorktreeRefinement — drift writeback evidence

> Helper note(notes/ 不强制 12-key frontmatter;此 note 记录 P2.2 实施前发现的契约冲突 + user 拍板裁决 + 双向 writeback 摘要)

## 触发(2026-05-05 P2.2 实施前)

P2.2 实装 `change-apply-direct.md` 加 3 段 Preflight 时,Claude controller 静态读了三处契约,发现矛盾:

| 来源 | 锚点 | direct 是否走 worktree |
|---|---|---|
| 本 change spec.md L48-51 | `Scenario: change-apply-direct + change-apply-parallel 同款 Preflight Worktree section` | **要求** direct 加 Preflight Worktree |
| 本 change design.md L70 | `D-WorktreeEnforce Statement: ...三个命令模板均加 ## Preflight Worktree step...` | **要求** direct 加 Preflight Worktree |
| archived `2026-05-04-adopt-subagent-driven-development/design.md` D-Worktree-Detail 第 5 项 | "`change-apply-direct` fallback 路径仍跑在主 worktree(无需 isolation)" | **不要求** direct 走 worktree |
| 现网 `change-apply-direct.md` L66 Guardrails | "direct 路径不进 isolated worktree(沿 design.md D-Worktree-Detail 第 5 项)" | **不要求** direct 走 worktree |

archived D-Worktree-Detail 第 5 项是 `adopt-subagent-driven-development` codex round 1 review F1 沉淀的决策(评估保留 fallback 路径不走 worktree 的轻量语义);本 change propose 阶段 D-WorktreeEnforce statement 写"3 个命令均加" **未与 archived 第 5 项对齐**,P2.2 实装时实证暴露。

## User 拍板(2026-05-05)

按 `feedback_autonomy_boundary_simplified.md` framework / design 不匹配 fence,Claude 升级 user 拍板。给出三选项:

- **(A)** Direct 也走 worktree:接受 spec.md / design.md 字面契约,加显式 D-DirectWorktreeOverride decision 覆盖 archived 第 5 项;改写 change-apply-direct.md 加 worktree 步骤。代价:每次 direct 多 ~10-20s 开销,违 direct "轻量 fallback" 语义。
- **(B)** Direct 不走 worktree(**user 拍板选用**):沿 archived 第 5 项;改本 change spec.md / design.md 收窄到 subagent + parallel 两个命令;direct 命令模板 P2.2 只加 2 段 Preflight(Skill Cascade + Task Granularity)。
- **(C)** Hybrid env flag opt-in:加 `FORGEUE_DIRECT_WORKTREE=1` opt-in。代价:协议复杂度上升,既不像 (A) 干净统一也不像 (B) 与 archived 对齐。

User 给出"按B走"。

## Writeback 实装(本 commit)

按 4 类 DRIFT taxonomy,本次属 `evidence_contradicts_contract`(实施暴露本 change 内部 spec / design 与 archived 历史决策三方不一致);走 inline writeback 协议:

### spec.md(本 change `specs/examples-and-acceptance/spec.md`)

**Requirement: Preflight Worktree runtime enforcement** 段收窄:

- 范围声明:`/forgeue:change-apply-{subagent,parallel}` **两个**命令模板(原 "三个" 含 direct,改为 "两个")
- 加显式段说明 direct 不强制 + 引 archived 第 5 项保留依据
- 加 Scenario:`change-apply-parallel` 同款 Preflight Worktree(原 scenario 把 direct + parallel 合并,现拆分)
- 加 Scenario:`change-apply-direct 沿 archived 第 5 项不强制 Preflight Worktree`(新增 negative scenario 锁住 direct 不强制行为)
- 加 Scenario:`direct implementation evidence 缺 worktree_path 字段 finish_gate pass-through`(锁住 fence pass-through 行为)
- 改 Scenario:原 `implementation evidence 缺 worktree_path 字段 finish_gate 阻断` 改为 `subagent / parallel implementation evidence 缺 worktree_path 字段 finish_gate 阻断`(显式排除 direct)

### design.md(本 change `design.md`)

**D-WorktreeEnforce** 段:

- Statement 收窄:"两个命令"(subagent + parallel),direct 排除
- 加显式段说明 direct 沿 archived;指向新 D-DirectWorktreeRefinement
- 强制性段 evidence frontmatter 字段说明改为基于 `triggered_by_command` ∈ frozenset 而不是 `change-apply-*` 类

新增 **D-DirectWorktreeRefinement** decision(在 D-WorktreeEnforce 后),含:

- Statement:direct 不加 Preflight Worktree,沿 archived 第 5 项
- Why:direct 是轻量 fallback,~10-20s worktree 开销不划算;archived 第 5 项是 codex round 1 沉淀决策不主动覆盖
- Trigger origin:由 P2.2 实施时实证暴露 + user 2026-05-05 拍板 (B)
- 实装影响:spec / design / fence frozenset / change-apply-direct.md 四处一致
- Alternatives considered:列 (A)/(B)/(C) 三选项 + user 拍板 (B)

### tools/forgeue_finish_gate.py(`_check_worktree_path` fence)

- 原 `_CHANGE_APPLY_COMMAND_PREFIX = "change-apply-"` + `triggered.startswith(prefix)` 删除
- 改为 `_WORKTREE_REQUIRED_COMMANDS: frozenset[str] = {"change-apply-subagent", "change-apply-parallel"}` + `triggered not in _WORKTREE_REQUIRED_COMMANDS` pass-through
- docstring 显式说明 direct fence pass-through + 引 D-DirectWorktreeRefinement

### tests/unit/test_forgeue_finish_gate.py

- 原 `test_worktree_path_empty_string_blocks` 用 `triggered_by_command="change-apply-direct"`,新协议下 direct pass-through → 测试失败(已修);改为用 `change-apply-subagent` 触发空字符串 block 路径
- 新增 `test_worktree_path_not_required_for_change_apply_direct` 锁住 direct pass-through 行为
- 新增 `test_worktree_path_required_for_change_apply_parallel` 锁住 parallel 与 subagent 同等强制行为

## 验证

- `pytest -q tests/unit/test_forgeue_finish_gate.py` 全绿(101 passed,原 99 + 新加 direct/parallel 2 个;原 test_worktree_path_empty_string_blocks 协议改后修正未变测试数 99→100,加 1 个 direct → 100→101)
- `pytest -q` 全套 regress 跟随本 commit 一并落

## 影响 P2.x 后续 task

- **P2.2** 改:change-apply-direct.md 只加 2 段 Preflight(Skill Cascade + Task Granularity),**不**加 Preflight Worktree(本 evidence 落 task 描述 update)
- **P2.6** 加:fence test 验证 direct 不含 Preflight Worktree section(negative scenario 守门)
- **P2.6** 改:原 `test_each_apply_cmd_has_preflight_worktree_section` fence(3 个 apply 命令)改为(2 个 apply 命令:subagent + parallel)
- **P4.x** 文档同步:沿本 D-DirectWorktreeRefinement 在 quickstart / forgeue_integrated_ai_workflow.md 同步 direct 不走 worktree 的 contract 边界

## 后续守门

- finish_gate `_check_worktree_path` fence 是 fence pass-through 而非默认 deny — 防止后续 change 误改 frozenset 重新破坏 archived 决策时,本 evidence 留 anchor reasoning 给 codex 后续 review 引用
- 本 D-decision 在 P10 archive 时随本 change spec delta 一起 sync 到 `openspec/specs/examples-and-acceptance/spec.md`(P10.3 协议)

## writeback_commit

本 evidence 与 spec.md / design.md / finish_gate / 测试改动单一 commit 落账(commit SHA 写入本 evidence 母 commit 后 5 类 evidence 引用此 commit)。
