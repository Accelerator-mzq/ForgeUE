---
description: Show active and recent Codex jobs for this repository, including review-gate status
argument-hint: '[job-id] [--wait] [--timeout-ms <ms>] [--all]'
allowed-tools: Bash(node:*)
---

!`node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" status "$ARGUMENTS"`

If the user did not pass a job ID:
- Render the command output as a single Markdown table for the current and past runs in this session.
- Keep it compact. Do not include progress blocks or extra prose outside the table.
- Preserve the actionable fields from the command output, including job ID, kind, status, phase, elapsed or duration, summary, and follow-up commands.

If the user did pass a job ID:
- Present the full command output to the user.
- Do not summarize or condense it.

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.

Two changes vs upstream plugin source:

1. Removed `disable-model-invocation: true` from frontmatter so Claude
   can poll /codex:status without user prompt, useful when Claude
   launched a background review and needs to know when results ready.

2. Replaced ${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs with an
   inline broker discovery one-liner. Reason: Claude Code injects
   CLAUDE_PLUGIN_ROOT only when invoking the file at the plugin path;
   files under .claude/commands/ (override path) do NOT receive that
   env var. Empty interpolation yields /scripts/... which Git-Bash on
   Windows translates to E:\Program Files\Git\scripts\... (mingw root)
   and node throws MODULE_NOT_FOUND. Fix: discover the broker via
   shell glob over $USERPROFILE on Windows / $HOME on POSIX, version-
   sort, take latest. printf '%s\n' avoids `ls -F` trailing `*`.

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/status.md
Last synced: 2026-04-27 (codex plugin v1.0.4)
On plugin upgrade: diff this against the new upstream and re-sync if body
changed; preserve BOTH the missing `disable-model-invocation` line AND
the broker discovery one-liner (do NOT restore ${CLAUDE_PLUGIN_ROOT}).
-->
