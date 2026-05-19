# Backlog Registry

`active.md` / `archived.md` 是 **生成产物** —— 由 `/forge:archive`(或 `forge backlog`)自动重生成,**请勿手编**。本 `README.md` 是一次性静态种子,可本地补充。

- `active.md` —— 当前未决 scope-entry(Future Work + Out of Scope 计入待办数;Non-Goals 单列不计入)。
- `archived.md` —— tombstone:已被后续 change 经 `superseding_entries` 认领为 superseded / obsolete / completed / inherited 的 entry。

数据源:

1. **主数据源**:`forge/changes/archive/*/{proposal,design}.md` 内的 `forge-scope-entries/v1` YAML 块。富字段(priority / reason 等)须写进源头 scope-entry,手编 active.md / archived.md 会被下次重生成冲掉。
2. **第二数据源**:`forge/legacy-requirements.yaml`(由 `forge legacy-bridge extract --finalize` 产出)— 活跃的 legacy requirement 条目渲染到 `active.md` 的 `## Legacy Requirements` 段;已退役的条目渲染到 `archived.md` 的 `## Legacy Requirements — Retired` 段。

查询:`forge backlog list`。CI 守门:`forge backlog --check`。
