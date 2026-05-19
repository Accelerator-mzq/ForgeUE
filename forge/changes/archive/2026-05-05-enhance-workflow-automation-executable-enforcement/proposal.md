## Why

刚 ship 的 `enhance-workflow-automation-runtime-enforcement` change 在 Pre-P0 codex round 1 被挑出 5 个 finding,2 个 medium 已 inline writeback,**3 个 high(F1/F2/F3)被 deferred 到本 follow-on**。原因:F1/F2/F3 揭示当前 worktree / parallel / continuity 三处 enforcement 是 markdown advisory + LLM 自报 frontmatter,**无法在实际 dispatch 前形成确定性阻断**:

- **F1**:Preflight Worktree 是命令模板里的 markdown step,controller 跳过后 subagent 已在主 worktree 修改,只有 finish_gate 才能事后 catch(`enhance-workflow-automation-runtime-enforcement/notes/pre_p0/codex_review_round1.md` F1 段)。
- **F2**:parallel dispatch 的 `task_files_disjoint` 是 controller frontmatter 声明,不是 implementer 实际 diff;真实失败场景(共享 fixture / global config / import hub)不被 catch。
- **F3**:round 2 fix continuity 的 `round_1_implementer_id` / `round_2_fix_implementer_id` 由同一 controller 写入 frontmatter,**可伪造**(controller emulation drift 或误填可复制同 id 通过 fence)。

本 change 用**可执行脚本(executable enforcement)**替代 markdown advisory,把这 3 处升级为 deterministic gate:命令模板只能消费 machine-generated 制品(receipt JSON / actual diff / append-only ledger),LLM 不能直接写关键字段,finish_gate 比较机器制品与 evidence frontmatter 一致性 → 任何 controller drift 在 finish_gate 前一步被阻断。

时机:刚 ship 的 advisory 协议是 `enhance-workflow-automation-runtime-enforcement` 自身 dogfood 后的最小可行版,3 个 high finding 已被显式 deferred 跟踪;本 change 是**第一个真正应用刚 ship 协议的 follow-on**,既能闭环 F1/F2/F3,又能验证刚 ship 的 8 D-decision / 4 fence / 3 命令(change-apply-subagent / parallel / direct)在真实 multi-file scope change 下的运行时行为。

## What Changes

- **W1(F1 close)**:新增 `tools/forgeue_preflight_wrapper.py` executable script。
  - 命令层在 dispatch 任何 subagent 前调用 wrapper:wrapper 创建 / 验证 isolated worktree(沿用 `superpowers:using-git-worktrees` skill),写 machine-generated `<change>/preflight_receipts/<receipt_id>.json`(含 base SHA / target worktree path / cwd / cascade check status / created_at);
  - 命令模板**只能消费** receipt path,不允许 LLM 直接填 evidence frontmatter `worktree_path` 字段;
  - `forgeue_finish_gate.py` `_check_worktree_path` fence 升级:原来比较 evidence frontmatter `worktree_path` non-null,现在校验 receipt 文件存在 + receipt 内容 path 与 evidence frontmatter `worktree_path` 字符串一致;
  - 闭环 Gap B(F1):controller 跳过 preflight 时,finish_gate 因找不到 receipt 立即 fail-closed,而不是事后 audit。

- **W2(F2 close)**:`/forgeue:change-apply-parallel` 命令模板加可执行 file overlap 检测步骤。
  - 主 session 在 dispatch 后等所有 implementer subagent commit、然后主 session **自动**在每个 subagent worktree 内跑 `git diff --name-only <base_sha>..HEAD` 收集**实际** changed-files set;
  - 主 session 跑 set intersection;若 intersection 非空(actual overlap)→ 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(用户无 prompt);
  - actual changed-files 写入 evidence frontmatter `task_files_actual`(与原有 declaration `task_files_disjoint` 并列;finish_gate 比较两者一致性);
  - 闭环 Gap C(F2):共享 fixture / shared config / undeclared file 修改在主 session 一次 git diff 后立即被 catch,不依赖 controller 声明诚实性。

- **W3(F3 close)**:新增 `tools/forgeue_dispatch_ledger.py` executable script。
  - 命令模板包裹 Task / SendMessage 调用为 wrapper invocation:wrapper 在调用前向 `<change>/dispatch_ledger.jsonl`(append-only,JSONL)写一行(含 agent_id / round / role / dispatch_at_iso / parent_session_id / task_subject_hash);
  - LLM 不能直接 echo / sed / Edit 写 ledger(命令模板里 ledger path 走 wrapper,不暴露给 LLM 文本上下文);
  - `forgeue_finish_gate.py` `_check_round_fix_continuity` fence 升级:原来比较 evidence frontmatter `subagent_continuity` 字段一致性,现在 cross-check ledger 中真实 dispatch 记录 vs evidence frontmatter `subagent_continuity` 字段;ledger 缺失 → fail-closed;
  - 闭环 Gap D(F3):agent_id 由 wrapper 在 dispatch 时写入,LLM 无法手写 → frontmatter 伪造路径关闭。

- 加 `runtime_enforcement_protocol_version: v2`(沿 v1 兼容协议,仅 W1/W2/W3 新字段触发 v2 gate)。
- 命令模板更新:`/forgeue:change-apply-subagent` / `/forgeue:change-apply-parallel` 的 `## Preflight` 段加 wrapper 调用 + receipt 消费 + ledger wrapper 包裹 dispatch 步骤。
- finish_gate 4 fence 升级:`_check_worktree_path` / `_check_round_fix_continuity` / `_check_skill_cascade` / `_check_task_granularity`(`_check_task_granularity` 不变;前两个升级为 receipt + ledger 物证比对;`_check_skill_cascade` 沿用 v1 多 root 探测,无需变化但要传播 protocol_version=v2 报告字段)。
- 新加 `_check_dispatch_ledger`(W3)+ `_check_file_overlap_actual`(W2)2 个 fence。

## Capabilities

### New Capabilities

(无新增 capability;沿用 examples-and-acceptance,本 change 工具属同一工作流验收范畴。)

### Modified Capabilities

- `examples-and-acceptance`:扩展 5 ADDED Requirement 到 W1 receipt + W2 actual overlap + W3 dispatch ledger + 4 fence 升级 + protocol_version v2 migration。

## Impact

- **新增工具**:`tools/forgeue_preflight_wrapper.py`、`tools/forgeue_dispatch_ledger.py`(stdlib-only;沿前 change `forgeue_*.py` 7 工具风格)。
- **修改工具**:`tools/forgeue_finish_gate.py`(2 fence 升级 + 2 fence 新增 + protocol_version v2 dispatch)。
- **修改命令模板**:`.claude/commands/forgeue:change-apply-subagent` + `.claude/commands/forgeue:change-apply-parallel`(Preflight 段 wrapper 调用)。
- **修改 backbone skill**:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(W1/W2/W3 wrapper invocation 协议描述)。
- **frontmatter schema 扩展**:`runtime_enforcement_protocol_version: v2` + `worktree_receipt_path` + `dispatch_ledger_path` + `task_files_actual`(只对 v2+ evidence 强制;v1 evidence pass-through;archived enhance-workflow-automation-runtime-enforcement evidence 不受影响)。
- **测试矩阵**:新增 fence 单元测试覆盖 receipt 缺失 / 内容不一致 / ledger 缺失 / 实际 overlap detected / protocol v2 vs v1 兼容 / archived fixture 回归 6 类。
- **文档同步**:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C 加 W1/W2/W3 wrapper 协议;`CHANGELOG.md` [Unreleased];`CLAUDE.md` 工作流速查清单加 protocol v2 字段说明。
- **archived change 兼容性**:archived 2026-05-05-enhance-workflow-automation-runtime-enforcement 自身 evidence 是 v1,本 change ship 后跑 finish_gate replay 不会被新 fence 误杀(沿 v1 fence pass-through 协议)。
- **不引入新 vendor API 调用**(本 change 全 stdlib + Bash + Skill tool 编排;无 ADR-007 钱 fence 触发)。
- **Dogfood 边界**:本 change 自身实施时 W1 wrapper 还没 ship,所以本 change evidence frontmatter `worktree_path` 仍走 LLM 自报(沿 v1 advisory);ship 后下一个 change 才能机器生成 receipt(W1 真实战 dogfood 在 follow-on)。本 change 仍可用 v1 advisory 协议 + finish_gate audit 安全 archive。**(F5 round 1 codex inline writeback)**:archive 前必跑 `tests/integration/test_v2_e2e_synthetic_change.py` synthetic fixture(D-W4-IntegrationGate)— mock 完成 v2 协议端到端实跑(W1 + W2 + W3 + finish_gate + overlap 负例 + v1/legacy 回归);P10.0 必过 gate。

## Round 1 Codex Adversarial Review Inline Writeback Summary(2026-05-05)

Pre-P0 codex round 1 raise 5 high finding(`review/codex_design_review.md` + `review/design_cross_check.md`):

- **F1**(wrapper 不直接 invoke Skill → controller 跳过 worktree step 后无法证明 cwd in worktree):**accepted-codex,inline writeback** → wrapper 自己用 `git worktree` subprocess 自管 worktree(不依赖 Skill tool)+ 强制 cwd 校验在 wrapper-managed worktree 内(否则 fail-closed exit 6)+ receipt 加 `is_isolated_worktree: bool` + `worktree_action: enum` 2 新字段 + P0.4 加 wrong-cwd / dirty 2 negative test
- **F2**(dispatch ledger 在 Task 之前写 synthetic uuid_v4 与真实 agent_id 无关):**accepted-codex,partial inline + deferred** → (a) inline:改 post-dispatch ledger capture(Skill(Task) 返回后 capture 真实 agent_id);evidence frontmatter `pre_dispatch_metadata: advisory` 诚实标注。(b) deferred:真 wrapper-bound dispatch 留 follow-on `enhance-workflow-automation-ledger-binding`
- **F3**(ledger fence 只校验公开字段 wrapper_version + timestamp,LLM 可写 well-formed forge 通过):**accepted-codex,降级标注 + deferred** → (a) inline:evidence frontmatter `ledger_forgery_resistance: advisory` 诚实标注 well-formed forge 不阻断;fence 仅 catch crude forge(timestamp 倒流 / 字段缺失 / agent_id 格式不对)。(b) deferred:cryptographic enforcement(HMAC + LLM 不可见 key)留 follow-on `enhance-workflow-automation-ledger-binding`(同 F2)
- **F4**(W2 actual diff 用 git diff 漏 untracked file):**accepted-codex,inline writeback** → spec.md / design.md / tasks.md 改 SHALL `git status --porcelain=v1 -z` + committed diff 合集 + implementer worktree clean precondition fail-closed;OQ-2 标 `resolved-inline`
- **F5**(P12.2 真 dogfood 在"后置(可选)"段;archive 前 v2 协议无端到端实跑):**accepted-codex,inline writeback** → 加 P5.5 v2 e2e integration test fixture(`tests/integration/test_v2_e2e_synthetic_change.py`)+ P10.0 必过 archive gate;P12.2 重定义为辅助实战 dogfood

**Inline writeback 净增量**:
- design.md 8 → 9 D-decision(加 D-W4-IntegrationGate)+ R3 升级 + R7 部分缓解 + 加 R8 advisory 透明性
- spec.md 4 ADDED → 5 ADDED(加 v2 e2e integration test fixture Requirement)+ 3 MODIFIED(parallel + worktree + round_2 continuity)字段更新
- tasks.md 12 phase → 13 phase(加 P5.5)+ P10 加 P10.0 必过 gate + P12.3 加 follow-on tracking
- 总工程量:原 estimate ~8h → 新 estimate ~15h(+88%)
- follow-on:1 个新 architectural change(`enhance-workflow-automation-ledger-binding`)tracked 在 P12.3
- evidence frontmatter v2 字段:5 → 7(加 `pre_dispatch_metadata` + `ledger_forgery_resistance` 2 advisory 标注字段)
