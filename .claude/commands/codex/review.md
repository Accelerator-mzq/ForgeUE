---
description: Run a Codex code review against local git state
argument-hint: '[--wait|--background] [--base <ref>] [--scope auto|working-tree|branch] [--stage <hint>]'
allowed-tools: Read, Glob, Grep, Bash(node:*), Bash(git:*)
---

Run a Codex review through the shared built-in reviewer.

Raw slash-command arguments:
`$ARGUMENTS`

Core constraint:
- This command is review-only.
- Do not fix issues, apply patches, or suggest that you are about to make changes.
- Your only job is to run the review and return Codex's output verbatim to the user.

## Preflight Skill Cascade — N/A (D-SkillCascadeCheck disclaimer)

This command is a **pure codex CLI dispatch** (codex-companion broker subprocess
runs GPT-5.4 review), **invokes no Superpowers SKILL**, so the
`## Preflight Skill Cascade` section is N/A — `tools/forgeue_skill_cascade_check.py`
does not apply to this command.

When ForgeUE controllers dispatch this command from
`/forgeue:change-{plan,verify,review}`, the Preflight Skill Cascade check is
the **caller's** responsibility (verifying Superpowers SKILL dependencies of the
caller command), and is not duplicated at this codex CLI layer.

Evidence frontmatter MAY still carry `runtime_enforcement_protocol_version: v1`
when the caller command is on the protocol v1 path; `forgeue_finish_gate.py::_check_skill_cascade`
fence applies only to implementation evidence types (`codex_*_review` types are
fence pass-through and do not require the `skill_cascade_audit` field).

## review_type Enumeration

<!-- P2.3 F1 writeback：5 类 review_type 独立 counter，防止不同 review subject 串用同一路径 -->

The following five review types are recognized. Each type uses its own counter file
and evidence file path, with NO cross-type sharing:

- `codex_design_review`       — invoked at stage S2 (design review)
- `codex_plan_review`         — invoked at stage S3 (plan / tasks review)
- `codex_verification_review` — invoked at stage S5 (verification review)
- `codex_adversarial_review`  — always via `/codex:adversarial-review` command
- `codex_mixed_scope_review`  — `/codex:review --base main` (branch review spanning multiple stages)

**review_type derivation rules:**
- `/codex:adversarial-review` command → always `codex_adversarial_review`
- `/codex:review --base main` (branch / base review) → `codex_mixed_scope_review`
- `/codex:review` (scope auto / working-tree) → infer from `--stage` hint arg:
  - `--stage S2` → `codex_design_review`
  - `--stage S3` → `codex_plan_review`
  - `--stage S5` → `codex_verification_review`
  - no hint → default to `codex_mixed_scope_review`

**Counter file paths** (one file per review_type, per change_id — NO cross-type reads/writes):
- `notes/codex_design_review_round_counter.txt`
- `notes/codex_plan_review_round_counter.txt`
- `notes/codex_verification_review_round_counter.txt`
- `notes/codex_adversarial_review_round_counter.txt`
- `notes/codex_mixed_scope_review_round_counter.txt`

## Round Counter & Context Bridge

<!-- P2.4：round N→N+1 自动注入 round N verdict reference；跨 change / 跨 review_type 禁止共享 -->

**On command start:**

1. Derive `review_type` (see Enumeration section above).
2. Read `openspec/changes/<change_id>/notes/<review_type>_round_counter.txt`.
   - If file does not exist or reads `0`: counter `N = 0` (round 1, no prior context).
   - If file reads `N` (N ≥ 1): this invocation is **round N+1**, with prior context.
3. If `N ≥ 1`, prepend the following fence to the review prompt **before any other content**:

```
本次 review 是 round {N+1}（继承 round {N} verdict）。
**强制要求**：开始 review 前 MUST 先读
`openspec/changes/<change_id>/notes/<review_type>_review_round{N}.md`，
理解上轮已 raise + accepted/rejected 的 finding 与 Claude 决议，避免重复 raise 已解决问题。
若有引用上轮 finding ID（F1/F2/...），请显式标记 `（承 round{N}-FN）`。
```

4. Run the review (foreground or background per Execution Mode rules below).
5. On completion: increment counter to `N+1`; write counter file; save output to
   `openspec/changes/<change_id>/notes/<review_type>_review_round{N+1}.md`.

**Isolation constraints:**
- Same `change_id` only — never carry round context across change boundaries.
- Same `review_type` only — `codex_design_review` round 1 does NOT feed into
  `codex_plan_review` round 1 (different review subjects).
- Direct predecessor only — round N+1 reads round N, not round N-1 or N-2.

## Execution Mode Rules

<!-- P2.2：默认 background；仅当全部 3 条 AND 满足时才前台 wait；不弹 AskUserQuestion -->

**Default: background.** Run in background unless ALL THREE of the following conditions
are simultaneously true (3-AND gate for foreground):

1. **Size**: `git diff --shortstat` / `git diff --shortstat --cached` shows ≤ 2 files
   **AND** ≤ 50 total lines changed.
2. **Non-adversarial**: the invocation is NOT via `/codex:adversarial-review`
   (adversarial always runs in background regardless of size).
3. **Must-wait**: the main session's next action strictly requires the review result
   before proceeding (e.g. round 1 finding determines whether round 2 is needed).

If ANY of the three conditions is false → **run in background immediately, no question asked.**
If ALL three are true → run in the foreground.

**Explicit flag overrides size estimation:**
- If the raw arguments include `--wait`: run foreground, no estimation needed.
- If the raw arguments include `--background`: run background, no estimation needed.

**How to estimate size (when no explicit flag):**
- For working-tree review: run `git status --short --untracked-files=all` first, then
  `git diff --shortstat --cached` and `git diff --shortstat`.
- For base-branch review: use `git diff --shortstat <base>...HEAD`.
- Treat untracked files/dirs as reviewable work even when `git diff --shortstat` is empty.
- Only conclude nothing-to-review when the relevant scope is actually empty.
- When in doubt, run in background rather than declaring nothing to review.

**Do NOT use `AskUserQuestion` to ask the user which mode to use.** The 3-AND gate
above fully determines the mode without user input.

## Polling Convention

<!-- P2.5 F4 writeback：background launch 必须 capture job id；main session 依赖结果前必须 poll -->

When the review runs in background:

1. **Capture job id**: parse the first line of `codex-companion.mjs` stdout:
   `Codex review started in the background. Job id: <id>`
   Write the captured id to `openspec/changes/<change_id>/notes/<review_type>_active_jobs.txt`
   (append mode, one id per line; sticky across turns).

2. **After launching**, tell the user:
   "Codex review started in the background.
   Run `/codex:status --wait <job>` and `/codex:result <job>` to consume verdict."

3. **Before consuming verdict**: Main session MUST poll job before consuming verdict via /codex:status --wait + /codex:result.
   - Use `/codex:status --wait <job>` to block until the job is done.
   - Use `/codex:result <job>` to retrieve the full output.
   - Only write `autonomy_decision: claude_codex_concurred` evidence AFTER the result is in hand.
   - **Result finalization check** (NOT based on round counter — counter increments AFTER
     result consumption, so it is necessarily un-incremented at poll time and cannot serve
     as a finalization signal). Treat the result as un-finalized if ANY of:
     - codex result output is missing a top-level `verdict` field (or `### Verdict:` section absent)
     - the persisted evidence frontmatter shows `disputed_open != 0`
     - the persisted evidence frontmatter is missing the `resolved_at` field (round not finalized)
   - On any of the above → change `autonomy_decision` to `user_required` and escalate to user.

## Argument Handling

- Preserve the user's arguments exactly.
- Do not strip `--wait` or `--background` yourself.
- Do not add extra review instructions or rewrite the user's intent.
- The companion script parses `--wait` and `--background`, but Claude Code's
  `Bash(..., run_in_background: true)` is what actually detaches the run.
- `/codex:review` is native-review only. It does not support staged-only review,
  unstaged-only review, or extra focus text.
- If the user needs custom review instructions or more adversarial framing,
  they should use `/codex:adversarial-review`.
- `--stage <hint>` is a ForgeUE local extension (not passed to codex-companion.mjs);
  strip it before building the companion invocation command.

## Foreground Flow

- Run:
```bash
node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" review "$ARGUMENTS"
```
- Return the command stdout verbatim, exactly as-is.
- Do not paraphrase, summarize, or add commentary before or after it.
- Do not fix any issues mentioned in the review output.

## Background Flow

- Launch the review with `Bash` in the background:
```typescript
Bash({
  command: `node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" review "$ARGUMENTS"`,
  description: "Codex review",
  run_in_background: true
})
```
- Capture the job id from stdout first line (see Polling Convention above).
- After launching the command, tell the user:
  "Codex review started in the background.
  Run `/codex:status --wait <job>` and `/codex:result <job>` to consume verdict."

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.

Five changes vs upstream plugin source (enhance-workflow-automation P2):

1. Removed `disable-model-invocation: true` from frontmatter so Claude
   (the model) can invoke /codex:review through the shared broker, per
   design.md sec 4 commands table assumption that S5 verification stage
   hooks into /codex:review --base <main>. Per design.md sec 3 "Codex
   Review Output Exposure Protocol (verbatim-first)", Claude MUST
   surface codex output verbatim alongside Claude's framing in the same
   response. The command-level lock is removed; the content-level
   integrity contract remains.

2. Replaced ${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs with an
   inline broker discovery one-liner. Reason: Claude Code injects
   CLAUDE_PLUGIN_ROOT only when invoking the file at the plugin path;
   files under .claude/commands/ (override path) do NOT receive that
   env var. Empty interpolation yields /scripts/... which Git-Bash on
   Windows translates to E:\Program Files\Git\scripts\... (mingw root)
   and node throws MODULE_NOT_FOUND. Fix: discover the broker via
   shell glob over $USERPROFILE on Windows / $HOME on POSIX,
   version-sort, take latest. printf '%s\n' avoids `ls -F` trailing `*`.

3. Replaced AskUserQuestion size-estimation two-choice prompt with
   3-AND gate default background policy (enhance-workflow-automation
   D-DefaultBackground). Old: recommend background / wait then ask user.
   New: default background unless ALL THREE conditions met (≤2 files /
   ≤50 lines / non-adversarial / must-wait); explicit --wait/--background
   flags still override. AskUserQuestion removed from allowed-tools.

4. Added ## Round Counter & Context Bridge section (D-CodexContextBridge):
   5 review_type isolated counters + per-round evidence naming +
   round N+1 prompt injection fence. Codex round 1 F1 finding writeback
   (accepted-codex, writeback_commit 99540e2).

5. Added ## Polling Convention section (F4 writeback):
   background launch → capture job id → write active_jobs.txt →
   main session MUST /codex:status --wait + /codex:result before
   consuming verdict. Removed "Do not call BashOutput or wait for
   completion in this turn." (upstream text that contradicts default
   background protocol).

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/review.md
Last synced: 2026-04-27 (codex plugin v1.0.4); override updated 2026-05-05 (P2)
On plugin upgrade: diff this against the new upstream and re-sync if body
changed; preserve ALL FIVE overrides above (disable-model-invocation removed /
broker discovery one-liner / 3-AND gate default background / Round Counter
& Context Bridge / Polling Convention).
-->
