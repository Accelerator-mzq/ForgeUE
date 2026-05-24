"""UEAssetManifest builder (§F4-1, §B.11).

Given a set of framework Artifacts + a UEOutputTarget, derive a declarative
manifest of UE-side imports. File-backed image/audio/mesh payloads are assumed
to already live under `<UEOutputTarget.project_root>/Content/Generated/<run_id>/`
by the time the UE-side script reads this manifest — the export executor is
responsible for the actual file copy.

Rules (§E.1 — framework only DECLARES; UE-side script EXECUTES):
- One UEAssetEntry per importable Artifact
- Mapping (modality.shape) → asset_kind:
    image.raster                 → texture
    image.sprite_sheet           → texture
    audio.waveform               → sound_wave
    mesh.gltf / mesh.fbx / mesh.obj → static_mesh
    material.definition          → material
    video.mp4                    → file_media_source  (Phase 3 D1;webm follow-on)
- Naming policy: `house_rules` applies UE prefix table (§E.8 convention):
    T_<base>  for texture   S_<base> for sound_wave
    SM_<base> for static_mesh
    M_<base>  for material
    MS_<base> for file_media_source  (Phase 3 D1)
- `target_package_path` = `<UEOutputTarget.asset_root>/<UEName>`
- `source_uri` is POSIX, relative to project_root, pointing at the payload file
  (inline payloads are rejected — only file-backed Artifacts can become assets).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from framework.core.artifact import Artifact
from framework.core.enums import PayloadKind
from framework.core.ue import (
    UEAssetEntry,
    UEAssetManifest,
    UEDependency,
    UEOutputTarget,
)


# (modality, shape) → asset_kind
_KIND_MAP: dict[tuple[str, str], str] = {
    ("image", "raster"): "texture",
    ("image", "sprite_sheet"): "texture",
    ("audio", "waveform"): "sound_wave",
    ("mesh", "gltf"): "static_mesh",
    ("mesh", "fbx"): "static_mesh",
    ("mesh", "obj"): "static_mesh",
    ("material", "definition"): "material",
    # OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1:
    # video.mp4 → file_media_source(`unreal.FileMediaSourceFactory` 一行 import,
    # D12 drop target 由 framework contract 层 derive_drop_target 统一决定:
    # mp4 文件落 Content/Movies/<run_id>/ packaging 外挂,.uasset 落
    # Content/Generated/<run_id>/ asset_root 沿用)。webm follow-on
    # `comfy-video-webm-adoption` 时扩 ("video","webm") entry。
    ("video", "mp4"): "file_media_source",
}


def is_manifest_importable(art: Artifact) -> bool:
    """art 是否在 _KIND_MAP 命中 — manifest 能力的单一真源.

    Used by `ExportExecutor._is_importable` AND `manifest_builder.build_manifest`
    to keep import filtering consistent across modules(沿 OpenSpec change
    fix-export-d12-and-skipped-evidence-filter design D10 — round 1 codex F1
    修订:消除 modality whitelist 与 _KIND_MAP shape map 双源).

    返回 True 必须同时满足:
    1. payload_ref.kind == PayloadKind.file(只能导入 file-backed Artifact)
    2. (modality, shape) 在 _KIND_MAP 命中(unsupported shape 如 video.webm 返 False)
    """
    # 中文注释:single source check — 把 ExportExecutor 与 build_manifest filter 收敛到一处
    if art.payload_ref.kind != PayloadKind.file:
        return False
    return _KIND_MAP.get((art.artifact_type.modality, art.artifact_type.shape)) is not None


_PREFIX_BY_KIND: dict[str, str] = {
    "texture": "T_",
    "sound_wave": "S_",
    "static_mesh": "SM_",
    "material": "M_",
    # Phase 3 D1:MS_ 前缀(沿 SM_ / S_ / T_ / M_ 风格,2 字符前缀)
    "file_media_source": "MS_",
}


def derive_drop_target(
    art: Artifact, *, target: UEOutputTarget, run_id: str,
) -> tuple[Path, str]:
    """返回 (drop_dir, target_filename) — D12 路径分流 + UE naming for video,
    raw basename for non-video.

    Precondition: caller MUST 用 `is_manifest_importable(art)` filter;
    若 _KIND_MAP miss(defensive)→ fall through 非 video 分支返 raw basename,
    不 raise(沿 OpenSpec change fix-export-d12-and-skipped-evidence-filter
    design D10 + round 1 codex F1 修订).

    - video + `_KIND_MAP[(modality, shape)] == "file_media_source"` →
        (Movies/<run_id>, MS_<base>.mp4)
    - 其他 importable modality(image/audio/mesh/material)→
        (Generated/<run_id>, raw_basename)
        其中 raw_basename = Path(art.payload_ref.file_path).name(沿 design D1 修订:
        round 1 codex F2 — 非 video 不改 filename, 避免 NG1 超范围 + 同 display_name
        collision)
    """
    # 中文注释:project_root 由 UEOutputTarget 提供绝对路径
    project_root = Path(target.project_root)
    kind = _KIND_MAP.get((art.artifact_type.modality, art.artifact_type.shape))
    if kind == "file_media_source" and art.artifact_type.modality == "video":
        # video → Content/Movies/<run_id>/MS_<base>.<ext>(D12 packaging path 分流)
        ue_name = _derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)
        ext = Path(art.payload_ref.file_path).suffix or ".mp4"
        return (
            project_root / "Content" / "Movies" / run_id,
            f"{ue_name}{ext}",
        )
    # 非 video importable + defensive _KIND_MAP miss fall-through(round 1 codex F1)
    # 沿 design D1 修订:image/audio/mesh/material 保 raw basename(不走 UE naming)
    return (
        project_root / "Content" / "Generated" / run_id,
        Path(art.payload_ref.file_path).name,
    )


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_]+")


class ManifestBuildError(ValueError):
    """Raised when a manifest cannot be built from the given artifacts.

    Reserved for future structural errors. Phase A 收敛后(A.4)`build_manifest`
    不再 raise 此类(原 non-file payload errors.append 路径已被 `is_manifest_importable`
    silent skip 取代);保留 public symbol 防外部消费者依赖,便于将来加新 error category。
    """


def build_manifest(
    *,
    run_id: str,
    target: UEOutputTarget,
    artifacts: Iterable[Artifact],
    import_rules: dict | None = None,
    manifest_id: str | None = None,
    selected_artifact_ids: set[str] | None = None,
) -> UEAssetManifest:
    """Produce a UEAssetManifest from a set of importable Artifacts.

    - *selected_artifact_ids*: if given, only Artifacts with those ids are
      included; others are silently skipped (§E.6 approve filter).
    - *import_rules*: free-form dict threaded to the UE-side script
      (e.g. overwrite policy, LOD settings). MVP leaves defaults empty.
    """
    run_asset_folder = f"{target.asset_root.rstrip('/')}/{run_id}"
    entries: list[UEAssetEntry] = []

    for art in artifacts:
        if selected_artifact_ids is not None and art.artifact_id not in selected_artifact_ids:
            continue
        # OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase A:
        # filter 收敛到 is_manifest_importable 单源(沿 design D10 + round 1 codex F1);
        # 旧"_KIND_MAP miss silent skip + payload.kind != file → errors.append"双 branch
        # 合并到一处 helper,与 ExportExecutor._is_importable 共用同一 single source
        if not is_manifest_importable(art):
            # Non-importable artifact (bundle / report / text / unmapped shape /
            # non-file payload)— silent skip.
            continue
        # is_manifest_importable 已确保 _KIND_MAP 命中 + file payload;此处直接 dict 访问
        kind = _KIND_MAP[(art.artifact_type.modality, art.artifact_type.shape)]
        ue_name = _derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)
        target_obj_path = f"{run_asset_folder}/{ue_name}"
        target_pkg_path = target_obj_path   # Package + object paths coincide in UE 5.x naming
        # source_uri 从 derive_drop_target 计算(沿 design D1 修订 — 单源契约)
        # video → Content/Movies/<run_id>/MS_<base>.mp4
        # 非 video → Content/Generated/<run_id>/<raw basename>
        drop_dir, filename = derive_drop_target(art, target=target, run_id=run_id)
        drop_relative = drop_dir.relative_to(Path(target.project_root)).as_posix()
        source_uri = f"{drop_relative}/{filename}"
        entries.append(UEAssetEntry(
            asset_entry_id=f"ae_{art.artifact_id}",
            artifact_id=art.artifact_id,
            asset_kind=kind,
            source_uri=source_uri,
            target_object_path=target_obj_path,
            target_package_path=target_pkg_path,
            ue_naming={
                "policy": target.asset_naming_policy,
                "prefix": _PREFIX_BY_KIND.get(kind, ""),
                "base_name": ue_name[len(_PREFIX_BY_KIND.get(kind, "")):] if ue_name.startswith(_PREFIX_BY_KIND.get(kind, "")) else ue_name,
                "ue_name": ue_name,
            },
            import_options=_default_import_options(kind, art),
            metadata_overrides={
                k: v for k, v in art.metadata.items()
                if k in {"width", "height", "duration_sec", "sample_rate",
                         "poly_count", "transparent_background", "tileable",
                         "texture_usage_hint", "color_space", "intended_use",
                          # Phase 3 D1:video metadata fields(由 ffprobe 尽力回填,
                          # 解析失败时允许 None)
                         "frame_count", "fps", "loop", "play_on_open"}
            },
        ))

    expected = set(target.expected_asset_kinds or [])
    seen_kinds = {e.asset_kind for e in entries}
    missing = expected - seen_kinds
    import_rules_final = dict(import_rules or {})
    if missing:
        import_rules_final["missing_expected_kinds"] = sorted(missing)

    manifest = UEAssetManifest(
        manifest_id=manifest_id or f"m_{run_id}",
        run_id=run_id,
        project_target={
            "project_name": target.project_name,
            "project_root": target.project_root,
            "asset_root": target.asset_root,
            "run_asset_folder": run_asset_folder,
            "import_mode": target.import_mode.value,
        },
        assets=entries,
        import_rules=import_rules_final,
        naming_policy={
            "policy": target.asset_naming_policy,
            "prefix_table": dict(_PREFIX_BY_KIND),
        },
        path_policy={
            "run_asset_folder": run_asset_folder,
            "asset_root": target.asset_root,
        },
        dependencies=_derive_dependencies(entries),
    )
    return manifest


# ---- helpers ----

def _derive_ue_name(art: Artifact, *, kind: str, policy: str) -> str:
    prefix = _PREFIX_BY_KIND.get(kind, "")
    hint = (art.metadata or {}).get("ue_asset_name") or (art.metadata or {}).get("display_name")
    base = str(hint) if hint else art.artifact_id
    base = _SAFE_NAME.sub("_", base).strip("_") or "Asset"
    if base.startswith(prefix):
        return base
    return f"{prefix}{base}"


def _default_import_options(kind: str, art: Artifact) -> dict:
    """Kind-specific import hint dict. UE-side script consumes these."""
    md = art.metadata or {}
    if kind == "texture":
        return {
            "compression_settings": "default",
            "color_space": md.get("color_space", "sRGB"),
            "has_alpha": bool(md.get("transparent_background", False)),
            "tileable": bool(md.get("tileable", False)),
            "usage_hint": md.get("texture_usage_hint", "albedo"),
            "source_format": art.format,
        }
    if kind == "sound_wave":
        return {
            "loopable": bool(md.get("loopable", False)),
            "sample_rate": md.get("sample_rate"),
            "intended_use": md.get("intended_use", "sfx"),
            "source_format": art.format,
        }
    if kind == "static_mesh":
        return {
            "import_materials": False,   # MVP Phase B: skip derived materials
            "generate_lightmap_uvs": True,
            "up_axis": md.get("up_axis", "Z"),
            "scale_unit": md.get("scale_unit", "cm"),
            "source_format": art.format,
        }
    if kind == "file_media_source":
        # OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1:
        # FileMediaSource import options;5 个 video metadata 字段由 candidate
        # 顶层字段传递;解析失败时可能为 None。loop / play_on_open default False
        # (用户在 bundle 显式 override 时 set)。
        return {
            "loop": bool(md.get("loop", False)),
            "play_on_open": bool(md.get("play_on_open", False)),
            "duration_seconds": md.get("duration_seconds"),
            "frame_count": md.get("frame_count"),
            "width": md.get("width"),
            "height": md.get("height"),
            "fps": md.get("fps"),
            "source_format": art.format,
        }
    return {"source_format": art.format}


def _derive_dependencies(entries: list[UEAssetEntry]) -> list[UEDependency]:
    """Thin MVP: no cross-asset refs yet. Reserved for materials → textures etc."""
    return []
