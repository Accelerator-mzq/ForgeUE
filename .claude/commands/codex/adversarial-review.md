---
description: Run a Codex review that challenges the implementation approach and design choices
argument-hint: '[--wait|--background] [--base <ref>] [--scope auto|working-tree|branch] [focus ...]'
allowed-tools: Read, Glob, Grep, Bash(node:*), Bash(git:*), AskUserQuestion
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

Execution mode rules:
- If the raw arguments include `--wait`, do not ask. Run in the foreground.
- If the raw arguments include `--background`, do not ask. Run in a Claude background task.
- Otherwise, estimate the review size before asking:
  - For working-tree review, start with `git status --short --untracked-files=all`.
  - For working-tree review, also inspect both `git diff --shortstat --cached` and `git diff --shortstat`.
  - For base-branch review, use `git diff --shortstat <base>...HEAD`.
  - Treat untracked files or directories as reviewable work for auto or working-tree review even when `git diff --shortstat` is empty.
  - Only conclude there is nothing to review when the relevant scope is actually empty.
  - Recommend waiting only when the scoped review is clearly tiny, roughly 1-2 files total and no sign of a broader directory-sized change.
  - In every other case, including unclear size, recommend background.
  - When in doubt, run the review instead of declaring that there is nothing to review.
- Then use `AskUserQuestion` exactly once with two options, putting the recommended option first and suffixing its label with `(Recommended)`:
  - `Wait for results`
  - `Run in background`

Argument handling:
- Preserve the user's arguments exactly.
- Do not strip `--wait` or `--background` yourself.
- Do not weaken the adversarial framing or rewrite the user's focus text.
- The companion script parses `--wait` and `--background`, but Claude Code's `Bash(..., run_in_background: true)` is what actually detaches the run.
- `/codex:adversarial-review` uses the same review target selection as `/codex:review`.
- It supports working-tree review, branch review, and `--base <ref>`.
- It does not support `--scope staged` or `--scope unstaged`.
- Unlike `/codex:review`, it can still take extra focus text after the flags.

Foreground flow:
- Run:
```bash
node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" adversarial-review "$ARGUMENTS"
```
- Return the command stdout verbatim, exactly as-is.
- Do not paraphrase, summarize, or add commentary before or after it.
- Do not fix any issues mentioned in the review output.

Background flow:
- Launch the review with `Bash` in the background:
```typescript
Bash({
  command: `node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" adversarial-review "$ARGUMENTS"`,
  description: "Codex adversarial review",
  run_in_background: true
})
```
- Do not call `BashOutput` or wait for completion in this turn.
- After launching the command, tell the user: "Codex adversarial review started in the background. Check `/codex:status` for progress."

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.

Two changes vs upstream plugin source:

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

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/adversarial-review.md
Last synced: 2026-04-27 (codex plugin v1.0.4)
On plugin upgrade: preserve BOTH the missing `disable-model-invocation`
line AND the broker discovery one-liner (do NOT restore
${CLAUDE_PLUGIN_ROOT}).
-->
