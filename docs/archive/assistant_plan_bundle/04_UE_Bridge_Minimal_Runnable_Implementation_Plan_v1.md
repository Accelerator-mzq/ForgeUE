# UE Bridge 最小可运行实现方案 v1

## 0. 文档目的

本文定义 UE Bridge 的最小可运行实现方案，并明确其边界：

- **先读后写**
- **先低风险后高风险**
- **先声明式清单，再执行式操作**
- **Bridge 负责执行，不负责替代上游推理与评审**

本文的目标不是一步到位做“全自动 UE Agent”，而是先建立安全、可控、可审计的桥接层。

---

## 1. Bridge 的定位

UE Bridge 位于编排层与 UE 编辑器之间。

```text
Task / Workflow / Artifact / Verdict
          ↓
   UE Asset Manifest
          ↓
       UE Bridge
          ↓
   Unreal Editor / Content Browser / Asset Tools
```

Bridge 负责：

- 读取 Manifest
- 校验导入前提
- 生成 Import Plan
- 执行低风险导入或创建动作
- 回传执行结果与证据

Bridge 不负责：

- 自己决定资产应该长什么样
- 自己生成资产
- 越权修改大量工程内容
- 绕过上游 Review 直接落库

---

## 2. Bridge 设计原则

### 2.1 Read Before Write
任何写入前，先做读取与确认：

- 项目是否可访问
- Content 根路径是否合法
- 目标包路径是否存在或可创建
- 同名资源是否已存在
- Manifest 是否完整
- 文件是否存在

### 2.2 Low Risk Before High Risk
先支持低风险动作，再逐步扩展。

### 2.3 Declarative Before Imperative
先接 Manifest，再转换为 Import Plan，再执行。

### 2.4 Evidence First
每次导入/创建动作都返回证据对象，而不是只返回成功/失败字符串。

---

## 3. 建议分阶段实现边界

### 3.1 Phase A：只读探测层
只做以下事情：

- 读取项目路径
- 检查目标 Content 根路径
- 检查目标目录是否存在
- 检查同名资产是否存在
- 检查源文件是否可访问
- 返回 Readiness Report

不做任何写操作。

### 适合作为首批能力

- `inspect_project`
- `inspect_package_path`
- `inspect_existing_asset`
- `inspect_source_file`
- `validate_manifest`

---

### 3.2 Phase B：低风险导入层
只做外部资源导入，不做复杂编辑。

建议首批支持：

- 导入纹理
- 导入音频
- 导入静态网格
- 创建目标文件夹
- 输出导入结果清单

不做：

- 批量重命名整个目录
- 改 GameMode
- 改地图绑定
- 改蓝图逻辑
- 改项目配置

---

### 3.3 Phase C：低风险关联创建层
在导入稳定后，再考虑：

- 根据已导入贴图创建 Material
- 根据已导入 Sound Wave 创建 Sound Cue
- 根据 Manifest 建立轻量依赖关系

仍应限制在“局部新增”，避免修改已有复杂资产。

---

### 3.4 Phase D：中高风险编辑层
最后才考虑：

- 修改已有 Material
- 修改已有 Blueprint
- 修改场景对象
- 写项目级配置
- 改默认地图 / GameMode

这些必须在：

- Review 完整
- Manifest 完整
- 人工批准或强策略约束
- 审计与回滚能力具备

之后再上。

---

## 4. Bridge 的最小输入

Bridge 输入应为：

- `ue_asset_manifest`
- 可选的 `ue_import_plan`
- 运行上下文
- 权限策略

建议结构：

```json
{
  "manifest_id": "manifest_001",
  "run_id": "run_001",
  "project_ref": {
    "project_root": "D:/UEProjects/MyProject",
    "uproject_path": "D:/UEProjects/MyProject/MyProject.uproject"
  },
  "permission_policy": {
    "allow_create_folder": true,
    "allow_import_texture": true,
    "allow_import_audio": true,
    "allow_import_mesh": true,
    "allow_modify_existing_assets": false
  }
}
```

---

## 5. Bridge 的最小输出

Bridge 输出不应只是一句“导入成功”，而应输出执行证据。

建议结构：

```json
{
  "bridge_run_id": "bridge_001",
  "status": "partial_success",
  "operations": [
    {
      "op_id": "op_001",
      "kind": "import_texture",
      "status": "success",
      "target_object_path": "/Game/Generated/Tavern/Textures/T_TavernWall_Albedo"
    }
  ],
  "warnings": [],
  "errors": [],
  "evidence": []
}
```

---

## 6. 推荐工具能力分层

### 6.1 Inspect 类
只读，不修改。

- `inspect_project`
- `inspect_content_path`
- `inspect_asset_exists`
- `inspect_manifest`

### 6.2 Plan 类
只生成计划，不执行。

- `build_import_plan`
- `check_permission_scope`
- `dry_run_import`

### 6.3 Execute 类
真正写入，但只开放低风险动作。

- `create_folder`
- `import_texture`
- `import_audio`
- `import_static_mesh`
- `create_material_from_template`
- `create_sound_cue_from_template`

---

## 7. Manifest 到 Import Plan 的转换

Bridge 不建议直接拿 Manifest 就开写。
建议先生成 `ImportPlan`。

### 7.1 转换目的

- 检查执行顺序
- 显式列出每一步将做什么
- 在执行前暴露风险点
- 支持 dry-run

### 7.2 顺序建议

1. 校验项目与路径
2. 创建缺失目录
3. 导入基础资产（纹理/音频/网格）
4. 创建派生资产（材质/Sound Cue）
5. 输出结果与证据

---

## 8. 读写边界建议

### 8.1 默认允许的低风险写

- 在允许目录下创建新文件夹
- 导入新纹理到新路径
- 导入新音频到新路径
- 导入新静态网格到新路径
- 基于模板创建新材质或新 Sound Cue

### 8.2 默认禁止的高风险写

- 覆盖已有关键资产
- 修改默认地图
- 修改项目配置
- 修改已有 Blueprint 图逻辑
- 修改核心 GameMode
- 修改插件配置
- 删除目录与批量删除资源

---

## 9. 与 Review 的关系

Bridge 不应自行充当审查者，但必须尊重上游 Verdict。

例如：

- `Verdict.decision = reject` → Bridge 不执行
- `Verdict.decision = human_review_required` → Bridge 仅生成 dry-run plan
- `Verdict.decision = approve` → Bridge 进入执行

Bridge 只做权限与执行层决策，不重写上游业务裁决。

---

## 10. 与 UE 交互的推荐实现路径

在 UE 环境里，最小可运行 Bridge 优先推荐：

### 10.1 Python Editor Scripting
适合：

- 资源导入
- 文件夹创建
- 轻量资产创建
- 读取项目状态

优点：

- 迭代快
- 适合 MVP
- 易于配合 Manifest/JSON

### 10.2 Remote Control / 命令式桥接
适合后期扩展，但不建议一开始承担核心导入流程。

### 10.3 C++/Plugin
适合在 MVP 稳定后承接更严格的执行边界、批量处理与工程内分发。

---

## 11. 最小工具接口建议

### 11.1 inspect_project(project_root)
返回项目是否可访问、uproject 是否存在、Content 根目录是否存在。

### 11.2 validate_manifest(manifest_json)
返回 schema 校验、路径策略校验、权限策略校验结果。

### 11.3 dry_run_import(manifest_json)
返回将执行的操作列表、冲突点、需要创建的目录、潜在覆盖风险。

### 11.4 execute_import_plan(import_plan_json)
仅执行已批准的低风险动作，返回逐操作证据。

---

## 12. 证据对象建议

Bridge 每个操作应输出：

- 输入清单
- 目标路径
- UE 目标对象路径
- 执行状态
- 若失败则错误原因
- 若成功则对象引用信息
- 截图或日志引用（如有）

示例：

```json
{
  "evidence_item_id": "evi_001",
  "op_id": "op_001",
  "kind": "import_texture",
  "status": "success",
  "source_uri": "artifacts/run_001/tavern_wall_albedo.png",
  "target_object_path": "/Game/Generated/Tavern/Textures/T_TavernWall_Albedo",
  "log_ref": "logs/bridge_001/op_001.log"
}
```

---

## 13. 回滚策略建议

MVP 阶段不要求完整自动回滚，但至少应支持：

- 记录已创建对象
- 记录已导入对象
- 失败后停止后续操作
- 输出可人工清理清单

完整自动回滚应放在更后阶段实现。

---

## 14. 建议文件级实现拆解

### 14.1 Core 层
- `schemas/ue_asset_manifest.py`
- `schemas/ue_import_plan.py`
- `schemas/bridge_result.py`

### 14.2 Bridge 层
- `bridge/manifest_validator.py`
- `bridge/project_inspector.py`
- `bridge/import_plan_builder.py`
- `bridge/ue_python_executor.py`
- `bridge/result_collector.py`

### 14.3 UE Editor Script 层
- `ue_scripts/import_texture.py`
- `ue_scripts/import_audio.py`
- `ue_scripts/import_static_mesh.py`
- `ue_scripts/create_material_from_template.py`
- `ue_scripts/create_sound_cue_from_template.py`

---

## 15. MVP 闭环建议

建议最先跑通以下 3 条链路：

### 15.1 图片导入链
`concept_image / texture_image -> ue_asset_manifest -> dry_run -> import_texture`

### 15.2 音频导入链
`music_track / sfx_clip -> ue_asset_manifest -> dry_run -> import_audio`

### 15.3 图转 3D 结果导入链
`mesh_asset -> ue_asset_manifest -> dry_run -> import_static_mesh`

这三条都只涉及低风险新增，不涉及修改已有复杂资产。

---

## 16. 不建议的做法

### 16.1 一开始就做“自动改蓝图 + 自动改地图 + 自动改配置”
风险过高，定位失控。

### 16.2 不做 dry-run 直接执行
会让上游 Manifest 缺陷直接进入 UE 项目。

### 16.3 Bridge 自己猜命名和目录
应由 Manifest 显式声明。

### 16.4 上游 Review 未通过仍然写入
会破坏整条生产链的质量控制。

---

## 17. 结论

UE Bridge 的最小可运行实现应遵循：

- 先读后写
- 先 dry-run 再 execute
- 先低风险新增，后高风险修改
- 先接 Manifest，再转 Import Plan
- 先输出证据，再讨论自动回滚与复杂编辑

这条路径最适合你的框架早期落地：
既能让生产模式真正连到 UE，又不会过早把系统推向高风险的“全自动工程改写器”。
