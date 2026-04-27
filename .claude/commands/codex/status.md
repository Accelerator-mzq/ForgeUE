---
description: Show active and recent Codex jobs for this repository, including review-gate status
argument-hint: '[job-id] [--wait] [--timeout-ms <ms>] [--all]'
allowed-tools: Bash(node:*)
---

!`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" status "$ARGUMENTS"`

If the user did not pass a job ID:
- Render the command output as a single Markdown table for the current and past runs in this session.
- Keep it compact. Do not include progress blocks or extra prose outside the table.
- Preserve the actionable fields from the command output, including job ID, kind, status, phase, elapsed or duration, summary, and follow-up commands.

If the user did pass a job ID:
- Present the full command output to the user.
- Do not summarize or condense it.

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.
Sole change: removed `disable-model-invocation: true` from frontmatter so
Claude can poll /codex:status without user prompt, useful when Claude
launched a background review via /codex:review or /codex:adversarial-review
and needs to know when results are ready.

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/status.md
Last synced: 2026-04-27 (codex plugin v1.0.4)
-->
