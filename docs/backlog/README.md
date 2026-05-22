# Backlog 登记表

`active.md` / `archived.md` 是项目当前 backlog,已从原 `forge/backlog/` 迁移到 `docs/backlog/`。从本迁移完成后,本目录由项目维护,不再由 forge 命令生成。

- `active.md` —— 当前未决 scope-entry(Future Work + Out of Scope 计入待办数;Non-Goals 单列不计入)。
- `archived.md` —— tombstone:已被后续变更认领为 superseded / obsolete / completed / inherited 的 entry。

数据源:

1. `docs/archive/forge_changes/*/{proposal,design}.md` 内的 `forge-scope-entries/v1` YAML 块是历史来源。
2. `docs/archive/forge_migration/legacy-requirements.yaml` 是 legacy requirement 快照来源。
3. 新增 backlog 项直接维护在 `docs/backlog/active.md`;退役项维护在 `docs/backlog/archived.md`。

维护约定:

- 不硬编码测试总数;测试事实以实际命令输出为准。
- 变更 backlog 时同步更新相关 `docs/requirements/SRS.md` 或验收文档引用。
- 历史 archive 不重写原始叙述;只在当前文档中指向新路径。
