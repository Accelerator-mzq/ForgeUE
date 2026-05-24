# Engine Bridge + Godot 4 适配设计

日期: 2026-05-23
范围: `D:\ClaudeProject\ForgeUE_codex`
状态: 待用户审阅
关联: FOR-30 背景讨论,但本设计优先处理多引擎抽象,不直接启用 Unreal RemoteControl

## 目标重定义

ForgeUE 从 UE 专用生产链框架升级为多引擎内容交付框架。

核心层继续负责多模型生成、Artifact 治理、Review、Workflow 和 Runtime。引擎层通过 adapter 把内容交付到具体 runtime。Unreal 是第一个 adapter,Godot 4.x 是第二个 adapter。

新的第一性原理表述:

```text
多模型生成内容
  -> 产物治理
  -> review / 选择
  -> 通过 EngineAdapter 交付到某个实时引擎项目
```

## 事实基线

- 当前 `Task` 直接持有 `ue_target`,核心对象叫 `UEOutputTarget`。
- 当前 `ExportExecutor` 直接依赖 `framework.ue_bridge.*`,并要求 `ctx.task.ue_target` 存在。
- 当前 README / SRS / HLD 把 UE Bridge 写作框架中心能力。
- Godot 4 第一阶段已由用户确认锁定为 Godot 4.x,且目标是直接驱动 editor/headless import,不是只写文件契约。

Godot 外部事实来源:

- `sourced_on`: 2026-05-23
- `source_url`: https://docs.godotengine.org/en/4.4/tutorials/editor/command_line_tutorial.html
- `source_url`: https://docs.godotengine.org/en/4.0/tutorials/assets_pipeline/import_process.html

## 采用方案

采用方案 B:先抽 Engine Bridge,再迁移 Unreal,再加 Godot。

不采用的方案:

- 方案 A:保留 `ue_target` 并旁路新增 `godot_target`。短期快,但会让核心层长期堆积 `if unreal / if godot`。
- 方案 C:新建 Godot 路径而冻结 UE 旧路径。短期风险小,但会形成两套 export 体系。

推荐方案的原因:框架真正稳定的边界是 engine adapter,不是某一个引擎。先抽象边界再接 Godot,长期可维护性最好。

## 架构边界

新增通用 engine bridge 层:

```text
src/framework/engine_bridge/
  core.py
  adapters.py
  registry.py
  unreal/
  godot4/
```

职责划分:

- `framework.core`:保留 Task / Run / Workflow / Artifact / Review 等引擎无关对象。
- `framework.engine_bridge.core`:定义 `EngineTarget` / `EngineManifest` / `EngineImportPlan` / `EngineEvidence`。
- `framework.engine_bridge.adapters`:定义 `EngineAdapter` 协议。
- `framework.engine_bridge.registry`:根据 `EngineTarget.engine` 选择 adapter。
- `framework.engine_bridge.unreal`:包装现有 `ue_bridge` 行为。
- `framework.engine_bridge.godot4`:实现 Godot 4.x headless import。

`ExportExecutor` 改为只做 adapter dispatch:

```python
# 中文注释:ExportExecutor 只选择 adapter,不直接写 Unreal / Godot 导入细节
target = resolve_engine_target(ctx.task)
adapter = EngineAdapterRegistry.resolve(target.engine)
return await adapter.export(ctx, target=target)
```

## EngineTarget

第一版通用 target:

```python
class EngineTarget(BaseModel):
    engine: Literal["unreal", "godot4"]
    project_name: str
    project_root: str
    import_mode: str
    asset_root: str = "generated"
    executable_path: str | None = None
    validation_hooks: list[str] = Field(default_factory=list)
    options: dict = Field(default_factory=dict)
```

兼容规则:

```python
# 中文注释:旧 bundle 仍可写 ue_target,loader / Task normalizer 自动转为 unreal target
if task.engine_target is None and task.ue_target is not None:
    task.engine_target = EngineTarget.from_ue_target(task.ue_target)
```

第一阶段保留 `ue_target` 作为兼容输入,新 example 和新文档使用 `engine_target`。

## Unreal Adapter

Unreal adapter 不重写现有逻辑,而是先包装当前行为。

保留:

- `manifest_only` 语义。
- `UEAssetManifest` / `UEImportPlan` / UE Evidence 的当前文件契约。
- `ue_scripts/` 独立于 framework 的约束。
- 当前 P4 / stub-unreal / commandlet 验证路径。

不在本设计中启用:

- `bridge_execute`。
- FOR-30 RemoteControl HTTP bridge。

FOR-30 后续应落为 `UnrealAdapter` 的独立 import mode,例如 `remote_control` 或未来 `bridge_execute`,而不是混入 Godot 抽象迁移。

## Godot 4 Adapter

Godot 第一阶段 import mode 为 `headless_import`。

推荐 bundle 形态:

```json
{
  "engine_target": {
    "engine": "godot4",
    "project_name": "ForgeGodotDemo",
    "project_root": "D:/GodotProjects/ForgeGodotDemo",
    "asset_root": "forgeue/generated",
    "import_mode": "headless_import",
    "executable_path": "C:/Godot/Godot_v4.x.exe"
  }
}
```

执行流程:

```text
upstream Artifacts
  -> Godot4Adapter.stage_artifacts()
  -> 写入 <project_root>/forgeue/generated/<run_id>/
  -> 生成 godot_manifest.json / godot_import_plan.json / evidence.json
  -> 执行 godot --headless --path <project_root> --import
  -> 验证源文件旁 .import 文件与 .godot/imported/ 产物
  -> 追加 evidence
  -> 返回 engine.export_bundle Artifact
```

Godot 可执行文件解析顺序:

1. `engine_target.executable_path`
2. `GODOT4_EXE`
3. 未配置时 preflight fail,报出明确错误

第一版 artifact 映射:

| Artifact | Godot 4 处理 |
| --- | --- |
| `image/png` / `image/jpeg` | 作为 Texture2D 源文件导入 |
| `audio/wav` / `audio/mp3` | 作为 AudioStream 源文件导入 |
| `mesh/glb` | 作为 glTF / scene 源文件导入 |
| `video/mp4` | 第一阶段 stage 文件并写 skipped evidence,不自动声明为 Godot runtime asset |

不手写 Godot `.import` 文件。ForgeUE 只放置源文件、调用 Godot 导入、验证导入结果。`.import` 与 `.godot/imported/` 由 Godot 自己生成。

## Evidence 契约

新增通用 evidence:

```python
class EngineEvidence(BaseModel):
    evidence_item_id: str
    op_id: str
    engine: Literal["unreal", "godot4"]
    kind: str
    status: Literal["success", "failed", "skipped"]
    source_uri: str | None = None
    target_uri: str | None = None
    log_ref: str | None = None
    error: str | None = None
```

Unreal adapter 可以继续写 UE evidence,同时由 bundle artifact 暴露通用 `engine="unreal"` metadata。Godot adapter 直接写 `EngineEvidence`。

## 分阶段实施

Phase 1:Engine Bridge 抽象

- 新增 `EngineTarget` / `EngineAdapter` / registry。
- `Task` 支持 `engine_target`。
- 保留 `ue_target` 兼容转换。
- `ExportExecutor` 改为 adapter dispatch。
- `UnrealAdapter` 包装当前 UE `manifest_only` 行为。
- 现有 UE tests 和 examples 必须继续通过。

Phase 2:Godot 4.x Headless Import MVP

- 新增 `Godot4Adapter`。
- 支持 image / audio / glb 三类资产 stage + import。
- 调用 `godot --headless --path <project_root> --import`。
- 写 `godot_manifest.json` / `godot_import_plan.json` / `evidence.json`。
- 无 Godot 安装时 live probe 默认 skip。

Phase 3:文档产品化

- SRS / HLD / LLD 从 UE-first 改 engine-first。
- `docs/contracts/` 新增 `engine-export-bridge`。
- `ue-export-bridge` 降级为 Unreal adapter contract。
- README / AGENTS / CLAUDE 同步项目定位。
- FOR-30 重新归类为 Unreal RemoteControl adapter 后续任务。

Phase 4:真实 Godot L2 验收

- 配置 `GODOT4_EXE`。
- 用最小 Godot 4 项目跑 headless import。
- 保存 evidence 文件。
- 验证 `.import` 与 `.godot/imported/` 存在。

## 测试计划

L0 单测:

- `EngineTarget` schema。
- `ue_target -> engine_target` 兼容转换。
- adapter registry resolve `unreal` / `godot4`。
- Godot artifact kind mapping。
- Godot command construction。
- Godot evidence append。

L1 集成:

- 旧 UE export example 仍产 manifest / plan / evidence。
- 新 Godot export example 在 fake Godot subprocess 下产 Godot bundle。
- 无 `GODOT4_EXE` 时 live probe skip。

L2 本机验收:

- `GODOT4_EXE` + demo project + headless import 真跑。
- Godot import 后 evidence 指向项目内验证产物。

## 非目标

- 不在本设计里改项目包名 `forgeue`。
- 不在本设计里支持 Godot 3.x。
- 不在本设计里启用 Unreal `bridge_execute`。
- 不在本设计里实现 Unreal RemoteControl HTTP bridge。
- 不在第一阶段删除 `ue_target` / `ue_bridge`。
- 不把 mp4 强行映射成 Godot runtime asset。

## 成功标准

- 核心文档承认 ForgeUE 的目标从 UE 专用转为多引擎内容交付。
- 新代码层存在 engine bridge 抽象,`ExportExecutor` 不直接依赖 Unreal 细节。
- 旧 UE bundle 仍可运行。
- 新 Godot 4 bundle 可在配置 `GODOT4_EXE` 后 headless import。
- Godot 无安装环境下自动化测试保持可跑,live 验证明确 skip。

## 风险与缓解

- 风险:一次性重命名 `ue_*` 造成大面积 churn。
  缓解:先新增 `engine_target`,保留 `ue_target` 兼容输入。
- 风险:Godot import 成功但验证过度依赖内部目录细节。
  缓解:第一阶段只验证源文件旁 `.import` 与 `.godot/imported/` 至少出现对应导入产物,不解析 Godot 内部二进制资源。
- 风险:Unreal 与 Godot evidence 过早统一导致 UE 历史契约破坏。
  缓解:Unreal adapter 保留现有 UE evidence,通用 evidence 先服务 Godot 与 engine bundle metadata。
- 风险:FOR-30 与 Godot 抽象迁移混 scope。
  缓解:FOR-30 明确降为 Unreal adapter 后续能力,本设计只处理抽象层与 Godot 4 headless import。
