# Unreal Bridge 包路径重命名实施计划

> **给执行 agent:** 必须使用 `superpowers:subagent-driven-development`(推荐)或 `superpowers:executing-plans` 按任务执行本计划。步骤使用 checkbox(`- [ ]`)语法跟踪。

**目标:** 将 Unreal manifest-only 文件契约主实现迁到 `framework.engine_bridge.unreal.contract`,同时保留 `framework.ue_bridge` 作为一个兼容周期的 alias。

**架构:** 新包成为生产代码和新增测试使用的主实现。旧 `framework.ue_bridge` 包保留为轻量 re-export modules,确保历史 import 继续工作且行为不变。Godot4 继续独立于 Unreal contract modules。

**技术栈:** Python 3.13,既有 `framework.core.ue` Pydantic models,pytest,现有 docs 五件套与 contracts。

---

## 文件结构

新增 Unreal contract 主实现 package:

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

保留兼容模块:

```text
src/framework/ue_bridge/
  __init__.py
  evidence.py
  import_plan_builder.py
  manifest_builder.py
  permission_policy.py
  inspect/
    __init__.py
    project.py
```

修改生产 import:

```text
src/framework/engine_bridge/unreal/adapter.py
src/framework/runtime/executors/export.py
```

修改测试:

```text
tests/unit/test_unreal_contract_package.py
tests/unit/test_ue_bridge.py
tests/unit/test_export_video_path_split.py
tests/integration/test_p4_ue_manifest_only.py
tests/unit/test_run_comparison_cli.py
tests/unit/test_run_comparison_loader.py
tests/unit/test_run_comparison_models.py
tests/unit/test_run_comparison_diff_engine.py
tests/unit/test_run_comparison_reporter.py
```

修改文档:

```text
CHANGELOG.md
docs/requirements/SRS.md
docs/design/HLD.md
docs/design/LLD.md
docs/testing/test_spec.md
docs/acceptance/acceptance_report.md
docs/contracts/artifact-contract/spec.md
docs/contracts/engine-export-bridge/spec.md
docs/contracts/ue-export-bridge/spec.md
docs/backlog/active.md
docs/backlog/archived.md
```

---

### 任务 1: 添加包边界测试

**涉及文件:**
- 新增: `tests/unit/test_unreal_contract_package.py`

- [ ] **步骤 1: 为新主实现 package 和兼容 alias 编写失败测试**

创建 `tests/unit/test_unreal_contract_package.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_unreal_contract_new_public_surface_imports():
    from framework.engine_bridge.unreal.contract import (
        EvidenceWriter,
        build_import_plan,
        build_manifest,
        is_op_allowed,
        load_evidence,
        permission_mask_for_manifest,
    )
    from framework.engine_bridge.unreal.contract.manifest_builder import (
        _KIND_MAP,
        _PREFIX_BY_KIND,
        _default_import_options,
        is_manifest_importable,
    )
    from framework.engine_bridge.unreal.contract.import_plan_builder import _IMPORT_OP_KIND

    assert build_manifest is not None
    assert build_import_plan is not None
    assert EvidenceWriter is not None
    assert load_evidence is not None
    assert is_op_allowed is not None
    assert permission_mask_for_manifest is not None
    assert is_manifest_importable is not None
    assert _KIND_MAP[("video", "mp4")] == "file_media_source"
    assert _PREFIX_BY_KIND["file_media_source"] == "MS_"
    assert _IMPORT_OP_KIND["file_media_source"] == "import_file_media_source"
    assert _default_import_options("file_media_source", type("A", (), {"metadata": {}, "format": "mp4"})())["source_format"] == "mp4"


def test_legacy_ue_bridge_reexports_match_new_contract():
    from framework.engine_bridge.unreal.contract import build_manifest as new_build_manifest
    from framework.engine_bridge.unreal.contract.evidence import new_evidence_id as new_id
    from framework.engine_bridge.unreal.contract.import_plan_builder import (
        _IMPORT_OP_KIND as new_import_op_kind,
    )
    from framework.engine_bridge.unreal.contract.manifest_builder import (
        _KIND_MAP as new_kind_map,
    )
    from framework.ue_bridge import build_manifest as legacy_build_manifest
    from framework.ue_bridge.evidence import new_evidence_id as legacy_id
    from framework.ue_bridge.import_plan_builder import (
        _IMPORT_OP_KIND as legacy_import_op_kind,
    )
    from framework.ue_bridge.manifest_builder import _KIND_MAP as legacy_kind_map

    assert legacy_build_manifest is new_build_manifest
    assert legacy_id is new_id
    assert legacy_import_op_kind is new_import_op_kind
    assert legacy_kind_map is new_kind_map


def test_unreal_adapter_uses_new_contract_imports():
    adapter_path = Path("src/framework/engine_bridge/unreal/adapter.py")
    source = adapter_path.read_text(encoding="utf-8")

    assert "framework.engine_bridge.unreal.contract" in source
    assert "framework.ue_bridge" not in source


def test_export_executor_uses_new_unreal_contract_importable_shim():
    export_path = Path("src/framework/runtime/executors/export.py")
    source = export_path.read_text(encoding="utf-8")

    assert "framework.engine_bridge.unreal.contract.manifest_builder" in source
    assert "framework.ue_bridge" not in source


def test_godot4_adapter_does_not_import_unreal_contracts():
    godot_path = Path("src/framework/engine_bridge/godot4/adapter.py")
    source = godot_path.read_text(encoding="utf-8")

    assert "framework.engine_bridge.unreal.contract" not in source
    assert "framework.ue_bridge" not in source
```

- [ ] **步骤 2: 运行新增测试,确认迁移前失败**

运行:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py -q
```

预期: 失败,错误包含 `ModuleNotFoundError: No module named 'framework.engine_bridge.unreal.contract'`。

- [ ] **步骤 3: 提交失败测试**

```bash
git add tests/unit/test_unreal_contract_package.py
git commit -m "test: add unreal contract package boundary fences"
```

---

### 任务 2: 创建 Unreal contract 主实现 package

**涉及文件:**
- 新增: `src/framework/engine_bridge/unreal/contract/__init__.py`
- 新增: `src/framework/engine_bridge/unreal/contract/evidence.py`
- 新增: `src/framework/engine_bridge/unreal/contract/import_plan_builder.py`
- 新增: `src/framework/engine_bridge/unreal/contract/manifest_builder.py`
- 新增: `src/framework/engine_bridge/unreal/contract/permission_policy.py`
- 新增: `src/framework/engine_bridge/unreal/contract/inspect/__init__.py`
- 新增: `src/framework/engine_bridge/unreal/contract/inspect/project.py`

- [ ] **步骤 1: 将现有实现文件复制到新 package**

运行:

```powershell
New-Item -ItemType Directory -Force -Path src/framework/engine_bridge/unreal/contract/inspect
Copy-Item src/framework/ue_bridge/evidence.py src/framework/engine_bridge/unreal/contract/evidence.py
Copy-Item src/framework/ue_bridge/import_plan_builder.py src/framework/engine_bridge/unreal/contract/import_plan_builder.py
Copy-Item src/framework/ue_bridge/manifest_builder.py src/framework/engine_bridge/unreal/contract/manifest_builder.py
Copy-Item src/framework/ue_bridge/permission_policy.py src/framework/engine_bridge/unreal/contract/permission_policy.py
Copy-Item src/framework/ue_bridge/inspect/project.py src/framework/engine_bridge/unreal/contract/inspect/project.py
```

- [ ] **步骤 2: 替换新 package 的 `__init__.py`**

写入 `src/framework/engine_bridge/unreal/contract/__init__.py`:

```python
"""framework.engine_bridge.unreal 使用的 Unreal contract package。

中文注释:这里是 Unreal manifest-only 文件契约的主实现路径;
`framework.ue_bridge` 仅保留为兼容 alias。
"""

from framework.engine_bridge.unreal.contract.evidence import EvidenceWriter, load_evidence
from framework.engine_bridge.unreal.contract.import_plan_builder import build_import_plan
from framework.engine_bridge.unreal.contract.manifest_builder import build_manifest
from framework.engine_bridge.unreal.contract.permission_policy import (
    is_op_allowed,
    permission_mask_for_manifest,
)

__all__ = [
    "EvidenceWriter",
    "build_import_plan",
    "build_manifest",
    "is_op_allowed",
    "load_evidence",
    "permission_mask_for_manifest",
]
```

- [ ] **步骤 3: 替换新 inspect package 的 `__init__.py`**

写入 `src/framework/engine_bridge/unreal/contract/inspect/__init__.py`:

```python
"""只读 Unreal project inspection helpers。"""

from framework.engine_bridge.unreal.contract.inspect.project import (
    PathStatus,
    ProjectReadiness,
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)

__all__ = [
    "PathStatus",
    "ProjectReadiness",
    "inspect_asset_exists",
    "inspect_content_path",
    "inspect_project",
    "validate_manifest",
]
```

- [ ] **步骤 4: 更新新 `permission_policy.py` 内部 import**

在 `src/framework/engine_bridge/unreal/contract/permission_policy.py` 中,替换 `permission_mask_for_manifest` 里的局部 import:

```python
from framework.engine_bridge.unreal.contract.import_plan_builder import (
    derive_required_op_kinds,
)
```

函数体保持不变。

- [ ] **步骤 5: 运行新 package 测试**

运行:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py::test_unreal_contract_new_public_surface_imports -q
```

预期: 新 package import 测试通过;兼容 alias 测试在任务 3 前仍会失败。

- [ ] **步骤 6: 提交主实现 package 创建**

```bash
git add src/framework/engine_bridge/unreal/contract tests/unit/test_unreal_contract_package.py
git commit -m "refactor: add unreal contract package"
```

---

### 任务 3: 将 `framework.ue_bridge` 转为兼容 shims

**涉及文件:**
- 修改: `src/framework/ue_bridge/__init__.py`
- 修改: `src/framework/ue_bridge/evidence.py`
- 修改: `src/framework/ue_bridge/import_plan_builder.py`
- 修改: `src/framework/ue_bridge/manifest_builder.py`
- 修改: `src/framework/ue_bridge/permission_policy.py`
- 修改: `src/framework/ue_bridge/inspect/__init__.py`
- 修改: `src/framework/ue_bridge/inspect/project.py`

- [ ] **步骤 1: 替换 `src/framework/ue_bridge/__init__.py`**

```python
"""framework.engine_bridge.unreal.contract 的兼容 alias。

中文注释:旧 `framework.ue_bridge` import 在一个兼容周期内保留;
新代码应使用 `framework.engine_bridge.unreal.contract`。
"""

from framework.engine_bridge.unreal.contract import (
    EvidenceWriter,
    build_import_plan,
    build_manifest,
    is_op_allowed,
    load_evidence,
    permission_mask_for_manifest,
)

__all__ = [
    "EvidenceWriter",
    "build_import_plan",
    "build_manifest",
    "is_op_allowed",
    "load_evidence",
    "permission_mask_for_manifest",
]
```

- [ ] **步骤 2: 替换 legacy `evidence.py`**

```python
"""Unreal contract evidence helpers 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.evidence import (
    EvidenceWriter,
    load_evidence,
    new_evidence_id,
)

__all__ = ["EvidenceWriter", "load_evidence", "new_evidence_id"]
```

- [ ] **步骤 3: 替换 legacy `import_plan_builder.py`**

```python
"""Unreal contract import plan builder 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.import_plan_builder import (
    _DERIVED_OP_KIND,
    _IMPORT_OP_KIND,
    build_import_plan,
    derive_required_op_kinds,
)

__all__ = [
    "_DERIVED_OP_KIND",
    "_IMPORT_OP_KIND",
    "build_import_plan",
    "derive_required_op_kinds",
]
```

- [ ] **步骤 4: 替换 legacy `manifest_builder.py`**

```python
"""Unreal contract manifest builder 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.manifest_builder import (
    _KIND_MAP,
    _PREFIX_BY_KIND,
    _default_import_options,
    _derive_dependencies,
    _derive_ue_name,
    build_manifest,
    derive_drop_target,
    is_manifest_importable,
    ManifestBuildError,
)

__all__ = [
    "ManifestBuildError",
    "_KIND_MAP",
    "_PREFIX_BY_KIND",
    "_default_import_options",
    "_derive_dependencies",
    "_derive_ue_name",
    "build_manifest",
    "derive_drop_target",
    "is_manifest_importable",
]
```

- [ ] **步骤 5: 替换 legacy `permission_policy.py`**

```python
"""Unreal contract permission policy 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.permission_policy import (
    _OP_ALLOW_ATTR,
    is_op_allowed,
    permission_mask_for_manifest,
)

__all__ = [
    "_OP_ALLOW_ATTR",
    "is_op_allowed",
    "permission_mask_for_manifest",
]
```

- [ ] **步骤 6: 替换 legacy inspect modules**

写入 `src/framework/ue_bridge/inspect/__init__.py`:

```python
"""Unreal contract inspection helpers 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.inspect import (
    PathStatus,
    ProjectReadiness,
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)

__all__ = [
    "PathStatus",
    "ProjectReadiness",
    "inspect_asset_exists",
    "inspect_content_path",
    "inspect_project",
    "validate_manifest",
]
```

写入 `src/framework/ue_bridge/inspect/project.py`:

```python
"""Unreal contract project inspection 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.inspect.project import (
    PathStatus,
    ProjectReadiness,
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)

__all__ = [
    "PathStatus",
    "ProjectReadiness",
    "inspect_asset_exists",
    "inspect_content_path",
    "inspect_project",
    "validate_manifest",
]
```

- [ ] **步骤 7: 运行兼容性测试**

运行:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py::test_legacy_ue_bridge_reexports_match_new_contract tests/unit/test_ue_bridge.py -q
```

预期: 通过。

- [ ] **步骤 8: 提交兼容 shims**

```bash
git add src/framework/ue_bridge tests/unit/test_unreal_contract_package.py
git commit -m "refactor: keep ue_bridge compatibility aliases"
```

---

### 任务 4: 迁移生产 import 和核心测试

**涉及文件:**
- 修改: `src/framework/engine_bridge/unreal/adapter.py`
- 修改: `src/framework/runtime/executors/export.py`
- 修改: `tests/unit/test_ue_bridge.py`
- 修改: `tests/unit/test_export_video_path_split.py`
- 修改: `tests/integration/test_p4_ue_manifest_only.py`

- [ ] **步骤 1: 更新 `UnrealAdapter` imports**

替换 `src/framework/engine_bridge/unreal/adapter.py` 的 top-level imports:

```python
from framework.engine_bridge.unreal.contract.evidence import EvidenceWriter, new_evidence_id
from framework.engine_bridge.unreal.contract.import_plan_builder import build_import_plan
from framework.engine_bridge.unreal.contract.inspect import inspect_project, validate_manifest
from framework.engine_bridge.unreal.contract.manifest_builder import build_manifest
from framework.engine_bridge.unreal.contract.permission_policy import is_op_allowed
```

替换 drop loop 中的局部 import:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import derive_drop_target
```

替换 `_is_importable` 中的局部 import:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import (
    is_manifest_importable,
)
```

- [ ] **步骤 2: 更新 `ExportExecutor._is_importable`**

在 `src/framework/runtime/executors/export.py` 中,替换:

```python
from framework.ue_bridge.manifest_builder import is_manifest_importable
```

为:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import (
    is_manifest_importable,
)
```

同步更新附近注释:

```python
# 兼容既有 Unreal contract;实际过滤规则仍由 manifest_builder 单一真源决定。
```

- [ ] **步骤 3: 更新核心 Unreal contract 测试,改用新路径**

在 `tests/unit/test_ue_bridge.py` 中,将来自 `framework.ue_bridge` 的 imports 替换为:

```python
from framework.engine_bridge.unreal.contract import (
    EvidenceWriter,
    build_import_plan,
    build_manifest,
    is_op_allowed,
    permission_mask_for_manifest,
)
from framework.engine_bridge.unreal.contract.evidence import load_evidence, new_evidence_id
from framework.engine_bridge.unreal.contract.inspect import (
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)
from framework.engine_bridge.unreal.contract.manifest_builder import ManifestBuildError
```

替换 late imports:

```python
from framework.engine_bridge.unreal.contract.import_plan_builder import _IMPORT_OP_KIND  # noqa: E402
from framework.engine_bridge.unreal.contract.manifest_builder import (  # noqa: E402
    _KIND_MAP,
    _PREFIX_BY_KIND,
    _default_import_options,
)
```

- [ ] **步骤 4: 更新 video path split 测试**

在 `tests/unit/test_export_video_path_split.py` 中,替换 imports:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import is_manifest_importable
from framework.engine_bridge.unreal.contract.manifest_builder import derive_drop_target  # noqa: E402
from framework.engine_bridge.unreal.contract.manifest_builder import build_manifest  # noqa: E402
```

- [ ] **步骤 5: 更新 P4 integration imports**

在 `tests/integration/test_p4_ue_manifest_only.py` 中,替换 imports:

```python
from framework.engine_bridge.unreal.contract import (
    EvidenceWriter,
    build_import_plan,
    build_manifest,
)
from framework.engine_bridge.unreal.contract.evidence import load_evidence
from framework.engine_bridge.unreal.contract.inspect import (
    inspect_content_path,
    inspect_project,
    validate_manifest,
)
```

- [ ] **步骤 6: 运行生产 import 测试**

运行:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/integration/test_p4_ue_manifest_only.py -q
```

预期: 通过。

- [ ] **步骤 7: 提交生产 import 迁移**

```bash
git add src/framework/engine_bridge/unreal/adapter.py src/framework/runtime/executors/export.py tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/integration/test_p4_ue_manifest_only.py
git commit -m "refactor: use unreal contract package in runtime"
```

---

### 任务 5: 更新 Run Comparison import fences

**涉及文件:**
- 修改: `tests/unit/test_run_comparison_cli.py`
- 修改: `tests/unit/test_run_comparison_loader.py`
- 修改: `tests/unit/test_run_comparison_models.py`
- 修改: `tests/unit/test_run_comparison_diff_engine.py`
- 修改: `tests/unit/test_run_comparison_reporter.py`
- 修改: `docs/design/LLD.md`

- [ ] **步骤 1: 更新 5 个测试文件中的 forbidden module tuples**

在每个 run-comparison 测试文件中,保留 `framework.ue_bridge`,并在它后面立即加入新的执行层主路径 prefix:

```python
_FORBIDDEN_FRAMEWORK_MODULES_LOADER = (
    "framework.runtime",
    "framework.providers",
    "framework.review_engine",
    "framework.ue_bridge",
    "framework.engine_bridge.unreal.contract",
    "framework.workflows",
    "framework.observability",
    "framework.server",
    "framework.schemas",
    "framework.pricing_probe",
    "framework.artifact_store.repository",
    "framework.artifact_store.payload_backends",
    "framework.artifact_store.lineage",
    "framework.artifact_store.variant_tracker",
)
```

沿用每个文件已有的 tuple 变量名;只新增这个字符串。

- [ ] **步骤 2: 更新 LLD import-fence 文案**

在 `docs/design/LLD.md` 中,更新 run comparison import-fence 段落,包含:

```text
runtime / providers / review_engine / ue_bridge / engine_bridge.unreal.contract /
workflows / observability / server / schemas / pricing_probe
```

并在同一段补充这句话:

```text
`framework.ue_bridge` 仍保留在清单中,因为它是同一个 Unreal execution contract 的 legacy compatibility alias。
```

- [ ] **步骤 3: 运行 run-comparison fence 测试**

运行:

```bash
python -m pytest tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py -q
```

预期: 通过。

- [ ] **步骤 4: 提交 import fence 更新**

```bash
git add tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py docs/design/LLD.md
git commit -m "test: fence unreal contract from comparison imports"
```

---

### 任务 6: 更新权威文档并结账 backlog 条目

**涉及文件:**
- 修改: `CHANGELOG.md`
- 修改: `docs/requirements/SRS.md`
- 修改: `docs/design/HLD.md`
- 修改: `docs/design/LLD.md`
- 修改: `docs/testing/test_spec.md`
- 修改: `docs/acceptance/acceptance_report.md`
- 修改: `docs/contracts/artifact-contract/spec.md`
- 修改: `docs/contracts/engine-export-bridge/spec.md`
- 修改: `docs/contracts/ue-export-bridge/spec.md`
- 修改: `docs/backlog/active.md`
- 修改: `docs/backlog/archived.md`

- [ ] **步骤 1: 更新当前文档,明确 canonical package 名称**

在 HLD、LLD 和 contracts 描述当前路径的位置使用这段文案:

```text
当前 Unreal contract 主实现位于
`src/framework/engine_bridge/unreal/contract/`。
`src/framework/ue_bridge/` 保留为一个兼容周期的 legacy compatibility alias。
```

在 SRS 中保留概念名 "Unreal 文件契约",但将实现路径引用替换为:

```text
`framework.engine_bridge.unreal.contract`
```

- [ ] **步骤 2: 更新测试规格**

在 `docs/testing/test_spec.md` 中,将 Unreal contract 行更新为:

```text
`test_ue_bridge.py` | `engine_bridge/unreal/contract/*` + `engine_bridge/unreal/adapter.py` | FR-ENGINE-003, FR-UE-001 ~ FR-UE-008 | L1,L2 | Unreal manifest-only contract、legacy `framework.ue_bridge` alias、ManifestBuilder modality 映射、PlanBuilder depends_on、Permission Phase C 默认拒绝、inspect_project / asset_exists、validate_manifest 重复路径、evidence 原子追加
```

将 `test_unreal_contract_package.py` 加入 Engine Bridge / Godot 4 区域,作为 package-boundary fence。

- [ ] **步骤 3: 更新 CHANGELOG**

在当前 Unreleased section 下新增一条:

```markdown
- **FOR-31 Unreal contract package rename**: Unreal manifest-only 文件契约主实现迁到 `framework.engine_bridge.unreal.contract`;`framework.ue_bridge` 保留为一个兼容周期的 compatibility alias;同步更新 runtime imports、run-comparison import fences、docs 和 backlog/Linear tracking,不改变 Unreal 或 Godot import 行为。
```

- [ ] **步骤 4: 归档 LR-0143**

在 `docs/backlog/active.md` 中:

```markdown
> 待办计 0 项(Future Work + Out of Scope;Non-Goals 不计入)。

## Future Work (0)

(无)
```

从 active 中移除 `LR-0143` 条目。

在 `docs/backlog/archived.md` 中,靠近其他 LR 条目新增 tombstone:

```markdown
### `LR-0143` **unreal-bridge-package-rename Unreal 文件契约包路径命名清理**

- **completed_on**: 2026-05-24
- **Linear**: `FOR-31`
- **summary**: Unreal manifest-only 文件契约主实现迁到 `framework.engine_bridge.unreal.contract`;`framework.ue_bridge` 保留为一个兼容周期的 compatibility alias。
- **verification**: 聚焦 Unreal contract tests、run-comparison import fences、Godot4 adapter tests,以及全量 `python -m pytest -q`。
```

- [ ] **步骤 5: 运行 docs/backlog grep 检查**

运行:

```bash
rg -n "src/framework/ue_bridge/|framework\\.ue_bridge|ue_bridge" docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts CHANGELOG.md docs/backlog
```

预期: 只剩当前文档中明确说明 `framework.ue_bridge` 是 legacy compatibility alias 的引用,以及 CHANGELOG 历史中的路径引用。

- [ ] **步骤 6: 提交文档和 backlog 更新**

```bash
git add CHANGELOG.md docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts/artifact-contract/spec.md docs/contracts/engine-export-bridge/spec.md docs/contracts/ue-export-bridge/spec.md docs/backlog/active.md docs/backlog/archived.md
git commit -m "docs: sync unreal contract package rename"
```

---

### 任务 7: 最终验证与证据

**涉及文件:**
- 新增: `demo_artifacts/2026-05-24/adhoc/for31_unreal_contract_rename/verification.md`
- Linear: `FOR-31`

- [ ] **步骤 1: 运行聚焦验证**

运行:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py -q
```

预期: 通过。

- [ ] **步骤 2: 运行 run-comparison fence 验证**

运行:

```bash
python -m pytest tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py -q
```

预期: 通过。

- [ ] **步骤 3: 运行全量验证**

运行:

```bash
python -m pytest -q
```

预期: 通过。将精确 pass/skip 计数记录到 evidence。

- [ ] **步骤 4: 本机 engine 可用时运行 L2 smoke 检查**

使用 2026-05-24 已验证过的本机路径。

UE commandlet 命令模板:

```powershell
$runId = "for31_unreal_contract_rename_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$env:FORGEUE_RUN_FOLDER = "D:/UnrealProjects/ForgeUEDemo/Content/Generated/$runId"
& "E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
  "D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject" `
  "-ExecutePythonScript=D:/ClaudeProject/ForgeUE_codex/ue_scripts/a1_run.py" `
  -stdout -unattended -nopause
```

Godot4 命令路径:

```powershell
$env:GODOT4_EXE = "E:/Godot/Godot_v4.6.2/Godot_v4.6.2-stable_win64_console.exe"
```

运行与 `demo_artifacts/2026-05-24/adhoc/godot4_headless/engine_bridge_godot4_l2_20260524_091408/godot4_headless_validation.md` 相同的 minimal Godot4 L2 fixture pattern。

如果任一 engine 命令无法运行,记录精确失败原因,不要宣称本变更的 L2 已通过。

- [ ] **步骤 5: 写入验证证据**

创建 `demo_artifacts/2026-05-24/adhoc/for31_unreal_contract_rename/verification.md`,内容为:

```markdown
# FOR-31 验证证据

日期: 2026-05-24

## 范围

- 主实现 package: `framework.engine_bridge.unreal.contract`
- Legacy alias: `framework.ue_bridge`
- Linear: `FOR-31`

## 命令

| command | result |
| --- | --- |
| 步骤 1 的 Focused Unreal/Godot contract pytest command | 从终端输出复制精确 pytest summary line。 |
| 步骤 2 的 Run-comparison fence pytest command | 从终端输出复制精确 pytest summary line。 |
| `python -m pytest -q` | 从终端输出复制精确 pytest summary line。 |

## L2

- UE commandlet: 记录 `passed`、`not run` 或 `failed`,并附具体 command log path 或失败消息。
- Godot4 headless: 记录 `passed`、`not run` 或 `failed`,并附具体 command log path 或失败消息。

## 备注

- `framework.ue_bridge` 保持为 compatibility alias。
- `Godot4Adapter` 不依赖 Unreal contract。
```

- [ ] **步骤 6: 更新 Linear**

使用 Linear MCP:

```text
Issue: FOR-31
Comment body:
FOR-31 本地实现已完成。

Evidence:
- Focused pytest: 从 verification evidence 复制精确 summary line。
- Full pytest: 从 verification evidence 复制精确 summary line。
- Verification file: demo_artifacts/2026-05-24/adhoc/for31_unreal_contract_rename/verification.md
- L2 status: 从 verification evidence 复制精确 UE 和 Godot4 status lines。

Backlog:
- LR-0143 已从 docs/backlog/active.md 移到 docs/backlog/archived.md。
```

只有在分支工作流满足 merge/push policy 后,才更新状态。

- [ ] **步骤 7: 确认最终 tracked state**

不要把 ignored `demo_artifacts` 文件加入 git。只提交 tracked docs/code/test 变更:

```bash
git status --short --ignored=matching
git log --oneline --max-count=8
```

预期: 没有 uncommitted tracked files。Evidence 保持 ignored,位于 `demo_artifacts` 下。
