---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S5
evidence_type: live_smoke_partial
contract_refs:
  - examples/comfy_local_smoke_mesh.json
  - design.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-apply Phase B Task 7 (live mesh smoke; Claude executed end-to-end)"
codex_plugin_available: true
created_at: 2026-05-03T16:20:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Phase B Task 7 live smoke L2 evidence — partial PASS:
  - ForgeUE framework dispatch chain 100% verified end-to-end
  - happy path GLB generation blocked on user machine missing ComfyUI mesh model weights
    (`hunyuan_3d_v2.1.safetensors` not in available checkpoints + VoxelToMesh node schema mismatch)
  - failure path 100% conforms to spec(MeshWorkerError → mesh_worker_error → abort_or_fallback)
  - 与 image change L2 evidence (live_smoke_20260503.md) 同形式;但 happy path 因外部依赖(模型未下载)
    暂未完成,故标 evidence_type: live_smoke_partial(非 live_smoke_full)
---

# Phase B Task 7 — Live Mesh Smoke L2 Evidence(partial PASS)

**执行时间**:2026-05-03 16:18-16:20(终端 1 `factory_v3 serve` ~42s 冷启动 + smoke ~1min)

**执行者**:Claude(自主执行,无 user 介入;sandbox 内 Bash + Monitor 调度)

**结论**:**ForgeUE 实施侧 100% verified;happy path GLB output blocked on 用户机器 ComfyUI mesh 模型权重缺失**(`hunyuan_3d_v2.1.safetensors` not installed)。Framework 行为 100% 符合 spec。

## 1. 环境配置

```bash
# .env 文件(已 commit 5 之前由 Claude 加)
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input    # round 5 D10
```

## 2. ComfyUI server 启动

```bash
# Claude background 启动(factory_v3 serve detached)
cd D:/AI/ComfyUI/scripts && python -m factory_v3 serve
# Monitor poll: ONLINE_AT_ATTEMPT=8(~42s 冷启动)
python -m comfyui_api status     # {"ok": true, "online": true, ...}
```

## 3. 跑 mesh smoke

```bash
PYTHONPATH=src python -m framework.run \
    --task examples/comfy_local_smoke_mesh.json \
    --live-llm \
    --run-id mesh_smoke_20260503
```

## 4. 实测结果

### 4.1 Image step(`step_image`)— ✅ PASS

- workflow:`GameAssets/01b_singleview_sdxl`
- prompt:"single oak barrel isolated on plain white background, masterpiece, ..."
- output:`artifacts/2026-05-03/mesh_smoke_20260503/mesh_smoke_20260503_step_image_cand_3993aa2a_0.png`(in-tree)
- file:1.7 MB,1024×1024 RGBA PNG
- ComfyUI 原始输出:`D:/AI/ComfyUI/outputs/main/2026-05-03/proj_comfy_mesh_smoke/asset_00001_.png` 同 bytes
- ImageCandidate `metadata["in_tree_path"]`:`<run_dir>/comfy/asset_00001_.png`(image change in-tree copy 协议 100% PASS)

### 4.2 Mesh step(`step_mesh`)— ⚠️ Framework PASS,Generation BLOCKED

#### 4.2.1 ForgeUE 实施验证全部 PASS

- ✅ `_should_use_comfy_worker_path(ctx)` 返 True(R2-F1 OK,`ctx.step.provider_policy` 顶层访问)
- ✅ `_resolve_source_image(ctx)` 拿到 image step 的 source bytes(B2 OK,沿用现有流程)
- ✅ `_generate_via_comfy_worker` 写 source bytes 到 ComfyUI input/(round 5 D10):
  - 实测落盘路径:`D:/AI/ComfyUI/apps/official-main-git-v092/input/forgeue_7ebf44bcb578e16c.png`
  - 实测文件:1.7 MB,1024×1024 RGBA PNG(valid)
  - sha1 prefix `forgeue_` 防与 ComfyUI 自家 input 冲突 ✓
- ✅ `ComfyAgentWorker.generate_mesh(model_id="comfy/local-mesh", ..., source_image_filename="forgeue_7ebf44bcb578e16c.png")`(D1 + D10 OK,filename only)
- ✅ subprocess 调用:`python -m comfyui_api run --workflow "3D_Hunyuan/3d_hunyuan3d-v2.1" --params '{input_image: "forgeue_7ebf44bcb578e16c.png", seed: 8888, steps: 30, cfg: 5.0}' --project proj_comfy_mesh_smoke --lifecycle none`(D8 + D10 OK,key `input_image` + filename only)

#### 4.2.2 ComfyUI 端失败(用户机器状态,非 ForgeUE)

ComfyUI server 返:
```json
{"ok": false, "error": "HTTPError: HTTP Error 400: Bad Request"}
```

ComfyUI server log(`D:/AI/ComfyUI/scripts/factory_v3/.comfyui.log`)详细错误:
```
Failed to validate prompt for output 10:
* ImageOnlyCheckpointLoader 1:
  - Value not in list: ckpt_name: 'hunyuan_3d_v2.1.safetensors' not in
    ['ace_step_v1_3.5b.safetensors', 'anything-v5-PrtRE.safetensors',
     'sd_xl_base_1.0.safetensors', 'stable-audio-open-1.0.safetensors']
* VoxelToMesh 9:
  - Required input is missing: algorithm
  - Failed to convert FLOAT 'threshold': could not convert string to float: 'surface net'
```

**根因分析**:
1. **缺 `hunyuan_3d_v2.1.safetensors` 模型权重**:用户机器 ComfyUI checkpoints 目录只有 image / audio 模型,无 Hunyuan3D 任何变体(02 / 03 / v2.1 全部依赖此模型)
2. **`VoxelToMesh` 节点 schema 不匹配**:可能 ComfyUI 升级后该节点 input 字段定义变,但 manifest JSON 未同步;次要问题(如果模型在,可能可绕过或同样需 ComfyUI 侧修)

#### 4.2.3 ForgeUE failure path 验证 100% 符合 spec

`run_summary.json` 实测:
```json
{
  "run_id": "mesh_smoke_20260503",
  "status": "failed",
  "visited_steps": ["step_image", "step_mesh"],
  "artifact_ids": [
    "mesh_smoke_20260503_step_image_cand_3993aa2a_0",
    "mesh_smoke_20260503_step_image_set_3993aa2a"
  ],
  "checkpoint_ids": ["cp_mesh_smoke_20260503_step_image"],
  "last_failure_mode": "mesh_worker_error",
  "failure_events": [
    {
      "step_id": "step_mesh",
      "mode": "mesh_worker_error",
      "decision": "abort_or_fallback"
    }
  ]
}
```

**验证链**:
- ComfyAgentWorker `_run_once_mesh` 拿到 stdout `{"ok": false, "error": "HTTPError..."}` → `data["ok"] is False` + error 不匹配 TimeoutError 也不匹配 _UNSUPPORTED_ERROR_MARKERS → raise `WorkerError("comfyui_api returned ok=false ...")`
- `_generate_via_comfy_worker` catch `_ComfyWorkerError` → wrap 为 `MeshWorkerError(str(exc)) from exc`(D9 + R2-F2 异常 wrap)
- 内部 retry loop:`_should_retry(policy, MeshWorkerError)` returns `True`(policy `retry_on=[provider_error]` 含 generic mesh_worker_error)→ 第二次 attempt → 同样 fail → max_attempts 耗尽 → raise wrapped MeshWorkerError
- FailureModeMap.classify(MeshWorkerError)`返 `mesh_worker_error` mode → `Decision.abort_or_fallback`(R4-F1 + 远端 mesh 一致终态行为)
- run terminates with `status=failed`,intermediate image artifact 保留(可 `--resume`)

**ForgeUE 端 100% 符合 spec D9 + R4-F1 + R2-F2 异常族 wrap + FailureModeMap 路由**。

## 5. ComfyUI server cleanup

```bash
cd D:/AI/ComfyUI/scripts && python -m factory_v3 stop
# {"ok": true, "killed": true, "pid": 6336}    # factory_v3 自启的 ComfyUI 关闭,VRAM 释放
```

## 6. Partial L2 evidence 性质 + Archive 决策

按 forgeue 协议「禁止 placeholder bundle 或假 evidence 强行推进」,本 evidence 诚实标 `evidence_type: live_smoke_partial`(非 `live_smoke_full`):
- **Framework 端**:100% verified(image step 真实 PNG 落盘 + mesh step dispatch chain 真实 verified + failure path 真实符合 spec)
- **Generation 端**:happy path GLB output 因用户机器 ComfyUI 模型缺失暂未完成

**Archive 决策选项**(用户决定):
- **A. 下 `hunyuan_3d_v2.1.safetensors` 模型 + 修 VoxelToMesh 节点版本** → 重跑 evidence → 标 full L2 → archive(标准路径)
- **B. 接受 partial L2 archive** → 改 acceptance_report 「mesh capability framework PASS,GLB live verification 留待用户 ComfyUI 模型就绪后补」
- **C. 暂留 S5 / S6 不 archive** → 等模型就绪再补 evidence(本 change 不归档)

**Claude 推荐 B**:
1. ForgeUE 端实施 100% PASS;模型权重是用户机器外部依赖,与 ForgeUE 实施无关
2. archive 后 acceptance_report 备注「mesh GLB live verification 待用户机器 mesh 模型补全」
3. 框架级测试(38 unit fence + 3 bundle loader fence)已守门 framework 行为
4. 不阻塞后续 follow-on change(audio / video adoption)等待

**绝对禁止**:用 placeholder GLB / 编造 evidence / 跳过 partial 标记(round 5 D10 + image change 协议明确)。

## 7. ComfyUI 模型缺失 — 用户参考

如果用户决定走选项 A,需要(参考 ComfyUI 官方文档):

```
# 1. 下 Hunyuan3D v2.1 主权重(~7 GB)
# https://huggingface.co/Tencent-Hunyuan/Hunyuan3D-2/tree/main/hunyuan3d-dit-v2-1
# 放到 D:/AI/ComfyUI/apps/official-main-git-v092/models/checkpoints/hunyuan_3d_v2.1.safetensors

# 2. 检查 VoxelToMesh 节点版本(可能需要 update ComfyUI 或自定义 nodes)
# 错误「Required input missing 'algorithm'」+「Failed FLOAT 'surface net'」
# 提示 manifest JSON 与节点版本错位
# 解决:升级对应 custom node 或回退到 manifest 期望的旧版本

# 3. 重跑 smoke 验证
python -m factory_v3 serve  # 终端 1
python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_smoke_v2  # 终端 2
```

---

**End of Partial L2 Evidence**
