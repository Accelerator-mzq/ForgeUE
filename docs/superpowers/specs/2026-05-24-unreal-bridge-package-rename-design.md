# Unreal Bridge Package Rename 设计

日期: 2026-05-24
范围: `D:\ClaudeProject\ForgeUE_codex`
状态: 待用户审阅
关联: Linear `FOR-31`, backlog `LR-0143`

## 目标

FOR-31 只解决命名与路径边界问题:当前 `src/framework/ue_bridge/` 已经只服务 Unreal adapter,但包名仍像一个通用 engine bridge。新结构应让读代码的人一眼看出:

```text
runtime export
  -> engine_bridge registry
      -> unreal adapter
          -> unreal contract
      -> godot4 adapter
```

本次不改变 Unreal manifest-only 行为,不改变 Godot4 行为,不启用 `bridge_execute`。

## 当前事实

- `UnrealAdapter` 当前直接 import `framework.ue_bridge.*`。
- `Godot4Adapter` 不依赖 `framework.ue_bridge.*`。
- `ExportExecutor._is_importable` 还有一个旧 UE contract 兼容 shim,内部调用 `ue_bridge.manifest_builder.is_manifest_importable`。
- 测试中 `test_ue_bridge.py`、`test_export_video_path_split.py`、`test_p4_ue_manifest_only.py` 直接覆盖 Unreal 文件契约。
- 文档和 contracts 中大量引用 `ue_bridge`;archive 历史引用更多。

## 采用方案

采用方案 1:把 Unreal 文件契约主实现迁到:

```text
src/framework/engine_bridge/unreal/contract/
  __init__.py
  evidence.py
  import_plan_builder.py
  manifest_builder.py
  permission_policy.py
  inspect/
    __init__.py
    project.py
```

保留旧路径:

```text
src/framework/ue_bridge/
```

但旧路径只作为 compatibility re-export 层。新业务代码和新测试一律使用:

```python
from framework.engine_bridge.unreal.contract import build_manifest
from framework.engine_bridge.unreal.contract.manifest_builder import is_manifest_importable
```

旧 import 在一个兼容周期内继续可用:

```python
from framework.ue_bridge import build_manifest
from framework.ue_bridge.manifest_builder import is_manifest_importable
```

保留旧 import 是为了不一次性打断历史脚本、第三方调用和 archive 中可复现实验记录。

## 不采用的方案

- 顶层 `src/framework/unreal_bridge/`:名字更短,但无法表达它是 `engine_bridge/unreal` 的下游契约。
- 只新增 alias、不移动主实现:风险最低,但不满足本次路径结构清理目标。
- 删除 `src/framework/ue_bridge/`:过早破坏兼容,且项目约定 Codex 不执行删除文件操作。

## 代码边界

### 新主路径

`framework.engine_bridge.unreal.contract` 是主实现包。`UnrealAdapter`、`ExportExecutor._is_importable`、Unreal contract 相关测试都应改用新路径。

### 旧兼容路径

`framework.ue_bridge` 下的文件保留,内容改为薄 re-export。示例:

```python
"""Compatibility alias for framework.engine_bridge.unreal.contract."""

from framework.engine_bridge.unreal.contract.manifest_builder import (
    build_manifest,
    derive_drop_target,
    is_manifest_importable,
)
```

子模块也保留对应 re-export,例如 `framework.ue_bridge.manifest_builder` 转发到 `framework.engine_bridge.unreal.contract.manifest_builder`。

### Godot 不变

`framework.engine_bridge.godot4` 不应 import `framework.engine_bridge.unreal.contract` 或 `framework.ue_bridge`。FOR-31 需要加或保留测试防线证明这一点。

### UE scripts 不变

`ue_scripts/` 是在 Unreal Python 进程中执行的独立脚本,不依赖 framework import。FOR-31 不改它们的运行方式。

## 文档边界

必须更新当前权威文档:

- `docs/requirements/SRS.md`
- `docs/design/HLD.md`
- `docs/design/LLD.md`
- `docs/testing/test_spec.md`
- `docs/acceptance/acceptance_report.md`
- `docs/contracts/artifact-contract/spec.md`
- `docs/contracts/engine-export-bridge/spec.md`
- `docs/contracts/ue-export-bridge/spec.md`
- `docs/backlog/active.md`
- `CHANGELOG.md`

archive 历史引用原则上不批量改。archive 表示当时事实,大量重写会制造噪声。当前权威文档需要明确:

```text
framework.ue_bridge is a legacy compatibility alias.
Current Unreal contract implementation lives under
framework.engine_bridge.unreal.contract.
```

## 测试计划

聚焦测试:

```bash
python -m pytest tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py -q
```

全量测试:

```bash
python -m pytest -q
```

建议增加或调整的 fence:

- 新路径 public import 可用。
- 旧 `framework.ue_bridge` public import 仍可用。
- `UnrealAdapter` 使用新 contract 路径。
- `Godot4Adapter` 不依赖 Unreal contract / legacy `ue_bridge`。
- run comparison import-fence 的 deny list 同步处理新旧路径。

L2 手工验收按条件执行:

- 真实 UE commandlet smoke。
- 真实 Godot4 L2 smoke。

如果 L2 环境缺失,不得宣称 L2 通过,只能引用最近一次已有证据并说明本轮未复跑。

## 成功标准

- `src/framework/engine_bridge/unreal/contract/` 成为 Unreal 文件契约主实现路径。
- 新代码不再直接依赖 `framework.ue_bridge`。
- `framework.ue_bridge` 旧 import 仍可用。
- `Godot4Adapter` 对 Unreal contract 零依赖。
- UE manifest-only 自动化不回归。
- Godot4 adapter 自动化不回归。
- 文档五件套和 contracts 的当前权威路径更新完成。
- Backlog `LR-0143` 与 Linear `FOR-31` 在收尾时结账。

## 风险与缓解

- 风险:大范围 import 改名造成行为改动。
  缓解:先复制主实现到新路径,旧路径 re-export;测试从行为层验证 manifest / plan / evidence 完全一致。
- 风险:run comparison import-fence 漏掉新路径。
  缓解:把新旧 Unreal contract 路径都纳入 fence 语义,避免只读 comparison 层误 import 执行链路。
- 风险:文档 archive 批量改写造成历史事实失真。
  缓解:archive 不批量改,仅当前权威文档说明 legacy alias。
- 风险:真实 L2 smoke 成本高或依赖本机环境。
  缓解:自动化是 merge gate;L2 是 release evidence gate,可复用本机已确认路径执行,失败时单独记录原因。
