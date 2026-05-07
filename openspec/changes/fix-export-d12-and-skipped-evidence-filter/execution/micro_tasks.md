---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md
  - design.md
  - execution/execution_plan.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-07T19:35:00Z
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-07T18:25:00Z
---

# fix-export-d12-and-skipped-evidence-filter Micro-tasks

> Per-task TDD 步骤 + actual code + commit 指引。沿 ForgeUE protocol(`/forgeue:change-apply-subagent`):Phase A/B/C 派 implementer + spec_review + code_quality_review subagent;Phase D / E 走 controller 主流程 direct(doc sync 是单 subagent doc-sync type;verify/review/finish 是命令链 controller)。每 sub-task 走 red → green → commit;commit message 含 `tasks.md#X.Y` anchor + subagent evidence ref(若派 subagent)。

## P0. Baseline + dispatch 准备

### tasks.md#P0.1 跑 baseline pytest

- [ ] 跑 `python -m pytest -q` 期望基线绿(无 pre-existing fail 计入回归基线)
- [ ] 若 fail → check working tree;不动其他 active change

### tasks.md#P0.2 启动状态查询

- [ ] `python tools/forgeue_finish_gate.py --change fix-export-d12-and-skipped-evidence-filter --json`(预期 PASS — 当前无 evidence drift)
- [ ] `python tools/forgeue_change_state.py --change fix-export-d12-and-skipped-evidence-filter --json`(预期 state: S2)

### tasks.md#P0.3 写 verification/baseline.md

- [ ] 落 `openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/baseline.md`,12-key audit frontmatter + 实测 pytest 基线 PASS + finish_gate / change_state 启动 JSON

### Commit P0

```bash
git add openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/baseline.md
git commit -m "$(cat <<'EOF'
feat(forgeue): fix-export-d12-and-skipped-evidence-filter P0 — baseline

Tasks: tasks.md#P0.1 P0.2 P0.3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase A — F-C Framework schema + drop loop

> Owner: subagent dispatch(implementer + spec_review + code_quality_review per micro-task);Type: implementation_type_1(framework code 改;`src/framework/core/` + `src/framework/ue_bridge/` + `src/framework/runtime/executors/`)

### A.1 Evidence schema 加 `skip_reason` field(tasks.md#1.1)

#### A.1.1 写 fence test(red)

- [ ] Create `tests/unit/test_evidence_skip_reason.py`,加 case `test_evidence_load_legacy_no_skip_reason_field_defaults_to_none`:
```python
def test_evidence_load_legacy_no_skip_reason_field_defaults_to_none():
    """旧 evidence.json fixture(无 skip_reason 字段)Pydantic load 时默认 None"""
    from framework.core.ue import Evidence
    legacy = {"evidence_item_id": "ev_1", "op_id": "op_drop_X",
              "kind": "drop_file", "status": "success",
              "source_uri": "/foo/bar.png",
              "target_object_path": "Content/Generated/r/bar.png"}
    ev = Evidence.model_validate(legacy)
    assert ev.skip_reason is None
```

#### A.1.2 跑 test 应 fail

- [ ] `python -m pytest tests/unit/test_evidence_skip_reason.py::test_evidence_load_legacy_no_skip_reason_field_defaults_to_none -v` 期望 FAIL(`AttributeError: 'Evidence' object has no attribute 'skip_reason'` 或 Pydantic strict 失败)

#### A.1.3 实施 schema 改动(green)

- [ ] Modify `src/framework/core/ue.py:86-97`,`Evidence` class 加字段:
```python
class Evidence(BaseModel):
    """Per-operation execution proof (§B.11, E.3)."""

    evidence_item_id: str
    op_id: str
    kind: str
    status: Literal["success", "failed", "skipped"]
    # OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase A:
    # skip_reason 区分 framework PermissionPolicy denied vs UE-side no-handler
    # skipped(沿 D3 + design.md §Decisions D3 + spec.md "Evidence schema includes
    # `skip_reason` enum field" Requirement);default None 后向兼容旧 evidence
    skip_reason: Literal["permission_denied", "no_handler"] | None = None
    source_uri: str | None = None
    target_object_path: str | None = None
    log_ref: str | None = None
    error: str | None = None
```

#### A.1.4 跑 test 应 PASS

- [ ] `python -m pytest tests/unit/test_evidence_skip_reason.py::test_evidence_load_legacy_no_skip_reason_field_defaults_to_none -v` 期望 PASS

#### A.1.5 加余下 2 个 case(test_export_permission_denied_evidence_carries_skip_reason / test_evidence_dump_excludes_none_skip_reason)

- [ ] Append to `tests/unit/test_evidence_skip_reason.py`:
```python
def test_evidence_dump_excludes_none_skip_reason():
    """skip_reason=None 时 model_dump_json 输出 null(Pydantic 默认行为;
    若用 exclude_none=True 则字段 omitted)"""
    from framework.core.ue import Evidence
    import json
    ev = Evidence(evidence_item_id="ev_1", op_id="op_X",
                  kind="drop_file", status="success")
    dumped = json.loads(ev.model_dump_json())
    # Pydantic v2 默认行为:None 字段输出 null
    assert dumped.get("skip_reason") is None

def test_export_permission_denied_evidence_carries_skip_reason():
    """ExportExecutor permission mask emit 路径必须带 skip_reason="permission_denied".
    本 case 在 A.5 ExportExecutor permission emit 修改后才 PASS,先 declare red"""
    # 略 — 在 A.5 微任务后跑;test 内部走 ExportExecutor.execute 在 PermissionPolicy()
    # 默认下创建 material 触发 permission denied,assert evidence skip_reason=permission_denied
    pytest.skip("blocked on A.5")
```

#### A.1.6 commit

```bash
git add src/framework/core/ue.py tests/unit/test_evidence_skip_reason.py
git commit -m "feat(forgeue): A.1 Evidence.skip_reason field + legacy compat fence

Tasks: tasks.md#1.1 1.10(partial)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### A.2 `is_manifest_importable` helper + `_is_importable` 收敛(tasks.md#1.2 1.3 + D10)

#### A.2.1 写 fence test(red)

- [ ] Create `tests/unit/test_export_video_path_split.py`(此文件后续多个 case 都 append),加 case `test_is_manifest_importable_requires_file_payload_kind`:
```python
import pytest
from pathlib import Path
from framework.core.artifact import Artifact, ArtifactType, PayloadRef, PayloadKind, Lineage, ProducerRef
from framework.ue_bridge.manifest_builder import is_manifest_importable

def _mkart(modality, shape, payload_kind=PayloadKind.file, file_path="/tmp/x.png"):
    return Artifact(
        artifact_id="a_1",
        artifact_type=ArtifactType(modality=modality, shape=shape, internal=f"{modality}.{shape}"),
        payload_ref=PayloadRef(kind=payload_kind, file_path=file_path) if payload_kind == PayloadKind.file else PayloadRef(kind=payload_kind, inline_blob=b"x"),
        lineage=Lineage(producers=[ProducerRef(producer_kind="step", producer_id="s_1")]),
        metadata={},
    )

def test_is_manifest_importable_requires_file_payload_kind():
    """payload.kind != file 时返 False(不论 modality / shape)"""
    art = _mkart("image", "png", payload_kind=PayloadKind.inline_blob)
    assert is_manifest_importable(art) is False

def test_is_manifest_importable_returns_false_for_unmapped_shape():
    """video.webm 在 _KIND_MAP miss → False(沿 D10 _KIND_MAP 单一真源)"""
    art = _mkart("video", "webm")
    assert is_manifest_importable(art) is False

def test_is_manifest_importable_returns_true_for_video_mp4():
    art = _mkart("video", "mp4")
    assert is_manifest_importable(art) is True
```

#### A.2.2 跑 test 应 fail

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py::test_is_manifest_importable -v -k is_manifest_importable` 期望 FAIL(ImportError:no `is_manifest_importable`)

#### A.2.3 实施 `is_manifest_importable`(green)

- [ ] Modify `src/framework/ue_bridge/manifest_builder.py`,在 `_KIND_MAP` 定义之后加 public helper:
```python
def is_manifest_importable(art: Artifact) -> bool:
    """art 是否在 _KIND_MAP 命中 — manifest 能力的单一真源.

    Used by `ExportExecutor._is_importable` AND `manifest_builder.build_manifest`
    to keep import filtering consistent across modules(沿 OpenSpec change
    fix-export-d12-and-skipped-evidence-filter design D10 — round 1 codex F1
    修订:消除 modality whitelist 与 _KIND_MAP shape map 双源).
    """
    if art.payload_ref.kind != PayloadKind.file:
        return False
    return _KIND_MAP.get((art.artifact_type.modality, art.artifact_type.shape)) is not None
```

#### A.2.4 收敛 `_is_importable`(green)

- [ ] Modify `src/framework/runtime/executors/export.py:212-220`:
```python
@staticmethod
def _is_importable(art: Artifact) -> bool:
    # OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase A:
    # 收敛到 _KIND_MAP 单一真源(沿 design D10 + round 1 codex F1 修订);
    # 旧 modality-only whitelist 与 manifest_builder shape-aware filter 不一致,
    # 导致 unsupported shape(如 video.webm)在新 derive_drop_target 路径下 crash export
    from framework.ue_bridge.manifest_builder import is_manifest_importable
    return is_manifest_importable(art)
```

#### A.2.5 跑 test 应 PASS

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py -v -k is_manifest_importable` 期望 3 PASS

#### A.2.6 commit

```bash
git add src/framework/ue_bridge/manifest_builder.py src/framework/runtime/executors/export.py tests/unit/test_export_video_path_split.py
git commit -m "feat(forgeue): A.2 is_manifest_importable single source + _is_importable converge

Tasks: tasks.md#1.2 1.3 1.9(partial)
round 1 codex F1 inline writeback (D10)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### A.3 `derive_drop_target` helper(tasks.md#1.4)

#### A.3.1 写 fence test(red)

- [ ] Append to `tests/unit/test_export_video_path_split.py`:
```python
from framework.core.ue import UEOutputTarget
from framework.ue_bridge.manifest_builder import derive_drop_target

def _mktarget(project_root="/tmp/proj", policy="gdd_preferred_then_house_rules"):
    return UEOutputTarget(
        project_name="P", project_root=project_root, asset_root="/Game/Generated/T",
        asset_naming_policy=policy,
    )

def test_derive_drop_target_video_mp4():
    art = _mkart("video", "mp4", file_path="/tmp/run/abc.mp4")
    art.metadata = {"display_name": "OpeningScene"}
    target = _mktarget()
    drop_dir, filename = derive_drop_target(art, target=target, run_id="run_a")
    assert drop_dir == Path("/tmp/proj/Content/Movies/run_a")
    # MS_<base> 由 _derive_ue_name 计算;期望 MS_OpeningScene
    assert filename == "MS_OpeningScene.mp4"

def test_derive_drop_target_preserves_raw_filename_for_non_video():
    """round 1 codex F2 fence:image/audio/mesh/material 保 raw artifact basename"""
    target = _mktarget()
    cases = [
        ("image", "png", "/tmp/run/def456.png"),
        ("audio", "flac", "/tmp/run/ghi.flac"),
        ("mesh", "glb", "/tmp/run/jkl.glb"),
    ]
    for modality, shape, fp in cases:
        art = _mkart(modality, shape, file_path=fp)
        art.metadata = {"display_name": "ShouldNotAffectFilename"}
        drop_dir, filename = derive_drop_target(art, target=target, run_id="run_a")
        assert drop_dir == Path("/tmp/proj/Content/Generated/run_a")
        assert filename == Path(fp).name  # raw basename, not <ue_name>.<ext>

def test_derive_drop_target_falls_through_for_unmapped_shape():
    """round 1 codex F1 defensive fence:_KIND_MAP miss 不 raise,fall through"""
    art = _mkart("video", "webm", file_path="/tmp/run/x.webm")
    target = _mktarget()
    drop_dir, filename = derive_drop_target(art, target=target, run_id="run_a")
    # fall through 到非 video 分支(D10 单源,正常调用 caller 已 filter,defensive only)
    assert drop_dir == Path("/tmp/proj/Content/Generated/run_a")
    assert filename == "x.webm"  # raw basename
```

#### A.3.2 跑 test 应 fail

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py -v -k derive_drop_target` 期望 FAIL(ImportError)

#### A.3.3 实施 `derive_drop_target`(green)

- [ ] Modify `src/framework/ue_bridge/manifest_builder.py`,在 `is_manifest_importable` 之后加:
```python
def derive_drop_target(
    art: Artifact, *, target: UEOutputTarget, run_id: str,
) -> tuple[Path, str]:
    """返回 (drop_dir, target_filename) — D12 路径分流 + UE naming for video,
    raw basename for non-video.

    Precondition: caller MUST 用 `is_manifest_importable(art)` filter;
    若 _KIND_MAP miss(defensive)→ fall through 非 video 分支返 raw basename,不 raise
    (沿 design D10 + round 1 codex F1 修订).

    - video + `_KIND_MAP[(modality, shape)] == "file_media_source"` → (Movies/<run_id>, MS_<base>.mp4)
    - 其他 importable modality(image/audio/mesh/material)→ (Generated/<run_id>, raw_basename)
        其中 raw_basename = Path(art.payload_ref.file_path).name(沿 design D1 修订:
        round 1 codex F2 — 非 video 不改 filename, 避免 NG1 超范围 + 同 display_name collision)
    """
    project_root = Path(target.project_root)
    kind = _KIND_MAP.get((art.artifact_type.modality, art.artifact_type.shape))
    if kind == "file_media_source" and art.artifact_type.modality == "video":
        ue_name = _derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)
        ext = Path(art.payload_ref.file_path).suffix or ".mp4"
        return (
            project_root / "Content" / "Movies" / run_id,
            f"{ue_name}{ext}",
        )
    # 非 video importable + defensive _KIND_MAP miss fall-through(round 1 codex F1)
    return (
        project_root / "Content" / "Generated" / run_id,
        Path(art.payload_ref.file_path).name,  # raw basename 沿 D1 修订
    )
```

#### A.3.4 跑 test 应 PASS

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py -v -k derive_drop_target` 期望 3 PASS

#### A.3.5 commit

```bash
git add src/framework/ue_bridge/manifest_builder.py tests/unit/test_export_video_path_split.py
git commit -m "feat(forgeue): A.3 derive_drop_target helper + raw basename for non-video

Tasks: tasks.md#1.4 1.9(partial)
round 1 codex F1+F2+F4 inline writeback (D1+D2+D10)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### A.4 `build_manifest` 用 `derive_drop_target` 计算 source_uri + filter consolidate(tasks.md#1.5)

#### A.4.1 写 fence test(red)

- [ ] Append `test_manifest_entry_source_uri_matches_framework_drop_path`(单源契约)+ `test_manifest_silent_skip_unmapped_shape_consistent_with_export`(D10 一致性)。Test 走 `build_manifest(...)` 检查 entries source_uri 字段。

#### A.4.2 实施 `build_manifest` 改写(green)

- [ ] Modify `src/framework/ue_bridge/manifest_builder.py::build_manifest`:
  - L98-104 silent skip 改:
```python
for art in artifacts:
    if selected_artifact_ids is not None and art.artifact_id not in selected_artifact_ids:
        continue
    if not is_manifest_importable(art):
        # OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase A 修订:
        # filter 收敛到 is_manifest_importable 单一真源(沿 design D10 + round 1 codex F1)
        continue
    if art.payload_ref.kind != PayloadKind.file:
        # 双重防御 — is_manifest_importable 已含 file kind check,但保留兜底
        errors.append(...)
        continue
    kind = _KIND_MAP[(art.artifact_type.modality, art.artifact_type.shape)]  # 已确认 not None
    ue_name = _derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)
    # source_uri 从 derive_drop_target 计算(沿 design D1 修订 — 单源契约)
    drop_dir, filename = derive_drop_target(art, target=target, run_id=run_id)
    # source_uri = drop_dir 相对 project_root 的 POSIX 路径 + filename
    drop_relative = drop_dir.relative_to(Path(target.project_root)).as_posix()
    source_uri = f"{drop_relative}/{filename}"
    target_obj_path = f"{run_asset_folder}/{ue_name}"
    target_pkg_path = target_obj_path
    entries.append(UEAssetEntry(
        ...
        source_uri=source_uri,  # 例:"Content/Movies/<run_id>/MS_<base>.mp4" 或 "Content/Generated/<run_id>/<raw_basename>"
        ...
    ))
```

#### A.4.3 跑 test 应 PASS + 既有 test 不回归

- [ ] `python -m pytest tests/unit/test_ue_bridge.py tests/unit/test_export_video_path_split.py -v` 期望全 PASS

#### A.4.4 commit

```bash
git add src/framework/ue_bridge/manifest_builder.py tests/unit/test_export_video_path_split.py
git commit -m "feat(forgeue): A.4 build_manifest filter + source_uri via derive_drop_target

Tasks: tasks.md#1.5 1.9(partial)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### A.5 `ExportExecutor` drop loop + permission emit 改写(tasks.md#1.6 1.7)

#### A.5.1 写 fence test(red)

- [ ] Append `test_export_drops_video_to_content_movies_and_image_preserves_raw_filename` + `test_export_unsupported_shape_does_not_crash_drop_loop` + `test_export_permission_denied_evidence_carries_skip_reason`。

#### A.5.2 跑 test 应 fail

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py tests/unit/test_evidence_skip_reason.py -v` 期望多 FAIL

#### A.5.3 实施 drop loop + permission emit 改(green)

- [ ] Modify `src/framework/runtime/executors/export.py::ExportExecutor.execute`(L91-125 + L149-158):
```python
# L91 改:不再单一 run_folder,evidence_writer 仍用 generated_run_folder
generated_run_folder = Path(target.project_root) / "Content" / "Generated" / ctx.run.run_id
generated_run_folder.mkdir(parents=True, exist_ok=True)
evidence_writer = EvidenceWriter(path=generated_run_folder / "evidence.json")

importable = [a for a in upstream_artifacts if self._is_importable(a)]  # 已收敛到 is_manifest_importable
if approve_filter is not None:
    importable = [a for a in importable if a.artifact_id in approve_filter]

# L102-125 drop loop 改用 derive_drop_target
copied_manifest_entries_ids: set[str] = set()
file_drop_evidence: list[Evidence] = []
if not dry_run:
    for art in importable:
        src_fs = self._resolve_source_path(ctx, art)
        if src_fs is None:
            file_drop_evidence.append(Evidence(
                evidence_item_id=new_evidence_id("ev"),
                op_id=f"op_drop_{art.artifact_id}",
                kind="drop_file",
                status="failed",
                error=f"cannot resolve source file for {art.artifact_id}",
            ))
            continue
        from framework.ue_bridge.manifest_builder import derive_drop_target
        drop_dir, target_filename = derive_drop_target(
            art, target=target, run_id=ctx.run.run_id,
        )
        drop_dir.mkdir(parents=True, exist_ok=True)
        target_fs = drop_dir / target_filename
        shutil.copy2(src_fs, target_fs)
        copied_manifest_entries_ids.add(art.artifact_id)
        file_drop_evidence.append(Evidence(
            evidence_item_id=new_evidence_id("ev"),
            op_id=f"op_drop_{art.artifact_id}",
            kind="drop_file",
            status="success",
            source_uri=art.payload_ref.file_path,
            target_object_path=str(target_fs.relative_to(Path(target.project_root))),
        ))

# 既有 manifest 构建逻辑使用 generated_run_folder 沿用
run_folder = generated_run_folder  # alias 防其他逻辑(如 _persist_*)引用

# L149-158 permission denied evidence 加 skip_reason="permission_denied"
denied_evidence: list[Evidence] = []
for op in plan.operations:
    if not is_op_allowed(self._permission, op):
        denied_evidence.append(Evidence(
            evidence_item_id=new_evidence_id("ev"),
            op_id=op.op_id,
            kind=op.kind,
            status="skipped",
            skip_reason="permission_denied",  # OpenSpec change Phase A 修订
            error="PermissionPolicy does not grant this op kind",
        ))
```

#### A.5.4 审视 `_rebase_artifact_source` helper

- [ ] Read `src/framework/runtime/executors/export.py::_rebase_artifact_source`,确认改完 build_manifest 后该 helper 是否仍被调用;若 dead code 则删除并 commit
- [ ] 若仍调用,确保 source_uri 一致(本 change spec source_uri = derive_drop_target 计算结果,_rebase_artifact_source 若再 rewrite 会破坏单源)

#### A.5.5 跑 全套 test 应 PASS

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py tests/unit/test_evidence_skip_reason.py tests/unit/test_ue_bridge.py -v` 期望全 PASS

#### A.5.6 commit

```bash
git add src/framework/runtime/executors/export.py tests/unit/test_export_video_path_split.py tests/unit/test_evidence_skip_reason.py
git commit -m "feat(forgeue): A.5 ExportExecutor drop loop derive_drop_target + permission denied skip_reason

Tasks: tasks.md#1.6 1.7 1.8 1.9 1.10

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### A.6 Phase A 完整 fence sweep(tasks.md#1.9 1.10 完成)

#### A.6.1 跑 Phase A 完整 fence

- [ ] `python -m pytest tests/unit/test_export_video_path_split.py tests/unit/test_evidence_skip_reason.py -v` 期望全 PASS(共 ~9 case)
- [ ] `python -m pytest -q` 期望 baseline + 9 (新 fence 增加;无回归)

#### A.6.2 落 implementer / spec_review / code_quality_review subagent evidence

- [ ] 走 `superpowers:subagent-driven-development` 协议:每 phase A 子任务 dispatch implementer 已经完成的 incremental 修;主 controller commit 后跑 spec_review subagent + code_quality_review subagent 评审 phase A 整体 → 落 `execution/task_phaseA_implementer.md` + `task_phaseA_spec_review.md` + `task_phaseA_code_quality_review.md`(12-key frontmatter)

---

## Phase B — F-D UE 端 filter + simplify

> Owner: subagent dispatch;Type: implementation_type_1(UE-side stdlib + stub-unreal 测试)

### B.1 `evidence_writer.make_record` 加 `skip_reason` kwarg + fence(tasks.md#2.1 2.6)

#### B.1.1 写 fence test(red)

- [ ] Create `tests/unit/test_evidence_writer_skip_reason.py`:
```python
def test_make_record_with_skip_reason_appears_in_json(tmp_path):
    """make_record 加 skip_reason kwarg 后,append 到 evidence.json 该字段写入"""
    import sys; sys.path.insert(0, str(Path("ue_scripts")))
    from evidence_writer import make_record, append
    rec = make_record(op_id="op_X", kind="import_texture", status="skipped",
                     error="no UE-side handler for kind=foo",
                     skip_reason="no_handler")
    assert rec["skip_reason"] == "no_handler"

def test_make_record_without_skip_reason_yields_null_or_omitted_field():
    """legacy 调用(无 skip_reason kwarg)不写字段或字段值为 None"""
    import sys; sys.path.insert(0, str(Path("ue_scripts")))
    from evidence_writer import make_record
    rec = make_record(op_id="op_X", kind="import_texture", status="success")
    # skip_reason 在 dict 中要么不存在,要么为 None
    assert rec.get("skip_reason") is None
```

#### B.1.2 跑 test fail

- [ ] `python -m pytest tests/unit/test_evidence_writer_skip_reason.py -v` FAIL

#### B.1.3 实施 `make_record` 改(green)

- [ ] Modify `ue_scripts/evidence_writer.py::make_record`:加 optional kwarg `skip_reason: str | None = None`;序列化时若不为 None 则写入 dict。

#### B.1.4 跑 test PASS

- [ ] `python -m pytest tests/unit/test_evidence_writer_skip_reason.py -v` PASS

#### B.1.5 commit

```bash
git add ue_scripts/evidence_writer.py tests/unit/test_evidence_writer_skip_reason.py
git commit -m "feat(forgeue): B.1 evidence_writer.make_record skip_reason kwarg

Tasks: tasks.md#2.1 2.6

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### B.2 `run_import.py` filter + no-handler skip_reason(tasks.md#2.2 2.3 2.5)

#### B.2.1 写 fence test(red)

- [ ] Create `tests/unit/test_run_import_skipped_filter.py`(stub-unreal):
```python
def test_pre_skipped_only_includes_permission_denied(tmp_path, stub_unreal):
    """双 skipped entry(permission_denied vs no_handler)区分"""
    # 构 evidence.json 两条 skipped:permission_denied + no_handler
    # 调 run_import.run(...) 检查 pre_skipped_op_ids 仅含 permission_denied 那条 op_id

def test_no_handler_skipped_does_not_pre_filter(tmp_path, stub_unreal):
    """UE 端写的 no-handler skipped 不被 pre-scan 吞;若 plan 含 op 进入 dispatch"""
```

#### B.2.2 实施 `run_import.py` 改(green)

- [ ] Modify `ue_scripts/run_import.py:67-73`:
```python
pre_skipped_op_ids: set[str] = set()
try:
    import json as _json
    with open(bundle.evidence_path, "r", encoding="utf-8") as _f:
        for _ev in _json.load(_f) or []:
            if (_ev.get("status") == "skipped"
                and _ev.get("skip_reason") == "permission_denied"
                and _ev.get("op_id")):
                pre_skipped_op_ids.add(_ev["op_id"])
except Exception:
    pass
```
- [ ] Modify L89-92 no-handler append 时带 `skip_reason="no_handler"`:
```python
if handler is None:
    evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
        op_id=op["op_id"], kind=kind, status="skipped",
        error=f"no UE-side handler for kind={kind}",
        skip_reason="no_handler",
    ))
    continue
```

#### B.2.3 跑 test PASS

- [ ] `python -m pytest tests/unit/test_run_import_skipped_filter.py -v` PASS

#### B.2.4 commit

```bash
git add ue_scripts/run_import.py tests/unit/test_run_import_skipped_filter.py
git commit -m "feat(forgeue): B.2 run_import.py filter only permission_denied + no_handler emit

Tasks: tasks.md#2.2 2.3 2.5

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### B.3 `domain_video.import_video_entry` rewrite(tasks.md#2.4 2.7;round 1 codex F3 修订)

#### B.3.1 写 fence test(red)— 5 case

- [ ] Create `tests/unit/test_domain_video_no_copy.py`(stub-unreal):
```python
def test_domain_video_does_not_invoke_shutil_copy2(tmp_path, stub_unreal, monkeypatch):
    """框架已 drop;UE 端不再 copy"""
    called = []
    monkeypatch.setattr("shutil.copy2", lambda *a, **kw: called.append((a, kw)))
    # 构 entry source_uri="Content/Movies/r/MS_x.mp4" + 实测 mp4 文件存在
    # 调 import_video_entry → assert not called

def test_domain_video_file_path_derived_from_source_uri(tmp_path, stub_unreal):
    """round 1 codex F3 fence:set_editor_property('file_path', ...) value
    等于 source_uri 去 'Content/' 前缀(NOT target_object_path 反推)"""
    # entry source_uri="Content/Movies/run_a/MS_OpeningScene.mp4"
    # entry target_object_path="/Game/Generated/run_a/MS_OpeningScene"
    # call import_video_entry → stub_unreal 拦截 set_editor_property,assert
    # call args == ("file_path", "Movies/run_a/MS_OpeningScene.mp4")

def test_domain_video_rejects_non_d12_source_uri(tmp_path, stub_unreal):
    """round 1 codex F3:source_uri 不以 'Content/Movies/' 起首 → return failed"""
    # entry source_uri="Content/Generated/run/foo.mp4"(legacy 路径)
    # call → assert status="failed", error contains "D12 Movies/<run_id>/<filename>.mp4"

def test_domain_video_returns_failed_on_source_target_mismatch(tmp_path, stub_unreal):
    """round 1 codex F3:source_uri 反推 (run_id, ue_name) 与 target 反推不等 → failed"""
    # entry source_uri="Content/Movies/run_a/MS_x.mp4"
    # entry target_object_path="/Game/Generated/run_b/MS_y"
    # call → assert status="failed", error contains "mismatch"

def test_domain_video_returns_failed_when_source_mp4_missing(tmp_path, stub_unreal):
    """source_uri 物理文件不存在 → failed"""
    # entry source_uri="Content/Movies/r/MS_missing.mp4"(实际无此文件)
    # call → assert status="failed", error contains "source mp4 not found"
```

#### B.3.2 跑 test fail

- [ ] `python -m pytest tests/unit/test_domain_video_no_copy.py -v` FAIL(部分 case 当前实现碰巧 PASS,部分 fail;预期 file_path / mismatch / non-d12 这 3 个 fail)

#### B.3.3 实施 `domain_video.import_video_entry` rewrite(green)

- [ ] Modify `ue_scripts/domain_video.py:31-108`,完整 rewrite import_video_entry:
```python
def import_video_entry(entry: dict, *, project_root: str) -> dict:
    """Import a video Artifact as `unreal.FileMediaSource` `.uasset`.

    OpenSpec change fix-export-d12-and-skipped-evidence-filter B.3 修订:
    1. Framework `ExportExecutor` drop loop 已经把 mp4 写到
       `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`(D12 单源);
       本函数 NOT copy mp4 / NOT mkdir(沿 design D6 简化幅度 α)
    2. FileMediaSource.file_path 从 `entry["source_uri"]` 派生(去 Content/ 前缀;
       round 1 codex F3 修订:消除"验证一个 path / 引用另一个 path"latent design smell)
    3. Mismatch fence:source_uri 反推 (run_id, ue_name) 与 target_object_path 反推
       必须相等(round 1 codex F3:守门 manifest bug / hand-edit / re-run race)
    """
    unreal = _unreal()
    source_uri = entry["source_uri"]
    target = entry["target_object_path"]

    # source_uri D12 layout 校验
    if not source_uri.startswith("Content/Movies/"):
        return _evidence(
            entry, status="failed",
            error="source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout: " + source_uri,
        )
    relative_to_content = source_uri[len("Content/"):]  # e.g. "Movies/<run_id>/MS_<base>.mp4"
    parts = relative_to_content.split("/")
    if len(parts) != 3 or parts[0] != "Movies" or not parts[2].endswith(".mp4"):
        return _evidence(
            entry, status="failed",
            error="source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout: " + source_uri,
        )
    run_id_from_source = parts[1]
    ue_name_from_source = parts[2][:-len(".mp4")]

    # target_object_path 反推
    target_parts = target.split("/")
    ue_name_from_target = target_parts[-1]
    run_id_from_target = target_parts[-2] if len(target_parts) >= 2 else "default"

    # mismatch fence
    if (run_id_from_source != run_id_from_target
            or ue_name_from_source != ue_name_from_target):
        return _evidence(
            entry, status="failed",
            error=(f"source_uri / target_object_path mismatch: "
                   f"source=({run_id_from_source}, {ue_name_from_source}) vs "
                   f"target=({run_id_from_target}, {ue_name_from_target})"),
        )

    # 物理文件存在性检查
    source_fs = Path(project_root) / source_uri
    if not source_fs.is_file():
        return _evidence(
            entry, status="failed",
            error=f"source mp4 not found at {source_fs}",
        )

    # FileMediaSource asset 创建 + file_path
    folder = "/".join(target_parts[:-1])
    asset_name = target_parts[-1]
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.FileMediaSourceFactoryNew()
    media_source_class = unreal.FileMediaSource
    new_asset = asset_tools.create_asset(
        asset_name=asset_name, package_path=folder,
        asset_class=media_source_class, factory=factory,
    )
    if new_asset is None:
        return _evidence(
            entry, status="failed",
            error="asset_tools.create_asset returned None for FileMediaSource",
        )

    # file_path 从 source_uri 派生(round 1 codex F3 单源)
    new_asset.set_editor_property("file_path", relative_to_content)

    package = new_asset.get_outer()
    if package is not None:
        unreal.EditorAssetLibrary.save_loaded_asset(new_asset)

    return _evidence(entry, status="success", target_object_path=target)
```

#### B.3.4 跑 test PASS

- [ ] `python -m pytest tests/unit/test_domain_video_no_copy.py -v` 期望 5 PASS

#### B.3.5 commit

```bash
git add ue_scripts/domain_video.py tests/unit/test_domain_video_no_copy.py
git commit -m "feat(forgeue): B.3 domain_video file_path from source_uri + mismatch fence + delete copy

Tasks: tasks.md#2.4 2.7
round 1 codex F3 inline writeback (D6)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### B.4 Phase B 完整 fence sweep + subagent evidence

- [ ] `python -m pytest tests/unit/test_evidence_writer_skip_reason.py tests/unit/test_run_import_skipped_filter.py tests/unit/test_domain_video_no_copy.py -v` 期望全 PASS(~9 case)
- [ ] subagent evidence 落 `execution/task_phaseB_*.md`

---

## Phase C — Integration test + L2 live smoke

> Owner: implementation_type_4(integration);L2 用户 loop

### C.1 修改 `tests/integration/test_p4_ue_manifest_only.py`(tasks.md#3.1)

#### C.1.1 重命名既有 case + 加新 case

- [ ] 既有 `test_p4_domain_video_copies_mp4_to_content_movies_subdir` 重构为 `test_p4_domain_video_creates_file_media_source_uasset_without_copying_mp4_file_path_from_source_uri`(reflect new contract)
- [ ] 加 `test_p4_export_drops_video_mp4_to_content_movies_directly`(framework drop 后 mp4 已在 Movies/<run_id>/MS_<base>.mp4)
- [ ] 加 `test_p4_domain_video_returns_failed_when_mp4_missing`(防御路径)
- [ ] 加 `test_p4_domain_video_rejects_non_d12_source_uri`(round 1 codex F3 D12 layout fence)
- [ ] 加 `test_p4_domain_video_returns_failed_on_source_target_mismatch`(round 1 codex F3 mismatch fence)

#### C.1.2 跑 test PASS

- [ ] `python -m pytest tests/integration/test_p4_ue_manifest_only.py -v` 期望全 PASS

#### C.1.3 commit

```bash
git add tests/integration/test_p4_ue_manifest_only.py
git commit -m "test(forgeue): C.1 P4 integration test D12 path split + source_uri mismatch fence

Tasks: tasks.md#3.1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### C.2 L2 live smoke `comfy_local_smoke_video.json`(tasks.md#3.2)

#### C.2.1 用户开 ComfyUI 终端 + Claude 跑 framework run

- [ ] **用户操作**:终端 1 跑 `python -m factory_v3 serve`(detached,~30-90s 冷启动)
- [ ] **Claude 操作**:终端 2 export env + 跑:
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
export FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input
python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm \
    --run-id cluster2_l2_$(date +%H%M%S)
```

#### C.2.2 实证产物布局

- [ ] check `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` 存在(framework drop 写入)
- [ ] check `<project_root>/Content/Generated/<run_id>/manifest.json` + `import_plan.json` + `evidence.json` 存在
- [ ] check `<project_root>/Content/Generated/<run_id>/` 下**不**含 raw `*.mp4` 文件(F-C 修复后 mp4 不再 leak 到 Generated/)
- [ ] check evidence.json 含 framework drop entries `target_object_path` 反映实际 Movies/ 路径
- [ ] artifacts 落 `artifacts/<today>/cluster2_l2_<HHMMSS>/<artifact_id>.mp4`(framework artifact 落地不变)

#### C.2.3 落 verification/live_smoke_video.md

- [ ] 写 `verification/live_smoke_video.md`(12-key audit frontmatter + 实证截图 / 路径 / 文件大小 + run_id + ComfyUI 模型版本)

#### C.2.4 commit

```bash
git add openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/live_smoke_video.md
git commit -m "test(forgeue): C.2 L2 live smoke video — D12 path split implementations

Tasks: tasks.md#3.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### C.3(选)P4 真机 commandlet evidence(tasks.md#3.3)

- [ ] 若 user 装 UE 5.x:终端 UE Python Console 跑 `exec(open('<repo>/ue_scripts/run_import.py').read())`(指 cluster2_l2_<HHMMSS> run folder 通过 `FORGEUE_RUN_FOLDER` env)
- [ ] 实证:domain_video 不 copy + FileMediaSource asset 创建 + .uasset file_path 引用 Movies/<run_id>/MS_<base>.mp4
- [ ] 落 `verification/p4_real_ue.md`(若用户跑了)

---

## Phase D — Doc sync gate

> Owner: doc-sync subagent;Type: doc-sync(non-implementation)

### D.1-D.10 详细列表见 tasks.md 4.1-4.11

- [ ] 4.1 LLD Evidence schema 段(skip_reason field 描述)
- [ ] 4.2 LLD ExportExecutor + manifest_builder D12 段(derive_drop_target 函数 + path 表格)
- [ ] 4.3 HLD UE Export Bridge 章节(若有 framework drop physical layout 图)
- [ ] 4.4 test_spec.md(新 fence test 索引;~18 case)
- [ ] 4.5 acceptance_report.md(若 video FR/NFR 矩阵需更新)
- [ ] 4.6 CHANGELOG.md(本 change 条目)
- [ ] 4.7 CLAUDE.md ComfyUI 接入段 video 路径表述更新
- [ ] 4.8 AGENTS.md(若有 mentions of `Content/Generated/` video 路径)
- [ ] 4.9 跑 `python tools/forgeue_doc_sync_check.py --change fix-export-d12-and-skipped-evidence-filter`(预期 exit 0)
- [ ] 4.10 active.md retire 2 entries(`fix-video-export-path-split-d12-violation` + `fix-run-import-skipped-filter-permission-only` 标 `cancelled-completed: <commit-ref>`)→ 移到 archived.md
- [ ] 4.11 evidence frontmatter `followon_continuity` 4-list 在 P5/P6 阶段 verify_report.md / cross-check evidence 中正确填写

### D.11 commit

```bash
git add docs/ openspec/specs/ue-export-bridge/spec.md openspec/backlog/ CHANGELOG.md CLAUDE.md AGENTS.md
git commit -m "docs(forgeue): D.x doc-sync gate + active.md retire 2 follow-on

Tasks: tasks.md#4.1-4.11

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase E — Verify + Review + Finish

> Owner: controller 主流程(命令链触发,非 subagent);Type: verification + review hook

### E.1 跑全套 pytest(tasks.md#5.1)

- [ ] `python -m pytest -q` 期望 baseline + ~18(新 fence case)无回归

### E.2 Level 0/1/2 verify + codex `/codex:review --base main` hook(tasks.md#5.2)

- [ ] 走 `/forgeue:change-verify fix-export-d12-and-skipped-evidence-filter`(L0 lint / L1 unit / L2 integration + L2 live smoke 已完成)
- [ ] 跑 codex `/codex:review --base main`(verification hook;无 cross-check 强制 — single-direction code review)
- [ ] 落 `verification/verify_report.md` + `review/codex_verification_review.md`

### E.3 `/forgeue:change-review` finalize(tasks.md#5.3)

- [ ] Superpowers `requesting-code-review` finalize + codex `/codex:adversarial-review` mixed scope
- [ ] 写 `review/review_cross_check.md` + `review/codex_adversarial_review_round_counter.txt` 增 1 + 落 round 2 evidence(若需要)
- [ ] blocker 全部回写

### E.4 `/forgeue:change-doc-sync`(tasks.md#5.4)

- [ ] Documentation Sync Gate(10 文档静态扫 + README §4.3 提示词 + 应用 [REQUIRED])
- [ ] `forgeue_doc_sync_check` exit 0

### E.5 `/forgeue:change-finish`(tasks.md#5.5)

- [ ] finish_gate(中心化最后防线;evidence 完整性 + frontmatter 全检 + cross-check disputed_open=0 + writeback 真实性 + tasks unchecked + `openspec validate --strict` + 4 类 v1 advisory fence + followon_continuity)
- [ ] writeback_commit `pending` → 真实 hash sweep(全 evidence frontmatter)
- [ ] 落 `verification/finish_gate_report.md`

### E.6 archive(USER 范围;Fence #1 不可逆)(tasks.md#5.6)

- [ ] **USER required** Fence #1 不可逆:`openspec archive fix-export-d12-and-skipped-evidence-filter` + active.md → archived.md tombstone(用户授权后)
- [ ] squash merge dev → main(用户授权后)
- [ ] active.md 推动 2 entries 迁 archived.md

---

## Self-Review

- [x] **Spec coverage**:specs/ue-export-bridge/spec.md 5 Requirements 全部对应 micro-task(`is_manifest_importable` → A.2;`derive_drop_target` → A.3+A.4;Evidence skip_reason → A.1+A.5;run_import filter → B.2;domain_video file_path → B.3;Permission tiers update → A.5)
- [x] **Placeholder scan**:无 TBD / TODO / 占位符
- [x] **Type consistency**:`Evidence.skip_reason: Literal["permission_denied", "no_handler"] | None = None` + `derive_drop_target(art, *, target: UEOutputTarget, run_id: str) -> tuple[Path, str]` 跨 phase 一致
- [x] **F1-F4 round 1 codex 4 finding 全 inline writeback**:tasks.md A.2 / A.3 / A.5 / B.3 各 fence + design 修订
- [x] **commit message 含 `tasks.md#X.Y` anchor**:每个 phase commit 都标
