# ComfyUI Agent API v3 适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 ForgeUE 对 ComfyUI agent CLI 的集成对齐 v3（2026-06-11）契约：error_code 结构化错误分类、comfyui_api serve/stop 子命令迁移、mesh 路径 input_image 自动上传（退役 `FORGEUE_COMFY_INPUT_DIR`）、video smoke 切 teacache manifest、cancel 多租户边界标注。

**Architecture:** 两个本机仓库——ForgeUE（git，分支 `codex/comfy-agent-api-v3-adaptation`）与上游 `D:\AI\ComfyUI\scripts`（**非 git 仓库**，直接编辑 + 上游 pytest 验收）。顺序：A2 证据固化 → A3 teacache（上游 manifest 补丁先行，用 stock CLI 跑 L2）→ 上游 CLI 扩展（serve/stop + error_code）→ ForgeUE 消费迁移 → A1 mesh auto-upload → 文档同步收尾。每个 ForgeUE task 单独 commit。

**Tech Stack:** Python stdlib（asyncio subprocess / argparse / json）、pytest、ComfyUI agent CLI（`python -m comfyui_api`）。

**已实证的关键事实（计划依据，执行时不必重查）:**
- 上游 `D:\AI\ComfyUI` 不是 git 仓库（`git rev-parse` fatal）。
- `comfyui_api/cli.py` 现有 8 子命令；错误兜底在 `main()` L446-454 与 `cmd_run` L186-188 / `cmd_batch` L211-212, L220-222；serve 实现已在 `comfyui_api/serve.py`（`serve_action()` / `stop_action()`，`factory_v3/serve.py` 只是 shim）。
- patcher 实际错误串：`Missing required param '...'`（L123）、`Param '...' value {value} out of range [lo, hi]`（L134）→ ForgeUE marker `"value out of range"` **匹配不上**实际串（中间有数值），是 latent bug，本次随 error_code fallback 一并修。
- teacache manifest（`manifests/Vedio/Wan2.1-T2V-1.3B_native_teacache.json`）缺 5 个 VHS widget params（5sec/native 有）；不补则 run 必 HTTP 400（round-7 R2 同因）。
- `GameAssets/03_mini_image_to_3d_hunyuan` 标准 manifest **不暴露** `input_image`（用 LoadImageOutput 节点）→ loadimage 变体 manifest 仍必须保留；A1 退役的是 ForgeUE 侧 input-dir 写入机制。
- 上游 `runner._auto_upload_input_images`（runner.py L180-195）：参数名 `input_image` 前缀 + 值含路径分隔符 + 文件存在 → 自动 POST /upload/image；裸文件名不动。
- ForgeUE 4 个 `_run_once_*` 的 ok=false 分类块完全同构（comfy_worker.py L935-949 / L1296-1310 / L1536-1550 / L1797-1811）。
- `FORGEUE_COMFY_INPUT_DIR` 引用面：`comfy_provider_config.py:91`、`generate_mesh.py:122-141`、`comfy_worker.py:1355-1358`（注释）、`config/models.yaml:116`、`tests/unit/test_generate_mesh_comfy.py`（~20 处）、`tests/unit/test_comfy_provider_config.py:29,62,69,89`。dry_run_pass 无引用。

---

### Task 0: 分支 + 评估证据固化（A2）

**Files:**
- Create: `docs/archive/forge_changes/2026-06-11-comfy-agent-api-v3-adaptation/notes/a2_upstream_v3_verification.md`

- [ ] **Step 0.1: 建分支**

```bash
git checkout -b codex/comfy-agent-api-v3-adaptation
```

- [ ] **Step 0.2: 验证 `_native` manifest 也有 5 个 VHS params（round-7 R2 称两份都补过）**

```bash
python -c "
import json
m=json.load(open(r'D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native.json',encoding='utf-8'))
print(sorted(m['params'].keys()))"
```
Expected: 含 `format`/`frame_rate`/`loop_count`/`pingpong`/`save_output`。

- [ ] **Step 0.3: 写 A2 证据 note**

内容要点（全部已实证）：runner.py video block 仍在（L365-381，注释仍标 user-authored）；v3 文档已把 `outputs.video` 列为正式五键契约（AGENT_API.md §1.3）→ 风险从"漏 → 静默不收集"降级为"上游契约的一部分"；5sec manifest 13 params 在；teacache manifest 缺 5 VHS params（Task 2 补）；标准 03_mini manifest 无 input_image → loadimage 变体仍必须；上游非 git 仓库 → 上游改动无 commit 证据，以 pytest + 手测输出留档。

- [ ] **Step 0.4: Commit**

```bash
git add docs/archive/forge_changes/2026-06-11-comfy-agent-api-v3-adaptation/
git commit -m "docs: comfy agent api v3 适配 A2 上游状态实证"
```

---

### Task 1: A3 上游 — teacache manifest 补 5 个 VHS widget patches

**Files:**
- Modify: `D:\AI\ComfyUI\scripts\comfyui_api\manifests\Vedio\Wan2.1-T2V-1.3B_native_teacache.json`（上游，非 git）

- [ ] **Step 1.1: 在 manifest `params` 末尾加 5 个字段（与 5sec manifest 逐字一致）**

```json
"frame_rate": {"type": "float", "default": 24.0,
  "patches": [{"node_class": "VHS_VideoCombine", "field": "frame_rate"}]},
"loop_count": {"type": "int", "default": 0,
  "patches": [{"node_class": "VHS_VideoCombine", "field": "loop_count"}]},
"format": {"type": "string", "default": "video/h264-mp4",
  "patches": [{"node_class": "VHS_VideoCombine", "field": "format"}]},
"pingpong": {"type": "bool", "default": false,
  "patches": [{"node_class": "VHS_VideoCombine", "field": "pingpong"}]},
"save_output": {"type": "bool", "default": true,
  "patches": [{"node_class": "VHS_VideoCombine", "field": "save_output"}]}
```

注意：teacache workflow JSON 的 VHS inputs 占位符有错位（`pingpong: 'pix_fmt'`、`save_output: 'crf'`），manifest patch 按 field 名覆盖真值，不受影响；但在 A2 note 里记一笔。

- [ ] **Step 1.2: 验证 manifest 解析 + 上游测试**

```bash
cd D:/AI/ComfyUI/scripts
python -m comfyui_api params --workflow Vedio/Wan2.1-T2V-1.3B_native_teacache  # 应列出 13 params
python -m pytest comfyui_api/tests/test_manifests.py -q
```
Expected: 13 params；pytest 全 PASS。

---

### Task 2: A3 ForgeUE — video smoke 切 teacache + L2 实测

**Files:**
- Modify: `examples/comfy_local_smoke_video.json:50,56`
- Create: `docs/archive/.../notes/live_smoke_video_teacache.md`
- 不动 `examples/cluster2_l2_video_export.json`（export L2 evidence 锚定已验证 baseline，留 5sec）

- [ ] **Step 2.1: 改 bundle**

`"comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec"` → `"Vedio/Wan2.1-T2V-1.3B_native_teacache"`；`"num_frames": 81` → `33`（teacache 默认，约 1.4s 视频，smoke 只验 pipeline 真通）。其余参数不动。

- [ ] **Step 2.2: 查 ForgeUE 测试是否硬编码旧 manifest 名**

```bash
grep -rn "native_5sec" tests/ src/ examples/
```
命中 `examples/cluster2_l2_video_export.json` 之外的测试断言则同步改。

- [ ] **Step 2.3: 离线回归**

```bash
python -m pytest tests/ -q -k "example or examples"
```
Expected: PASS（examples_smoke 类 fence 吃新 bundle）。

- [ ] **Step 2.4: L2 实测（真 GPU 生成）**

```bash
cd D:/AI/ComfyUI/scripts && python -m comfyui_api status   # online:false 则 python -m factory_v3 serve
cd D:/ClaudeProject/ForgeUE_codex
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id video_teacache_smoke_20260611
```
Expected: status succeeded；`artifacts/2026-06-11/video_teacache_smoke_20260611/*.mp4` 真实存在（>100KB，BMFF 校验已过）。耗时目标 ~2.5min（vs 5sec 的 ~7min）。

- [ ] **Step 2.5: 写 evidence note + Commit**

note 记录：耗时对比、产物路径、文件大小、`comfyui_api status` 输出摘要。

```bash
git add examples/comfy_local_smoke_video.json docs/archive/forge_changes/2026-06-11-comfy-agent-api-v3-adaptation/
git commit -m "feat: video smoke 默认 manifest 切 teacache(7min→~2.5min)+L2 evidence"
```

---

### Task 3: 上游 — comfyui_api 加 serve/stop 子命令

**Files:**
- Modify: `D:\AI\ComfyUI\scripts\comfyui_api\cli.py`
- Modify: `D:\AI\ComfyUI\scripts\comfyui_api\tests\test_cli.py`

- [ ] **Step 3.1: 先写失败测试（上游 test_cli.py 风格：SimpleNamespace + capture_stdout + patch.object）**

```python
def test_cli_serve_outputs_action_result():
    """serve 子命令直通 serve_action,输出 JSON,ok=false 时 exit 2。"""
    from comfyui_api import serve as serve_mod
    args = SimpleNamespace()
    with patch.object(serve_mod, "serve_action",
                      return_value={"ok": True, "already_running": True, "ready_url": "http://x"}):
        out, code = capture_stdout(cli.cmd_serve, args)
    parsed = json.loads(out)
    assert parsed["ok"] is True and parsed["already_running"] is True
    assert code == 0

def test_cli_serve_failure_exits_2_with_error_json():
    from comfyui_api import serve as serve_mod
    args = SimpleNamespace()
    with patch.object(serve_mod, "serve_action",
                      return_value={"ok": False, "error": "config not found; ..."}):
        out, code = capture_stdout(cli.cmd_serve, args)
    parsed = json.loads(out)
    assert parsed["ok"] is False and code == 2

def test_cli_stop_outputs_action_result():
    from comfyui_api import serve as serve_mod
    args = SimpleNamespace()
    with patch.object(serve_mod, "stop_action",
                      return_value={"ok": True, "killed": False, "reason": "no pid file"}):
        out, code = capture_stdout(cli.cmd_stop, args)
    parsed = json.loads(out)
    assert parsed["ok"] is True and parsed["killed"] is False
    assert code == 0

def test_cli_parser_registers_serve_and_stop():
    """argparse 注册面 fence:serve/stop 是合法子命令。"""
    with patch.object(sys, "argv", ["comfyui_api", "serve"]), \
         patch.object(cli, "cmd_serve") as fake:
        cli.main()
    assert fake.called
```

- [ ] **Step 3.2: 跑测试确认 FAIL**

```bash
cd D:/AI/ComfyUI/scripts && python -m pytest comfyui_api/tests/test_cli.py -q -k "serve or stop"
```
Expected: FAIL（`cli has no attribute cmd_serve`）。

- [ ] **Step 3.3: 实现 cmd_serve / cmd_stop + parser 注册**

cli.py 顶部 import 行加 `serve as serve_mod`（保持惰性无副作用：serve.py 顶层只有可选 psutil import）。`cmd_wait` 之后加：

```python
# ---------------------------------------------------------------------------
# cmd_serve / cmd_stop
# ---------------------------------------------------------------------------

def cmd_serve(args):
    """启动 ComfyUI（detached）。已在运行则 already_running=true 无副作用。

    实现即 comfyui_api.serve.serve_action（2026-06-11 自 factory_v3 迁入）；
    此前唯一 CLI 入口在 factory_v3 serve，本命令补齐 comfyui_api 自身的
    进程管理入口，外部 orchestrator 不必再依赖 factory_v3。
    """
    result = serve_mod.serve_action()
    _print_json(result)
    sys.exit(0 if result.get("ok") else 2)


def cmd_stop(args):
    """停止 serve 启动的 ComfyUI（只关 .comfyui.pid 记录的自启进程）。"""
    result = serve_mod.stop_action()
    _print_json(result)
    sys.exit(0 if result.get("ok") else 2)
```

main() 里 wait parser 之后注册：

```python
    # serve
    sp = sub.add_parser("serve", help="Start ComfyUI (detached); no-op if already running")
    sp.set_defaults(func=cmd_serve)

    # stop
    sp = sub.add_parser("stop", help="Stop the ComfyUI instance started by serve")
    sp.set_defaults(func=cmd_stop)
```

模块 docstring 命令清单 8 → 10（加 serve / stop 两行）。

- [ ] **Step 3.4: 测试过 + 手测**

```bash
python -m pytest comfyui_api/tests/test_cli.py -q
python -m comfyui_api stop    # 无 pid file 时应输出 {"ok": true, "killed": false, "reason": "no pid file"}
```

---

### Task 4: 上游 — 统一错误输出加 error_code 结构化字段

**Files:**
- Modify: `D:\AI\ComfyUI\scripts\comfyui_api\cli.py`
- Modify: `D:\AI\ComfyUI\scripts\comfyui_api\tests\test_cli.py`
- Modify: `D:\AI\ComfyUI\docs\workflows\COMFYUI_AGENT_API.md`

- [ ] **Step 4.1: 失败测试（表驱动）**

```python
@pytest.mark.parametrize("exc,expected_code", [
    (ValueError("Missing required param 'text' for workflow 'X'"), "missing_required_param"),
    (ValueError("Param 'width' value 99999 out of range [256, 2048]"), "param_out_of_range"),
    (RuntimeError("ComfyUI rejected prompt: {'error': 'value_not_in_list ...'}"), "value_not_in_list"),
    (FileNotFoundError("API workflow not found: 'X' at ..."), "workflow_not_found"),
    (FileNotFoundError("input image not found: D:/x.png"), "input_image_not_found"),
    (TimeoutError("Prompt 'p' did not complete within 600s"), "timeout"),
    (RuntimeError("ComfyUI unreachable for 30 consecutive polls ..."), "comfy_unreachable"),
    (RuntimeError("Prompt 'p' not found in history nor queue — ..."), "prompt_lost"),
    (RuntimeError("Prompt 'p' error: [...]"), "prompt_errored"),
    (RuntimeError("failed to start ComfyUI: port busy"), "serve_failed"),
    (KeyError("whatever"), "unknown"),
])
def test_error_code_classification(exc, expected_code):
    assert cli._error_code(exc) == expected_code

def test_cmd_run_failure_json_contains_error_code():
    args = SimpleNamespace(workflow="W", params='{"x":1}', params_file=None,
                           lifecycle="none", timeout=60, project="p",
                           detach=False, render_views=None)
    with patch.object(cli.lifecycle, "with_lifecycle",
                      side_effect=ValueError("Missing required param 'text' for workflow 'W'")), \
         patch.object(cli, "_decide_timeout", return_value=60):
        out, code = capture_stdout(cli.cmd_run, args)
    parsed = json.loads(out)
    assert parsed["ok"] is False
    assert parsed["error_code"] == "missing_required_param"
    assert code == 2
```

- [ ] **Step 4.2: 跑测试确认 FAIL**（`cli has no attribute _error_code`）

- [ ] **Step 4.3: 实现 `_error_code` + 接线**

cli.py helpers 区加：

```python
# (exception 判别, error_code) 有序规则表:类型优先,msg 子串次之。
# error_code 是 stable 契约(下游 agent/框架按 code 分类,不再耦合错误文案;
# 文案仍可自由演进)。新增错误类型时同步更新 AGENT_API.md §5 表。
def _error_code(exc: BaseException) -> str:
    msg = str(exc)
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, FileNotFoundError):
        if "input image not found" in msg:
            return "input_image_not_found"
        return "workflow_not_found"
    if isinstance(exc, ValueError):
        if "Missing required param" in msg:
            return "missing_required_param"
        if "out of range" in msg:
            return "param_out_of_range"
        return "invalid_arguments"
    if "value_not_in_list" in msg:
        return "value_not_in_list"
    if "unreachable for" in msg:
        return "comfy_unreachable"
    if "not found in history nor queue" in msg:
        return "prompt_lost"
    if "failed to start ComfyUI" in msg:
        return "serve_failed"
    if isinstance(exc, RuntimeError) and "ComfyUI rejected" in msg:
        return "comfy_rejected"
    if isinstance(exc, RuntimeError) and "error" in msg and "Prompt" in msg:
        return "prompt_errored"
    return "unknown"


def _fail_json(exc: BaseException) -> dict:
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
            "error_code": _error_code(exc)}
```

接线（4 处异常路径全部换 `_fail_json(e)`）：
- `cmd_run` L186-188 except 块 → `_print_json(_fail_json(e))`
- `cmd_batch` 外层 except L220-222 → 同上
- `cmd_batch` per-item except L211-212 → `results.append({"index": i, **_fail_json(e)})`
- `main()` 全局兜底 L452-454 → `_print_json(_fail_json(e))`
- `cmd_run` detach 校验两处手写 dict（L144-149, L152-157）加 `"error_code": "invalid_arguments"`
- `cmd_status` / `cmd_cancel` 的 `ComfyUI offline` dict 加 `"error_code": "comfy_unreachable"`
- `cmd_serve` / `cmd_stop`：result ok=false 时输出前补 `result.setdefault("error_code", "serve_failed" if <serve> else "stop_failed")`

注意 `value_not_in_list` 判定要在 `comfy_rejected` 之前（rejected response 文本里含 value_not_in_list 时取细码）——规则表顺序已保证。

- [ ] **Step 4.4: 上游全量测试**

```bash
cd D:/AI/ComfyUI/scripts && python -m pytest comfyui_api -q
```
Expected: 全 PASS（既有失败断言只查 ok/error，加字段不破坏）。

- [ ] **Step 4.5: 上游文档同步 `COMFYUI_AGENT_API.md`**

- 头部修订行追加 `2026-06-11 (v3.1: serve/stop 子命令 + error_code 结构化错误字段)`
- §1 标题 "8 个命令" → "10 个命令"；错误契约段：`{"ok": false, "error": "...", "error_code": "<stable-code>"}`
- 新增 §1.9 serve / §1.10 stop（命令、输出 JSON 示例、"只关自启进程"安全语义、与 factory_v3 serve/stop 的关系：实现同源，factory_v3 入口保留兼容）
- §5 错误表加 `error_code` 列（missing_required_param / param_out_of_range / workflow_not_found / value_not_in_list / serve_failed / timeout / prompt_errored / comfy_unreachable / prompt_lost / input_image_not_found / comfy_rejected / invalid_arguments / unknown）
- §10.5.1 矩阵 "comfyui_api（6 命令）" → "（10 命令）"

---

### Task 5: ForgeUE — lifecycle 迁移到 comfyui_api serve/stop

**Files:**
- Modify: `src/framework/runtime/lifecycle.py:226-296`（_spawn_serve / _spawn_stop + docstrings L35,85,95,232,239,248,267,283）
- Modify: `src/framework/runtime/orchestrator.py:70`（注释）
- Modify: `src/framework/providers/workers/comfy_worker.py:1954,1970`（aprobe 错误信息）
- Modify: `tests/unit/test_comfy_lifecycle.py`

- [ ] **Step 5.1: 失败 fence（捕获 argv 断言新命令）**

test_comfy_lifecycle.py 加（沿该文件 captured-args monkeypatch 模式）：

```python
@pytest.mark.asyncio
async def test_spawn_serve_uses_comfyui_api_serve(monkeypatch, tmp_path):
    """v3 迁移 fence:_spawn_serve 调 `python -m comfyui_api serve`(不再 factory_v3)。

    上游 2026-06-11 已把 serve 实现迁入 comfyui_api.serve 并补 CLI 子命令;
    ForgeUE 迁移后对 factory_v3 模块零依赖。
    """
    captured = {}
    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        class P:
            pid = 1
        return P()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    mgr = ComfyLifecycleManager(scripts_dir=tmp_path)
    await mgr._spawn_serve()
    assert captured["args"][1:4] == ("-m", "comfyui_api", "serve")

@pytest.mark.asyncio
async def test_spawn_stop_uses_comfyui_api_stop(monkeypatch, tmp_path):
    captured = {}
    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        class P:
            async def wait(self):
                return 0
        return P()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    mgr = ComfyLifecycleManager(scripts_dir=tmp_path)
    await mgr._spawn_stop()
    assert captured["args"][1:4] == ("-m", "comfyui_api", "stop")
```

- [ ] **Step 5.2: RED 确认** `python -m pytest tests/unit/test_comfy_lifecycle.py -q` → 2 FAIL

- [ ] **Step 5.3: 实现**

lifecycle.py L254 `"-m", "factory_v3", "serve"` → `"-m", "comfyui_api", "serve"`；L275 `"-m", "factory_v3", "stop"` → `"-m", "comfyui_api", "stop"`。同文件 7 处 docstring/注释里 `factory_v3 serve/stop` 改 `comfyui_api serve/stop`（L35/85/95/227/232/239/248/267/283）。orchestrator.py:70 注释同步。comfy_worker.py:1954/1970 错误信息改为：`start ComfyUI via 'python -m comfyui_api serve' then retry`（删掉"comfyui_api 没有 serve 子命令"的旧说明）。

- [ ] **Step 5.4: GREEN + 相邻回归**

```bash
python -m pytest tests/unit/test_comfy_lifecycle.py tests/unit/test_comfy_subprocess.py -q
```

- [ ] **Step 5.5: Commit**

```bash
git add -A src/framework tests/unit/test_comfy_lifecycle.py
git commit -m "refactor: lifecycle serve/stop 迁移 comfyui_api 子命令,退役 factory_v3 依赖"
```

---

### Task 6: ForgeUE — error_code 优先分类（共享 helper 提取）

**Files:**
- Modify: `src/framework/providers/workers/comfy_worker.py`（L556-560 markers、L935-949 / L1296-1310 / L1536-1550 / L1797-1811 四块 → 共享 helper）
- Modify: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 6.1: 失败 fences**

```python
def _fake_fail_json(**kw):
    d = {"ok": False, "error": kw.pop("error", "boom")}
    d.update(kw)
    return json.dumps(d)

# 1) error_code=timeout 优先于文案(文案无 TimeoutError 也判 WorkerTimeout)
# 2) error_code=missing_required_param → WorkerUnsupportedResponse
# 3) error_code 未知值(如 "comfy_unreachable")→ WorkerError(可 retry)
# 4) 无 error_code + 旧文案 marker → 旧 fallback 行为不变
# 5) patcher 实际串 "Param 'width' value 99999 out of range [256, 2048]"
#    (无 error_code)→ WorkerUnsupportedResponse(修 latent marker mismatch)
```

每条用既有 test_comfy_subprocess.py 的 subprocess-mock 模式喂 stdout JSON 断言异常类型。

- [ ] **Step 6.2: RED 确认**（第 1/2/5 条会 FAIL：现 marker `"value out of range"` 不匹配、无 error_code 逻辑）

- [ ] **Step 6.3: 实现共享 helper**

```python
# Failure-mode discriminators (round 2 spec D5 + round 3 P2 sync probe).
# v3.1 起为 fallback:上游 error_code 结构化字段优先(_raise_comfy_failure)。
# "out of range" 修正:patcher 实际串是 "value {N} out of range",
# 旧 marker "value out of range" 永匹配不上(latent bug,2026-06-11 修)。
_UNSUPPORTED_ERROR_MARKERS = (
    "Missing required param",
    "out of range",
    "value_not_in_list",
)

# error_code → WorkerUnsupportedResponse 的 deterministic 集合
# (retry 无意义:参数错/manifest 错/模型未装/输入文件缺)
_ERROR_CODE_UNSUPPORTED = frozenset({
    "missing_required_param", "param_out_of_range", "value_not_in_list",
    "workflow_not_found", "input_image_not_found", "invalid_arguments",
    "comfy_rejected",
})


def _raise_comfy_failure(data: dict, returncode: int | None, context: str) -> None:
    """ok=false 统一分类:error_code 优先,error 文案 marker fallback。

    上游 comfyui_api v3.1(2026-06-11)起在失败 JSON 里输出结构化 error_code;
    code 缺失(旧版 CLI)时退回字符串 marker 分类,行为与 round 2 spec D5 一致。
    """
    error_msg = str(data.get("error", ""))
    error_code = data.get("error_code")
    if isinstance(error_code, str) and error_code:
        if error_code == "timeout":
            raise WorkerTimeout(
                f"{context}: comfyui_api timeout (error_code=timeout): {error_msg}")
        if error_code in _ERROR_CODE_UNSUPPORTED:
            raise WorkerUnsupportedResponse(
                f"{context}: deterministic error (error_code={error_code}): {error_msg}")
        raise WorkerError(
            f"{context}: comfyui_api returned ok=false "
            f"(exit {returncode}, error_code={error_code}, error: {error_msg})")
    if "TimeoutError" in error_msg:
        raise WorkerTimeout(f"{context}: ComfyUI reported TimeoutError: {error_msg}")
    for marker in _UNSUPPORTED_ERROR_MARKERS:
        if marker in error_msg:
            raise WorkerUnsupportedResponse(
                f"{context}: deterministic param error: {error_msg}")
    raise WorkerError(
        f"{context}: comfyui_api returned ok=false "
        f"(exit {returncode}, error: {error_msg})")
```

四个调用点统一替换为：

```python
        if not data.get("ok"):
            _raise_comfy_failure(data, returncode, "ComfyAgentWorker")           # image
            # mesh/audio/video 分别传 "ComfyAgentWorker.agenerate_mesh" / "...audio" / "...video"
```

保留各 context 字符串与原异常信息前缀一致（既有 fence 用 match= 匹配 "deterministic param error" 等短语，fallback 路径短语未变）。

- [ ] **Step 6.4: GREEN + 全 comfy 单测**

```bash
python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_comfy_subprocess_audio.py tests/unit/test_comfy_subprocess_video.py -q
```

- [ ] **Step 6.5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "feat: comfy 失败分类 error_code 优先+共享 helper,修 out-of-range marker latent bug"
```

---

### Task 7: A1 ForgeUE — mesh 路径切 v3 auto-upload，退役 FORGEUE_COMFY_INPUT_DIR

**Files:**
- Modify: `src/framework/runtime/executors/generate_mesh.py:121-176`
- Modify: `src/framework/providers/workers/comfy_worker.py`（agenerate_mesh 守门 + L1355-1358 metadata 注释）
- Modify: `src/framework/providers/comfy_provider_config.py`（删 input_dir 字段）
- Modify: `config/models.yaml:116`（删 input_dir 键）
- Modify: `tests/unit/test_generate_mesh_comfy.py`、`tests/unit/test_comfy_provider_config.py`

- [ ] **Step 7.1: 失败 fences（test_generate_mesh_comfy.py）**

- 改写 `test_generate_via_comfy_worker_writes_source_bytes_to_comfyui_input_dir_with_forgeue_prefix` → `..._writes_staging_png_under_run_dir_and_passes_abs_path`：断言 `ctx.run_dir/"comfy"/f"forgeue_{sha1}.png"` 落盘 + `call_kwargs["source_image_filename"] == str(staging_path)`（绝对路径）
- 改写 `test_generate_via_comfy_worker_raises_when_FORGEUE_COMFY_INPUT_DIR_unset` → `..._succeeds_without_input_dir_env`：unset env + provider_config 无 input_dir 仍成功
- 删 `test_generate_via_comfy_worker_uses_yaml_input_dir_when_env_absent`；新增 worker 守门 fence：`spec.comfy_image_param_key="source_pic"`（非 input_image 前缀）→ `WorkerUnsupportedResponse`（auto-upload 只认 input_image* 前缀）
- 清理其余 ~15 处 `monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", ...)`（连同 provider_config["input_dir"] 注入）

- [ ] **Step 7.2: RED 确认**

- [ ] **Step 7.3: 实现 executor 侧**

generate_mesh.py L121-141 整块替换：

```python
        # comfy-agent-api-v3-adaptation(2026-06-11):source bytes 写 in-tree
        # staging 文件(<run_dir>/comfy/forgeue_<sha1>.png,idempotent via sha1),
        # 以绝对路径传给 worker → CLI;v3 起 `comfyui_api run` 对 input_image*
        # 本地路径自动 POST /upload/image(AGENT_API.md §1.3),原 round 5 D10
        # 的 FORGEUE_COMFY_INPUT_DIR 写入机制退役(上游 upload 落 ComfyUI 自家
        # input/,文件名仍 forgeue_<sha1>.png,server 侧语义与旧机制一致)。
        staging_dir = ctx.run_dir / "comfy"
        staging_dir.mkdir(parents=True, exist_ok=True)
        sha1_hex = hashlib.sha1(source_image_bytes).hexdigest()[:16]
        input_path = staging_dir / f"forgeue_{sha1_hex}.png"
        if not input_path.exists():
            input_path.write_bytes(source_image_bytes)
```

L171 `source_image_filename=input_filename` → `source_image_filename=str(input_path)`。检查同文件后续是否有 metadata 补 `comfy_input_dir` 的代码（round 5 D10 修订提及），有则改为记 staging path。

- [ ] **Step 7.4: 实现 worker 侧守门 + 注释**

agenerate_mesh L1169 `image_param_key = ...` 之后加：

```python
        if not image_param_key.startswith("input_image"):
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.agenerate_mesh: spec.comfy_image_param_key="
                f"{image_param_key!r} 不以 'input_image' 开头;comfyui_api v3 "
                "input_image* 本地路径自动上传只对该前缀参数生效(AGENT_API.md §1.3)"
            )
```

L1355-1358 metadata 注释更新（值现为 in-tree staging 绝对路径，上游 run 自动 upload）。

- [ ] **Step 7.5: 退役 config 链**

comfy_provider_config.py：dataclass 删 `input_dir` 字段、resolve 删 L91-92；models.yaml:116 删 `input_dir:` 行（留一行注释指 v3 auto-upload）；test_comfy_provider_config.py 删 L29/62/69/89 相关注入与断言。

- [ ] **Step 7.6: GREEN + 全量单测**

```bash
python -m pytest tests/unit -q
```

- [ ] **Step 7.7: mesh L2 实测（验证 auto-upload 真链路）**

```bash
unset FORGEUE_COMFY_INPUT_DIR
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_autoupload_smoke_20260611
ls "D:/AI/ComfyUI/apps/official-main-git-v092/input/" | grep forgeue_   # 上游 upload 落进 input/
```
Expected: status succeeded；`artifacts/2026-06-11/mesh_autoupload_smoke_20260611/*.glb` 真实 GLB（glTF magic）；ComfyUI input/ 出现新 `forgeue_<sha1>.png`（由上游 /upload/image 放入，非 ForgeUE 直写）。写 `notes/live_smoke_mesh_autoupload.md`。

- [ ] **Step 7.8: Commit**

```bash
git add -A src config/models.yaml tests examples docs/archive/forge_changes/2026-06-11-comfy-agent-api-v3-adaptation/
git commit -m "feat: mesh source image 走 v3 input_image 自动上传,退役 FORGEUE_COMFY_INPUT_DIR"
```

---

### Task 8: 文档同步 + cancel 边界标注 + backlog/CHANGELOG

**Files:**
- Modify: `CLAUDE.md`、`AGENTS.md:35`、`README.md:342`
- Modify: `docs/testing/test_spec.md:595-596`、`docs/design/LLD.md:847` 附近、`docs/requirements/SRS.md`（grep FORGEUE_COMFY_INPUT_DIR / factory_v3）、`docs/acceptance/acceptance_report.md`（grep 同上）
- Modify: `docs/ai_workflow/validation_matrix.md:226-244`、`docs/contracts/provider-routing/spec.md:379,385`、`docs/contracts/examples-and-acceptance/spec.md:325,413`
- Modify: `docs/backlog/active.md`、`CHANGELOG.md`

- [ ] **Step 8.1: CLAUDE.md 更新**（要点）

1. 子命令清单：`{list, params, run, batch, status, cancel, upload, wait, serve, stop}`；删"不含 serve"旧注
2. 启停建议：`python -m comfyui_api serve/stop`（factory_v3 serve/stop 留作兼容入口）
3. mesh 段：删 `FORGEUE_COMFY_INPUT_DIR` REQUIRED 表述与 cleanup find 命令；改述 v3 auto-upload + in-tree staging
4. 顶部 env 列表删 `FORGEUE_COMFY_INPUT_DIR`
5. video 段：smoke 默认 manifest 改 teacache（~2.5min），5sec 留 export example；must-preserve 清单更新为 6 文件（runner.py[降级:已是 v3 契约]、2×loadimage、native/native_5sec/teacache 3×Wan manifest）
6. 失败分类:注明 error_code 优先 + marker fallback

- [ ] **Step 8.2: LLD cancel 边界标注**（LLD.md ComfyAgentWorker cancel 小节，§5.x）

> 已知边界：`comfyui_api cancel`（无 --prompt-id）是全局 /interrupt；ComfyUI 被多 agent / factory_v3 共享时可能中断他方 prompt。单机单用户场景可接受；精确取消需 detach 模式拿 prompt_id 后 `cancel --prompt-id`，见 backlog `comfy-detach-wait-adoption`。

- [ ] **Step 8.3: 其余文档 sweep**

```bash
grep -rn "FORGEUE_COMFY_INPUT_DIR\|factory_v3" --include="*.md" . | grep -v docs/archive | grep -v node_modules
```
逐个改：serve/stop 表述、INPUT_DIR 退役、test_spec fence 清单补新 fence 名。

- [ ] **Step 8.4: backlog + CHANGELOG**

active.md Future Work 加 `comfy-detach-wait-adoption`（detach+wait submit-then-poll + cancel --prompt-id 精确取消；触发条件：ComfyUI 多租户共享或需要 run 间精确取消时）；待办计数 0→1。CHANGELOG 加本次条目。

- [ ] **Step 8.5: Commit**

```bash
git add -A
git commit -m "docs: v3 适配五件套/CLAUDE/contracts 同步+cancel 边界标注+backlog 结账"
```

---

### Task 9: 全量验证 + 收尾

- [ ] **Step 9.1: ForgeUE 全量**

```bash
python -m pytest -q
```
Expected: 全 PASS（用例数以实测为准）。

- [ ] **Step 9.2: 上游全量**

```bash
cd D:/AI/ComfyUI/scripts && python -m pytest comfyui_api -q
```

- [ ] **Step 9.3: verification-before-completion 清单**（证据：两个 pytest 输出、2 份 L2 notes、上游手测输出）

- [ ] **Step 9.4: finishing-a-development-branch**（merge/PR 选项交用户）

---

## Self-Review

- Spec 覆盖：A2(Task 0) / A3(Task 1-2) / serve+stop 上游(Task 3) / error_code 上游(Task 4) / lifecycle 迁移(Task 5) / error_code 消费(Task 6) / A1(Task 7) / cancel 标注+文档(Task 8) ✓；detach+wait 明确不做 → 转 backlog 条目 ✓
- 类型一致：`_error_code(exc)->str`、`_fail_json(exc)->dict`、`_raise_comfy_failure(data, returncode, context)` 各 task 引用一致 ✓
- 顺序依赖：Task 5 依赖 Task 3（上游子命令先存在）；Task 2 L2 用 stock CLI（Task 3/4 之前）隔离变量 ✓
