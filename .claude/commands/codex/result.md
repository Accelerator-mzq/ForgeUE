---
description: Show the stored final output for a finished Codex job in this repository
argument-hint: '[job-id]'
allowed-tools: Bash(node:*)
---

!`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" result "$ARGUMENTS"`

Present the full command output to the user. Do not summarize or condense it. Preserve all details including:
- Job ID and status
- The complete result payload, including verdict, summary, findings, details, artifacts, and next steps
- File paths and line numbers exactly as reported
- Any error messages or parse errors
- Follow-up commands such as `/codex:status <id>` and `/codex:review`

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.
Sole change: removed `disable-model-invocation: true` from frontmatter so
Claude can read finished codex job results without user prompt, useful
when Claude launched a background review and needs to consume the output.

Per-repo scope (broker stores results per-repo), so reading other-repo
results is impossible — privacy concern is bounded.

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/result.md
Last synced: 2026-04-27 (codex plugin v1.0.4)
-->
