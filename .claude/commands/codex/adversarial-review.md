---
description: Run a Codex review that challenges the implementation approach and design choices
argument-hint: '[--wait|--background] [--base <ref>] [--scope auto|working-tree|branch] [focus ...]'
allowed-tools: Read, Glob, Grep, Bash(node:*), Bash(git:*)
---

Run an adversarial Codex review through the shared plugin runtime.
Position it as a challenge review that questions the chosen implementation, design choices, tradeoffs, and assumptions.
It is not just a stricter pass over implementation defects.

Raw slash-command arguments:
`$ARGUMENTS`

Core constraint:
- This command is review-only.
- Do not fix issues, apply patches, or suggest that you are about to make changes.
- Your only job is to run the review and return Codex's output verbatim to the user.
- Keep the framing focused on whether the current approach is the right one, what assumptions it depends on, and where the design could fail under real-world conditions.

## review_type Enumeration

<!-- P2.3 F1 writeback：5 类 review_type 独立 counter，防止不同 review subject 串用同一路径 -->

The following five review types are recognized. Each type uses its own counter file
and evidence file path, with NO cross-type sharing:

- `codex_design_review`       — invoked at stage S2 (design review)
- `codex_plan_review`         — invoked at stage S3 (plan / tasks review)
- `codex_verification_review` — invoked at stage S5 (verification review)
- `codex_adversarial_review`  — always via `/codex:adversarial-review` command (this command)
- `codex_mixed_scope_review`  — `/codex:review --base main` (branch review spanning multiple stages)

**For this command (`/codex:adversarial-review`):**
The review_type is always `codex_adversarial_review` — no derivation needed.

**Counter file paths** (one file per review_type, per change_id — NO cross-type reads/writes):
- `notes/codex_design_review_round_counter.txt`
- `notes/codex_plan_review_round_counter.txt`
- `notes/codex_verification_review_round_counter.txt`
- `notes/codex_adversarial_review_round_counter.txt`
- `notes/codex_mixed_scope_review_round_counter.txt`

## Round Counter & Context Bridge

<!-- P2.4：round N→N+1 自动注入 round N verdict reference；跨 change / 跨 review_type 禁止共享 -->

**On command start:**

1. `review_type` = `codex_adversarial_review` (fixed for this command).
2. Read `openspec/changes/<change_id>/notes/codex_adversarial_review_round_counter.txt`.
   - If file does not exist or reads `0`: counter `N = 0` (round 1, no prior context).
   - If file reads `N` (N ≥ 1): this invocation is **round N+1**, with prior context.
3. If `N ≥ 1`, prepend the following fence to the review prompt **before any other content**:

```
本次 review 是 round {N+1}（继承 round {N} verdict）。
**强制要求**：开始 review 前 MUST 先读
`openspec/changes/<change_id>/notes/codex_adversarial_review_review_round{N}.md`，
理解上轮已 raise + accepted/rejected 的 finding 与 Claude 决议，避免重复 raise 已解决问题。
若有引用上轮 finding ID（F1/F2/...），请显式标记 `（承 round{N}-FN）`。
```

4. Run the review (always in background — see Execution Mode Rules below).
5. On completion: increment counter to `N+1`; write counter file; save output to
   `openspec/changes/<change_id>/notes/codex_adversarial_review_review_round{N+1}.md`.

**Isolation constraints:**
- Same `change_id` only — never carry round context across change boundaries.
- Same `review_type` only — `codex_adversarial_review` counter does NOT share with
  `codex_design_review`, `codex_plan_review`, `codex_verification_review`, or `codex_mixed_scope_review`.
- Direct predecessor only — round N+1 reads round N, not round N-1 or N-2.

## Execution Mode Rules

<!-- P2.2：adversarial 永远 background，不弹 AskUserQuestion；只有显式 --wait flag 可 override -->

**Adversarial always runs in background.** This command always runs in the background
regardless of scope size, because adversarial deep-analysis requires full async context
and must not block the main session.

The only exception:
- If the raw arguments include `--wait`: run in the foreground (explicit user override).

**Do NOT use `AskUserQuestion` to ask the user which mode to use.**
There is no size estimation for adversarial review — it is always background.

## Polling Convention

<!-- P2.5 F4 writeback：background launch 必须 capture job id；main session 依赖结果前必须 poll -->

When the review runs in background (always, unless `--wait`):

1. **Capture job id**: parse the first line of `codex-companion.mjs` stdout:
   `Codex review started in the background. Job id: <id>`
   Write the captured id to `openspec/changes/<change_id>/notes/codex_adversarial_review_active_jobs.txt`
   (append mode, one id per line; sticky across turns).

2. **After launching**, tell the user:
   "Codex adversarial review started in the background.
   Run `/codex:status --wait <job>` and `/codex:result <job>` to consume verdict."

3. **Before consuming verdict**: Main session MUST poll job before consuming verdict via /codex:status --wait + /codex:result.
   - Use `/codex:status --wait <job>` to block until the job is done.
   - Use `/codex:result <job>` to retrieve the full output.
   - Only write `autonomy_decision: claude_codex_concurred` evidence AFTER the result is in hand.
   - If result is not yet finalized (round counter not incremented / `disputed_open != 0` /
     `verdict` field missing) → change `autonomy_decision` to `user_required` and escalate.

## Argument Handling

- Preserve the user's arguments exactly.
- Do not strip `--wait` or `--background` yourself.
- Do not weaken the adversarial framing or rewrite the user's focus text.
- The companion script parses `--wait` and `--background`, but Claude Code's
  `Bash(..., run_in_background: true)` is what actually detaches the run.
- `/codex:adversarial-review` uses the same review target selection as `/codex:review`.
- It supports working-tree review, branch review, and `--base <ref>`.
- It does not support `--scope staged` or `--scope unstaged`.
- Unlike `/codex:review`, it can still take extra focus text after the flags.

## Foreground Flow

- Run:
```bash
node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" adversarial-review "$ARGUMENTS"
```
- Return the command stdout verbatim, exactly as-is.
- Do not paraphrase, summarize, or add commentary before or after it.
- Do not fix any issues mentioned in the review output.

## Background Flow

- Launch the review with `Bash` in the background:
```typescript
Bash({
  command: `node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" adversarial-review "$ARGUMENTS"`,
  description: "Codex adversarial review",
  run_in_background: true
})
```
- Capture the job id from stdout first line (see Polling Convention above).
- After launching the command, tell the user:
  "Codex adversarial review started in the background.
  Run `/codex:status --wait <job>` and `/codex:result <job>` to consume verdict."

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.

Five changes vs upstream plugin source (enhance-workflow-automation P2):

1. Removed `disable-model-invocation: true` from frontmatter so Claude
   (the model) can invoke /codex:adversarial-review through the shared
   broker, per design.md sec 4 commands table assumption that S6 review
   stage hooks into /codex:adversarial-review (mixed scope, blocker
   independent verification).

   Note: design.md sec 3 "Codex Review Output Exposure Protocol
   (verbatim-first)" still applies -- when Claude triggers this
   command, the resulting codex output MUST appear verbatim in the
   same Claude response that contains the independent verification
   table + finding classification + Resolution proposal. The
   command-level lock is removed; the content-level integrity contract
   remains.

2. Replaced ${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs with an
   inline broker discovery one-liner (see status.md for full
   reasoning). Discovery via shell glob over $USERPROFILE / $HOME,
   version-sorted, picks latest plugin install.

3. adversarial always runs in background (D-DefaultBackground):
   removed AskUserQuestion / size estimation. Adversarial deep-analysis
   always needs full async context; only --wait explicit flag overrides.
   AskUserQuestion removed from allowed-tools.

4. Added ## Round Counter & Context Bridge section (D-CodexContextBridge):
   review_type fixed as codex_adversarial_review; 5 review_type isolated
   counters listed for cross-reference; per-round evidence naming +
   round N+1 prompt injection fence. Codex round 1 F1 finding writeback
   (accepted-codex, writeback_commit 99540e2).

5. Added ## Polling Convention section (F4 writeback):
   background launch → capture job id → write active_jobs.txt →
   main session MUST /codex:status --wait + /codex:result before
   consuming verdict. Removed "Do not call BashOutput or wait for
   completion in this turn." (upstream text that contradicts default
   background protocol).

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/adversarial-review.md
Last synced: 2026-04-27 (codex plugin v1.0.4); override updated 2026-05-05 (P2)
On plugin upgrade: preserve ALL FIVE overrides above (disable-model-invocation removed /
broker discovery one-liner / adversarial always background / Round Counter
& Context Bridge / Polling Convention).
-->
