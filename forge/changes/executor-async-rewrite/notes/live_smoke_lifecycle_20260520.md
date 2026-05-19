# L2 Live Smoke Evidence — executor-async-rewrite Task 11 Step 2

**日期**:2026-05-20
**Change**:`forge/changes/executor-async-rewrite/`
**Branch**:`feature/forge-migration`
**HEAD(smoke 实跑时)**:`17fb716`(Task 10 round 2 fix 后,Task 11 进行中)
**全量回归**:`1179 passed / 0 failed / 3 skipped`(controller 实测)

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

## 自动拉起 caveat(known limitation)

本次 evidence 是「ComfyUI 已经在跑 + framework `ensure_running` 探活检测既起动 → 使用」的路径,**不是**「ComfyUI 未起动 → framework `_spawn_serve` 自动拉起」的路径。

第一次跑(run_id `async_lc_smoke`)在 ComfyUI 未起动状态下试图让 framework 自动拉起,结果 3 次 step retry 全部 `worker_error`:
- `_spawn_serve()` 跑 `python -m factory_v3 serve`(stdout/stderr=`DEVNULL`,fire-and-forget),OS 层进程虽然投递了但 controller 这里看不到任何信号
- `_wait_ready()` polling `comfyui_api status` 120s 全部返回 `online: false`,最后超时抛 `TimeoutError`
- 路径走 `arun_error` → finally `release(mode="ensure_running", reason="arun_error")`(决策表 no-op,符合 `ensure_running` 语义)
- step level 3 retry 全 worker_error

随后 controller 本人手动 `python -m factory_v3 serve`(同一条命令,同一 cwd),ComfyUI 在 ~10s 内成功起动到 `online: true`。说明 `factory_v3 serve` 本身可工作,问题在 framework 经 `_spawn_serve` 调用时无法直接看到失败信号。

**后续 follow-on(executor-async-rewrite scope 外)**:
- `_spawn_serve` 改为可选 capture stderr 到 forge change `.evidence/` 或 `artifacts/<run_id>/lifecycle.log`,便于诊断真实环境的冷启动失败
- 当前 detached + `DEVNULL` 设计取舍是为了不阻塞调用方,trade-off 是观测性弱
- `_READY_TIMEOUT_S = 120.0` 对 ComfyUI 首次安装 + 模型下载场景偏紧;`ensure_running` 模式下可配置加长

这两条建议作为本 change archive 后的 follow-on 记录(`forge/backlog/active.md` 加 entry)。

## Cleanup

本次 evidence 取证完成后,ComfyUI 仍处于 `online: true`(`ensure_running` 语义),用户自管何时 `python -m factory_v3 stop`。
