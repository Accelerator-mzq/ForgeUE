---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S4
evidence_type: debug_log
contract_refs:
  - design.md
  - specs/artifact-contract/spec.md
  - specs/provider-routing/spec.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
detected_env: claude-code
triggered_by: "/forgeue:change-apply Phase B Task 1.3 (probe ComfyUI manifest params schema)"
codex_plugin_available: true
created_at: 2026-05-03T15:55:00+08:00
aligned_with_contract: true
drift_decision: written-back-to-design+specs+tasks+proposal (round 5 contract writeback per user-authorized 方案 A;DRIFT type 4 resolved)
writeback_commit: ebeb953
drift_reason: |
  Phase A 实施 commit 3 完成后,Phase B Task 1.3 实地 probe `comfyui_api params --workflow 3D_Hunyuan/3d_hunyuan3d-v2.1`
  暴露 design D7 的 implementability gap(round 1-4 codex review 全部未抓到此问题,因为
  无人跑过真实 manifest probe;design D7 + spec/artifact-contract Requirement
  「Mesh worker source image bytes are written to in-tree input file」假设
  ComfyUI LoadImage 接受任意绝对路径,实际只接受 ComfyUI 自己的 input/ 目录的 filename)。
writeback_commit: ebeb953
reasoning_notes_anchor: null
note: |
  本 debug_log 记录 Phase B Task 1.2-1.3 实地 probe 发现 + DRIFT type 4 的回写决策待定。
  Phase A 6 commit 已落,但 Phase B 实施在此处停下,等待用户决策修复方案。
---

# Phase B Task 1.2-1.3 ComfyUI Manifest Probe — Implementation Discovery

## Probe 命令 + 结果

### Task 1.2: `comfyui_api list`(grep mesh / 3D / glb)

可用 mesh-related manifests(本机 ComfyUI scripts/ 实测):

| Manifest | 输入模式 | 输出 | 备注 |
|---|---|---|---|
| `3D_Hunyuan/3d_hunyuan3d-v2.1` | `LoadImage`(input/ filename)| `model/glb` only | **候选** — 接外部 image,纯 GLB 输出 |
| `GameAssets/02_mini_textured_3d_hunyuan` | `LoadImageOutput`(只读 ComfyUI outputs/)| `model/glb` only(textured)| **不适合** ForgeUE DAG — 输入只能从 ComfyUI 历史输出加载 |
| `GameAssets/03_mini_image_to_3d_hunyuan` | 同 02 用 `LoadImageOutput` | mini GLB(无纹理)| 同 02 — 不适合 |
| `GameAssets/combined_shape_zimage` | 内部链式(text-to-image-to-mesh)| GLB | **不适合** — 单 manifest 内含 image step,不接受外部 image |
| `GameAssets/combined_textured_zimage` | 同 combined_shape | textured GLB | 同上 |

**唯一适合 ForgeUE image-to-mesh DAG 的 manifest**:`3D_Hunyuan/3d_hunyuan3d-v2.1`。

### Task 1.3: `comfyui_api params --workflow 3D_Hunyuan/3d_hunyuan3d-v2.1`

```json
{
  "params": {
    "input_image": {
      "type": "string", "required": true,
      "description": "输入图像文件名(放在 ComfyUI input 目录)",
      "patches": [{"node_class": "LoadImage", "field": "image"}]
    },
    "seed": {"type": "int", "default": 322640478891522, ...},
    "steps": {"type": "int", "default": 30, "range": [10, 100], ...},
    "cfg": {"type": "float", "default": 5.0, ...},
    "filename_prefix": {"type": "string", "default": "mesh/ComfyUI", ...}
  },
  "outputs": {"primary": "model/glb"}
}
```

**关键**:
- `input_image` 是 **filename**(string),不是绝对路径
- ComfyUI `LoadImage` 节点查找规则:**只读 ComfyUI 自己的 `input/` 目录**(`D:/AI/ComfyUI/apps/official-main-git-v092/input/`),不接受任意路径
- ForgeUE 必须把 source bytes 写到该 input/ 目录,不是 `<run_dir>/comfy/input/`

## DRIFT type 4: design D7 与 ComfyUI LoadImage 实际语义冲突

### 当前 contract(round 1-4 收敛后)

`design.md` D7 + `specs/artifact-contract/spec.md` Requirement「Mesh worker source image bytes are written to in-tree input file before subprocess invocation」:

> The system SHALL guarantee that ... the upstream source image bytes resolved by `_resolve_source_image(ctx)` are written to an in-tree input file under `<ctx.run_dir>/comfy/input/<sha1_hex>.png` ... before the worker subprocess is invoked.

`tests/unit/test_generate_mesh_comfy.py` (commit 4 落):
```python
def test_generate_via_comfy_worker_writes_source_bytes_to_in_tree_input_file_with_sha1_name:
    expected_path = ctx.run_dir / "comfy" / "input" / f"{expected_sha1}.png"
    ...
    assert expected_path.read_bytes() == src_bytes
```

### 实际 ComfyUI 行为

`LoadImage` 节点的 `image` 字段:**filename(不带路径前缀),resolve 到 ComfyUI 安装目录的 `input/` 子目录**。绝对路径或任意位置的文件 ComfyUI 找不到 → workflow execution 在 LoadImage 步报「missing input image file」错。

**Phase A 已实施代码会让 live smoke 100% 失败**(commit 3 `_generate_via_comfy_worker` 写到 `<run_dir>/comfy/input/<sha1>.png`,然后注入 `comfy_params["image_path"] = "<run_dir>/.../<sha1>.png"`;ComfyUI LoadImage 拿这个路径,找不到对应文件,raise)。

### 根因(round 1-4 codex review 全部 miss)

- R1 codex 抓 `MeshCandidate.payload` 不存在,但**没核对 ComfyUI LoadImage 节点查找规则**
- R2 codex 抓 `provider_policy` 路径错 + 异常族不交叉 + `Artifact.payload`,但同样没跑真机 probe
- R3 + R4 同样没跑
- Claude design D7 凭直觉假设「ComfyUI 接受任意绝对路径」(常见 framework 假设),无人验证
- **真正发现路径**:Phase B Task 1.3 第一次跑 `comfyui_api params` 看到「filename ... 放在 ComfyUI input 目录」description 时才显形

按 forgeue 协议「DRIFT type 4: evidence_exposes_contract_gap」,这是 implementation 暴露的 contract 漏洞,**必须回写**。

## 修复方案(用户决策点)

### 方案 A — `FORGEUE_COMFY_INPUT_DIR` env var + 写到 ComfyUI input/

- 加新 env var `FORGEUE_COMFY_INPUT_DIR`(默认空,REQUIRED for mesh path);用户配置 ComfyUI 自己 input/ 目录绝对路径
- `_generate_via_comfy_worker` 写 source bytes 到 `Path(FORGEUE_COMFY_INPUT_DIR) / f"forgeue_{sha1}.png"`
- 注入 `comfy_params["input_image"] = f"forgeue_{sha1}.png"`(filename only)
- ComfyUI LoadImage 在自己 input/ 找到文件
- **NFR-PORT-004 含义改变**:source image input 不再是「ForgeUE 项目树内 artifact」而是「外部依赖文件」;`tar artifacts/<run_id>/` 不含 input image(但 GLB output 仍 in-tree)
- spec/artifact-contract Requirement 重写「Mesh worker source image bytes are written to ComfyUI input/ directory (configured via FORGEUE_COMFY_INPUT_DIR)」
- design D7 修订:input/output 分别处理(input 在 ComfyUI 域,output 在 ForgeUE 域)
- D8 `comfy_image_param_key` 默认从 `"image_path"` 改为 `"input_image"`(对应 LoadImage 字段名)
- 优点:实际可工作 + 与 ComfyUI 节点语义一致
- 缺点:scope 外的副作用(ForgeUE artifact 不再 self-contained for input);依赖额外 env var 配置

### 方案 B — 双拷贝(in-tree + ComfyUI input/)

- `_generate_via_comfy_worker` 同时写 source bytes 到 `<run_dir>/comfy/input/<sha1>.png`(满足 NFR)+ `<comfy_input_dir>/forgeue_<sha1>.png`(供 LoadImage)
- 注入 `comfy_params["input_image"] = f"forgeue_<sha1>.png"`
- ComfyUI 找到文件 + ForgeUE artifact tree 仍 self-contained
- 缺点:双拷贝(I/O 浪费);cleanup 责任不清(ComfyUI input/ 目录长期累积);仍需 `FORGEUE_COMFY_INPUT_DIR` env var

### 方案 C — 用接受绝对路径的 ComfyUI manifest(自定义节点)

- 寻找/扩展支持 `LoadImageFromPath` 类节点的 manifest
- 本机 18 manifest 全部用 `LoadImage` / `LoadImageOutput`,无此类节点
- 需要用户在 ComfyUI 侧加自定义节点(超 ForgeUE scope)
- **不可行** in current ComfyUI installation

### 方案 D — abort Phase 1 mesh adoption,回退到 ComfyUI image-only

- 撤销 Phase A 6 commits(或留 worker capability dispatch 但禁用 mesh)
- SRS §7.3 TBD-009 行更新「ComfyUI agent CLI mesh capability adoption blocked on ComfyUI LoadImage node accepting absolute paths」
- 远端 mesh 继续走 Hunyuan3D
- 缺点:本 change 实质失败;Phase A 工作浪费

### Claude 推荐:**方案 A**

理由:
1. 实际可工作;与 ComfyUI 节点语义对齐
2. NFR-PORT-004 影响有限:input 文件不是 ForgeUE「产物」(artifact),而是「输入」;NFR-PORT-004 原意是「产物落项目树」,input 文件已经是 ForgeUE artifact(`<run_id>_img`)的副本拷贝,真源在 ForgeUE 内
3. 已有 `FORGEUE_COMFY_*` env var 模式(B-A round 2 决议),加一个不破坏架构
4. 方案 B 双拷贝引入复杂度但 NFR 收益小(input 不是产物,not lineage 关键)
5. 方案 D 太重,4 轮 codex review + Phase A 工作不应轻易放弃

## Writeback 工作量(若选方案 A)

- design.md D7 / D8 修订
- proposal.md What Changes / Impact / 环境段更新
- specs/artifact-contract/spec.md「Mesh worker source image bytes ...」Requirement 重写 + Scenario 修
- specs/provider-routing/spec.md `_generate_via_comfy_worker` 内部行为段修
- tasks.md §1.3 + §3.6 + §4.2 + §6.4 同步
- 实施改 commit 3 `_generate_via_comfy_worker`(+加 env var 读取 + 写入位置改 + filename injection)
- 改 commit 4 fence(`test_generate_mesh_comfy.py` source bytes 写入 location 断言改;`test_comfy_subprocess.py` D8 fence 改 `image_path` → `input_image` 默认值)

约 8-10 file 改动 + 2 commit(contract writeback commit + implementation commit β)。

## 当前 Phase A 状态

- commit 1 `0cafe62` config:**仍正确**(model id + alias 与节点语义无关)
- commit 2 `8f32ad7` worker capability dispatch:**仍正确**(三段表 + capability dispatch 与 input 路径无关)
- commit 3 `ff8bc36` executor + dry-run:**实施层有 bug**(_generate_via_comfy_worker 写入位置错;dry-run 不受影响)
- commit 4 `7dc8fac` 38 mesh fence:**部分 fence 假设错**(test_generate_via_comfy_worker_writes_source_bytes_to_in_tree_input_file_... 断言错)
- commit α `0a31d20` plan writeback:**仍有效**
- commit β `894c150` frontmatter backfill:**仍有效**

修复方案 A 落地后:
- commit 3 改为「写 ComfyUI input/ 目录 + filename injection」
- commit 4 fence 改 path 断言 + key 默认值改 `input_image`
- baseline 仍应 = 1230(fence 修复后等效)

## Next Steps

1. **用户决策**:方案 A / B / D(A 推荐)
2. **回写 contract**:design + 4 spec deltas + tasks + proposal 全部修订(plan-only writeback,不算新 codex review round)
3. **修 implementation**:commit β 改 `_generate_via_comfy_worker` 写入位置 + key 默认值;改对应 fence
4. **重新 Phase B Task 5-7**:用 `3D_Hunyuan/3d_hunyuan3d-v2.1` manifest + 用户在 host 侧跑 live smoke
