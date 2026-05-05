---
name: "ForgeUE: Change Apply (DEPRECATED)"
description: DEPRECATED — 用 change-apply-subagent / change-apply-direct 替代
category: ForgeUE Workflow
tags: [forgeue, deprecated]
---

> **DEPRECATED**:本命令已废弃,根据 change 复杂度选择:
>
> - 多独立 task(file scope 不交叉 / 无 sequential dep)→ 并行 dispatch:`/forgeue:change-apply-parallel <id>`(自 `enhance-workflow-automation-runtime-enforcement` change 起)
> - 多 micro-task / 需要强 review checkpoint(default subagent path,sequential):`/forgeue:change-apply-subagent <id>`
> - 小 change(< 3 micro-task)/ budget 紧张(fallback direct path,主 worktree):`/forgeue:change-apply-direct <id>`
>
> 路由决策树(沿 design.md D-ParallelDispatch):
>
> ```
> 是否多 task?
>   yes → 是否独立 file scope + 无 sequential dependency?
>     yes → /forgeue:change-apply-parallel(并行)
>     no  → /forgeue:change-apply-subagent(sequential per-task,fresh subagent)
>   no(单 task / 微调)→ /forgeue:change-apply-direct(executing-plans + TDD,主 worktree)
> ```
>
> 本命令文件保留 1 个 archive cycle 过渡,下一 change(`add-forgeue-brainstorm-stage` 或同等 follow-on)删除。
>
> 详见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.6 subagent-driven-development 集成边界 + design.md D-ParallelDispatch / D-DirectWorktreeRefinement 决策。
