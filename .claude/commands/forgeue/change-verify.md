---
name: "ForgeUE: Change Verify"
description: Level 0/1/2 验证 + codex /codex:review --base <main> verification hook(代码级,无 cross-check)
category: ForgeUE Workflow
tags: [forgeue, workflow, S5, verify]
---

S4→S5 transition:跑 Level 0/1/2 验证(`forgeue_verify` 编排 pytest / live LLM / live UE/ComfyUI),并在 claude-code+plugin 环境跑 codex `/codex:review --base <main>` verification hook(代码级单向挑错,**不**走 cross-check)。

**Input**: 必须指定 change name(`/forgeue:change-verify <id> --level 0|1|2`);默认 `--level 0`。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`;读 `auto_codex_review` / `codex_plugin_available`。
2. **绑定 active change** — abort if missing。
3. **检查 S4 进入条件**:所有 micro-task done + 上轮 writeback-check exit 0。
4. **Superpowers `verification-before-completion` skill auto-trigger**(skill 主导验证清单)。
5. **forgeue_verify 编排**:
   - `python tools/forgeue_verify.py --change <id> --level 0|1|2 --json`
   - Level 0(默认):`python -m pytest -q` + offline bundle 冒烟;**无 paid 默认**
   - Level 1(需 LLM key,env guard `{1,true,yes,on}` 严格):真实 LLM provider + visual review + provider routing live
   - Level 2(需 ComfyUI/UE/贵族 API,opt-in):mesh / UE export / a1_run commandlet
   - 输出落 `verification/verify_report.md`(12-key frontmatter / `evidence_type: verify_report`;Level 1/2 SKIP 必有 reason)
6. **codex verification review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL;**单向挑错,无 cross-check**):
   - 跑 `/codex:review --base <main>`(代码级,base = origin/main 或显式 base)
   - 输出落 `review/codex_verification_review.md`(`evidence_type: codex_verification_review`)
   - 若 codex 找到代码 bug 反映 design.md 接口错位 → DRIFT type 3 → 回写 design.md
7. **回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`(若 codex review 暴露 contract 漏洞)。
8. **状态推进** — verify_report 无 [FAIL] + writeback-check exit 0 → 进 S6。

**Output Format**

```
## ForgeUE Change Verify: <change-id> --level <N> (S4→S5)

### Verification report
- verification/verify_report.md
- Level 0: <PASS | FAIL>; tests run: <N>; failures: <count>
- Level 1: <PASS | SKIP + reason | FAIL>
- Level 2: <PASS | SKIP + reason | FAIL>

### codex verification review
- review/codex_verification_review.md: <findings count>
- code-level findings reflecting design drift: <count> (writeback required)

### Writeback check
- DRIFT count: <N>
- next: <S6 ready | blocked + reason>
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(同 change-plan)。
- **paid provider / live UE / live ComfyUI 默认不开**:Level 1/2 必须 env guard 严格 `{1,true,yes,on}`(case-insensitive);未 opt-in 则 SKIP 落 reason。
- **不静默重试贵族 API**(沿 ADR-007 + ForgeUE memory `feedback_no_silent_retry_on_billable_api`):mesh.generation 等失败时 surface job_id,user 决定 `--resume`。
- **verification 不走 cross-check**(design.md §3 Cross-check Protocol carve-out):codex `/codex:review --base <main>` 是单向挑错,Claude 独立验证 file:line(沿 `feedback_verify_external_reviews`)再决定接受;不写 verify_cross_check.md。
- **evidence 不能成新规范源**:codex 找到的代码 bug 若映射 design.md 接口错位 → 回写 design.md(DRIFT type 3 protocol)。

**References**

- `design.md` §4 commands 表(`/forgeue:change-verify` 行)— hook 真源:`forgeue_verify + /codex:review --base <main>`
- `design.md` §3 Cross-check Protocol(verification carve-out:不走 cross-check)
- `docs/ai_workflow/validation_matrix.md` Level 0/1/2 矩阵(`forgeue_verify.py` 是机器版)
- `forgeue_integrated_ai_workflow.md` §B.4 / §D
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
