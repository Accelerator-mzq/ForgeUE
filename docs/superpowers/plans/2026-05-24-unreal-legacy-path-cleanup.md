# FOR-32 Unreal Legacy Path Cleanup 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. If the user explicitly asks for Subagent-Driven execution, use `superpowers:subagent-driven-development` instead. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 Unreal 侧 legacy 路径收敛到 `framework.engine_bridge.unreal.contract` + `engine_scripts/unreal/`,并输出旧路径人工删除清单。

**Architecture:** `engine_scripts/unreal/` 成为 UE Editor / commandlet Python 脚本当前入口,继续保持不依赖 `framework.*`。`src/framework/ue_bridge/` 与 `ue_scripts/` 不由 Codex 删除,但当前代码、测试和文档入口全部切离旧路径;旧路径列入人工删除清单。

**Tech Stack:** Python 3.12, pytest, UnrealEditor-Cmd.exe commandlet, Godot 4.x headless import, Markdown docs。

---

## 文件结构

- Create: `engine_scripts/unreal/a1_run.py`
- Create: `engine_scripts/unreal/run_import.py`
- Create: `engine_scripts/unreal/manifest_reader.py`
- Create: `engine_scripts/unreal/evidence_writer.py`
- Create: `engine_scripts/unreal/domain_texture.py`
- Create: `engine_scripts/unreal/domain_mesh.py`
- Create: `engine_scripts/unreal/domain_audio.py`
- Create: `engine_scripts/unreal/domain_material.py`
- Create: `engine_scripts/unreal/domain_video.py`
- Create: `tests/unit/test_unreal_engine_scripts_path.py`
- Modify: `tests/unit/test_domain_video_no_copy.py`
- Modify: `tests/unit/test_evidence_writer_skip_reason.py`
- Modify: `tests/unit/test_run_import_skipped_filter.py`
- Modify: `tests/integration/test_p4_ue_manifest_only.py`
- Modify: `tests/unit/test_unreal_contract_package.py`
- Modify: `tests/unit/test_ue_bridge.py`
- Modify: `src/framework/engine_bridge/unreal/contract/__init__.py`
- Modify: `src/framework/comparison/cli.py`
- Modify: README / SRS / HLD / LLD / test_spec / acceptance_report / contracts / backlog / CHANGELOG
- Not deleted by Codex: `src/framework/ue_bridge/`, `ue_scripts/`

---

## 任务 1: 添加新 UE engine scripts 路径 fence

**Files:**
- Create: `tests/unit/test_unreal_engine_scripts_path.py`

- [ ] **步骤 1: 写 failing tests**

```python
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_SCRIPTS_DIR = REPO_ROOT / "engine_scripts" / "unreal"
EXPECTED_SCRIPT_NAMES = {
    "a1_run.py",
    "domain_audio.py",
    "domain_material.py",
    "domain_mesh.py",
    "domain_texture.py",
    "domain_video.py",
    "evidence_writer.py",
    "manifest_reader.py",
    "run_import.py",
}


def test_engine_scripts_unreal_directory_contains_expected_entrypoints():
    assert ENGINE_SCRIPTS_DIR.is_dir()
    actual = {path.name for path in ENGINE_SCRIPTS_DIR.glob("*.py")}
    assert EXPECTED_SCRIPT_NAMES <= actual


def test_engine_scripts_unreal_do_not_import_framework_package():
    offenders: list[str] = []
    for path in ENGINE_SCRIPTS_DIR.glob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import framework") or stripped.startswith("from framework"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}:{line}")
    assert offenders == []


def test_engine_scripts_unreal_a1_run_docstring_uses_new_path():
    source = (ENGINE_SCRIPTS_DIR / "a1_run.py").read_text(encoding="utf-8")
    assert "engine_scripts" in source
    assert "ue_scripts" not in source
```

- [ ] **步骤 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/unit/test_unreal_engine_scripts_path.py -q
```

Expected: fails because `engine_scripts/unreal/` does not exist yet.

---

## 任务 2: 创建 `engine_scripts/unreal/` 当前脚本入口

**Files:**
- Create: `engine_scripts/unreal/*.py`

- [ ] **步骤 1: 复制当前 UE-side scripts 到新路径**

Run:

```powershell
New-Item -ItemType Directory -Force -Path engine_scripts/unreal | Out-Null
Copy-Item ue_scripts/*.py engine_scripts/unreal/
```

- [ ] **步骤 2: 修改新路径中的文档字符串**

Edit:

- `engine_scripts/unreal/a1_run.py`:示例路径改为 `engine_scripts/unreal/a1_run.py`。
- `engine_scripts/unreal/run_import.py`:Console 示例改为 `engine_scripts/unreal/run_import.py`。
- `engine_scripts/unreal/domain_video.py`:NFR-PORT-003 文案改为 `engine_scripts/unreal/ MUST NOT import framework.*`。
- `engine_scripts/unreal/evidence_writer.py`:把旧 `framework/ue_bridge/evidence.py` 描述改成 `framework/engine_bridge/unreal/contract/evidence.py`。

- [ ] **步骤 3: 运行新路径 fence**

Run:

```powershell
python -m pytest tests/unit/test_unreal_engine_scripts_path.py -q
```

Expected: `3 passed`.

- [ ] **步骤 4: 提交**

```powershell
git add engine_scripts/unreal tests/unit/test_unreal_engine_scripts_path.py
git commit -m "test: add unreal engine scripts path fences"
```

---

## 任务 3: 切换 UE-side 单测和集成测试到新路径

**Files:**
- Modify: `tests/unit/test_domain_video_no_copy.py`
- Modify: `tests/unit/test_evidence_writer_skip_reason.py`
- Modify: `tests/unit/test_run_import_skipped_filter.py`
- Modify: `tests/integration/test_p4_ue_manifest_only.py`

- [ ] **步骤 1: 替换测试 helper 路径**

Mechanical replacements:

```text
Path(__file__).resolve().parent.parent.parent / "ue_scripts"
→ Path(__file__).resolve().parents[2] / "engine_scripts" / "unreal"

Path(__file__).parents[2] / "ue_scripts"
→ Path(__file__).parents[2] / "engine_scripts" / "unreal"
```

中文注释 / docstring 中的“加 ue_scripts/ 到 sys.path”改为“加 engine_scripts/unreal/ 到 sys.path”。

- [ ] **步骤 2: 跑聚焦测试**

Run:

```powershell
python -m pytest tests/unit/test_domain_video_no_copy.py tests/unit/test_evidence_writer_skip_reason.py tests/unit/test_run_import_skipped_filter.py tests/integration/test_p4_ue_manifest_only.py -q
```

Expected: pass; skips only来自既有 end-to-end fixture skip。

- [ ] **步骤 3: 提交**

```powershell
git add tests/unit/test_domain_video_no_copy.py tests/unit/test_evidence_writer_skip_reason.py tests/unit/test_run_import_skipped_filter.py tests/integration/test_p4_ue_manifest_only.py
git commit -m "test: use unreal engine scripts path"
```

---

## 任务 4: 收敛 `framework.ue_bridge` 当前契约引用

**Files:**
- Modify: `tests/unit/test_unreal_contract_package.py`
- Modify: `tests/unit/test_ue_bridge.py`
- Modify: `src/framework/engine_bridge/unreal/contract/__init__.py`
- Modify: `src/framework/comparison/cli.py`

- [ ] **步骤 1: 移除测试中的 legacy import 依赖**

In `tests/unit/test_unreal_contract_package.py`, replace the legacy alias test with a current-path-only fence:

```python
def test_unreal_contract_public_imports_use_current_package():
    from framework.engine_bridge.unreal.contract import build_manifest
    from framework.engine_bridge.unreal.contract.evidence import new_evidence_id
    from framework.engine_bridge.unreal.contract.import_plan_builder import _IMPORT_OP_KIND
    from framework.engine_bridge.unreal.contract.manifest_builder import _KIND_MAP

    assert callable(build_manifest)
    assert new_evidence_id().startswith("ev_")
    assert _IMPORT_OP_KIND["texture"] == "import_texture"
    assert ("image", "png") in _KIND_MAP
```

Do not import `framework.ue_bridge` from current tests.

- [ ] **步骤 2: 更新当前 contract docstrings**

`src/framework/engine_bridge/unreal/contract/__init__.py`:

```python
"""framework.engine_bridge.unreal 使用的 Unreal contract package。

中文注释:这里是 Unreal manifest-only 文件契约的主实现路径。
旧 `framework.ue_bridge` 目录仅作为 FOR-32 人工删除清单中的 legacy path 保留,
新代码不得依赖它。
"""
```

`tests/unit/test_ue_bridge.py` 顶部 docstring 改成“历史文件名保留,测试目标是 Unreal contract 当前路径”。

- [ ] **步骤 3: 更新 run-comparison docstring**

`src/framework/comparison/cli.py` forbidden 描述改为同时列出:

```text
`framework.review_engine` / `framework.ue_bridge` legacy prefix /
`framework.engine_bridge.unreal.contract` / `framework.workflows`
```

- [ ] **步骤 4: 跑聚焦测试**

Run:

```powershell
python -m pytest tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py -q
```

Expected: pass.

- [ ] **步骤 5: 提交**

```powershell
git add tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py src/framework/engine_bridge/unreal/contract/__init__.py src/framework/comparison/cli.py
git commit -m "test: remove current ue_bridge alias dependency"
```

---

## 任务 5: 同步当前文档与 backlog

**Files:**
- Modify: `README.md`
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/design/HLD.md`
- Modify: `docs/design/LLD.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Modify: `docs/contracts/artifact-contract/spec.md`
- Modify: `docs/contracts/engine-export-bridge/spec.md`
- Modify: `docs/contracts/ue-export-bridge/spec.md`
- Modify: `docs/contracts/examples-and-acceptance/spec.md`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`
- Modify: `CHANGELOG.md`

- [ ] **步骤 1: 当前路径替换**

Current docs use:

```text
engine_scripts/unreal/
engine_scripts/unreal/a1_run.py
engine_scripts/unreal/run_import.py
```

Historical archive docs remain unchanged.

- [ ] **步骤 2: `framework.ue_bridge` 文案收敛**

Current docs should say:

```text
Unreal contract 主实现位于 `framework.engine_bridge.unreal.contract`。
`src/framework/ue_bridge/` 是 FOR-32 人工删除清单中的 legacy path,不再是当前契约入口。
```

- [ ] **步骤 3: backlog 结账**

Move `LR-0144` from `docs/backlog/active.md` to `docs/backlog/archived.md` after implementation verification.

Archived tombstone content:

```markdown
## 2026-05-24 FOR-32 completion

### `LR-0144` **unreal-legacy-path-cleanup Unreal legacy 路径命名收敛**

- **new_status**: completed
- **reason**: 当前 UE-side 脚本入口迁到 `engine_scripts/unreal/`;当前契约和测试不再依赖 `framework.ue_bridge`;旧路径按项目纪律列入人工删除清单。
- **evidence**: `engine_scripts/unreal/`, `tests/unit/test_unreal_engine_scripts_path.py`, focused pytest, full pytest, real UE commandlet, Godot4 L2/no-impact evidence.
- **manual_delete_list**: `src/framework/ue_bridge/`, `ue_scripts/`
- **archived_by**: FOR-32 unreal-legacy-path-cleanup 2026-05-24
```

- [ ] **步骤 4: 跑文档 grep 验证**

Run:

```powershell
rg -n "ue_scripts|framework\\.ue_bridge" README.md docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts docs/backlog/active.md CHANGELOG.md -S
```

Expected: only historical CHANGELOG entries, backlog archived tombstones, or explicit manual-delete / legacy-forbidden notes remain.

- [ ] **步骤 5: 提交**

```powershell
git add README.md docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts/artifact-contract/spec.md docs/contracts/engine-export-bridge/spec.md docs/contracts/ue-export-bridge/spec.md docs/contracts/examples-and-acceptance/spec.md docs/backlog/active.md docs/backlog/archived.md CHANGELOG.md
git commit -m "docs: sync unreal legacy path cleanup"
```

---

## 任务 6: 最终验证与证据

**Files:**
- Create ignored evidence: `demo_artifacts/2026-05-24/adhoc/for32_unreal_legacy_path_cleanup/verification.md`

- [ ] **步骤 1: 跑聚焦测试**

Run:

```powershell
python -m pytest tests/unit/test_unreal_engine_scripts_path.py tests/unit/test_unreal_contract_package.py tests/unit/test_ue_bridge.py tests/unit/test_domain_video_no_copy.py tests/unit/test_evidence_writer_skip_reason.py tests/unit/test_run_import_skipped_filter.py tests/integration/test_p4_ue_manifest_only.py tests/unit/test_godot4_adapter.py -q
```

Expected: pass.

- [ ] **步骤 2: 跑 run-comparison fence**

Run:

```powershell
python -m pytest tests/unit/test_run_comparison_cli.py tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_models.py tests/unit/test_run_comparison_diff_engine.py tests/unit/test_run_comparison_reporter.py -q
```

Expected: pass.

- [ ] **步骤 3: 跑全量测试**

Run:

```powershell
python -m pytest -q
```

Expected: pass;精确 pass/skip 写入 evidence。

- [ ] **步骤 4: 跑真实 UE commandlet**

Use new script path:

```powershell
$runId = "for32_unreal_legacy_path_cleanup_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$env:FORGEUE_RUN_FOLDER = "D:/UnrealProjects/ForgeUEDemo/Content/Generated/$runId"
& "E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
  "D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject" `
  "-ExecutePythonScript=D:/ClaudeProject/ForgeUE_codex/engine_scripts/unreal/a1_run.py" `
  -stdout -unattended -nopause
```

Expected: exit code `0`; evidence has `drop_file`, `create_folder`, `import_texture` success; `.uasset` exists.

- [ ] **步骤 5: 跑 Godot4 no-regression smoke**

Run existing Godot4 headless L2 pattern with:

```powershell
$env:GODOT4_EXE = "E:/Godot/Godot_v4.6.2/Godot_v4.6.2-stable_win64_console.exe"
```

Expected: staged PNG, `.import`, `.godot/imported`, and `godot_import` success.

- [ ] **步骤 6: 写 evidence**

Create `demo_artifacts/2026-05-24/adhoc/for32_unreal_legacy_path_cleanup/verification.md` with:

```markdown
# FOR-32 验证证据

## Commands
- Focused pytest: copy the exact pytest summary line from step 1.
- Run-comparison pytest: copy the exact pytest summary line from step 2.
- Full pytest: copy the exact pytest summary line from step 3.
- git diff --check: exit code 0

## L2
- UE commandlet: record passed, failed, or blocked-user-environment plus the log path.
- Godot4 headless: record passed, failed, or blocked-user-environment plus the log path.

## Manual Delete List
- `src/framework/ue_bridge/`
- `ue_scripts/`
```

- [ ] **步骤 7: Linear 同步**

Comment on `FOR-32` with evidence paths and verification summaries. Only set Done after PR merge.
