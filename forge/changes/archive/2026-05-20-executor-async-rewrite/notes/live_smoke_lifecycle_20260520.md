# L2 Live Smoke Evidence — executor-async-rewrite Task 11 Step 2

**日期**:2026-05-20
**Change**:`forge/changes/executor-async-rewrite/`
**Branch**:`feature/forge-migration`
**HEAD(smoke 实跑时)**:`17fb716`(Task 10 round 2 fix 后,Task 11 进行中);Fluid Pause #2 根因修复后 HEAD 待新 commit
**全量回归**:`1179 passed / 0 failed / 3 skipped`(既起动 path);`1185 passed / 0 failed / 3 skipped`(Fluid Pause #2 根因修复 + 6 新 fence 后)

## 目的

实证 Task 1-10 整体在真实 ComfyUI 上跑通 image 生成的端到端链路:
- async executor(Task 1-2 + Task 5-6 硬切)
- ComfyAgentWorker async-subprocess + comfy-submission 串行锁(Task 3-4)
- ComfyLifecycleManager + orchestrator try/finally release + aclose 钩子(Task 8-9)
- comfy_lifecycle 四模式 gate(Task 10)

## 环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows 11 Pro |
| ForgeUE Python | 3.13.13(`sys.executable`,跑 `framework.run`) |
| ComfyUI Python | 3.12.6(`D:\AI\ComfyUI\apps\official-main-git-v092\main.py`,独立 venv) |
| PyTorch | 2.10.0+cu130 |
| GPU | NVIDIA RTX 4060 Laptop GPU(VRAM 8GB,可用 7.4GB) |
| ComfyUI 版本 | 0.9.2 |
| ComfyUI 监听 | 127.0.0.1:8188 |
| `FORGEUE_COMFY_SCRIPTS_DIR` | `D:/AI/ComfyUI/scripts` |
| `FORGEUE_COMFY_LIFECYCLE` env | `ensure_running` |
| Bundle `comfy_lifecycle` | `ensure_running`(bundle 内显式,spec 优先于 env) |

## Bundle

`examples/comfy_local_smoke.json` —— 单步 image.generation,workflow `GameAssets/01b_singleview_sdxl`,512×512,prompt 为 oak barrel 静物。本次 evidence 期间将 `comfy_lifecycle` 由 `"none"` 改为 `"ensure_running"`(Task 11 同步,沿 tasks.md Task 11 Files 列表)。

## 实跑命令

```bash
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
FORGEUE_COMFY_LIFECYCLE=ensure_running \
python -m framework.run \
  --task examples/comfy_local_smoke.json \
  --live-llm \
  --run-id async_lc_smoke2
```

## 跑前状态

`comfyui_api status` 报告 `online: true`(本人 controller 在 evidence 取证前先用 `python -m factory_v3 serve` 手动暖启了 ComfyUI,见下方"自动拉起 caveat")。

## 跑后结果

`run_summary.json`(全量):
```json
{
  "run_id": "async_lc_smoke2",
  "status": "succeeded",
  "visited_steps": ["step_image"],
  "cache_hits": [],
  "artifact_ids": [
    "async_lc_smoke2_step_image_cand_73ff24e5_0",
    "async_lc_smoke2_step_image_set_73ff24e5"
  ],
  "checkpoint_ids": ["cp_async_lc_smoke2_step_image"],
  "trace_id": "trace_async_lc_smoke2",
  "termination_reason": null,
  "last_failure_mode": null,
  "failure_events": [],
  "revise_events": [],
  "verdicts": []
}
```

**关键指标**:
- `status: succeeded`,无 retry,无 fallback,无 failure events
- 单 step `step_image` 一次跑通(非 retry path)
- 产出 1 个 image candidate + 1 个 candidate_set bundle

## Artifact 产出

```
artifacts/2026-05-20/async_lc_smoke2/
├── _artifacts.json                                                   # repository index
├── _checkpoints.json                                                 # checkpoint store
├── async_lc_smoke2_step_image_cand_73ff24e5_0.png    192,985 bytes   # repository-put PNG
├── comfy/
│   └── asset_00001_.png                                              # ComfyUI agent CLI 输出原文件
└── run_summary.json
```

候选 image 共 192,985 bytes(~193KB),由 ComfyUI 经 SDXL workflow 实际渲染。文件存在性 + 字节大小 controller 实测。

## 跑后 lifecycle 状态

```bash
$ cd D:/AI/ComfyUI/scripts && python -m comfyui_api status
online: True
```

ComfyUI 在 run 结束后**仍在跑** —— 符合 `ensure_running` 模式的 `_RELEASE_STOPS` 决策表(`ensure_running` × `run_end` = no-op)。如果是 `ensure_release`,run_end 时 framework 会调 `factory_v3 stop`(决策表中 `("ensure_release","run_end") in _RELEASE_STOPS`)。

## 实证覆盖矩阵

| Task | 实证点 | 实证程度 |
|---|---|---|
| Task 1 | orchestrator 临时 async bridge | ✅ Task 6 已删,bridge 不在 `arun` 中 |
| Task 2 | 6 个无 worker executor 转 async | ✅ 单测 1179 passed,本次未直接命中(bundle 只有 image step) |
| Task 3 | ComfyAgentWorker async-subprocess + comfy-submission 串行锁 | ✅ `agenerate` 实际跑过 `asyncio.create_subprocess_exec` 调 `comfyui_api run`,产出 PNG |
| Task 4 | ComfyAgentWorker cancel + /interrupt | ⚠️ 单测验证;本次 happy path 跑通,未触发 cancel |
| Task 5 | 5 个 worker-backed executor 转 async | ✅ `GenerateImageExecutor` 真实跑通 `await worker.agenerate(...)` |
| Task 6 | StepExecutor.execute ABC 硬切 async + 删 bridge | ✅ `await executor.execute(ctx)` 直走 |
| Task 7 | cascade-cancel 真停 + drain 显式失败 | ⚠️ 单测验证;本次单 step 无 cascade |
| Task 8 | ComfyLifecycleManager(ensure / release / status 状态机) | ✅ `_detect_comfy_lifecycle` 检测 bundle `ensure_running`,manager 构建,`ensure()` 调 `status() → True`(既起动),`_framework_started=False` |
| Task 9 | Orchestrator 持有 lifecycle + try/finally + aclose | ✅ `arun` 内 manager 构建 + `ensure()` 走通,run_end 路径调 `release(mode="ensure_running", reason="run_end")` — 决策表 no-op,符合预期。`framework.run` 退出前调 `await orch.aclose()` |
| Task 10 | 解锁 comfy_lifecycle 四模式 gate | ✅ bundle `comfy_lifecycle: "ensure_running"` 通过 `__init__` + 4 个 `agenerate*` gate 全部 `_VALID_LIFECYCLES` 集合检查 |

## Fluid Pause #2:自动拉起 path 根因修复 + 实证(2026-05-20)

### 第一次自动拉起失败(`async_lc_smoke` / `async_lc_auto_smoke`)

ComfyUI 未起动状态下试图让 framework 自动拉起,3 次 step retry 全部 `worker_error`。controller 初判为「`_spawn_serve` 观测性不足」,加 `FORGEUE_COMFY_LIFECYCLE_LOG` env-conditional log capture 后**仍**失败,且 log file **未创建** → `_spawn_serve` 根本没被调到。

### 根因(Task 8 round 1 reviewer 漏抓)

`ComfyLifecycleManager.status()` 旧实现仅看 `proc.returncode == 0`,**没 parse stdout JSON 的 `online` 字段**。实测:`comfyui_api status` 即使 ComfyUI off 也 **exit 0** + 输出 `{"ok": true, "online": false}`(自身报告 status 调用成功,而非 ComfyUI online 状态)。

错误链:
1. `ensure()` 调 `status() → True`(returncode 0 误判,实际 online=false)
2. `_framework_started=False`(认为 "ComfyUI 已在跑,不是本框架起的")→ `_ensured=True` → return
3. `_spawn_serve` 永远不被调用(吻合 log file 缺失现象)
4. executor 走 `worker.agenerate` → 真实接 ComfyUI → connection refused → `WorkerError` × 3 retry

### 修复(`src/framework/runtime/lifecycle.py:status`)

`status()` 改为 parse stdout JSON 看 `"online"` 字段:
- `returncode != 0` → False(快路径)
- exit 0 + JSON parse 成功 → `bool(data.get("online"))`
- exit 0 + 非 JSON / 解码失败 → False(保守判定)

附 6 个新 fence(`tests/unit/test_comfy_lifecycle.py`):
- `test_status_returns_false_when_online_false_in_json`(根因 fence)
- `test_status_returns_true_when_online_true_in_json`
- `test_status_returns_false_when_stdout_is_not_json`(防御性)
- `test_status_returns_false_when_returncode_nonzero`(returncode fast-path)
- `test_spawn_serve_writes_log_when_env_set`(log capture branch fence)
- `test_spawn_serve_uses_devnull_when_env_unset`(后向兼容 fence)

并附 `_spawn_serve` 的 env-conditional log capture(`FORGEUE_COMFY_LIFECYCLE_LOG`)— 虽不是根因,但对未来诊断有价值,保留作为加固。

### 自动拉起 path 实证(`async_lc_auto_smoke3`)

```bash
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
FORGEUE_COMFY_LIFECYCLE=ensure_running \
FORGEUE_COMFY_LIFECYCLE_LOG=forge/changes/executor-async-rewrite/notes/spawn_serve_auto3_20260520.log \
python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id async_lc_auto_smoke3
```

**跑前**:`python -m comfyui_api status` → `online: false`(controller `factory_v3 stop` 后确认)
**结果**:
```json
{
  "run_id": "async_lc_auto_smoke3",
  "status": "succeeded",
  "visited_steps": ["step_image"],
  "artifact_ids": [
    "async_lc_auto_smoke3_step_image_cand_73ff24e5_0",
    "async_lc_auto_smoke3_step_image_set_73ff24e5"
  ],
  "failure_events": []
}
```

**关键指标**:
- `status: succeeded`,单 step,无 retry,无 fallback
- PNG 候选 **192,985 bytes**(与 `async_lc_smoke2` 既起动 path **deterministic 一致** — 同 seed 7777 / 同 SDXL workflow)
- `_spawn_serve` log file:160 bytes / 7 lines / 含 `{pid: 54368, started_in_s: 66.2, log_path: D:\AI\ComfyUI\scripts\factory_v3\.comfyui.log}` — factory_v3 冷起动 ComfyUI **66 秒**(在 `_READY_TIMEOUT_S=120.0` 内)
- 跑后 `comfyui_api status` → `online: true`(`ensure_running` × `run_end` 决策表 no-op,符合预期)
- artifact: `artifacts/2026-05-20/async_lc_auto_smoke3/async_lc_auto_smoke3_step_image_cand_73ff24e5_0.png` 192985 bytes,controller 实测

### Follow-on(executor-async-rewrite scope 内已闭)

- ~~`_spawn_serve` 观测性不足~~ → 已加 env-conditional log capture(2026-05-20)
- ~~自动拉起 path 不通~~ → 已修 `status()` JSON parse(2026-05-20 Fluid Pause #2 根因)
- `_READY_TIMEOUT_S = 120.0` 对超大模型首次下载场景偏紧 → 保留为 follow-on(可配置化,backlog active 增 entry)

## Cleanup

本次 evidence 取证完成后,ComfyUI 仍处于 `online: true`(`ensure_running` 语义),用户自管何时 `python -m factory_v3 stop`。
