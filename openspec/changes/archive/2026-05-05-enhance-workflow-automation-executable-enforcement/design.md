## Context

刚 ship 的 `enhance-workflow-automation-runtime-enforcement` change(2026-05-05 archived,见 `openspec/changes/archive/2026-05-05-enhance-workflow-automation-runtime-enforcement/`)在 Pre-P0 codex round 1 收 5 个 finding,其中 3 个 high(F1 Worktree preflight / F2 Parallel file disjoint / F3 Round 2 continuity)被显式 deferred 到本 follow-on,2 个 medium(F4 Skill root multi-source / F5 Protocol version migration)inline writeback。

3 个 deferred high 的共同根因:**markdown 命令模板 step + LLM 自报 frontmatter declaration + finish_gate audit 全链路 advisory not deterministic**。controller 跳过 markdown step 时 subagent 已修改;finish_gate 是 archive 时才扫,无法 abort dispatch;frontmatter 由同一 controller 写,可伪造。

本 change 用 **executable enforcement layer** 替代 markdown advisory:

- W1(F1)— `tools/forgeue_preflight_wrapper.py`:命令层在 dispatch 前调用 wrapper,wrapper 创建 / 验证 worktree + 写 machine-generated receipt JSON,命令模板**只能消费** receipt(LLM 不直接填 worktree_path)
- W2(F2)— `/forgeue:change-apply-parallel` 命令模板加 actual diff 收集步骤:主 session 在 dispatch 后 git diff --name-only 每个 worktree → cross-check disjoint,actual overlap 时自动降级 sequential
- W3(F3)— `tools/forgeue_dispatch_ledger.py`:命令层 wrapper 在每次 Task / SendMessage 调用前写 append-only JSONL ledger,LLM 不能 echo / Edit 写 ledger,finish_gate 比较 ledger vs evidence frontmatter 一致性

**Stakeholders**:
- ForgeUE user(msc)— 协议严格性最终受益方
- Claude controller(主 session)— 失去手写 worktree_path / agent_id 的"自由",但 emulation drift 不再误伤
- 弱 LLM controller / 跨会话 — wrapper 物证可重放,不依赖 controller context

## Goals / Non-Goals

**Goals:**

- G1(W1):新建 `tools/forgeue_preflight_wrapper.py`(stdlib only),命令层调用 wrapper 创建 worktree + 写 receipt JSON;`/forgeue:change-apply-{subagent,parallel}` 命令模板 Preflight Worktree section 升级为 wrapper invocation
- G2(W1):`forgeue_finish_gate.py::_check_worktree_path` fence 升级 — 校验 receipt 文件存在 + receipt path 与 evidence frontmatter `worktree_path` 一致;evidence frontmatter 加 `worktree_receipt_path` 字段(non-null when v2)
- G3(W2):`/forgeue:change-apply-parallel` 命令模板加可执行 file overlap 检测 — 主 session 自动收集每 implementer worktree 的 actual `git diff --name-only`,evidence frontmatter 加 `task_files_actual` 字段;actual overlap detected → 自动降级 sequential(无 user prompt)
- G4(W2):`forgeue_finish_gate.py` 加 `_check_file_overlap_actual` fence — `task_files_actual` 与 `task_files_disjoint` declaration 一致性 + actual disjoint 验证
- G5(W3):新建 `tools/forgeue_dispatch_ledger.py`(stdlib only),提供 `append <change> <agent_id> <round> <role> [task_subject_hash]` 子命令;命令模板包裹 Task / SendMessage 调用为 wrapper invocation
- G6(W3):`forgeue_finish_gate.py::_check_round_fix_continuity` fence 升级 — cross-check `<change>/dispatch_ledger.jsonl` 中真实 dispatch vs evidence frontmatter `subagent_continuity` 字段;ledger 缺失 → fail-closed
- G7(W3):evidence frontmatter 加 `dispatch_ledger_path` 字段(指向 `<change>/dispatch_ledger.jsonl`,non-null when v2)
- G8:加 `runtime_enforcement_protocol_version: v2` migration — v2 fence 仅对 v2+ evidence 强制;v1 evidence 沿 v1 fence;archived enhance-workflow-automation-runtime-enforcement evidence(v1)pass-through
- G9:`forgeue_finish_gate.py` 加 `_check_file_overlap_actual` + `_check_dispatch_ledger` 2 个新 fence(共 6 runtime fence)
- G10:11 处文档同步(沿 enhance-workflow-automation-runtime-enforcement P3 模式),加 ADR-012(W1+W2+W3 三 D 合记 ADR)

**Non-Goals:**

- 不改 `superpowers:using-git-worktrees` SKILL.md 自身(只在 wrapper 内部 invoke,沿 SKILL 协议)
- 不实现 task subject 内容相似度判定(NOT 语义匹配,只 hash 内容 reproducible 比对)
- 不强制 ledger 加密 / signing(stdlib 范围内 append-only file,文件系统层防篡改;LLM context 隔离即足够)
- 不接入 Hook system(不动 `~/.claude/settings.json` hook;wrapper 调用走命令模板 Bash step)
- 不改 v1 fence 行为(v1 evidence 完全 pass-through,沿 v1 advisory)
- 不本 change 自 dogfood W1(W1 ship 后下一个 change 才是真 dogfood;本 change 自身 evidence 仍走 v1 advisory worktree_path)

## Decisions

### D-W1-ReceiptSchema:Preflight wrapper 自创 worktree + receipt JSON 格式(F1 round 1 codex inline writeback)

**Statement**(round 1 F1 inline writeback 后):**`tools/forgeue_preflight_wrapper.py` 自己用 `git worktree` subprocess 创建 / 验证 isolated worktree(不依赖 Skill tool / 不依赖命令模板 controller),并校验 wrapper 调用时 cwd 实际位于 wrapper 管理的 worktree 内**;然后写 `<change>/preflight_receipts/<receipt_id>.json`。命令模板**只能消费** receipt path,不允许 LLM 直接写 evidence frontmatter `worktree_path`。

**Wrapper 自创 worktree 算法**(stdlib + git CLI subprocess):
1. 计算 target worktree path:`<repo_root>/.worktrees/<change-id>/`
2. 跑 `git worktree list --porcelain` 解析:
   - 若 target path 在 list 中且 prunable=false + branch 与 `<change-id>` 关联 + clean tree(无 dirty file 经 `git status --porcelain` 校验)→ **reuse**(`is_isolated_worktree: true` + `worktree_action: reused`)
   - 若 target path 在 list 中但 dirty → fail-closed exit 6(`worktree_action: rejected_dirty`)
   - 若 target path 不在 list 中 → 跑 `git worktree add <target> -b <change-id>` 创建(`worktree_action: created`)
3. **强制 cwd 校验**:wrapper 比较 `os.path.realpath(os.getcwd())` 与 worktree path 的 realpath:
   - 一致 → continue
   - 不一致 → fail-closed exit 6(`worktree_action: rejected_wrong_cwd`)+ stderr 提示 "wrapper 必须在 isolated worktree 内调用"
4. 生成 receipt(见下 schema)

**Receipt JSON 字段**(13 字段,F1 inline writeback 加 2 新字段:`is_isolated_worktree` + `worktree_action`):

```json
{
  "receipt_id": "preflight-<change>-<iso8601>-<short_random>",
  "change_id": "enhance-workflow-automation-executable-enforcement",
  "protocol_version": "v2",
  "worktree_path": "D:/ClaudeProject/ForgeUE_claude/.worktrees/<change-id>/",
  "is_isolated_worktree": true,
  "worktree_action": "created",
  "base_sha": "0aa4ed0...",
  "base_branch": "dev",
  "cwd_at_invocation": "D:/ClaudeProject/ForgeUE_claude/.worktrees/<change-id>/",
  "skill_cascade_check": {
    "skill_invoked": "superpowers:using-git-worktrees",
    "exit_code": 0,
    "checked_at": "2026-05-05T12:34:56+08:00"
  },
  "created_at": "2026-05-05T12:34:56+08:00",
  "wrapper_version": "1.1"
}
```

`worktree_action` enum:`created` / `reused` / `rejected_dirty` / `rejected_wrong_cwd`(后两个出现时 wrapper 直接 exit 6,不写 receipt;字段保留是为 audit 失败原因可追溯)。

`is_isolated_worktree: true` 是 finish_gate v2 fence `_check_worktree_path` 必须 assert 的字段(false 或缺失 → fence exit 非 0)。

**LLM-readable 字段约定**(命令模板可在 evidence frontmatter 引用):
- `worktree_path`:LLM 直接 copy 到 evidence frontmatter `worktree_path`(finish_gate 比较 receipt vs evidence 字符串一致)
- `receipt_id`:LLM 写到 evidence frontmatter `worktree_receipt_path`(相对 `<change>/` 的 path,如 `preflight_receipts/preflight-<...>.json`)
- 其他 11 字段是 finish_gate 内部用,LLM 不必读取

**F1 round 1 codex finding 关闭**:codex F1 揭示 "wrapper 不直接 invoke Skill tool" 的 round 1 设计漏洞 — controller 跳过命令模板 worktree step 时 wrapper 仅校验当前 git 状态,无法证明 cwd 在 isolated worktree。**inline writeback** 后 wrapper 自管 worktree(创建 / 校验 / 强制 cwd in worktree),不再依赖 controller invoke Skill tool。F1 闭环。

**Why**:
- 字段最小化(LLM 能复制的只有 2 个),减少手写错误
- protocol_version + wrapper_version 自描述,后续协议升级有版本号 anchor
- skill_cascade_check 嵌入 receipt — wrapper 内部已经跑过 cascade,evidence 不必重复扫描
- **wrapper 自管 worktree**(F1 round 1 inline writeback)— 不依赖 controller 自觉度,确保 receipt 物证只在真实 isolated worktree 中产生

**Alternatives considered**:
- (a) Bare path 字符串 receipt(无 JSON 结构)— 拒绝,无版本 / 无 cascade 嵌入,不可扩展
- (b) 嵌套深 schema(per-task-id receipt)— 拒绝,本 change 一个 receipt 对应一次 dispatch session,不需要细粒度
- (c) 顶层 flat JSON + 2 LLM 字段 + protocol/wrapper version — **选用**
- (d) wrapper 仅 advisory(round 1 原设计)— **F1 round 1 codex inline writeback 后拒绝**;改为 wrapper 自管 worktree(deterministic enforcement)

**Tradeoff**:
- (+)LLM 复制路径只有 2 个字段,误填风险低
- (+)receipt 自描述含 base_sha,事后 audit 可重放
- (+)wrapper 自管 worktree → controller 跳 markdown step 也无法绕过(F1 关闭)
- (-)evidence frontmatter 与 receipt 双写(LLM 复制到 frontmatter + receipt 文件存在),fence 双校验冗余但兜底强
- (-)wrapper 调用必须在 wrapper 创建的 worktree 内(用户 / controller 在 main repo 调用 wrapper 时 wrapper 第一次跑会跳到错误 cwd 检测;mitigation:wrapper 第一次跑时检测 cwd 是 main repo + target worktree 不存在 → 创建 worktree 后 stdout 输出 "请 cd 到 <worktree path> 重新调用 wrapper" + exit 6)
- (-)`.worktrees/<change-id>/` 目录占用 disk(per change 一份;mitigation:archive 时删除 worktree)

### D-W2-OverlapDetection:Parallel actual file overlap 检测时机 + 降级路径(F4 round 1 codex inline writeback)

**Statement**(round 1 F4 inline writeback 后):`/forgeue:change-apply-parallel` 命令模板在 dispatch 后**等所有 implementer subagent commit 完成**(Skill tool 阻塞返回),然后主 session 跑 deterministic 步骤:

0. **Precondition — implementer worktree clean fail-closed 检查**(F4 inline writeback 加):对每个 implementer worktree 跑 `git status --porcelain=v1`;若返回非空(任何 dirty / untracked / staged 但 uncommitted file)→ 命令 abort + Bash 写 `<change>/parallel_abort_dirty_<iso>.log` 记录 dirty implementer agent_id + dirty files + 自动降级 sequential(沿 step 3 同款降级路径)
1. 对每个 implementer subagent,在其 clean worktree 内**收集 actual changed-files set**(F4 inline writeback 改 — 原 `git diff --name-only <base_sha>..HEAD` 漏 untracked file):
   - 跑 `git status --porcelain=v1 -z`(收集 untracked / staged / dirty 全套;但 step 0 已强制 clean,理论只剩 staged → committed 的 file)— 实际由 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集组成(包含 committed diff 与 untracked files;-z 防文件名含空格 / 特殊字符)
   - 解析 NUL-separated 输出为 file path set
2. 主 session 计算所有 implementer set intersection(任意两个 implementer 之间)
3. 若 intersection 非空 → **abort + 自动降级**:
   - 命令模板 Bash 写 `<change>/parallel_abort_<iso>.log` 记录 overlap detected files + 涉及 implementer agent_id
   - 主 session 自动 invoke `/forgeue:change-apply-subagent` sequential(用户无 prompt;沿 user feedback `feedback_no_continue_prompts_between_phases.md`)
   - evidence frontmatter `task_independence_assertion: false` + `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`(或 `dirty_implementer_worktree` 在 step 0 触发时)
4. 若 intersection 空 → evidence frontmatter `task_files_actual` 字段写各 implementer 的 changed-files set + `task_independence_assertion: true`

**F4 round 1 codex finding 关闭**:codex F4 揭示 spec.md 写 SHALL `git diff --name-only` 但 design.md OQ-2 自承漏 untracked file;**inline writeback** 改:
- spec.md / design.md 改 SHALL `git status --porcelain=v1 -z` + committed diff 合集(覆盖 untracked)
- step 0 加 implementer worktree clean precondition fail-closed(implementer 漏 add 文件 → dirty → 降级 sequential)
- OQ-2 标 `resolved-inline`

**Why**:
- "actual diff" 优于 "declaration":controller 声明可错(import / shared fixture 不在直接 file scope),actual diff 是物证
- 降级 sequential 而非 abort:user feedback 明确不要 prompt;sequential 是已 ship 的可靠路径
- declaration vs actual 双写到 frontmatter:fence 既可校验"controller 是否诚实"(declaration 与 actual 不一致 → audit fail)又可校验"actual disjoint 是否真成立"

**Alternatives considered**:
- (a) Dispatch 前 dry-run static analysis 推断 file scope — 拒绝,任何 controller emulation drift 都会让 static 失效;diff 是 ground truth
- (b) Overlap detected → abort + ask user 选择 retry / sequential / cancel — 拒绝,违反 `feedback_no_continue_prompts_between_phases.md`(连续推不要每轮问)
- (c) Abort + 自动降级 sequential — **选用**;降级路径是已 ship 的 default,user 自动获得正确结果

**Tradeoff**:
- (+)伪 disjoint 在 dispatch 后立即被 catch(implementer 已花 token,但 review / merge 之前 catch — 损失 implementer wall-clock 不损失质量)
- (+)降级路径不打断 user(沿 feedback)
- (-)implementer 无谓 work(降级后 sequential 实施会 redo;mitigation:degraded_at evidence 记录 overlap files,sequential 实施时可参考 implementer 的 diff 作为 hint)
- (-)主 session Bash + git 调用增加 ~5-10 sec wall-clock

### D-W3:Dispatch ledger umbrella(W3 design decisions group)

> **Umbrella anchor**:`D-W3` 作为 W3 dispatch ledger 设计决策的总称,实际细分为 3 个子决策:
> - `D-W3-LedgerFormat`(JSONL append-only + wrapper-only write 文件协议)
> - `D-W3-WrapperImpl`(命令模板 wrapper invoke 模式 — F2 round 1 inline writeback 后改 post-dispatch capture)
> - `D-DispatchWrapperBoundary`(LLM 不能直接写 receipt / ledger 的实施边界 — F3 round 1 inline writeback 后加 advisory 标注)
>
> codex round 1 finding F2 / F3 使用 `D-W3` shorthand 时指向以上 umbrella(具体 finding 见 `review/codex_design_review.md`)。

### D-W3-LedgerFormat:Dispatch ledger JSONL append-only + wrapper-only write

**Statement**:每个 active change 在 `<change>/dispatch_ledger.jsonl`(append-only)记录每次 Task / SendMessage 调用,JSONL 一行一记录:

```json
{"agent_id":"ad79e93a40414763e","round":1,"role":"implementer","task_subject_hash":"sha256:abc...","dispatched_at":"2026-05-05T12:35:00+08:00","parent_session_id":"<controller-session-uuid-or-null>","wrapper_version":"1.0"}
{"agent_id":"ad20e8a4019787c51","round":1,"role":"spec_reviewer","task_subject_hash":"sha256:def...","dispatched_at":"2026-05-05T12:36:00+08:00","parent_session_id":"<controller-session-uuid-or-null>","wrapper_version":"1.0"}
{"agent_id":"ad79e93a40414763e","round":2,"role":"implementer_round_2_fix","task_subject_hash":"sha256:ghi...","dispatched_at":"2026-05-05T12:45:00+08:00","parent_session_id":"<controller-session-uuid-or-null>","wrapper_version":"1.0"}
```

**Wrapper 调用约定**(命令模板内):
```bash
python tools/forgeue_dispatch_ledger.py append \
  --change <change-id> \
  --agent-id "$IMPLEMENTER_AGENT_ID" \
  --round 1 \
  --role implementer \
  --task-subject-hash "$(echo -n "$TASK_SUBJECT" | sha256sum | cut -d' ' -f1)"
```

`agent_id` 来自:
- 新 dispatch:Skill tool 派 Agent 后返回的真实 ID(命令模板从 Skill tool 输出 capture)
- Round 2 fix:`SendMessage(to=<previous_id>)` 时复用同一 ID(wrapper 校验同 ID 已在 ledger 出现过)

**LLM-isolation 防篡改**:
- 命令模板里 ledger path 走 wrapper invocation,**不**作为 file path 暴露给 LLM 上下文(命令模板 Read tool 不读 ledger;Write/Edit tool 不指 ledger path)
- LLM 若手写 echo / sed 试图改 ledger,wrapper 不参与,但 finish_gate 校验 ledger 行 timestamp 单调性 + wrapper_version 字段 + JSON well-formed → 手工伪造的行会被 catch(timestamp 倒流 / wrapper_version 缺失 / JSON 不合 schema)

**Why**:
- JSONL 比 markdown 更易 reproducible parse
- Append-only 物证天然防覆盖(每行独立记录,改 round 1 不能改 round 2)
- task_subject_hash 而非明文 → 既能比对又不暴露任务文本(避免 ledger 变成另一份 evidence)

**Alternatives considered**:
- (a) Markdown table — 拒绝,parse 易碎;append 时易破坏 table 格式
- (b) SQLite 数据库 — 拒绝,引入 binary file 不利 git diff;wrapper 复杂度高
- (c) JSONL append-only + wrapper-only write — **选用**

**Tradeoff**:
- (+)JSONL 简单 + git diff 友好 + stdlib 解析
- (+)Append-only 防 round 2 篡改 round 1
- (-)LLM 仍能 echo > 强制 overwrite 整个文件(mitigation:fence 校验 timestamp 单调性 + wrapper_version + 行数与 evidence subagent_continuity 字段对账)
- (-)wrapper 调用增加 1 次 Python 启动(~100-200ms),每次 dispatch 1 次

### D-DispatchWrapperBoundary:LLM 不能直接写 receipt / ledger 的实施边界(F3 round 1 codex partial inline writeback + deferred)

**Statement**:命令模板对 LLM 暴露的 file path:
- **可读不可写**:`<change>/preflight_receipts/<receipt_id>.json`(LLM 复制 worktree_path / receipt_id 到 evidence frontmatter)
- **不读不写**:`<change>/dispatch_ledger.jsonl`(完全 wrapper 间接;LLM 上下文里只看到 wrapper 命令)

具体在命令模板 markdown 里:
- 不写 `Read(<change>/dispatch_ledger.jsonl)` 或类似 step
- 不写 `Write(<change>/preflight_receipts/...)` step,只 wrapper invoke
- evidence frontmatter `dispatch_ledger_path` 字段值是固定字符串 `dispatch_ledger.jsonl`(无变量),LLM 不需"读取后写入"

**finish_gate 防篡改 fence**:
- `_check_dispatch_ledger`:校验 ledger JSONL 每行 well-formed + timestamp 单调递增 + wrapper_version 字段存在 + 行数等于 evidence frontmatter `subagent_continuity` 中声明的 dispatch 数 + agent_id 命名格式 [a-f0-9]{17}+(Claude Code 自动生成 ID 格式)
- `_check_worktree_path` v2:校验 receipt 文件存在 + receipt JSON well-formed + receipt `worktree_path` == evidence frontmatter `worktree_path` + receipt `is_isolated_worktree: true`

**F3 round 1 codex finding partial close**:
- **Inline writeback**:F3 揭示 wrapper_version + timestamp + dispatch_ledger_path 都是 LLM 可观测 / 可写域 → 同一 controller 写出 monotonic ts + ver=1.0 + agent_id 命名格式即可通过 fence。**本 change scope 内 inline 接受这个 limitation**:evidence frontmatter 加 `ledger_forgery_resistance: advisory`(沿 v1 fence advisory 同等级,诚实标注 well-formed forge 不阻断);finish_gate 仅 catch crude forge(timestamp 倒流 / wrapper_version 缺失 / JSON 不合 schema / agent_id 格式不对)
- **Deferred**:真 cryptographic enforcement(wrapper 写 nonce/HMAC,key 在 LLM 不可见 env var 域;fence 校验 HMAC 一致性)留 follow-on `enhance-workflow-automation-ledger-binding`(同 F2 deferred 同 follow-on)

**evidence frontmatter `ledger_forgery_resistance: advisory` 标注**(F3 inline writeback 加):
- 字段值固定 `advisory`(本 change scope 内);follow-on `enhance-workflow-automation-ledger-binding` ship 后改为 `cryptographic`
- finish_gate v2 fence 不依赖此字段值判断 enforce 强度,仅 audit 用;但记录在 evidence 中诚实暴露当前 enforcement 等级

**Why**:
- LLM context isolation 是 W3 防伪造的第一层(`<change>/dispatch_ledger.jsonl` 不在命令模板 LLM 可见 file path 列表)
- fence 校验是第二层(crude forge 阻断 — timestamp 倒流 / wrapper_version 缺失 / JSON 不合 schema / agent_id 格式不对)
- well-formed forge 第三层留 cryptographic enforcement follow-on;**本 change scope 内 advisory 接受**(沿 v1 fence advisory 同等级)
- 完全 cryptographic signing(HMAC / GPG sign each ledger line)留 follow-on `enhance-workflow-automation-ledger-binding` 若实证不够

**Alternatives considered**:
- (a) GPG sign 每行 ledger — 本 change scope 内拒绝,**deferred to follow-on**;user 没有 GPG infra,但 follow-on 可用 wrapper-managed env var key + HMAC
- (b) ledger path 暴露给 LLM 但靠 fence 反欺诈 — 拒绝,LLM 看到 path 后会试图 explain / debug 它,context noise
- (c) Wrapper-only write + LLM context isolation + fence 双层校验 + advisory 标注 — **本 change scope 选用**(F3 inline writeback)

### D-DegradationPath:W2 overlap detected 自动降级 sequential

**Statement**:见 D-W2-OverlapDetection step 3。

**关键**:降级**不需要** user 介入,因为:
- sequential 是已 ship 的稳定路径(`/forgeue:change-apply-subagent`)
- user feedback 明确连续推 phase 不要 prompt
- evidence frontmatter `degraded_to` + `degradation_reason` 字段事后可 audit
- finish_gate `_check_file_overlap_actual` fence 在 `degraded_to == change-apply-subagent` 时仍校验 sequential 路径自身的 4 类 evidence(implementer / spec_review / code_quality_review / final_review)完整性

**fence 行为**:
- evidence frontmatter `triggered_by_command: change-apply-parallel` + `degraded_to: change-apply-subagent` → fence 走 sequential 校验逻辑
- 无 `degraded_to` 字段 → 走 parallel 校验逻辑(校验 task_files_actual disjoint)

### D-W4-IntegrationGate:v2 e2e integration test fixture(F5 round 1 codex inline writeback)

**Statement**:本 change archive 前必须有一次 **v2 协议端到端实跑**,通过 synthetic active change fixture 模拟 v2 evidence 流;archive 阻断条件:`pytest -q tests/integration/test_v2_e2e_synthetic_change.py` 不全绿。

**fixture 实施**(`tests/integration/test_v2_e2e_synthetic_change.py`,新建):
- 用 `tmp_path` 创建 synthetic active change 目录(`openspec/changes/test-v2-synthetic/`)
- 跑 `tools/forgeue_preflight_wrapper.py` 创建 worktree + 写 receipt(W1 全链路)
- 模拟 Skill(Task) 返回(mock 真实 agent_id 格式)+ 跑 `tools/forgeue_dispatch_ledger.py append`(W3 ledger 全链路)
- 跑 `tools/forgeue_dispatch_ledger.py verify`(W3 ledger verify)
- 模拟 parallel 场景:2 个 implementer 各自 commit + 跑 W2 actual diff(`git status --porcelain=v1 -z` + committed diff 合集)
- 跑 W2 overlap 负例:模拟 2 implementer 修改同一文件 → 自动降级 sequential
- 跑 `tools/forgeue_finish_gate.py` 全 6 fence(skill_cascade / round_fix_continuity v2 / task_granularity / worktree_path v2 / file_overlap_actual / dispatch_ledger)on synthetic v2 evidence

**fixture pass 条件**:
- 全部 W1/W2/W3/finish_gate 步骤 OK + overlap 负例正确触发降级
- v2 fence 全部对 synthetic v2 evidence enforce(不 pass-through)
- v1 fence pass-through synthetic legacy evidence(回归回退兼容)

**F5 round 1 codex finding 关闭**:codex F5 揭示原 P12.2 在 "后置(可选)" 段,archive 前 v2 协议无端到端实跑 → 坏 v2 协议会 ship。**inline writeback** 加 D-W4-IntegrationGate fixture(本 change scope 内必过 gate),archive 前一次 v2 全链路实跑。

**Why**:
- 接受 codex 主张:advisory dogfood gap 不能完全靠下一 change 闭环,本 change scope 内必须有自证物
- synthetic fixture 比真 dogfood 成本低(tmp_path + mock + stdlib 编排,~200 LOC vs 一个完整 follow-on change)
- D-DogfoodGap 沿用("本 change 自身实施 evidence 仍 v1");D-W4-IntegrationGate 是 v2 自证(fixture 跑 v2 evidence;不影响本 change 自身 evidence v1 路径)

**Alternatives considered**:
- (a) 跳过 fixture,沿 D-DogfoodGap 让下一 change 真 dogfood(round 1 原方案)— **F5 round 1 codex inline writeback 后拒绝**;archive 前没自证物
- (b) 创建 minimal real follow-on change 跑 v2(更接近真实)— 拒绝,工程量大 + 引入 cross-change 依赖
- (c) synthetic fixture 跑全链路 v2(W1 + W2 + W3 + finish_gate + overlap 负例)— **F5 inline writeback 选用**

**Tradeoff**:
- (+)archive 前 v2 协议有端到端实跑物证(消除 F5 风险)
- (+)fixture 是回归测试,后续 v2 协议演进也有锚点
- (-)增加 ~4h 工程量(fixture + mock + 6 fence on synthetic + overlap 负例)
- (-)fixture 是 mock,与真 dogfood 仍有 gap(mock 真实 Skill tool 返回 vs 真实 Skill tool 返回);P12.2 仍保留作辅助实战 dogfood

### D-FrontmatterSchemaExtension:protocol_version v2 + 4 new fields

**Statement**(round 1 F2 + F3 inline writeback 后):v2 evidence frontmatter 在 v1 12-key 基础上加 7 字段(原 5 + 2 新 advisory 标注字段):

```yaml
runtime_enforcement_protocol_version: v2
worktree_receipt_path: preflight_receipts/preflight-<change>-<iso>-<short>.json  # W1
dispatch_ledger_path: dispatch_ledger.jsonl  # W3 (固定值,LLM 不需变量)
task_files_actual:  # W2 (parallel only;sequential evidence 留空)
  - implementer_agent_id: ad79e93a40414763e
    files:
      - tools/forgeue_preflight_wrapper.py
      - tests/unit/test_preflight_wrapper.py
  - implementer_agent_id: ad20e8a4019787c51
    files:
      - tools/forgeue_dispatch_ledger.py
      - tests/unit/test_dispatch_ledger.py
degraded_to: null  # null 或 change-apply-subagent;非 null 时配 degradation_reason
degradation_reason: null  # null 或 actual_file_overlap_detected / dirty_implementer_worktree
pre_dispatch_metadata: advisory  # F2 inline writeback;advisory 标注 — agent_id 是 dispatch 后 capture,无 pre-dispatch 物证
ledger_forgery_resistance: advisory  # F3 inline writeback;advisory 标注 — fence 仅 catch crude forge,well-formed forge 不阻断;follow-on `enhance-workflow-automation-ledger-binding` ship 后改为 cryptographic
```

**v1 vs v2 兼容**:
- v1 fence(skill_cascade / round_fix_continuity / task_granularity)对 v1 / v2 evidence **都生效**(无回归 break)
- v2 fence(file_overlap_actual / dispatch_ledger / worktree_path v2 加严)**仅对 v2 evidence 生效**(`runtime_enforcement_protocol_version != v2` 直接 pass-through)
- archived enhance-workflow-automation-runtime-enforcement evidence(v1)在本 change ship 后 replay finish_gate 不被 v2 fence 误杀

**Why**:沿 v1 ship 时同款 protocol_version migration 模式(D-ProtocolVersionMigration);v1 → v2 单调递增,新 fence 只严不松。

### D-DogfoodGap:本 change 自身仍走 v1 advisory(W1 wrapper 还没 ship)

**Statement**:本 change 实施时 W1 wrapper 还没 ship → 本 change evidence frontmatter `worktree_path` 仍走 LLM 自报(v1 advisory);**不**含 `worktree_receipt_path` / `dispatch_ledger_path` / `task_files_actual` 字段(这些是 v2 evidence 才有);`runtime_enforcement_protocol_version: v1`(本 change 自身 evidence 仍是 v1)。

**Why**:bootstrap 期不可能用未 ship 的 wrapper(没法跑)。本 change 第一个真正 dogfood W1/W2/W3 的是**下一个**change(任意 follow-on,无论是 webm / handoff-persistence 还是 audio-metadata)。

**Migration timing**:
- 本 change archive 后的下一个 active change(任何 change)`/forgeue:change-apply-subagent` 调用时,命令模板自动跑 W1 wrapper → evidence frontmatter 加 v2 字段
- 下一个 change 实施时若用 `/forgeue:change-apply-parallel` 也自动跑 W2 actual diff
- finish_gate 在下一个 change archive 时第一次实际 enforce v2 fence

**Risk acceptance**:本 change 自身 worktree 漏 preflight 风险与 advisory ship 时同 risk 等级(R6 在 v1 ship 时已被 user accept);本 change ship 后立即 W2 dogfood 闭环

### D-W3-WrapperImpl:dispatch ledger wrapper post-dispatch capture 模式(F2 round 1 codex partial inline writeback + deferred)

**Statement**(round 1 F2 inline writeback 后):`/forgeue:change-apply-{subagent,parallel}` 命令模板在每个 Skill(Task) / SendMessage 调用**之后**(不是之前)嵌入 Bash step 调用 `forgeue_dispatch_ledger.py append`,从 Skill tool 返回 capture 真实 agent_id 然后 append ledger:

命令模板伪代码(markdown step):
```
4. **Dispatch implementer subagent**:
   a. Skill(Task): dispatch implementer subagent → capture return,parse 真实 agent_id
   b. Bash: python tools/forgeue_dispatch_ledger.py append \
        --change <change-id> --agent-id <真实_agent_id_from_Skill_return> --round 1 --role implementer \
        --task-subject-hash $(echo -n "$TASK" | sha256sum | cut -d' ' -f1)
   c. continue
```

**关键**(post-dispatch capture 模式):
- agent_id 在 Skill(Task) **返回后** capture(Claude Code Skill tool 返回 metadata 含真实 agent_id);ledger 写真实 ID,与原 round 1 设计的 uuid_v4 synthetic ID 不同
- ledger append 在 dispatch **之后**;subagent 已开始跑(若 subagent 失败,ledger 不会记录;evidence 中声明的 agent_id 必须等于 ledger 行数,而非 ⊇)
- task_subject_hash 在 dispatch 前生成(任务文本 hash,与 agent_id 无关);防 ledger 上下文泄漏(只 hash 不存明文)
- parent_session_id 字段 wrapper 自动从 env var(`CLAUDE_SESSION_ID` / 类似)读取,留空时为 null

**evidence frontmatter `pre_dispatch_metadata: advisory` 标注**(F2 inline writeback 加):
- 沿 v1 advisory 同款限制 — `agent_id` 是 dispatch 后 capture,不是 wrapper 拦截 dispatch 写入,**无法证明 dispatch 真实发生过**(LLM 仍可假装 dispatch 后写假 agent_id;mitigation:Skill tool 真实 agent_id 由 Claude Code 自动生成,LLM 难以预测正确格式 + finish_gate 校验 agent_id 命名格式 [a-f0-9]{17}+)
- frontmatter 加 `pre_dispatch_metadata: advisory`(诚实标注本字段非 deterministic 物证)

**F2 round 1 codex finding partial close**:
- (a) **Inline closed**:design.md round 1 设计(pre-dispatch uuid_v4 synthetic agent_id)被 codex 揭穿是 LLM 可写域 + 与真实 subagent 无关;**inline writeback** 改 post-dispatch capture 真实 agent_id;evidence 标注 `pre_dispatch_metadata: advisory`
- (b) **Deferred**:真 wrapper-bound dispatch(wrapper 拦截 Skill(Task) 调用 + 写 ledger 前拒绝 dispatch 直到 ledger 写入)需要 Hook system 或 Claude Code Skill tool 协议扩展;留 follow-on `enhance-workflow-automation-ledger-binding`

**Why**(post-dispatch 模式):
- 命令模板里的 Bash step 是 "wrapper 在命令层" 的实施手法,不引入新 hook 系统(不动 settings.json),也不依赖 Skill tool 自己写 ledger(Skill tool 没有这种 hook)
- post-dispatch 模式损失 pre-dispatch 物证但 capture 真实 agent_id;**advisory** 标注诚实接受这个 limitation,与 v1 fence advisory 同等级
- 真 deterministic enforcement 留 follow-on(需 Hook / Skill 扩展)

**Alternatives considered**:
- (a) 用 ~/.claude/settings.json `PreToolUse` hook 拦截 Task / SendMessage 自动写 ledger — **本 change scope 内拒绝,deferred to follow-on `enhance-workflow-automation-ledger-binding`**;跨 project 污染 + 不易测试 + 调试困难,但若 user 接受 ~/.claude/settings.json 改动可作真 enforcement 路径
- (b) 命令模板 Bash step pre-dispatch wrapper invoke — round 1 原设计;**F2 round 1 codex inline writeback 后拒绝**(wrapper 写 synthetic ID 与真实 subagent 无关)
- (c) Wrapper 完全替代 Skill(Task)调用(wrapper 内部 spawn agent)— 拒绝,Skill tool 是 Claude Code 唯一的 agent dispatch path,绕过会失去 stream / monitor / cost tracking
- (d) **post-dispatch capture 真实 agent_id**(F2 inline writeback)— **本 change scope 选用**;接受 advisory limitation

## Risks / Trade-offs

- **R1 W1 wrapper 路径漂移** → wrapper 创建 worktree 后路径与 receipt 不一致(如 worktree 创建在 `.worktrees/` 但 receipt 写绝对路径)。**Mitigation**:wrapper 内部 normalize 路径为绝对 + 校验 worktree 真实存在;fence `_check_worktree_path` 比较 normalize 后字符串

- **R2 W2 overlap 漏检** → `git diff --name-only` 不覆盖 untracked file(implementer 写新文件未 git add 时 diff 看不到)。**Mitigation**:命令模板 dispatch 后强制 `git add -A` 在 implementer worktree(implementer subagent 提交前必 add;若 implementer 没 commit,worktree dirty 已是异常状态,主 session 直接 abort);diff 用 `git status --short` 替代 / 或 `git diff --name-only HEAD` 包含 staged

- **R3 W3 ledger LLM well-formed forge**(F3 round 1 codex inline writeback 后升级)→ LLM 写出 monotonic timestamp + wrapper_version: "1.0" + agent_id 命名格式 [a-f0-9]{17}+ 即可绕过 fence。**Mitigation 沿 v1 advisory limitation**:本 change scope 内接受 advisory(`ledger_forgery_resistance: advisory` evidence 字段诚实标注);fence 仅 catch crude forge(timestamp 倒流 / wrapper_version 缺失 / JSON 不合 schema / agent_id 格式不对);**真 deterministic enforcement**(wrapper-managed env var key + HMAC,key 在 LLM 不可见域)留 follow-on `enhance-workflow-automation-ledger-binding`

- **R4 v1/v2 fence 矩阵复杂** → 同一 finish_gate 跑过 6 fence 时既要支持 v1 advisory 又要支持 v2 strict,代码分支多。**Mitigation**:fence 入口统一 dispatch on `runtime_enforcement_protocol_version`(v1 → 走 v1 logic / v2 → 走 v2 logic / 缺字段 → 走 v0 legacy pass-through);测试矩阵覆盖 3 种版本各 2 fence × 2 路径

- **R5 W2 自动降级损失 implementer wall-clock** → 4 个 implementer 并行已跑完,降级 sequential 又跑 4 遍。**Mitigation**:接受 — overlap 是 controller 误判,降级是修正;evidence 记录 overlap files 后 sequential 实施时可参考 implementer 的 diff 作为提示(non-binding)

- **R6 wrapper Python 启动开销 累积** → 每 dispatch 1 次 wrapper Python = ~150-200ms,N 个 implementer 累积 ~600-800ms。**Mitigation**:接受 — 相对 implementer 自身 wall-clock(典型 1-5 min)忽略不计

- **R7 自身 dogfood gap**(F5 round 1 codex inline writeback 后部分缓解)→ 本 change 自身不能 dogfood W1(W1 还没 ship);用户可能错觉"协议 ship 了但本 change 没用"。**Mitigation**:(a) proposal.md / design.md 显式标注 D-DogfoodGap;(b) **D-W4-IntegrationGate fixture**(`tests/integration/test_v2_e2e_synthetic_change.py`)在 archive 前必跑全链路 v2(W1 + W2 + W3 + finish_gate + overlap 负例);(c) 本 change archive 后第一个 follow-on change 是真实战 dogfood

- **R8 advisory limitation 标注透明性**(F2 + F3 round 1 codex inline writeback 后新增)→ 本 change scope 内 W3 ledger 的 pre-dispatch 物证 + well-formed forge resistance 是 advisory,不是 deterministic;若用户错觉 v2 协议是完全 deterministic 反而更危险。**Mitigation**:(a) evidence frontmatter 显式 `pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory` 字段诚实标注;(b) docs sync 时同步加同款 limitation 段;(c) follow-on `enhance-workflow-automation-ledger-binding` tracking 项明确触发条件(实测 advisory 不足挡 controller drift 时启动)

## Migration Plan

**Phase 1 - propose / design / specs / tasks 落 contract**(本次 propose stage)

**Phase 2 - 实装**(apply stage,沿 sequential dispatch — W1 wrapper 还没 ship,沿 v1 advisory):
- P0:`tools/forgeue_preflight_wrapper.py` 新建 + `tests/unit/test_preflight_wrapper.py`(receipt schema / worktree create / cascade check 内嵌)
- P1:`tools/forgeue_dispatch_ledger.py` 新建 + `tests/unit/test_dispatch_ledger.py`(append / timestamp 单调 / wrapper_version 校验)
- P2:`forgeue_finish_gate.py` 升级 — `_check_worktree_path` v2 + `_check_round_fix_continuity` v2 + 新 `_check_file_overlap_actual` + 新 `_check_dispatch_ledger`;fence 入口加 protocol_version dispatch
- P3:`tests/unit/test_forgeue_finish_gate.py` 加 v2 fence 守门测试 + v1/v2 protocol matrix
- P4:`/forgeue:change-apply-subagent` + `/forgeue:change-apply-parallel` 命令模板加 wrapper invocation step + ledger append step
- P5:11 处文档同步(沿 enhance-workflow-automation-runtime-enforcement P3 模式)+ 加 ADR-012(W1+W2+W3 合记)
- P6:Pre-P0 codex round 1 review(本 change 自身被 challenge 一轮)
- P7:Verify Level 0/1/2 + codex review hop
- P8:Doc Sync Gate
- P9:Finish Gate(本 change 自身 evidence 仍是 v1,fence 全 pass-through;但 v2 fence 自身的单元测试必须绿)

**Phase 3 - dogfood 闭环**(下一个 change 起):
- 下一个任意 active change `/forgeue:change-apply-subagent` 调用 → 命令模板自动跑 W1 wrapper → evidence v2
- 该 change archive 时 finish_gate 第一次实际 enforce v2 fence(receipt cross-check + ledger cross-check)

**Rollback**:每 phase 独立 commit,任意 phase 失败 `git revert <commit>`;archive 后 `git revert` archive commit + `git mv archive/<id> changes/<id>` 恢复 active

## Open Questions

**OQ-1**:W1 wrapper 在 worktree 已存在时是 reuse 还是 fail-closed?
- 倾向:**reuse if base_sha 一致 + clean tree**(同 change 多 phase 复用 worktree 节省创建开销);否则 fail-closed
- 留 codex round 1 挑战

**OQ-2**(**resolved-inline,F4 round 1 codex finding 后**):W2 actual diff 收集是否包含 untracked file?
- **决议**:**包含**;改 SHALL `git status --porcelain=v1 -z` + committed diff 合集(实际由 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集组成);加 step 0 implementer worktree clean precondition fail-closed(沿 D-W2-OverlapDetection step 0)
- 沿 spec.md "Parallel dispatch actual file overlap detection" Requirement(round 1 inline writeback 后)+ tasks.md P3.3 同步

**OQ-3**:W3 ledger 跨 change 是否共享(`<repo>/dispatch_ledger.jsonl`)还是 per-change(`<change>/dispatch_ledger.jsonl`)?
- 倾向:**per-change**(沿 design statement;隔离性强 + archive 一起带走 + 单 change finish_gate 不需扫全 repo)
- 留 codex round 1 挑战

**OQ-4**:Receipt 是否含 cleanup 信息(worktree remove timestamp)?
- 倾向:**否**(receipt 是 dispatch 时刻物证,cleanup 是 finish 时刻事件;如需 audit cleanup 加新文件 `<change>/preflight_receipts/<id>.cleanup.json` 由 finish_gate 写)
- 留 codex round 1 挑战
