# Artifact Contract 与 UE Asset Manifest 设计 v1

## 0. 文档目的

本文定义：

1. 生产模式中的通用 Artifact Contract
2. UE 侧可消费的 Asset Manifest 结构
3. 图片、音乐、3D、导入清单、元数据的统一表达方式

目标是避免“上游模型随便产出、下游脚本各自猜格式”的局面。

---

## 1. 设计原则

### 1.1 Artifact 先于 Bridge 标准化
先把中间产物的表达定义清楚，再谈 UE 导入。

### 1.2 Contract 应表达可消费性，而非只记录文件地址
一个好的 Artifact Contract 至少要回答：

- 这是什么产物
- 谁生成的
- 来自什么上游
- 有什么格式与规格
- 是否已通过校验
- 下游该怎样消费它

### 1.3 Manifest 是给 UE Bridge 的稳定出口
核心编排层不直接操纵 UE，而输出可消费 Manifest。

---

## 2. 通用 Artifact Contract

### 2.1 建议统一字段

```json
{
  "artifact_id": "art_001",
  "artifact_type": "concept_image",
  "artifact_role": "intermediate",
  "display_name": "tavern_concept_01",
  "format": "png",
  "mime_type": "image/png",
  "uri": "artifacts/run_001/tavern_concept_01.png",
  "producer": {
    "run_id": "run_001",
    "step_id": "step_generate_concepts",
    "provider_ref": "image_provider.main",
    "model_ref": "image_model_A"
  },
  "lineage": {
    "source_artifact_ids": ["art_spec_001"],
    "source_task_ids": ["task_001"]
  },
  "metadata": {},
  "validation": {},
  "tags": []
}
```

---

## 3. artifact_type 建议枚举

- `structured_answer`
- `spec_fragment`
- `design_brief`
- `concept_image`
- `texture_image`
- `sprite_sheet`
- `music_track`
- `sfx_clip`
- `mesh_asset`
- `material_definition`
- `asset_bundle`
- `review_report`
- `ue_asset_manifest`
- `ue_import_plan`

---

## 4. 不同类型 Artifact 的特定元数据

### 4.1 图片类 Artifact

适用类型：

- `concept_image`
- `texture_image`
- `sprite_sheet`

建议 metadata：

```json
{
  "width": 2048,
  "height": 2048,
  "aspect_ratio": "1:1",
  "color_space": "sRGB",
  "style_tags": ["fantasy", "warm", "stylized"],
  "prompt_summary": "fantasy tavern interior concept art",
  "seed": 12345,
  "transparent_background": false,
  "intended_use": "concept_reference"
}
```

### 图片类扩展字段建议

- `alpha_channel`
- `tileable`
- `texture_usage_hint`：如 `albedo / roughness / normal_reference`
- `variation_group_id`

---

### 4.2 音乐/音频类 Artifact

适用类型：

- `music_track`
- `sfx_clip`

建议 metadata：

```json
{
  "duration_sec": 92.3,
  "sample_rate": 44100,
  "channels": 2,
  "bit_depth": 16,
  "loopable": true,
  "loop_in_sec": 4.0,
  "loop_out_sec": 88.0,
  "mood_tags": ["cozy", "fantasy", "tavern"],
  "tempo_bpm": 84,
  "intended_use": "bgm"
}
```

### 音频类扩展字段建议

- `peak_db`
- `lufs`
- `stem_info`
- `cue_recommendation`

---

### 4.3 3D/网格类 Artifact

适用类型：

- `mesh_asset`

建议 metadata：

```json
{
  "mesh_format": "glb",
  "poly_count": 18234,
  "material_slots": 3,
  "has_uv": true,
  "has_rig": false,
  "scale_unit": "cm",
  "up_axis": "Z",
  "bounding_box": [120.0, 95.0, 210.0],
  "intended_use": "static_mesh"
}
```

### 3D 类扩展字段建议

- `lod_count`
- `collision_hint`
- `pivot_hint`
- `skeleton_name`
- `animation_compatible`

---

### 4.4 结构化文本类 Artifact

适用类型：

- `structured_answer`
- `spec_fragment`
- `design_brief`

建议 metadata：

```json
{
  "schema_name": "RoleConceptSpec",
  "schema_version": "1.0",
  "language": "zh-CN",
  "fields_complete": true
}
```

---

## 5. Artifact Validation Contract

每个 Artifact 应保留统一校验信息。

建议结构：

```json
{
  "validation": {
    "status": "passed",
    "checks": [
      {"name": "format_check", "result": "passed"},
      {"name": "metadata_required_fields", "result": "passed"},
      {"name": "path_policy_check", "result": "passed"}
    ],
    "warnings": [],
    "errors": []
  }
}
```

### 校验分层建议

- 文件层：是否存在、是否可访问、格式是否合法
- 元数据层：必填字段是否完整
- 业务层：是否满足当前生产步骤需要
- UE 层：是否满足导入规则

---

## 6. Artifact Lineage 设计

Lineage 用于追踪来源。

建议字段：

```json
{
  "lineage": {
    "source_artifact_ids": ["art_spec_001", "art_img_002"],
    "source_step_ids": ["step_extract_spec", "step_review_concepts"],
    "transformation_kind": "image_to_3d",
    "selected_by_verdict_id": "verdict_001"
  }
}
```

### 价值

- 追踪资产来源
- 回放生成链
- 做审计与可解释性
- 支持失败回退与版本对比

---

## 7. Candidate Bundle 表达

对于多候选场景，建议显式引入 `candidate_bundle`。

```json
{
  "artifact_id": "bundle_001",
  "artifact_type": "candidate_bundle",
  "metadata": {
    "candidate_count": 4,
    "selection_goal": "select best tavern concept"
  },
  "bundle_items": ["art_001", "art_002", "art_003", "art_004"]
}
```

---

## 8. UE Asset Manifest 的定位

UE Asset Manifest 是 Bridge 层的稳定输入。
它不一定等于 UE 最终导入结果，而是：

- 对导入目标进行声明
- 对资产命名与路径进行约束
- 对依赖关系进行整理
- 为 Bridge 提供低风险可执行计划

---

## 9. UE Asset Manifest 建议结构

```json
{
  "manifest_id": "manifest_001",
  "schema_version": "1.0",
  "run_id": "run_001",
  "project_target": {
    "project_name": "MyUEProject",
    "content_root": "/Game/Generated"
  },
  "assets": [],
  "import_rules": {},
  "naming_policy": {},
  "path_policy": {},
  "dependencies": []
}
```

---

## 10. Manifest 中的单资产条目

```json
{
  "asset_entry_id": "entry_001",
  "artifact_id": "art_010",
  "asset_kind": "texture",
  "source_uri": "artifacts/run_001/tavern_wall_albedo.png",
  "target_object_path": "/Game/Generated/Tavern/Textures/T_TavernWall_Albedo",
  "target_package_path": "/Game/Generated/Tavern/Textures",
  "ue_naming": {
    "asset_name": "T_TavernWall_Albedo",
    "prefix": "T_"
  },
  "import_options": {
    "sRGB": true,
    "compression": "Default"
  },
  "metadata_overrides": {
    "source_prompt_summary": "stone tavern wall texture"
  }
}
```

---

## 11. 建议的 asset_kind

- `texture`
- `material`
- `static_mesh`
- `skeletal_mesh`
- `sound_wave`
- `sound_cue`
- `data_asset`
- `ui_texture`
- `misc_reference`

---

## 12. 命名策略建议

Manifest 应显式输出命名策略，而不是让 Bridge 自己猜。

建议策略：

- Texture：`T_`
- Material：`M_`
- Static Mesh：`SM_`
- Skeletal Mesh：`SK_`
- Sound Wave：`SW_`
- Sound Cue：`SC_`

示例：

```json
{
  "naming_policy": {
    "texture_prefix": "T_",
    "material_prefix": "M_",
    "static_mesh_prefix": "SM_",
    "sound_wave_prefix": "SW_"
  }
}
```

如 GDD 已明确命名，则 Manifest 可记录 `name_source = gdd_mandated`。

---

## 13. 路径策略建议

建议 Manifest 输出明确路径策略：

```json
{
  "path_policy": {
    "texture_root": "/Game/Generated/Tavern/Textures",
    "material_root": "/Game/Generated/Tavern/Materials",
    "mesh_root": "/Game/Generated/Tavern/Meshes",
    "audio_root": "/Game/Generated/Tavern/Audio"
  }
}
```

这样 Bridge 可先做“只读检查”，确认路径合法后再导入。

---

## 14. 依赖关系表达

如果某材质依赖贴图，或某 Sound Cue 依赖 Sound Wave，应在 Manifest 显式声明：

```json
{
  "dependencies": [
    {
      "from_asset_entry_id": "entry_material_001",
      "to_asset_entry_id": "entry_texture_001",
      "dependency_type": "uses_texture"
    }
  ]
}
```

---

## 15. UE Import Plan

建议把 `ue_asset_manifest` 与 `ue_import_plan` 区分：

- `ue_asset_manifest`：声明式，描述“应该导入什么”
- `ue_import_plan`：执行式，描述“按什么顺序导入”

示例：

```json
{
  "plan_id": "plan_001",
  "manifest_id": "manifest_001",
  "operations": [
    {"op_id": "op_001", "kind": "import_texture", "asset_entry_id": "entry_texture_001"},
    {"op_id": "op_002", "kind": "create_material", "asset_entry_id": "entry_material_001"},
    {"op_id": "op_003", "kind": "import_audio", "asset_entry_id": "entry_audio_001"}
  ]
}
```

---

## 16. 最小必需字段建议

### 16.1 所有 Artifact 必需字段

- `artifact_id`
- `artifact_type`
- `format`
- `uri`
- `producer`
- `metadata`
- `validation`

### 16.2 所有 Manifest Entry 必需字段

- `asset_entry_id`
- `artifact_id`
- `asset_kind`
- `source_uri`
- `target_object_path`
- `target_package_path`

---

## 17. 不建议的做法

### 17.1 只存文件路径，不存元数据
会导致下游判断极不稳定。

### 17.2 不存 lineage
无法解释“为什么选中了这个资产”。

### 17.3 让 UE Bridge 自己猜命名与目录
会引入大量不可控行为。

### 17.4 把 Manifest 写成一次性脚本输入
应保留 schema 化与可验证性。

---

## 18. MVP 最小实现范围

MVP 建议先支持：

### Artifact 类型
- `structured_answer`
- `concept_image`
- `music_track`
- `mesh_asset`
- `ue_asset_manifest`

### Manifest 资产种类
- `texture`
- `static_mesh`
- `sound_wave`
- `misc_reference`

这样足够先跑通：

- 文本 → 图片候选 → 筛选 → 导出清单
- 文本 → 音乐 → 导出清单
- 图片 → 3D → 导出清单

---

## 19. 结论

Artifact Contract 的目标不是“记录生成过程”，而是让中间产物可消费、可校验、可追踪。
UE Asset Manifest 的目标不是“代替 UE 编辑器”，而是给 Bridge 层一个稳定、低风险、可审查的执行入口。
