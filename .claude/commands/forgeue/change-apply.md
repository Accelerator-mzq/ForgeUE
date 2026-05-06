---
name: "ForgeUE: Change Apply (DEPRECATED)"
description: DEPRECATED — 用 change-apply-subagent / change-apply-direct 替代
category: ForgeUE Workflow
tags: [forgeue, deprecated]
---

> **DEPRECATED**:本命令已废弃,根据 change 复杂度选择:
>
> - 多 micro-task / 需要强 review checkpoint(default subagent path,sequential):`/forgeue:change-apply-subagent <id>`
> - 小 change(< 3 micro-task)/ budget 紧张(fallback direct path,主 worktree):`/forgeue:change-apply-direct <id>`
>
> 路由决策树:
>
> ```
> 是否多 micro-task / 需要 spec compliance 强约束?
>   yes → /forgeue:change-apply-subagent(sequential per-task,fresh subagent + 4 类 evidence)
>   no(< 3 micro-task / budget 紧张)→ /forgeue:change-apply-direct(executing-plans + TDD,主 worktree)
> ```
>
> 注:`/forgeue:change-apply-parallel` 已在 `retire-parallel-and-worktree-fully` change(2026-05-06)整 retire — parallel dispatch 路径不再支持(沿 D-PostRetireParallelStrategy);若后续需要并行需重新 propose 独立 change。
>
> 本命令文件保留 1 个 archive cycle 过渡,下一 follow-on change 删除。
>
> 详见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.6 subagent-driven-development 集成边界 + design.md D-DirectWorktreeRefinement 决策。
