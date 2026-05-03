---
name: "ForgeUE: Change Finish"
description: Finish Gate(中心化最后防线);forgeue_finish_gate 阻断 evidence frontmatter aligned=false 而无 drift 的 archive
category: ForgeUE Workflow
tags: [forgeue, workflow, S7-to-S8, finish]
---

S7→S8 transition:Finish Gate(中心化最后防线)。`forgeue_finish_gate.py` 检查 evidence 完整性 + frontmatter 全检 + cross-check disputed_open + writeback_commit 真实性二次校验 + tasks unchecked + `openspec validate --strict` + `~/.claude/settings.json` review-gate hook 检查。

**Input**: 必须指定 change name(`/forgeue:change-finish <id>`)。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`。
2. **绑定 active change** — abort if missing。
3. **检查 S7 进入条件**:`verification/doc_sync_report.md` 落盘 + DRIFT 0 + REQUIRED 全应用。
4. **forgeue_finish_gate 编排**:
   - `python tools/forgeue_finish_gate.py --change <id> --json`
   - 检查项:
     - **evidence 完整性**:必含 `verification/verify_report.md` / `verification/doc_sync_report.md` / `review/superpowers_review.md` finalize / `review/codex_adversarial_review.md`(claude-code+plugin 时)等
     - **frontmatter 全检**:每份 evidence 12-key frontmatter 完整 + `aligned_with_contract: true`(或带 drift 标记 + reason ≥ 50 字 + Reasoning Notes anchor)
     - **cross-check disputed_open**:`design_cross_check.md` / `plan_cross_check.md` 必须 `disputed_open: 0`
     - **writeback_commit 二次校验**:每个 `written-back-to-*` 必有 `git rev-parse <sha>` PASS + `git show --stat <sha>` 触对应 artifact(spec.md ADDED Requirement Scenario 2 protocol 要求)
     - **tasks unchecked**:`tasks.md` 无 `[ ]` 残留(或带 SKIP reason)
     - **`openspec validate <id> --strict`** PASS
     - **`~/.claude/settings.json` review-gate hook**:若含 `--enable-review-gate` → WARN 提示用户 disable
   - exit 0(PASS)/ 2(任一 blocker)/ 3(目录不存)/ 1(IO 异常)
5. **写 finish_gate_report** — `verification/finish_gate_report.md`(`evidence_type: finish_gate_report` / 12-key frontmatter):列每项检查的 [OK]/[FAIL]/[WARN] + blocker reason。
6. **状态推进** — finish_gate exit 0 → 进 S8(可走 `/opsx:archive`);exit 2 → 报告 blocker,**不**推进,用户修后重跑。

**Output Format**

```
## ForgeUE Change Finish: <change-id> (S7→S8)

### Finish gate report
- verification/finish_gate_report.md
- evidence completeness: <PASS | FAIL: <missing files>>
- frontmatter aligned_with_contract: <PASS | FAIL: <files with aligned=false sans drift>>
- cross-check disputed_open: <PASS | FAIL: <files with disputed_open > 0>>
- writeback_commit verify: <PASS | FAIL: <stale shas / mismatched artifacts>>
- tasks unchecked: <count>
- openspec validate --strict: <PASS | FAIL>
- review-gate hook: <ABSENT (OK) | PRESENT (WARN)>

### Verdict
- exit code: <0|2|3|1>
- next: <S8 ready (run /opsx:archive) | blocked + blocker count + reason>
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(本命令检测 `~/.claude/settings.json`,若发现 review-gate hook → WARN)。
- **中心化最后防线**:exit 2 任一 blocker 阻断 archive;不允许"凑合"通过;evidence 含 `aligned_with_contract: false` 且未带 drift 标记 → exit 2(spec.md ADDED Requirement Scenario 2)。
- **writeback_commit 真实性二次校验**:`git rev-parse <sha>` + `git show --stat <sha>` 必须确认 commit 真存在且改对应 artifact(`design.md` / `proposal.md` / `tasks.md` / `specs/<cap>/spec.md`);否则 exit 2。
- **`disputed-permanent-drift` 必带 reason ≥ 50 字 + Reasoning Notes anchor**;否则 exit 2(spec.md ADDED Requirement Scenario 3)。
- **不让 evidence 成新规范源**:本命令是该原则的物理表达。
- **本命令不直接触发 `/codex:adversarial-review` / `/codex:review`**(本命令是 finish gate 综合检查,不属 stage review;review hook 出现在 `/forgeue:change-{plan,apply,verify,review}` 对应 stage)。

**References**

- `design.md` §4 commands 表(`/forgeue:change-finish` 行)— hook 真源:`forgeue_finish_gate`
- `design.md` §5 Tool Design(`forgeue_finish_gate.py` 检查矩阵)
- `specs/examples-and-acceptance/spec.md` ADDED Requirement(active change evidence 协议;archive 后合入主 spec)
- `forgeue_integrated_ai_workflow.md` §B.2(横切硬约束)+ §D
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
