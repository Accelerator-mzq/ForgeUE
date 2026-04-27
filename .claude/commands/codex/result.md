---
description: Show the stored final output for a finished Codex job in this repository
argument-hint: '[job-id]'
allowed-tools: Bash(node:*)
---

!`node "$(printf '%s\n' "${USERPROFILE:-$HOME}"/.claude*/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)" result "$ARGUMENTS"`

Present the full command output to the user. Do not summarize or condense it. Preserve all details including:
- Job ID and status
- The complete result payload, including verdict, summary, findings, details, artifacts, and next steps
- File paths and line numbers exactly as reported
- Any error messages or parse errors
- Follow-up commands such as `/codex:status <id>` and `/codex:review`

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.

Two changes vs upstream plugin source:

1. Removed `disable-model-invocation: true` from frontmatter so Claude
   can read finished codex job results without user prompt, useful when
   Claude launched a background review and needs to consume the output.
   Per-repo scope (broker stores results per-repo), so reading
   other-repo results is impossible -- privacy concern is bounded.

2. Replaced ${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs with an
   inline broker discovery one-liner (see status.md for full reasoning).
   tl;dr: CLAUDE_PLUGIN_ROOT is only injected for files at plugin path,
   not for .claude/commands/ overrides. Discovery via shell glob over
   $USERPROFILE / $HOME, version-sorted, picks latest plugin install.

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/result.md
Last synced: 2026-04-27 (codex plugin v1.0.4)
On plugin upgrade: preserve BOTH the missing `disable-model-invocation`
line AND the broker discovery one-liner.
-->
