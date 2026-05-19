# Active Backlog

> 生成产物 —— 由 `/forge:archive` 自动重生成,**勿手编**。Schema 见 README.md。
> 待办计 0 项(Future Work + Out of Scope;Non-Goals 不计入)。
> 另有 9 项 legacy requirements 待办(不计入上面 0)。

## Warnings (0)

(无)

## Future Work (0)

(无)

## Out of Scope (0)

(无)

## Non-Goals (0) — 原则不做,不计入待办

(无)


## Legacy Requirements (9)

### `docs/requirements/SRS.md`

- `LR-0004` **FR-WF-004 Step 支持 11 种 type** — Step 应支持 11 种 type:generate / transform / validate / review / select / export / import / inspect / plan / execute / custom
- `LR-0037` **FR-REVIEW-001 三种评审形态支持** — 系统应支持三种评审形态:`single_judge`、`panel_judge`(多 judge 并发)、`human_review`(留出接口)
- `LR-0039` **FR-REVIEW-003 Verdict 支持 9 种 decision** — Verdict 应支持 9 种 `decision`:`accept` / `revise` / `reject` / `retry_same_step` / `fallback_model` / `abort_or_fallback` / `escalate_human` / `human_review_required` / `stop`
- `LR-0041` **FR-REVIEW-005 5 维评分写入 scores_by_dimension** — Review 应支持 5 维评分:`quality` / `consistency` / `ue_compliance` / `aesthetics` / `technical_correctness`,写入 `scores_by_dimension`
- `LR-0111` **NFR-SEC-004 Dry-run Pass 校验 API key 已注入** — Dry-run Pass 应校验所需 provider 的 API key 已注入,缺失则 Run 不启动
- `LR-0114` **NFR-OBS-002 Step emit step_start/step_done/step_failed** — 每个 Step 应 emit `step_start` / `step_done` 事件,失败应 emit `step_failed` 并携带异常类型
- `LR-0115` **NFR-OBS-003 BudgetTracker 在 RunResult.budget_summary 汇总指定字段** — BudgetTracker 应在 `RunResult.budget_summary` 中汇总:`total_cost_usd` / `prompt_tokens` / `completion_tokens` / `total_tokens` / per-step breakdown
- `LR-0116` **NFR-OBS-004 长任务 poll emit worker_poll 事件** — 长任务 poll(mesh / comfy)应 emit `worker_poll` 事件,带 `elapsed_s` + 可选 `progress`
- `LR-0123` **NFR-PORT-002 CI 能在 Linux runner 跑通全量测试** — CI 应能在 Linux runner 跑通全量测试(除 UE 真机冒烟外)
