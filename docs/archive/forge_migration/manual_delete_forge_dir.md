# 退役 forge 目录人工删除清单

日期: 2026-05-22
范围: `D:\ClaudeProject\ForgeUE_codex`

## 背景

项目已将 forge 工作流内容复制迁移到:

- `docs/backlog/`
- `docs/contracts/`
- `docs/archive/forge_changes/`
- `docs/archive/forge_migration/`

Codex 不执行删除文件操作。旧目录由用户手动删除。

## 人工删除清单

- `D:\ClaudeProject\ForgeUE_codex\forge`

## 删除后只读验证

用户手动删除后,可让 Codex 执行:

```powershell
Test-Path forge
rg -n "forge/backlog|forge/specs|forge/changes|/forge:" README.md AGENTS.md CLAUDE.md docs\INDEX.md docs\ai_workflow docs\requirements docs\contracts -S
```

期望:

- `Test-Path forge` 输出 `False`。
- `rg` 不输出当前引用。
