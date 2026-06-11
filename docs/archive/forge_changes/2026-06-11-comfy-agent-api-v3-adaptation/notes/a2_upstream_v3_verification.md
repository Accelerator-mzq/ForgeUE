# A2 — 上游 COMFYUI_AGENT_API.md v3（2026-06-11）状态实证

> change: `comfy-agent-api-v3-adaptation` · 验证日期: 2026-06-11
> 验证方式: 直接读上游文件 + CLI 实测(上游 `D:\AI\ComfyUI` **非 git 仓库**,
> `git rev-parse --is-inside-work-tree` → fatal,故上游侧改动无 commit 证据,
> 以本 notes + pytest 输出留档)

## 1. v3 文档修订面(对照 ForgeUE 契约逐条核验)

来源: `D:\AI\ComfyUI\docs\workflows\COMFYUI_AGENT_API.md`(修订 2026-06-11 v3)。

| v3 变更 | ForgeUE 影响 | 实证 |
|---|---|---|
| 统一 JSON 错误契约(exit 2 + 永不裸 traceback) | 兼容增强;ForgeUE 本就 parse-stdout-JSON 优先 | `comfy_worker.py:916-949` |
| 新命令 `upload` / `wait` / `--detach` | 不破坏;detach+wait 留 backlog `comfy-detach-wait-adoption` | `cli.py:292-374` 实测 8 子命令 |
| `run` 对 `input_image*` 本地路径自动上传 | A1 适配点:mesh 路径可退役 `FORGEUE_COMFY_INPUT_DIR` | `runner.py:180-195` `_auto_upload_input_images` |
| `outputs` 五键(images/audio/glb/video/raw)文档化 | `outputs.video` 自此是上游正式契约(见 §2) | doc §1.3 |
| 解除 comfyui_api→factory_v3 反向依赖 | serve 实现已迁 `comfyui_api/serve.py`;ForgeUE lifecycle 可迁移(Task 5) | `factory_v3/serve.py` 现为 re-export shim |
| poll fail-fast 新错误串 | 落 ForgeUE generic WorkerError → 本地非 premium retry,行为正确 | `runner.py:259-288` |

## 2. runner.py video collection block 状态

- `comfyui_api/runner.py:365-381` video block(VHS_VideoCombine legacy `gifs` key 收集)**仍在**,
  注释仍标 "User-authored note (ForgeUE round-3 codex plan review PF1 fix, 2026-05-04) ... ComfyUI 重装时手工保留"。
- v3 文档 §1.3 已把 `outputs.video` 列为五键正式契约 → 该 block 的性质从
  "ForgeUE 单方面外挂补丁(漏 → 静默不收集)"升级为"上游文档化 API 的实现组成部分"。
- **结论**: 风险降级但不撤出 must-preserve 清单(上游无 git,重装仍可能丢);
  CLAUDE.md 标注降级理由(Task 8)。

## 3. Wan manifest VHS widget patches 状态(round-7 R2 项)

| manifest | VHS 5 params(frame_rate/loop_count/format/pingpong/save_output) |
|---|---|
| `Vedio/Wan2.1-T2V-1.3B_native_5sec.json` | ✅ 13 params,5 个全在 |
| `Vedio/Wan2.1-T2V-1.3B_native.json` | ✅ 13 params,5 个全在 |
| `Vedio/Wan2.1-T2V-1.3B_native_teacache.json` | ❌ **缺全部 5 个**(仅 8 params)→ Task 1 补 |

teacache workflow JSON(`workflows/official_main_validated_api/Vedio/..._teacache.json`)的
VHS_VideoCombine inputs 占位符存在**错位**(`pingpong: 'pix_fmt'`、`save_output: 'crf'`),
但 manifest patch 按 field 名写真值覆盖,不受占位符内容影响(5sec 同款机制已 L2 验证)。

## 4. mesh manifest 真相(修正 v3 文档 §3.1 表的水分)

- 标准 `GameAssets/03_mini_image_to_3d_hunyuan.json` manifest 实测 **不暴露 `input_image`**
  (workflow 用 LoadImageOutput 节点;params 仅 mesh_seed/mesh_steps/mesh_target_faces/filename_prefix/mesh_format)。
  v3 文档 §3.1 表标 "input_image / seed / mesh_format" 与实物不符。
- **结论**: user-authored `03_mini_image_to_3d_hunyuan_loadimage` 变体(workflow + manifest 两文件)
  **仍必须保留**;A1 退役的是 ForgeUE 侧 `FORGEUE_COMFY_INPUT_DIR` 直写机制,
  manifest 选择不变。

## 5. ForgeUE marker latent bug(本次顺带修)

patcher 实际错误串 `Param '{name}' value {value} out of range [lo, hi]`(`patcher.py:134`,
中间含数值),ForgeUE `_UNSUPPORTED_ERROR_MARKERS` 的 `"value out of range"` 子串
**永远匹配不上** → out-of-range 错误现状落 generic WorkerError(误 retry)。
Task 4(上游 error_code)+ Task 6(marker 改 `"out of range"` fallback)双层修复。
