## ADDED Requirements

### Requirement: `manifest_builder.is_manifest_importable` is the single source of truth for import filter

The system SHALL provide `manifest_builder.is_manifest_importable(art: Artifact) -> bool` as a public helper that checks `art.payload_ref.kind == PayloadKind.file AND _KIND_MAP.get((modality, shape)) is not None`. Both `ExportExecutor._is_importable` (drop loop filter) and `manifest_builder.build_manifest` (manifest entry filter) SHALL call this helper to ensure import-filter consistency across modules. Today's behaviour mismatch — `_is_importable` looks at `modality` only and `manifest_builder.build_manifest:101-104` does the actual `_KIND_MAP.get(...) is None` silent skip — causes unsupported shape (e.g. `video.webm`) to drop physical files into `Content/Generated/<run_id>/` while the manifest skips the entry, leaving orphan files. After this consolidation:

- Unsupported shape artifacts (e.g. `video.webm` before `comfy-video-webm-adoption` follow-on extends `_KIND_MAP`) are silently filtered out at BOTH the drop loop AND the manifest builder — no orphan files, no manifest entries, consistent silent-skip behaviour aligned with image/audio/mesh modality skip pattern.
- `ExportExecutor.execute` drop loop SHALL only process artifacts that pass `is_manifest_importable(art)`, guaranteeing every dropped file has a corresponding manifest entry.

This Requirement is a refactor (not a behaviour change) — the silent-skip semantics already exist in `manifest_builder.build_manifest:101-104`; this consolidates the filter to a single helper to keep ExportExecutor + manifest_builder aligned.

#### Scenario: video.webm artifact is silently filtered out of both drop loop and manifest

- **GIVEN** an `Artifact(modality="video", shape="webm", payload_ref=PayloadRef(kind=file, file_path="<artifact_root>/<run_id>/clip.webm"))`(unsupported shape — `_KIND_MAP[("video","webm")]` returns None until `comfy-video-webm-adoption` follow-on adds it)
- **WHEN** `ExportExecutor.execute(ctx)` runs end-to-end with this artifact in the upstream set
- **THEN** `is_manifest_importable(art)` returns False; `_is_importable(art)` returns False (consolidated to call `is_manifest_importable`); the drop loop does NOT copy the webm file; the manifest does NOT include an entry for this artifact; the export step completes without raising;`tests/unit/test_export_video_path_split.py::test_export_unsupported_shape_does_not_crash_drop_loop` fences this

#### Scenario: is_manifest_importable returns False for non-file payload kind

- **GIVEN** an `Artifact(modality="image", shape="png", payload_ref=PayloadRef(kind=inline_blob, ...))`(modality + shape match `_KIND_MAP` but payload kind is `inline_blob` not `file`)
- **WHEN** `is_manifest_importable(art)` is called
- **THEN** returns False (payload.kind ≠ file precondition); `tests/unit/test_export_video_path_split.py::test_is_manifest_importable_requires_file_payload_kind` fences this

### Requirement: ExportExecutor drop loop applies D12 path split for video mp4 via `manifest_builder.derive_drop_target`

The system SHALL split video mp4 drop path from other modalities according to D12 packaging contract:

- `manifest_builder.derive_drop_target(art, *, target: UEOutputTarget, run_id: str)` SHALL be a public helper that returns `(drop_dir: Path, target_filename: str)`:
  - For `art.artifact_type.modality == "video"` and `_KIND_MAP[(modality, shape)] == "file_media_source"` (currently mp4-only via `comfy-agent-cli-video-adoption` Phase 3 D7 mp4 sweep): returns `(<target.project_root>/Content/Movies/<run_id>, MS_<base>.mp4)` where `MS_<base>` is computed via `_derive_ue_name(art, kind="file_media_source", policy=target.asset_naming_policy)`.
  - For all other importable modalities (`image` / `mesh` / `audio` / `material`): returns `(<target.project_root>/Content/Generated/<run_id>, raw_basename)` where `raw_basename = Path(art.payload_ref.file_path).name` — preserving today's exact filename behaviour (sup design D1 NG1: 本 change 不改非 video 文件名).
  - Precondition: caller MUST pre-filter with `is_manifest_importable(art)`. If `_KIND_MAP.get((modality, shape))` returns None (defensive — caller missed the precondition), the helper falls through to the non-video branch and returns `(Generated/<run_id>, raw_basename)` — does NOT raise (round 1 codex F1: avoid surprising export crash for unsupported shape paths).
- `ExportExecutor.execute` drop loop SHALL invoke `derive_drop_target(art, target=ctx.task.ue_target, run_id=ctx.run.run_id)` per importable artifact, ensure the returned `drop_dir` exists via `mkdir(parents=True, exist_ok=True)`, then `shutil.copy2` the source file to `drop_dir / target_filename`. The Evidence `target_object_path` field SHALL be `str(target_fs.relative_to(Path(target.project_root)))` (POSIX-style relative path to project_root).
- `manifest_builder.build_manifest` SHALL also invoke `derive_drop_target(art, target=target, run_id=run_id)` to compute `UEAssetEntry.source_uri` so it matches the framework drop physical location:
  - For video: `source_uri = "Content/Movies/<run_id>/MS_<base>.mp4"`
  - For other modalities: `source_uri = "Content/Generated/<run_id>/<raw_basename>"` (preserves current raw artifact basename — round 1 codex F2: 不改非 video filename, avoid silent collision when two artifacts share `display_name`)

This is the **single source of truth** for "where does the framework drop physical files vs what does the manifest entry say": `derive_drop_target` is called both by `ExportExecutor.execute` (drop loop) and by `manifest_builder.build_manifest` (manifest entry source_uri). A fence test SHALL guard the cross-module consistency.

#### Scenario: ExportExecutor drops video mp4 to Content/Movies/<run_id>/MS_<base>.mp4 and image to Content/Generated/<run_id>/<raw_basename>

- **GIVEN** a `Run` with two upstream importable artifacts:(1) a video Artifact with `modality="video"`, `shape="mp4"`, `payload_ref.file_path = "<artifact_root>/<run_id>/abc123.mp4"`, `metadata={"display_name": "OpeningScene", ...}`;(2) an image Artifact with `modality="image"`, `shape="png"`, `payload_ref.file_path = "<artifact_root>/<run_id>/def456.png"`, `metadata={"display_name": "Tavern", ...}`;`Task.ue_target` populated with `UEOutputTarget`;`ExportExecutor` reaches export Step with `import_mode=manifest_only` and `Verdict.decision=approve`
- **WHEN** `ExportExecutor.execute(ctx)` runs end-to-end through the drop loop
- **THEN** the on-disk layout under `<project_root>/Content/` is:
  - `Content/Movies/<run_id>/MS_OpeningScene.mp4` (video mp4 dropped here per D12, ue_name `MS_OpeningScene`)
  - `Content/Generated/<run_id>/def456.png` (image dropped to Generated/ with **raw artifact basename** preserved — round 1 codex F2 修订: 非 video 不改 filename)
  - `Content/Generated/<run_id>/manifest.json` + `import_plan.json` + `evidence.json` (three-file deliverable unchanged)
- **AND** the resulting `manifest.json` `assets[]` for the video entry has `source_uri = "Content/Movies/<run_id>/MS_OpeningScene.mp4"`; for the image entry has `source_uri = "Content/Generated/<run_id>/def456.png"`(raw artifact filename)
- **AND** `tests/unit/test_export_video_path_split.py::test_export_drops_video_to_content_movies_and_image_preserves_raw_filename` fences this

#### Scenario: derive_drop_target preserves raw filename for non-video importable artifacts

- **GIVEN** importable artifacts of `modality ∈ {image, audio, mesh, material}` with various `shape` (e.g. `png`, `flac`, `glb`, `material_template`); each has `payload_ref.file_path` pointing at the framework's `<artifact_root>/<run_id>/<artifact_id>.<ext>`
- **WHEN** `derive_drop_target(art, target=target, run_id=run_id)` is invoked for each
- **THEN** the returned `target_filename` is `Path(art.payload_ref.file_path).name` (raw basename, same as today's `export.py:115` behaviour);the returned `drop_dir` is `<project_root>/Content/Generated/<run_id>`;`tests/unit/test_export_video_path_split.py::test_derive_drop_target_preserves_raw_filename_for_non_video` fences this

#### Scenario: derive_drop_target falls through to non-video branch when _KIND_MAP misses (defensive)

- **GIVEN** an artifact whose `(modality, shape)` is not in `_KIND_MAP`(e.g. caller missed `is_manifest_importable` precondition)
- **WHEN** `derive_drop_target(art, target=target, run_id=run_id)` is called directly
- **THEN** the helper falls through to the non-video branch and returns `(<project_root>/Content/Generated/<run_id>, raw_basename)`;does NOT raise ValueError;round 1 codex F1 修订:此分支是 defensive only,正常调用路径下 caller 已经通过 `is_manifest_importable` filter;`tests/unit/test_export_video_path_split.py::test_derive_drop_target_falls_through_for_unmapped_shape` fences this

### Requirement: Evidence schema includes `skip_reason` enum field for skipped status disambiguation

The system SHALL extend `framework.core.ue.Evidence` with a new field:

```python
class Evidence(BaseModel):
    ...
    status: Literal["success", "failed", "skipped"]
    skip_reason: Literal["permission_denied", "no_handler"] | None = None
    error: str | None = None
```

- `skip_reason` defaults to `None` for backward compatibility — old evidence.json fixtures (without the field) load via Pydantic with `skip_reason=None` and behave identically under the F-D filter (no permission_denied match, not pre-filtered).
- `ExportExecutor.execute` SHALL emit Evidence with `skip_reason="permission_denied"` exactly when `is_op_allowed(self._permission, op)` returns False (`src/framework/runtime/executors/export.py:151-158` permission-mask emit path).
- `evidence_writer.make_record` (UE-side helper at `ue_scripts/evidence_writer.py`) SHALL accept an optional `skip_reason: str | None = None` keyword argument; when `run_import.py` writes "no UE-side handler" skipped evidence (current `ue_scripts/run_import.py:89-92`), it SHALL pass `skip_reason="no_handler"`.
- The enum is closed at `Literal["permission_denied", "no_handler"]` — adding new values requires extending the Literal type and the F-D filter logic together.

#### Scenario: Evidence Pydantic load with old evidence.json (no skip_reason field) yields skip_reason=None

- **GIVEN** a legacy evidence.json file written before this change, containing entries with no `skip_reason` field (e.g. `{"evidence_item_id":"ev_1", "op_id":"op_drop_X", "kind":"drop_file", "status":"success", ...}`)
- **WHEN** `Evidence.model_validate({"evidence_item_id":"ev_1", ..., "status":"skipped", "error":"PermissionPolicy ..."})` loads the legacy entry
- **THEN** the resulting Evidence instance has `skip_reason=None` (Pydantic default applied);no validation error;`tests/unit/test_evidence_skip_reason.py::test_evidence_load_legacy_no_skip_reason_field_defaults_to_none` fences this

#### Scenario: ExportExecutor PermissionPolicy denied emit writes skip_reason="permission_denied"

- **GIVEN** a manifest containing a `create_material` operation under default `PermissionPolicy()` (`allow_create_material=False` by default)
- **WHEN** `ExportExecutor.execute` runs the permission mask loop and `is_op_allowed(policy, op)` returns False
- **THEN** the resulting Evidence record has `status="skipped"`, `skip_reason="permission_denied"`, `error="PermissionPolicy does not grant this op kind"`;`tests/unit/test_evidence_skip_reason.py::test_export_permission_denied_evidence_carries_skip_reason fence` fences this

#### Scenario: evidence_writer.make_record accepts skip_reason kwarg and propagates to JSON output

- **GIVEN** a UE-side caller invoking `evidence_writer.make_record(op_id="op_X", kind="import_texture", status="skipped", error="no UE-side handler for kind=import_texture", skip_reason="no_handler")`
- **WHEN** the resulting record is appended to evidence.json
- **THEN** the JSON entry includes `"skip_reason": "no_handler"`;the legacy evidence_writer call sites without `skip_reason` kwarg yield JSON entries with `skip_reason: null` (or omit the field — implementation choice via Pydantic `exclude_none`);`tests/unit/test_evidence_writer_skip_reason.py` fences this

### Requirement: run_import.py filters only PermissionPolicy-denied skipped evidence

The system SHALL ensure `ue_scripts/run_import.py` pre-scan filter (current L67-73) only skips operations whose evidence record carries `skip_reason="permission_denied"`:

```python
# ue_scripts/run_import.py (after this change)
pre_skipped_op_ids: set[str] = set()
try:
    with open(bundle.evidence_path, "r", encoding="utf-8") as _f:
        for _ev in _json.load(_f) or []:
            if (_ev.get("status") == "skipped"
                and _ev.get("skip_reason") == "permission_denied"
                and _ev.get("op_id")):
                pre_skipped_op_ids.add(_ev["op_id"])
except Exception:
    pass
```

This SHALL preserve the original intent (honour framework-side `PermissionPolicy.allow_*=False` deny without re-executing the op) while NOT silently swallowing UE-side append-on-second-read self-collisions where `run_import.py` itself writes `status="skipped"` with `skip_reason="no_handler"` (current L89-92 path) — those entries will NOT be added to `pre_skipped_op_ids` and will go through the normal handler dispatch path on subsequent reads (which is a no-op in single-pass execution but matters for hypothetical re-run scenarios).

#### Scenario: run_import.py honours PermissionPolicy denied skipped but not no-handler skipped

- **GIVEN** an evidence.json containing two skipped entries:(1) `{"op_id":"op_create_mat_X", "status":"skipped", "skip_reason":"permission_denied", "error":"PermissionPolicy does not grant this op kind"}` written by framework ExportExecutor;(2) `{"op_id":"op_unknown_Y", "status":"skipped", "skip_reason":"no_handler", "error":"no UE-side handler for kind=unknown"}` written by a hypothetical earlier UE-side append
- **WHEN** `run_import.run(...)` reads evidence.json and builds `pre_skipped_op_ids`
- **THEN** `pre_skipped_op_ids == {"op_create_mat_X"}`;`op_unknown_Y` is NOT pre-skipped (would proceed to `_OP_HANDLERS.get(kind)` lookup if it appeared in plan ops);`tests/unit/test_run_import_skipped_filter.py::test_pre_skipped_only_includes_permission_denied` fences this

## MODIFIED Requirements

### Requirement: domain_video.import_video_entry assumes mp4 already at source_uri, derives file_path from source_uri (single source of truth), and creates FileMediaSource .uasset

The system SHALL provide `ue_scripts/domain_video.py` with one entry point `import_video_entry(entry: dict, project_root: str) -> dict` that the UE-side `run_import.py` dispatcher invokes for `file_media_source` operations. The function SHALL:

- Read the source mp4 file path from `entry["source_uri"]` (POSIX path relative to project_root, per existing `manifest_builder.build_manifest` source_uri convention) — note: post-D12-fix this path is `Content/Movies/<run_id>/MS_<base>.mp4`, set by `ExportExecutor` drop loop via `manifest_builder.derive_drop_target`
- **NOT** copy the mp4 file — the framework `ExportExecutor.execute` drop loop already wrote the mp4 to its final D12-compliant location `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` per the new "ExportExecutor drop loop applies D12 path split" Requirement;`shutil.copy2` SHALL be removed from `domain_video.import_video_entry`
- **NOT** invoke `os.makedirs(<project_root>/Content/Movies/<run_id>/, exist_ok=True)` — the framework already created this directory in the drop loop;the makedirs SHALL be removed
- Verify `entry["source_uri"]` resolves to an existing mp4 file at `<project_root>/<source_uri>`;if missing, return `{"status": "failed", "error": f"source mp4 not found at <project_root>/<source_uri>", ...}` for the EvidenceWriter to append (defensive — fence framework drop failures)
- **Derive `FileMediaSource.file_path` from the verified `entry["source_uri"]`(round 1 codex F3 修订;NOT from `target_object_path` 反推,which decouples source-of-truth)**:
  - Strip `Content/` prefix from `source_uri` to get `relative_to_content`(e.g. `Content/Movies/<run_id>/MS_<base>.mp4` → `Movies/<run_id>/MS_<base>.mp4`)
  - Validate `relative_to_content.startswith("Movies/")` AND path part count == 3 (`Movies/<run_id>/<filename>.mp4`);if not, return `{"status": "failed", "error": "source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout", ...}`
  - Set `relative_file_path = relative_to_content`(used directly as FileMediaSource.file_path editor property)
- **Mismatch fence between source_uri and target_object_path**(round 1 codex F3 修订):the `(run_id, ue_name)` derived from `source_uri` (split path parts 1 + 2 of `Movies/<run_id>/<ue_name>.mp4`) MUST equal the `(run_id, ue_name)` derived from `target_object_path` (split path parts -2 + -1 of e.g. `/Game/Generated/<run_id>/<ue_name>`);if they differ, return `{"status": "failed", "error": "source_uri / target_object_path mismatch: source=(<run_id_a>, <ue_name_a>) vs target=(<run_id_b>, <ue_name_b>)", ...}` — guards manifest bug / hand-edit / re-run race
- Invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name=MS_<base>, package_path=<asset_root>/<run_id>, asset_class=unreal.FileMediaSource, factory=unreal.FileMediaSourceFactoryNew())` (round-7 R1 修订:UE 5.7 commandlet 实测验证 — `FileMediaSourceFactoryNew` 是正确工厂类名,`AssetTools.create_asset` 是 in-engine asset 创建路径,**NOT** `unreal.FileMediaSourceFactory()` + `unreal.AssetImportTask` 的 import-from-disk 路径)
- Set `unreal.FileMediaSource.file_path` editor property to `relative_file_path` (derived from source_uri above) — this is the **only** editor property set on the FileMediaSource asset
- `import_options.loop` / `import_options.play_on_open` MUST NOT be set as editor properties on FileMediaSource (round-7 R1 修订:UE 5.7 commandlet 实测 `set_editor_property("loop")` 报 `FileMediaSource: Failed to find property 'loop'` — 这两项是 `MediaPlayer` runtime properties 而非 `MediaSource` asset properties);保留在 manifest `import_options` 给 follow-on `comfy-video-level-sequence-adoption` / MediaPlayer 配置层消费
- Return a result dict matching the existing domain_*.import_*_entry contract: `{"status": "success" | "failed", "asset_path": <package path>, "error": <str | None>, ...}` for the EvidenceWriter to append
- SHALL NOT `import framework.*` (per existing NFR-PORT-003 invariant); only `import unreal` + stdlib

#### Scenario: domain_video.import_video_entry creates FileMediaSource .uasset without copying mp4 and derives file_path from source_uri

- **GIVEN** a `UEAssetEntry` for a video artifact: `{"asset_kind": "file_media_source", "source_uri": "Content/Movies/<run_id>/MS_<base>.mp4", "target_object_path": "/Game/Generated/<run_id>/MS_<base>", "target_package_path": "/Game/Generated/<run_id>/MS_<base>", "ue_naming": {"prefix": "MS_", "ue_name": "MS_<base>"}, "import_options": {"loop": false, "play_on_open": false, "source_format": "mp4", ...}}` and a stubbed `unreal` module;the mp4 file is **already** at `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` (because framework `ExportExecutor` drop loop pre-wrote it via `derive_drop_target` D12 split)
- **WHEN** `domain_video.import_video_entry(entry, project_root)` runs
- **THEN** the function does **NOT** invoke `shutil.copy2`;does **NOT** invoke `os.makedirs(<project_root>/Content/Movies/<run_id>/)`;`unreal.AssetToolsHelpers.get_asset_tools().create_asset(...)` is invoked exactly 1 time with `asset_class=unreal.FileMediaSource` + `factory=unreal.FileMediaSourceFactoryNew()`;the resulting `FileMediaSource.file_path` editor property is set to `Movies/<run_id>/MS_<base>.mp4` (**derived from source_uri stripping `Content/` prefix — single source of truth**, NOT target_object_path 反推);**`loop` / `play_on_open` editor properties are NOT set** (round-7 R1:UE FileMediaSource asset has no such properties — `set_editor_property("loop")` raises `Failed to find property`);the function returns `{"status": "success", "asset_path": "/Game/Generated/<run_id>/MS_<base>", ...}`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_creates_file_media_source_uasset_without_copying_mp4_file_path_from_source_uri` fences this

#### Scenario: domain_video.import_video_entry returns failed when source mp4 missing at expected D12 path

- **GIVEN** a `UEAssetEntry` for a video artifact with `source_uri="Content/Movies/<run_id>/MS_<base>.mp4"` but the mp4 file does NOT exist at that location (defensive — framework drop failed silently, hypothetically)
- **WHEN** `domain_video.import_video_entry(entry, project_root)` runs
- **THEN** the function returns `{"status": "failed", "error": "source mp4 not found at <project_root>/Content/Movies/<run_id>/MS_<base>.mp4", ...}`;does NOT invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_returns_failed_when_mp4_missing` fences this

#### Scenario: domain_video.import_video_entry returns failed when source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout

- **GIVEN** a `UEAssetEntry` with `source_uri="Content/Generated/<run_id>/<filename>.mp4"`(legacy / hand-edit;sits in Generated/ instead of Movies/)or `source_uri="Movies/<run_id>/<filename>.mp4"`(missing `Content/` prefix);the mp4 file may exist at the source path
- **WHEN** `domain_video.import_video_entry(entry, project_root)` runs
- **THEN** the function returns `{"status": "failed", "error": "source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout", ...}`;does NOT invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_rejects_non_d12_source_uri` fences this

#### Scenario: domain_video.import_video_entry returns failed when source_uri / target_object_path mismatch

- **GIVEN** a `UEAssetEntry` with `source_uri="Content/Movies/run_a/MS_base_a.mp4"` AND `target_object_path="/Game/Generated/run_b/MS_base_b"`(run_id 或 ue_name 不一致)— mp4 may exist at source path
- **WHEN** `domain_video.import_video_entry(entry, project_root)` runs
- **THEN** the function returns `{"status": "failed", "error": "source_uri / target_object_path mismatch: source=(run_a, MS_base_a) vs target=(run_b, MS_base_b)", ...}`;does NOT invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_returns_failed_on_source_target_mismatch` fences this — 守门 manifest bug / hand-edit / re-run race

#### Scenario: domain_video does not import framework modules

- **GIVEN** the `ue_scripts/domain_video.py` source file
- **WHEN** static analysis or `tests/unit/test_ue_scripts_no_framework_import.py::test_domain_video_does_not_import_framework` (or equivalent existing fence covering `domain_*.py` import sweep) inspects the imports
- **THEN** no `import framework` or `from framework` line exists; only `import unreal` + standard library imports; this preserves the NFR-PORT-003 invariant that `ue_scripts/` is framework-decoupled

### Requirement: Permission tiers govern domain operations

The system SHALL enforce `PermissionPolicy`: default allow for `create_folder` / `import_texture` / `import_audio` / `import_static_mesh` / `import_file_media_source` (D1: video import added as default-allow alongside the other three import kinds — read-only, content-creating, no destructive side effects); default deny for `create_material` / `create_sound_cue` (requires explicit allow flag); permanent deny for modifications of existing assets / blueprints / maps / configs / deletions.

The video import default-allow SHALL be carried by a new `PermissionPolicy.allow_import_file_media_source: bool = True` field on `framework.core.policies.PermissionPolicy` (`src/framework/core/policies.py:93-95` already declares `allow_import_texture` / `allow_import_audio` / `allow_import_static_mesh`; this change adds the fourth allow_import_* attribute) AND a corresponding `_OP_ALLOW_ATTR["import_file_media_source"] = "allow_import_file_media_source"` entry in `framework.ue_bridge.permission_policy._OP_ALLOW_ATTR` (`src/framework/ue_bridge/permission_policy.py:14-19`). Without both, `permission_policy.is_op_allowed(policy, op)` would default to deny, and `ExportExecutor.execute` (`src/framework/runtime/executors/export.py:157`) would emit an Evidence record `status="skipped"` with `skip_reason="permission_denied"` + `error="PermissionPolicy does not grant this op kind"` for every video import operation, breaking the L2 + a2_video P4 contract. (round-2 F1 codex finding accepted-codex 2026-05-04 + cluster 2 fix:round-1 design / spec / tasks 漏掉这两处的同步 sweep — 仅扩 `_OP_HANDLERS["import_file_media_source"] = domain_video.import_video_entry` 不够,permission tier 与 attr 映射必须同步;cluster-2 加 `skip_reason="permission_denied"` 字段使 Evidence 区分明确)

#### Scenario: Material creation is denied by default

- GIVEN a manifest that asks to create a material without an allow flag
- WHEN the framework builds the import plan
- THEN the `create_material` operation is skipped and the corresponding Evidence record carries `status="skipped"`, `skip_reason="permission_denied"`, `error="PermissionPolicy does not grant this op kind"` (cluster-2 fix:`skip_reason` field added 使 F-D run_import 过滤精确)

#### Scenario: import_file_media_source is allowed by default

- GIVEN a manifest that includes a `import_file_media_source` operation for a video asset (D1: FileMediaSource creation from external mp4 file)
- WHEN the framework builds the import plan and dispatches operations on the UE side
- THEN the `import_file_media_source` operation is allowed (default-allow tier, alongside the other three import_* kinds); the Evidence record on success carries `status=success`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_import_file_media_source_default_allow` fences this
