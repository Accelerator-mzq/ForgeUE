# FOR-32 Unreal Legacy Path Cleanup Design

关联: Linear `FOR-32`, backlog `LR-0144`

## 目标

FOR-31 已把 Unreal manifest-only 文件契约主实现迁到
`framework.engine_bridge.unreal.contract`,但项目里仍有两个历史路径:

- `src/framework/ue_bridge/`:一个兼容周期内的 re-export alias。
- `ue_scripts/`:UE Python 进程内执行的独立脚本层。

FOR-32 的目标是收敛命名边界,让新代码和新文档只使用明确的 Unreal engine
bridge 路径,同时不破坏真实 UE commandlet import。

## 决策

### D1: UE Python 脚本迁到 `engine_scripts/unreal/`

`ue_scripts/` 不属于 `framework` Python package,也不能 `import framework.*`。
因此不放进 `src/framework/engine_bridge/unreal/scripts/`,避免读者误以为它可复用
framework 运行时依赖。新路径使用:

```text
engine_scripts/unreal/
```

该目录仍是 UE Editor / commandlet 进程里的独立 Python 脚本目录,只允许 stdlib +
`import unreal`。

### D2: 运行入口全部改到新路径

真实 commandlet、README、HLD/LLD/contracts、测试 helper 都改为引用:

```powershell
-ExecutePythonScript="<repo>/engine_scripts/unreal/a1_run.py"
```

UE Python Console 手工入口改为:

```python
exec(open("<repo>/engine_scripts/unreal/run_import.py").read())
```

`a1_run.py` 内部 `SCRIPTS_DIR` 指向自身所在的新目录。

### D3: `framework.ue_bridge` 不再作为当前契约入口

当前实现和测试应只引用 `framework.engine_bridge.unreal.contract`。
run-comparison import fence 仍保留 `framework.ue_bridge` 作为 forbidden prefix,
直到用户完成旧目录人工删除;这不是把它当作当前契约,而是防止只读 comparison
路径意外拉起 legacy 包。

### D4: Codex 不执行删除文件操作

项目约定禁止 Codex 删除文件。因此 FOR-32 实施分两层:

1. Codex 可执行层:新增 `engine_scripts/unreal/`,切换所有运行入口、测试和文档,
   并确保当前代码路径不再引用 `framework.ue_bridge` 或 `ue_scripts`。
2. 人工删除层:输出清单给用户手工删除旧路径:
   - `src/framework/ue_bridge/`
   - `ue_scripts/`

删除前后都必须跑同一套验证。若用户后续明确要求由工具删除,需要单独确认该操作
覆盖项目默认禁令。

## 范围

### In Scope

- 新建 `engine_scripts/unreal/` 并复制 UE-side scripts。
- 修改 `tests/unit/test_domain_video_no_copy.py`,
  `tests/unit/test_evidence_writer_skip_reason.py`,
  `tests/unit/test_run_import_skipped_filter.py`,
  `tests/integration/test_p4_ue_manifest_only.py` 等测试中的脚本路径。
- 更新 README、五件套、contracts、backlog、CHANGELOG 中当前行为描述。
- 更新 run-comparison 说明文字,明确 `framework.ue_bridge` 只是待人工删除前的
  forbidden legacy prefix,不是当前运行入口。
- 输出旧路径人工删除清单。

### Out of Scope

- 不启用 `bridge_execute`。
- 不改 UE import manifest / plan / evidence schema。
- 不改 Godot4 adapter 行为。
- 不改历史 archive 文档中的旧路径引用,除非当前文档明确把它作为最新行为。

## 验收

- `framework.engine_bridge.unreal.contract` 仍是 Unreal contract 唯一当前实现路径。
- 当前测试和生产代码不 import `framework.ue_bridge`。
- 当前命令和文档不再把 `ue_scripts/` 作为最新入口。
- `engine_scripts/unreal/` 不包含 `import framework` 或 `from framework`。
- UE manifest-only 自动化通过。
- 真实 UE commandlet smoke 通过。
- Godot4 adapter 测试通过;如本地可用,跑 Godot4 headless L2 证明无回归。
- `docs/backlog/active.md` 中 `LR-0144` 收尾时移到 archived。

## 风险与缓解

- **风险: 真实 UE commandlet 仍引用旧脚本路径。**
  缓解:最终 L2 commandlet 使用新路径 `engine_scripts/unreal/a1_run.py`。
- **风险: UE-side 脚本被放入 framework 包后误用 framework import。**
  缓解:采用顶层 `engine_scripts/unreal/`,并加静态 import fence。
- **风险: 旧路径未删除导致用户仍能看到目录。**
  缓解:本轮输出人工删除清单;删除动作由用户执行。
