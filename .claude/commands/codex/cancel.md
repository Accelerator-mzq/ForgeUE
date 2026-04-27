---
description: Cancel an active background Codex job in this repository
argument-hint: '[job-id]'
allowed-tools: Bash(node:*)
---

!`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" cancel "$ARGUMENTS"`

Cancel the Codex job identified by `$ARGUMENTS`. If no job ID is supplied,
the companion script targets the most recent active job in this repository.
Present the broker's stdout verbatim to the user (success / not-found /
already-finished etc.) so the user knows the canceled job state without
ambiguity.

<!--
ForgeUE local override of openai-codex/codex/1.0.4 plugin command.
Sole change: removed `disable-model-invocation: true` from frontmatter so
Claude can cancel its own runaway codex jobs (rare but useful — e.g.,
realized prompt was wrong mid-review and want to redo with a better
brief). Claude SHOULD only cancel jobs Claude itself launched; canceling
a user-initiated job is a workflow violation.

Plugin source: ~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/cancel.md
Last synced: 2026-04-27 (codex plugin v1.0.4)
-->
