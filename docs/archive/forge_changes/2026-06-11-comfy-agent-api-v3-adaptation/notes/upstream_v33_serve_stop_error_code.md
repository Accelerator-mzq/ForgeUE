# 上游 comfyui_api v3.3 变更证据 — serve/stop 子命令 + error_code 结构化字段

> change: `comfy-agent-api-v3-adaptation` Task 3-4 · 日期: 2026-06-11
> 上游 `D:\AI\ComfyUI` 非 git 仓库,改动以本 note + 上游 pytest 输出留档。
> **并行变更说明**:执行期间上游文档/代码被维护者同步迭代(v3.1 --render-views /
> v3.2 factory_v3 loop),本次增量定名 **v3.3** 避免撞号;cli.py 编辑基于
> 含 v3.1/v3.2 的最新版本,无覆盖冲突。

## 改动文件(全部上游)

1. `D:/AI/ComfyUI/scripts/comfyui_api/cli.py`
   - 新增 `cmd_serve` / `cmd_stop`(直通 `comfyui_api.serve.serve_action/stop_action`,
     输出 JSON + ok=false exit 2)+ argparse 注册(8 → 10 子命令)
   - 新增 `_error_code(exc)`(异常 → 稳定 code,类型优先 + msg 子串次之,有序规则)
     与 `_fail_json(exc)`(统一失败 envelope)
   - 接线:cmd_run except / cmd_batch 外层 except + per-item / main() 全局兜底 →
     `_fail_json`;detach 校验 2 处 + status/cancel offline → 显式 error_code;
     cmd_serve/cmd_stop 失败 → `serve_failed` / `stop_failed`
2. `D:/AI/ComfyUI/scripts/comfyui_api/tests/test_cli.py`
   - 新增 19 个测试:serve/stop 4 个(输出直通 / exit code / argparse 注册)+
     `_error_code` 13 参数化分类 + cmd_run 失败 envelope + main() 兜底 envelope
3. `D:/AI/ComfyUI/docs/workflows/COMFYUI_AGENT_API.md`
   - 头部修订行加 v3.3;§1 "10 个命令" + 错误契约带 error_code;
     新增 §1.9 serve / §1.10 stop;§5 错误表改 4 列(error_code 为稳定契约列);
     §10 模块图 8 cmd → 10 cmd;§10.5.1 矩阵 6 命令 → 10 命令

## error_code 契约(v3.3)

`missing_required_param` / `param_out_of_range` / `invalid_arguments` /
`workflow_not_found` / `value_not_in_list` / `comfy_rejected` / `serve_failed` /
`stop_failed` / `timeout` / `prompt_errored` / `comfy_unreachable` / `prompt_lost` /
`input_image_not_found` / `unknown`

## 验证

```
TDD RED : 19 failed, 15 passed   (test_cli.py 追加后,实现前)
TDD GREEN: python -m pytest comfyui_api -q  ->  227 passed
手测   : python -m comfyui_api serve
         -> {"ok": true, "already_running": true, "ready_url": "http://127.0.0.1:8188/system_stats"}
         (ComfyUI 已运行时 no-op 语义正确)
```

## 动机(ForgeUE 侧)

- ForgeUE `_UNSUPPORTED_ERROR_MARKERS` 子串匹配上游错误文案是脆弱耦合;
  且 `"value out of range"` marker 与 patcher 实际串(`value {N} out of range`)
  **匹配不上**(latent bug,误把 deterministic 参数错当 generic error retry)。
  error_code 从根上解耦(Task 6 ForgeUE 消费)。
- ForgeUE `ComfyLifecycleManager` 此前必须调 `factory_v3 serve/stop`(唯一 CLI 入口);
  serve 实现 2026-06-11 已迁入 comfyui_api 包,本次补 CLI 入口后 ForgeUE 可对
  factory_v3 零依赖(Task 5 迁移),与 D-ScopeNoFactoryBlender 决策字面对齐。
