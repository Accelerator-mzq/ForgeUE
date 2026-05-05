---
name: forgeue-subagent-discipline
description: ForgeUE controller-side subagent dispatch 纪律 — superpowers:subagent-driven-development 之上 ForgeUE 自家 40% 经验补丁(model 矩阵 / cwd 严格 verify / cross-verify / cherry-pick recovery / inline fix vs round 2 决策 / skip review boundary)。enhance-workflow-automation-executable-enforcement P0-P3 实证沉淀。
license: MIT
compatibility: Requires Claude Code Agent tool + python -m pytest;沿 superpowers:subagent-driven-development(generic process scaffold)+ ForgeUE backbone forgeue-integrated-change-workflow
metadata:
  author: forgeue
  version: "1.0"
  derived_from_phases: enhance-workflow-automation-executable-enforcement P0/P1/P2/P3 实证
---

ForgeUE controller-side subagent dispatch 纪律 skill。superpowers:subagent-driven-development 提供 60% generic scaffold(per-task 3-stage process + loose 3-tier model selection + generic prompt templates),本 skill 补 40% scenario-specific judgment(实证从 enhance-workflow-automation-executable-enforcement P0/P1/P2/P3 沉淀)。

**何时启用**:任何 `/forgeue:change-apply-subagent` 或 `/forgeue:change-apply-parallel` 调用 → controller 主 session 在 dispatch Agent tool 之前 + 收 return 之后 + commit 之前 — 全流程参考本 skill 决策。

**真源 Skill**:`superpowers:subagent-driven-development`(per-task 3-stage 协议骨架 — 不复制不引用 prompt 模板,沿其内部协议)

## §1 Phase × Model 矩阵(controller 选 model 决策表)

每次 dispatch Agent tool 时**显式传 `model:` 参数**(不传 → inherit 父 session model;P0 教训 → 全部默认继承 Opus 4.7 1M context $5.90/phase)。

### implementer subagent

| 任务特征 | model | 实证 |
|---|---|---|
| Plan 含完整代码样例 + 1-3 stdlib 文件 + well-known pattern | **Haiku 4.5** | P1 W3 ledger 150 LOC + 12 fence ✅($0.14) |
| Markdown lint / 模板修改 / 跨 file mechanical edit | **Haiku 4.5** | P3 命令模板 + 8 fence ✅($0.22;**附加监控**:见 §3) |
| Multi-file integration(改既有 module + cross-fence wiring + 多 fence test) | **Sonnet 4.6** | P2 finish_gate v2 +367 LOC + 16 fence ✅($0.83) |
| Architecture / cross-subsystem refactor / new ABC / new ADR drafting | **Opus 4.7** | (本 change 实施未触发 — 留 architectural change 用) |

**Haiku 适用边界**:Plan 必须含**完整代码样例 + 具体 fence 名 + 完整测试模板**。否则升级 Sonnet。Haiku 不能做"design judgment from spec"任务(implementer 凭 spec 自由设计代码)。

### spec_reviewer subagent

| 任务特征 | model | 实证 |
|---|---|---|
| Phase scope 内 mechanical 比对(spec scenario × implementation file) + controller 给 pre-verified pytest 数据 | **Haiku 4.5** | P3 spec compliant ✅($0.13;**附加监控**:见 §4) |
| Cross-phase scope verification + needs phase decomposition judgment | **Sonnet 4.6** | (P1 Haiku scope-bleed 教训:跨 phase Requirement 的 spec → 升级 Sonnet) |

**Haiku spec_reviewer 必须严格 prompt**(沿 §4 — 否则 P1 + P2 教训复发:scope-bleed / 幻觉 URL / 错测试 count)。

### code_quality_reviewer subagent

| 任务特征 | model | 实证 |
|---|---|---|
| **任何 code-changing phase** | **Sonnet 4.6**(**不可省**) | P0 + P1 + P2 + P3 都跑 Sonnet code_quality;P3 抓 2 实质 bug(f-string + IMPL_FILES_JSON 序列化)Haiku implementer + Haiku spec_reviewer 都漏 |
| Architecture-level review(整 change 综合) | **Sonnet 4.6 or Opus 4.7** | final_reviewer at end of all phases |
| Markdown-only edit phase(P4 SKILL.md sync 类) | **可 skip subagent reviewer**(沿 §6) | controller 自己 verify pytest + 跑 commit |

**为什么 Sonnet 不可省**:Haiku implementer 留下的 bug(P3 实证 — f-string assert message + IMPL_FILES_JSON 序列化缺)只能靠 Sonnet judgment 抓。Haiku reviewer 看不到 runtime correctness 问题(只看静态字符串匹配)。

### final_reviewer(全 phase 完成后)

| 任务特征 | model |
|---|---|
| 整 change 综合 review(所有 phase 累积 implementation + evidence) | **Sonnet 4.6** |
| Stakes 高(release-critical / contract-rewriting change) | **Opus 4.7** |

## §2 STRICT cwd verify(防 worktree-scope leak)

**每次 implementer dispatch prompt 必含**:

```
## Working Directory(STRICT — verify before any work)

```bash
cd D:\ClaudeProject\ForgeUE_claude\.claude\worktrees\<change-id>
pwd  # MUST show .../.claude/worktrees/<change-id>
git branch --show-current  # MUST be worktree-<change-id>
git rev-parse HEAD  # MUST be <expected SHA>
```

If `pwd` 不显示 worktree path → **STOP report NEEDS_CONTEXT;不要在 main repo / dev branch 工作**。
```

**实证**:P3 implementer(Haiku)没遵循,落 dev branch → controller `git cherry-pick` 救援(orig 0939229 → cherry ddf8f87)。Subagent 继承父 session cwd 但**不严格遵循**指令,必须显式 STRICT 段。

**spec_reviewer + code_quality_reviewer 同款加**:他们读文件需要在正确 worktree 才能看到正确内容。

## §3 Controller cross-verify(防 subagent self-hallucination)

**implementer self-report 不可信**。Controller MUST 独立验证:

| Subagent claim | Controller verify 命令 |
|---|---|
| "X fence pass" | `python -m pytest tests/unit/test_<X>.py -v` |
| "全 regress 全绿,N PASS" | `python -m pytest -q`(注:用 `python -m pytest` 而非 `pytest` — pytest binary 可能走错 Python interpreter,P2 教训) |
| "Commit SHA `X`" | `git show <X> --stat` |
| "Spec scenario 全覆盖" | `grep -c "<spec-required-string>" <file>` |
| "改了 X 不改 Y" | `git diff <base>..HEAD --stat` |

**实证**:
- P2 spec_reviewer(Haiku)报 "1539 + 1 skipped" 实际 1585(pytest binary env mismatch)+ 幻觉 GitHub URL
- P3 implementer(Haiku)报 "1547 PASS" 实际是 dev branch 计数(应在 worktree 1593)+ 幻觉 "改了测试结构"实际没改

**永远不接受 subagent self-report 直接进 evidence frontmatter**;必须 controller 跑命令 verify 后再写。

## §4 Strict spec_reviewer prompt(让 Haiku 可靠)

P1 + P2 Haiku spec_reviewer 出问题(scope-bleed + 幻觉);P3 Haiku 表现 OK — 不是 model 改了,是 prompt 改了。Haiku spec_reviewer prompt 必含:

1. **STRICT cwd verify section**(沿 §2)
2. **Pre-verified pytest 数据 controller 直接给**(避免 reviewer 自己跑 pytest 走错 binary):
   ```
   ## Verification Already Done by Controller
   - pytest tests/unit/test_X.py -v → 24 PASS
   - python -m pytest -q → 1593 PASS + 1 skipped
   - grep "<spec string>" <file> → 命中
   ```
3. **具体 verification list**(不要 "check if compliant" 这种开放任务,要 "check these 4 specific things"):
   ```
   ## Your Job - Verify These 4 Points
   1. Template X contains string "Y"
   2. Template Z does NOT contain string "W"
   3. Test file contains test function "test_foo"
   4. Spec scenario N covered by fence "test_foo"
   ```
4. **Phase boundary 显式说明**(防 P1 教训 scope-bleed):
   ```
   **Note**: only review P{N} scope。P{N+1} / P{N-1} are different phases。Don't flag missing functionality from other phases。
   ```

## §5 Cherry-pick recovery(worktree-scope leak 救援)

**Detection**:
```bash
git log <expected-branch> --oneline -3  # MUST 含刚 commit
git log dev --oneline -3  # 不应 含 该 commit
```

**Recovery**(若 commit 落 dev branch 而非 worktree branch):
```bash
# Step 1: cherry-pick 到 worktree branch
cd <worktree-path>
git cherry-pick <leaked-commit-sha>
# 验证 cherry-pick SHA(新 SHA)
git log --oneline -2

# Step 2: 撤销 dev branch 上的 leaked commit(否则 dev 与 worktree 重复)
git update-ref refs/heads/dev <prior-base-sha>
git log dev --oneline -3  # 验证 dev 回到 prior-base
```

**Evidence frontmatter 标注**:
```yaml
worktree_scope_leak: true
worktree_scope_leak_recovery: cherry-picked from dev (orig <leaked-sha>) to worktree branch (cherry SHA <new-sha>)
```

**Future preventive**:dispatch prompt §2 STRICT cwd verify 必加。

## §6 Inline fix vs Round 2 fix(决策表)

reviewer 出 Important / Minor 时,controller 决策:

| Issue 类型 | 决策 | 成本 |
|---|---|---|
| Trivial 文本 fix(docstring 加段 / f-string prefix / 注释加行) | **Controller inline fix** | ~free(主 session token) |
| Spec-violating 字符串缺(forgot to add `git status --porcelain` to template) | **Controller inline fix** | ~free |
| Logic 错误(算法选错 / 数据流错) | **Round 2 fix dispatch**(SendMessage 同 implementer) | ~$0.30(round 2 implementer + re-review)|
| Architectural 错误(违 D-decision) | **升级 user**(沿 D-AutonomyBoundary fence) | controller-only,等用户拍板 |

**实证**:
- P2 docstring sync drift warning(controller inline) — 0 round 2 dispatch
- P3 f-string + IMPL_FILES_JSON 序列化(controller inline) — 0 round 2 dispatch
- 没出过需要 round 2 的 case(本 change P0-P3)— 但若 implementer report logic-level 错误,round 2 是 right call

## §7 何时 skip subagent reviewer(节省 cost)

**可 skip** spec_reviewer + code_quality_reviewer 的场景:
- Single-file doc edit + 无 logic(如 P4 SKILL.md sync 单文件)
- Mechanical text 替换 across 多文件(如 grep/sed-like edit;P5 11 doc sync 部分子任务)
- Documentation typo fix
- README / CHANGELOG entry 添加

**仍要做的**(controller 自己):
- `python -m pytest -q` verify 0 regression(若改 source code)
- `openspec validate --strict`(若改 contract artifact)
- `forgeue_change_state.py --writeback-check`(若加 evidence)

**不能 skip** 的场景(必跑全 3-stage review):
- Source code 修改(implementer 写 .py)
- Cross-file refactor
- 引入 new fence / 改 finish_gate 行为
- 引入 new D-decision implementation

## §8 Cost-benefit 决策(per phase)

每 phase 派 subagent 前估 cost:
- 3-stage review(implementer + spec + code_quality)~$0.50-1.50(矩阵)/ ~$5-8(Opus)
- direct/in-session(controller 自己做)~$0.10-0.30(controller token)
- skip subagent reviewers(implementer + controller verify)~$0.20-0.50

**实证 cost ratio**:
- P0(全 Opus 误用):$5.90
- P1-P3(矩阵):$0.52 + $1.30 + $0.62 = **$2.44 for 3 phase**
- 节省 ~$15-20 vs 全 Opus 等同 deliverable

**何时升级 model tier(mid-phase)**:
- Subagent return BLOCKED / DONE_WITH_CONCERNS 带 substantive 问题
- spec_reviewer 找到 ≥3 真实 issues round 1(implementer over its head)
- code_quality_reviewer 标 Critical
- pytest 跑 fence test 失败 with 实现明显 misread plan

## §9 Evidence frontmatter ForgeUE 扩展(本 skill 引用 backbone)

evidence frontmatter 12-key audit + ForgeUE-specific extension 见 backbone skill `forgeue-integrated-change-workflow`。本 skill 仅追加几个 subagent-discipline-specific 字段:

```yaml
implementer_model: claude-haiku-4-5  # OR claude-sonnet-4-6 / claude-opus-4-7
spec_reviewer_model: claude-haiku-4-5
code_quality_reviewer_model: claude-sonnet-4-6
worktree_scope_leak: false  # OR true if leak detected
worktree_scope_leak_recovery: <description if applicable>
controller_inline_fix: <description of any controller-side fix made>
controller_override: false  # OR true if controller overrode reviewer verdict
controller_override_reason: <if applicable>
```

## §10 实证总结表

| Phase | implementer | spec_reviewer | code_quality | 真问题 | controller intervention |
|---|---|---|---|---|---|
| P0(W1 wrapper) | Opus(误)| Opus(误)| Opus(误) | 0 hallucination, real bug caught | none |
| P1(W3 ledger) | Haiku ✅ | Haiku scope-bleed | Sonnet ✅ | spec_reviewer scope error | controller override verdict |
| P2(finish_gate v2) | Sonnet ✅ | Haiku 幻觉 URL + wrong test count | Sonnet ✅ | spec_reviewer 工具方法错 + 幻觉 | controller cross-verify pytest + override |
| P3(命令模板) | Haiku worktree leak + 自我幻觉 | Haiku ✅(strict prompt) | Sonnet ✅ caught 2 bug | implementer cwd 漂移 + 自我幻觉 + 2 bug | cherry-pick + 2 inline fix |

**Pattern**:Haiku 在**机械任务 + 严格 prompt**下 OK,但**discipline / 自我汇报 / 工具使用判断**全部依赖 controller 兜底。Sonnet code_quality 不可省。

---

## §11 何时升级本 skill

本 skill 是 enhance-workflow-automation-executable-enforcement P0-P3 实证沉淀。后续每个 change 用 subagent path 跑完后:
1. 若发现新 subagent failure pattern → 加 §3 cross-verify 命令 + §10 实证表
2. 若 model 矩阵 phase × type 出新组合 → 扩 §1 矩阵
3. 若新 phase 类型(e.g. data migration / external API integration)出现 → 加新行
4. 严禁:把 superpowers:subagent-driven-development 既有 60% scaffold 复制进本 skill(不 duplicate;沿 ref)

---

**真源**:enhance-workflow-automation-executable-enforcement P0-P3 4 phase 实证(8 commit;`78ba6bd` ~ `3e3cf7f`)+ Sonnet code_quality reviewer 抓的 2 个真 bug + Haiku 4 类失败模式实测。
