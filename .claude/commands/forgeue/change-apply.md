---
name: "ForgeUE: Change Apply (DEPRECATED)"
description: DEPRECATED — 用 change-apply-subagent / change-apply-direct 替代
category: ForgeUE Workflow
tags: [forgeue, deprecated]
---

> **DEPRECATED**:本命令已废弃,根据 change 复杂度选择:
>
> - 多 micro-task / 需要强 review checkpoint(default subagent path):`/forgeue:change-apply-subagent <id>`
> - 小 change(< 3 micro-task)/ budget 紧张(fallback direct path):`/forgeue:change-apply-direct <id>`
>
> 本命令文件保留 1 个 archive cycle 过渡,下一 change(`add-forgeue-brainstorm-stage` 或同等 follow-on)删除。
>
> 详见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.6 subagent-driven-development 集成边界。
