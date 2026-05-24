# Unreal Bridge Package Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Unreal manifest-only contract implementation under `framework.engine_bridge.unreal.contract` while keeping `framework.ue_bridge` as a compatibility alias for one cycle.

**Architecture:** The new package becomes the canonical implementation used by production code and new tests. The old `framework.ue_bridge` package remains as thin re-export modules, so historical imports keep working without behavior changes. Godot4 stays independent from Unreal contract modules.

**Tech Stack:** Python 3.13, Pydantic models already in `framework.core.ue`, pytest, existing docs five-pack and contracts.

---

## File Structure

Create canonical Unreal contract package:

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

Keep compatibility modules:

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

Modify production imports:

```text
src/framework/engine_bridge/unreal/adapter.py
src/framework/runtime/executors/export.py
```

Modify tests:

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

Modify docs:

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

### Task 1: Add Package Boundary Tests

**Files:**
- Create: `tests/unit/test_unreal_contract_package.py`

- [ ] **Step 1: Write failing tests for the new canonical package and compatibility alias**

Create `tests/unit/test_unreal_contract_package.py`:

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

- [ ] **Step 2: Run the new tests and confirm they fail before migration**

Run:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'framework.engine_bridge.unreal.contract'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/unit/test_unreal_contract_package.py
git commit -m "test: add unreal contract package boundary fences"
```

---

### Task 2: Create Canonical Unreal Contract Package

**Files:**
- Create: `src/framework/engine_bridge/unreal/contract/__init__.py`
- Create: `src/framework/engine_bridge/unreal/contract/evidence.py`
- Create: `src/framework/engine_bridge/unreal/contract/import_plan_builder.py`
- Create: `src/framework/engine_bridge/unreal/contract/manifest_builder.py`
- Create: `src/framework/engine_bridge/unreal/contract/permission_policy.py`
- Create: `src/framework/engine_bridge/unreal/contract/inspect/__init__.py`
- Create: `src/framework/engine_bridge/unreal/contract/inspect/project.py`

- [ ] **Step 1: Copy existing implementation files to the new package**

Run:

```powershell
New-Item -ItemType Directory -Force -Path src/framework/engine_bridge/unreal/contract/inspect
Copy-Item src/framework/ue_bridge/evidence.py src/framework/engine_bridge/unreal/contract/evidence.py
Copy-Item src/framework/ue_bridge/import_plan_builder.py src/framework/engine_bridge/unreal/contract/import_plan_builder.py
Copy-Item src/framework/ue_bridge/manifest_builder.py src/framework/engine_bridge/unreal/contract/manifest_builder.py
Copy-Item src/framework/ue_bridge/permission_policy.py src/framework/engine_bridge/unreal/contract/permission_policy.py
Copy-Item src/framework/ue_bridge/inspect/project.py src/framework/engine_bridge/unreal/contract/inspect/project.py
```

- [ ] **Step 2: Replace new package `__init__.py`**

Write `src/framework/engine_bridge/unreal/contract/__init__.py`:

```python
"""Unreal contract package used by framework.engine_bridge.unreal.

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

- [ ] **Step 3: Replace new inspect package `__init__.py`**

Write `src/framework/engine_bridge/unreal/contract/inspect/__init__.py`:

```python
"""Read-only Unreal project inspection helpers."""

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

- [ ] **Step 4: Update internal import in new `permission_policy.py`**

In `src/framework/engine_bridge/unreal/contract/permission_policy.py`, replace the local import in `permission_mask_for_manifest`:

```python
from framework.engine_bridge.unreal.contract.import_plan_builder import (
    derive_required_op_kinds,
)
```

The function body stays the same.

- [ ] **Step 5: Run new package tests**

Run:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py::test_unreal_contract_new_public_surface_imports -q
```

Expected: pass for the new package import test; compatibility alias tests still fail until Task 3.

- [ ] **Step 6: Commit canonical package creation**

```bash
git add src/framework/engine_bridge/unreal/contract tests/unit/test_unreal_contract_package.py
git commit -m "refactor: add unreal contract package"
```

---

### Task 3: Convert `framework.ue_bridge` to Compatibility Shims

**Files:**
- Modify: `src/framework/ue_bridge/__init__.py`
- Modify: `src/framework/ue_bridge/evidence.py`
- Modify: `src/framework/ue_bridge/import_plan_builder.py`
- Modify: `src/framework/ue_bridge/manifest_builder.py`
- Modify: `src/framework/ue_bridge/permission_policy.py`
- Modify: `src/framework/ue_bridge/inspect/__init__.py`
- Modify: `src/framework/ue_bridge/inspect/project.py`

- [ ] **Step 1: Replace `src/framework/ue_bridge/__init__.py`**

```python
"""Compatibility alias for framework.engine_bridge.unreal.contract.

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

- [ ] **Step 2: Replace legacy `evidence.py`**

```python
"""Compatibility alias for Unreal contract evidence helpers."""

from framework.engine_bridge.unreal.contract.evidence import (
    EvidenceWriter,
    load_evidence,
    new_evidence_id,
)

__all__ = ["EvidenceWriter", "load_evidence", "new_evidence_id"]
```

- [ ] **Step 3: Replace legacy `import_plan_builder.py`**

```python
"""Compatibility alias for Unreal contract import plan builder."""

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

- [ ] **Step 4: Replace legacy `manifest_builder.py`**

```python
"""Compatibility alias for Unreal contract manifest builder."""

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

- [ ] **Step 5: Replace legacy `permission_policy.py`**

```python
"""Compatibility alias for Unreal contract permission policy."""

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

- [ ] **Step 6: Replace legacy inspect modules**

Write `src/framework/ue_bridge/inspect/__init__.py`:

```python
"""Compatibility alias for Unreal contract inspection helpers."""

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

Write `src/framework/ue_bridge/inspect/project.py`:

```python
"""Compatibility alias for Unreal contract project inspection."""

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

- [ ] **Step 7: Run compatibility tests**

Run:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py::test_legacy_ue_bridge_reexports_match_new_contract tests/unit/test_ue_bridge.py -q
```

Expected: pass.

- [ ] **Step 8: Commit compatibility shims**

```bash
git add src/framework/ue_bridge tests/unit/test_unreal_contract_package.py
git commit -m "refactor: keep ue_bridge compatibility aliases"
```

---

### Task 4: Migrate Production Imports and Core Tests

**Files:**
- Modify: `src/framework/engine_bridge/unreal/adapter.py`
- Modify: `src/framework/runtime/executors/export.py`
- Modify: `tests/unit/test_ue_bridge.py`
- Modify: `tests/unit/test_export_video_path_split.py`
- Modify: `tests/integration/test_p4_ue_manifest_only.py`

- [ ] **Step 1: Update `UnrealAdapter` imports**

Replace top-level imports in `src/framework/engine_bridge/unreal/adapter.py`:

```python
from framework.engine_bridge.unreal.contract.evidence import EvidenceWriter, new_evidence_id
from framework.engine_bridge.unreal.contract.import_plan_builder import build_import_plan
from framework.engine_bridge.unreal.contract.inspect import inspect_project, validate_manifest
from framework.engine_bridge.unreal.contract.manifest_builder import build_manifest
from framework.engine_bridge.unreal.contract.permission_policy import is_op_allowed
```

Replace the local import in the drop loop:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import derive_drop_target
```

Replace the local import in `_is_importable`:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import (
    is_manifest_importable,
)
```

- [ ] **Step 2: Update `ExportExecutor._is_importable`**

In `src/framework/runtime/executors/export.py`, replace:

```python
from framework.ue_bridge.manifest_builder import is_manifest_importable
```

with:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import (
    is_manifest_importable,
)
```

Update the nearby comment:

```python
# 兼容既有 Unreal contract;实际过滤规则仍由 manifest_builder 单一真源决定。
```

- [ ] **Step 3: Update core Unreal contract tests to use new path**

In `tests/unit/test_ue_bridge.py`, replace imports from `framework.ue_bridge` with:

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

Replace late imports:

```python
from framework.engine_bridge.unreal.contract.import_plan_builder import _IMPORT_OP_KIND  # noqa: E402
from framework.engine_bridge.unreal.contract.manifest_builder import (  # noqa: E402
    _KIND_MAP,
    _PREFIX_BY_KIND,
    _default_import_options,
)
```

- [ ] **Step 4: Update video path split tests**

In `tests/unit/test_export_video_path_split.py`, replace imports:

```python
from framework.engine_bridge.unreal.contract.manifest_builder import is_manifest_importable
from framework.engine_bridge.unreal.contract.manifest_builder import derive_drop_target  # noqa: E402
from framework.engine_bridge.unreal.contract.manifest_builder import build_manifest  # noqa: E402
```

- [ ] **Step 5: Update P4 integration imports**

In `tests/integration/test_p4_ue_manifest_only.py`, replace imports:

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

- [ ] **Step 6: Run production import tests**

Run:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/integration/test_p4_ue_manifest_only.py -q
```

Expected: pass.

- [ ] **Step 7: Commit production import migration**

```bash
git add src/framework/engine_bridge/unreal/adapter.py src/framework/runtime/executors/export.py tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/integration/test_p4_ue_manifest_only.py
git commit -m "refactor: use unreal contract package in runtime"
```

---

### Task 5: Update Run Comparison Import Fences

**Files:**
- Modify: `tests/unit/test_run_comparison_cli.py`
- Modify: `tests/unit/test_run_comparison_loader.py`
- Modify: `tests/unit/test_run_comparison_models.py`
- Modify: `tests/unit/test_run_comparison_diff_engine.py`
- Modify: `tests/unit/test_run_comparison_reporter.py`
- Modify: `docs/design/LLD.md`

- [ ] **Step 1: Update forbidden module tuples in five test files**

In each run-comparison test file, keep `framework.ue_bridge` and add the new canonical execution-layer prefix immediately after it:

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

Use the existing tuple variable name in each file; only add the new string.

- [ ] **Step 2: Update LLD import-fence prose**

In `docs/design/LLD.md`, update the run comparison import-fence paragraph to include:

```text
runtime / providers / review_engine / ue_bridge / engine_bridge.unreal.contract /
workflows / observability / server / schemas / pricing_probe
```

Also add this sentence in the same paragraph:

```text
`framework.ue_bridge` remains listed because it is a legacy compatibility alias for the same Unreal execution contract.
```

- [ ] **Step 3: Run run-comparison fence tests**

Run:

```bash
python -m pytest tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py -q
```

Expected: pass.

- [ ] **Step 4: Commit import fence updates**

```bash
git add tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py docs/design/LLD.md
git commit -m "test: fence unreal contract from comparison imports"
```

---

### Task 6: Update Authoritative Docs and Close Backlog Entry

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/design/HLD.md`
- Modify: `docs/design/LLD.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Modify: `docs/contracts/artifact-contract/spec.md`
- Modify: `docs/contracts/engine-export-bridge/spec.md`
- Modify: `docs/contracts/ue-export-bridge/spec.md`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`

- [ ] **Step 1: Update current docs to name the canonical package**

Use this wording in HLD, LLD, and contracts where the current path is described:

```text
Current Unreal contract implementation lives under
`src/framework/engine_bridge/unreal/contract/`.
`src/framework/ue_bridge/` is retained as a legacy compatibility alias for one cycle.
```

In SRS terms, keep the concept name "Unreal 文件契约", but replace implementation path references with:

```text
`framework.engine_bridge.unreal.contract`
```

- [ ] **Step 2: Update test specification**

In `docs/testing/test_spec.md`, update the Unreal contract row to:

```text
`test_ue_bridge.py` | `engine_bridge/unreal/contract/*` + `engine_bridge/unreal/adapter.py` | FR-ENGINE-003, FR-UE-001 ~ FR-UE-008 | L1,L2 | Unreal manifest-only contract、legacy `framework.ue_bridge` alias、ManifestBuilder modality 映射、PlanBuilder depends_on、Permission Phase C 默认拒绝、inspect_project / asset_exists、validate_manifest 重复路径、evidence 原子追加
```

Add `test_unreal_contract_package.py` to the Engine Bridge / Godot 4 area as the package-boundary fence.

- [ ] **Step 3: Update CHANGELOG**

Add one bullet under the current Unreleased section:

```markdown
- **FOR-31 Unreal contract package rename**: moved the canonical Unreal manifest-only contract implementation to `framework.engine_bridge.unreal.contract`; retained `framework.ue_bridge` as a compatibility alias for one cycle; updated runtime imports, run-comparison import fences, docs, and backlog/Linear tracking without changing Unreal or Godot import behavior.
```

- [ ] **Step 4: Archive LR-0143**

In `docs/backlog/active.md`:

```markdown
> 待办计 0 项(Future Work + Out of Scope;Non-Goals 不计入)。

## Future Work (0)

(无)
```

Remove the `LR-0143` line from active.

In `docs/backlog/archived.md`, add a new tombstone near other LR entries:

```markdown
### `LR-0143` **unreal-bridge-package-rename Unreal 文件契约包路径命名清理**

- **completed_on**: 2026-05-24
- **Linear**: `FOR-31`
- **summary**: Canonical Unreal manifest-only contract implementation moved to `framework.engine_bridge.unreal.contract`; `framework.ue_bridge` remains a compatibility alias for one cycle.
- **verification**: focused Unreal contract tests, run-comparison import fences, Godot4 adapter tests, and full `python -m pytest -q`.
```

- [ ] **Step 5: Run docs/backlog grep checks**

Run:

```bash
rg -n "src/framework/ue_bridge/|framework\\.ue_bridge|ue_bridge" docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts CHANGELOG.md docs/backlog
```

Expected: only current-doc references that explicitly call `framework.ue_bridge` a legacy compatibility alias, plus archive-free paths in changelog history.

- [ ] **Step 6: Commit docs and backlog updates**

```bash
git add CHANGELOG.md docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts/artifact-contract/spec.md docs/contracts/engine-export-bridge/spec.md docs/contracts/ue-export-bridge/spec.md docs/backlog/active.md docs/backlog/archived.md
git commit -m "docs: sync unreal contract package rename"
```

---

### Task 7: Final Verification and Evidence

**Files:**
- Create: `demo_artifacts/2026-05-24/adhoc/for31_unreal_contract_rename/verification.md`
- Linear: `FOR-31`

- [ ] **Step 1: Run focused verification**

Run:

```bash
python -m pytest tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py -q
```

Expected: pass.

- [ ] **Step 2: Run run-comparison fence verification**

Run:

```bash
python -m pytest tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py -q
```

Expected: pass.

- [ ] **Step 3: Run full verification**

Run:

```bash
python -m pytest -q
```

Expected: pass. Record exact pass/skip counts in evidence.

- [ ] **Step 4: Run L2 smoke checks when local engines are available**

Use existing local paths proven on 2026-05-24.

UE commandlet command template:

```powershell
$runId = "for31_unreal_contract_rename_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$env:FORGEUE_RUN_FOLDER = "D:/UnrealProjects/ForgeUEDemo/Content/Generated/$runId"
& "E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
  "D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject" `
  "-ExecutePythonScript=D:/ClaudeProject/ForgeUE_codex/ue_scripts/a1_run.py" `
  -stdout -unattended -nopause
```

Godot4 command path:

```powershell
$env:GODOT4_EXE = "E:/Godot/Godot_v4.6.2/Godot_v4.6.2-stable_win64_console.exe"
```

Run the same minimal Godot4 L2 fixture pattern used by `demo_artifacts/2026-05-24/adhoc/godot4_headless/engine_bridge_godot4_l2_20260524_091408/godot4_headless_validation.md`.

If either engine command cannot run, record the exact failure reason and do not claim that L2 passed for this change.

- [ ] **Step 5: Write verification evidence**

Create `demo_artifacts/2026-05-24/adhoc/for31_unreal_contract_rename/verification.md` with:

```markdown
# FOR-31 Verification Evidence

日期: 2026-05-24

## Scope

- Canonical package: `framework.engine_bridge.unreal.contract`
- Legacy alias: `framework.ue_bridge`
- Linear: `FOR-31`

## Commands

| command | result |
| --- | --- |
| Focused Unreal/Godot contract pytest command from Step 1 | Copy the exact pytest summary line from terminal output. |
| Run-comparison fence pytest command from Step 2 | Copy the exact pytest summary line from terminal output. |
| `python -m pytest -q` | Copy the exact pytest summary line from terminal output. |

## L2

- UE commandlet: record `passed`, `not run`, or `failed`, followed by the concrete command log path or failure message.
- Godot4 headless: record `passed`, `not run`, or `failed`, followed by the concrete command log path or failure message.

## Notes

- `framework.ue_bridge` remains as compatibility alias.
- `Godot4Adapter` has no Unreal contract dependency.
```

- [ ] **Step 6: Update Linear**

Use Linear MCP:

```text
Issue: FOR-31
Comment body:
FOR-31 implementation completed locally.

Evidence:
- Focused pytest: copy the exact summary line from verification evidence.
- Full pytest: copy the exact summary line from verification evidence.
- Verification file: demo_artifacts/2026-05-24/adhoc/for31_unreal_contract_rename/verification.md
- L2 status: copy the exact UE and Godot4 status lines from verification evidence.

Backlog:
- LR-0143 moved from docs/backlog/active.md to docs/backlog/archived.md.
```

Set state only after merge/push policy is satisfied by the branch workflow.

- [ ] **Step 7: Confirm final tracked state**

Do not add ignored `demo_artifacts` files to git. Commit only tracked docs/code/test changes:

```bash
git status --short --ignored=matching
git log --oneline --max-count=8
```

Expected: no uncommitted tracked files. Evidence remains ignored under `demo_artifacts`.
