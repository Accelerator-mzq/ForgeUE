# FOR-7 Managed Process Registry Generalization 设计

> 目标：把 `Orchestrator` 里对 `ComfyLifecycleManager` 的专用分支收束成一个薄的 managed process registry，预留第二个托管 subprocess provider 的接入骨架，但不在本次实现第二个 provider 本身。

## 背景

当前运行时已经有一条稳定的 ComfyUI 托管链路：

- `ModelRegistry` 把 `provider_kind` / `provider_config` 透传到 `PreparedRoute`。
- `src/framework/providers/comfy_provider_config.py` 负责识别 Comfy route，并把 `spec` / 环境变量 / YAML 配置合并成 Comfy 运行配置。
- `src/framework/runtime/orchestrator.py` 仍然直接扫描 step，命中后直接构造 `ComfyLifecycleManager`。
- `StepContext.lifecycle` 只接受 `ExternalProcessLifecycle` 抽象，但 Orchestrator 现在仍知道具体类名。

这意味着第二个托管 subprocess provider 一旦出现，就很容易把同样的 route 扫描、配置解析、生命周期构造逻辑复制一遍。这个 change 的目的，就是把这条路径抽成一个稳定的 registry seam。

## 目标

1. `Orchestrator` 不再知道具体的 managed lifecycle 实现类。
2. 现有 ComfyUI 行为保持不变，包括 `ensure` / `release` / `aclose` 语义。
3. 未来第二个托管 subprocess provider 只需要新增一个 adapter 并注册，不需要改 Orchestrator 主流程。
4. 保持 `StepContext.lifecycle` 仍然是单一注入点，不把本次变更扩成多 lifecycle 运行时。

## 非目标

- 不实现第二个 provider 的具体启动、探活、停止逻辑。
- 不修改 `ComfyLifecycleManager` 的状态机语义。
- 不把 worker 侧的 Comfy 配置解析迁移进 registry。
- 不引入插件自动发现，也不做配置驱动的通用 provider 插件系统。
- 不把一个 run 变成多个并行 lifecycle 的调度器。

## 核心设计

### 1. ManagedProcessAdapter

每个托管 subprocess provider 用一个小 adapter 表达自己的接入方式。它只负责三件事：

- 判断某个 `PreparedRoute` 是否属于自己。
- 把 route + step config + 环境变量解析成本 provider 的运行配置。
- 构造对应的 `ExternalProcessLifecycle` 实例。

Comfy 是第一个 adapter，第二个 provider 以后也走同一接口。

### 2. ManagedProcessRegistry

新增一个运行时 registry，负责按固定顺序扫描 step 和 route，并把匹配的 adapter 交给当前 run。

registry 的职责很薄：

- 维护已注册的 managed process adapters。
- 按 workflow / step / route 顺序找第一个可用的 managed provider。
- 返回一个可直接注入的 `ExternalProcessLifecycle`，以及它对应的 `mode`。

registry 不负责模型路由，不负责 worker 选择，也不碰 `ModelRegistry` 本身。

### 3. Comfy adapter

Comfy 相关逻辑继续留在 provider 侧，直接复用现有 helper：

- `is_comfy_agent_route`
- `resolve_comfy_agent_config`

Comfy adapter 只把这些 helper 包成一个 registry 条目。这样做的好处是：

- Comfy 行为不变。
- 第二个 provider 以后不会被迫复用 Comfy 的配置结构。
- provider-specific 逻辑仍留在 `src/framework/providers/`，runtime 只看抽象接口。

### 4. Orchestrator 只持有抽象

`Orchestrator` 只依赖 `ExternalProcessLifecycle`：

- 构造时可注入 registry，默认使用项目级 registry。
- `arun()` 仍然只拿到一个 active lifecycle manager，并把它注入所有 step。
- `aclose()` 仍然只负责释放 `self_managed_session` 的 owner。

这保留了当前单 lifecycle 的运行模型，也把 provider 细节从 orchestration 里拿掉了。

## 运行时流程

1. `Orchestrator.arun()` 收到 workflow steps。
2. 它把 steps 交给 `ManagedProcessRegistry` 扫描。
3. registry 按步骤顺序、route 顺序、adapter 注册顺序找第一个匹配的 managed provider。
4. 如果没有匹配项，所有 step 的 `ctx.lifecycle` 都保持 `None`。
5. 如果匹配项的 `mode` 是 `none`，也不构造 lifecycle。
6. 如果匹配项需要托管，则 registry 返回一个 `ExternalProcessLifecycle`，Orchestrator 继续沿用现有 `ensure` / `release` / `aclose` 逻辑。

这条流和现在的行为对齐，只是把“谁负责选择和构造 manager”从 Orchestrator 挪到了 registry。

## 文件边界

- `src/framework/runtime/managed_process_registry.py`
  - 新增 registry、selection 结果和 adapter 接口。
- `src/framework/providers/comfy_provider_config.py`
  - 保留现有 Comfy 配置 helper，并补一个 Comfy adapter 入口。
- `src/framework/runtime/orchestrator.py`
  - 改成通过 registry 获取 managed lifecycle，不再直接引用 `ComfyLifecycleManager`。
- `tests/unit/test_managed_process_registry.py`
  - 覆盖 registry 选择、无匹配、注册顺序和 fake second adapter。
- `tests/unit/test_orchestrator.py`
  - 覆盖 lifecycle 注入、`self_managed_session`、`aclose()`、无 managed route。

## 错误处理

- 未匹配到任何 adapter：视为普通 run，不构造 lifecycle。
- Comfy lifecycle 配置非法：沿用现有 `ValueError` fail-fast。
- adapter 注册名重复：注册时直接拒绝。
- adapter 构造 lifecycle 失败：异常直接上抛，不由 registry 吞掉。
- `release` 超时和 cancellation 处理：保留现有 bounded helper，不在本 change 中改动。

## 测试策略

本次变更只需要最小但有代表性的单测覆盖：

- registry 能识别 Comfy route，并返回可用 selection。
- registry 可以注册一个 fake second adapter，证明骨架能承接第二个 provider。
- Orchestrator 在注入 registry 后，仍然把同一个 lifecycle 实例传给所有 step。
- `self_managed_session` 仍然只在 `aclose()` 时真正 stop。
- 没有 managed route 时，`ctx.lifecycle` 仍然为 `None`。

## 对现有文档的影响

实现完成后，需要把 `docs/design/LLD.md` 里 5.9 节关于 “暂不泛化成 ManagedProcessRegistry” 的旧表述改成新的 registry seam 事实，避免文档继续描述过时边界。
