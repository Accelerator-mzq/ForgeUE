## Context

ComfyUI 侧最近独立发布了 agent CLI(`python -m comfyui_api`,详见 `D:/AI/ComfyUI/docs/workflows/COMFYUI_AGENT_API.md`),把原本散在 ComfyUI HTTP 接口外的几件事都收编了:

- 18 个 workflow manifest 化(`comfyui_api list` / `params` / `run`)
- 4 lifecycle 模式管 ComfyUI 进程启停 + VRAM 释放(含 `.comfyui.pid` 防误杀用户进程)
- subgraph 展开 / param 类型校验 / range check / 模型存在性检查
- 错误分类标准化(exit code 2 + `error` 字段:OOM / `value_not_in_list` / `Missing required param` / `Timeout` / `param 'X' value out of range`)
- `<date>/<project>/` 子目录分组,product 路径含元信息

ForgeUE 当前 `src/framework/providers/workers/comfy_worker.py`(336 行)的 `HTTPComfyWorker` 完全在自己复刻这一层,而且要求 bundle 把整段 `workflow_graph` JSON inline 进 `step.config.spec`(见 commit 292420a 的 `examples/comfy/build_bundle.py`)。继续走 HTTP 路径意味着重复维护协议层 + workflow 参数化 + lifecycle 管理,且 bundle 协议远比真实需要复杂。

但 ForgeUE 框架侧的几件事新 CLI **不管也不打算管**,必须保留:

- `FakeComfyWorker` scripted 队列(549 用例里 P3 / L2 / a2_image / examples_smoke 全靠它 offline 跑;CI 不可能装 ComfyUI)
- `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` 三级异常 + `FailureModeMap` 路由(executor `_should_retry` / Verdict `abort_or_fallback` 都依赖)
- `ImageCandidate` → `PayloadRef.file` → `ArtifactRepository` 流(Artifact 一等公民、lineage、hash、resume cache)
- executor `metrics["cost_usd"]` / `chosen_model` / `_route_pricing` 接口(本地 GPU `cost_usd=0`,但接口必须在,FR-COST-008/009 守门)
- WS event(`worker_poll` / `step_start` / `step_done`,NFR-OBS-004)

约束:Windows 11 + Git-Bash + D: 盘;Python 3.12+;产物落 `./artifacts/<YYYY-MM-DD>/<run_id>/`(NFR-PORT-004);不 mock 关键边界(NFR-MAINT-004);新 contract 要走 `/forgeue:change-doc-sync` 同步 SRS / HLD / LLD / acceptance / CHANGELOG。

## Goals / Non-Goals

**Goals:**

- ComfyUI worker 内部协议层从手撸 HTTP 改为 subprocess 调用 `python -m comfyui_api`,白捡 lifecycle / manifest workflow / 标准化错误
- bundle `step.config.spec` 协议从"塞整段 `workflow_graph`"简化为"`comfy_workflow` + `comfy_params` + `comfy_lifecycle`"
- 所有框架侧契约(异常分级、Artifact 流、executor budget 接口、WS event、FakeComfyWorker)零破坏
- 所有 ComfyUI 输出文件 copy 进项目树内的 `artifacts/<run_id>/comfy/`,满足 `PayloadRef.file` 必须在项目树内的约定
- 新 contract 同步到 SRS §5.3 + FR-WORKER-001、HLD/LLD ComfyUI 子系统、CHANGELOG、acceptance_report

**Non-Goals:**

- 不接 `factory_v3`(其 9 状态机 + retry 与 ForgeUE Workflow / Verdict / TransitionEngine / DAG 直接重叠,接进来就两套状态机打架)
- 不接 `blender_pipeline`(GLB → 4 PNG 是另一项独立 worker,留作后续 change)
- 不改其它 provider(只动 ComfyUI 一个)
- 不为旧 HTTP 路径保留任何向后兼容代码(无 feature flag、无 `comfy_protocol: http|cli` 切换)
- 不在本 change 里接入视频 / 音频 / 编辑等其它 ComfyUI workflow 类别(本 change 只验证图像类 manifest workflow,其它类别后续 change)

## Decisions

### D1 — subprocess 调用配置:`config/models.yaml` 加 `comfy_api_scripts_dir`

**选项:**

- **A:** `config/models.yaml` `providers:` 段加新 provider entry `comfy_api`,字段 `scripts_dir: D:/AI/ComfyUI/scripts`(用户机器自配)
- **B:** 当作环境前提,worker 假设 `python -m comfyui_api` 在 PATH 与默认 cwd 可用,文档要求用户自跑 `python -m comfyui_api status` 自检
- **C:** 走环境变量 `FORGEUE_COMFY_SCRIPTS_DIR`,worker 启动时读

**选 A**,理由:

1. ModelRegistry 是 single source of truth(SRS FR-MODEL-001),把 ComfyUI 接入参数也放进去保持一致
2. B 的"环境前提"在 Windows + Git-Bash 下不可靠 —— `D:/AI/ComfyUI/scripts` 不在 default PATH,`cwd` 又是 ForgeUE 项目根而不是 ComfyUI 项目根,不显式配会大概率挂
3. C 引入 `.env` 之外的第二条环境变量入口,与现有 `DASHSCOPE_API_KEY` / `HUNYUAN_API_KEY` 这种 secret 用法语义不一致(scripts_dir 不是 secret)
4. A 让 dry-run 阶段(SRS FR-LC-002)能直接校验 `scripts_dir` 存在 + `python -m comfyui_api status` 可调,不可达直接 fail Run 而不是跑到 step 中段才崩

具体字段:

```yaml
providers:
  comfy_api:
    kind: subprocess_cli
    scripts_dir: "D:/AI/ComfyUI/scripts"      # 用户机器实际路径
    python_exe: null                           # 默认用 sys.executable
    default_lifecycle: "ensure_running"        # 4 模式之一
```

dry-run 校验:`Path(scripts_dir).exists()` + `(Path(scripts_dir) / "comfyui_api").is_dir()`。任一 False → Run 直接 fail。

### D2 — ComfyUI 输出文件:worker 内部 copy 到 `artifacts/<run_id>/comfy/`

**选项:**

- **A:** Worker 内部把 `outputs.images` 里的 PNG 从 `D:/AI/ComfyUI/outputs/main/<date>/<project>/...` copy 到 `artifacts/<run_id>/comfy/<original_filename>`,再注册 `PayloadRef.file` 指向 copy 后的路径
- **B:** `PayloadRef.file` 直接指向 ComfyUI 原始路径 + `payload_ref.metadata["external_root"] = "D:/AI/ComfyUI/outputs"`,不 copy

**选 A**,理由:

1. NFR-PORT-004 + A4 假设明确写"文件型 Artifact 落盘路径在项目树内,不落 C: 系统目录或外部根"。B 直接破例
2. ForgeUE 现有 `--artifact-root <dir>` + 跨天 resume + run_id 归档假设的全部前提是"产物在 `<artifact_root>/<run_id>/` 子树内"。B 让 resume / archive / `artifact_hash` 校验全要新增 external root 处理分支
3. ComfyUI 自家会按 `<date>/<project>/` 分组累积,长期不清理。ForgeUE artifact 应该是 self-contained 的(用户 `tar` 一个 `artifacts/<run_id>/` 就该能复现 / 归档),不应跨进程依赖外部目录状态
4. copy 成本可接受:单图 1-5 MB,Windows 同盘 copy < 100 ms,远低于 ComfyUI 生成耗时(20-180 s)

实施:`HTTPComfyWorker._collect_outputs(stdout_json)` 解析 `outputs.images` → `shutil.copy2(src, artifacts_dir / "comfy" / src.name)` → 用新路径构造 `ImageCandidate.data` + 元数据。`artifacts_dir` 由 worker 构造时通过 `run_context` 传入。

跨 worker 复用 `--project=<run_id>` 让 ComfyUI 自动按 run_id 分组(虽然我们 copy 走再用,但留这个映射方便事后人工对照)。

### D3 — `HTTPComfyWorker` 类完全砍掉,不抽象 `ComfyApi` 接口

**选项:**

- **A:** 抽象 `ComfyApi` Protocol(`run_workflow(name, params, lifecycle) -> JSON`),三实现共存:`HTTPComfyApi`(老 HTTP)、`SubprocessComfyApi`(新 CLI)、`FakeComfyApi`(scripted)
- **B:** 直接重写 `HTTPComfyWorker` 内部为 subprocess 调用,**类名保持 `HTTPComfyWorker`** 但实装变,异常分级 + 接口签名不动;`FakeComfyWorker` 保持 scripted 队列接口不变

**选 B**,理由:

1. ForgeUE 没有"在生产里同时跑 HTTP + CLI 两种 ComfyUI 接入"的真实需求 —— 用户机器只可能装一种 ComfyUI。抽象层为不存在的需求买单
2. CLAUDE.md "don't add features beyond what the task requires" + "no half-finished implementations" 明确反对预留扩展点。两实现共存就要再加一层 factory + provider type 选择,纯负担
3. HTTP 路径在主线根本没投入用 —— acceptance_report 写明 a2_image / L2 主线走 Qwen `image_fast`,FakeComfy 只用于"占位图被拒的工作流终止路径 smoke"。砍 HTTP 实装不破坏任何 ✅ 验收
4. 命名问题:类名继续叫 `HTTPComfyWorker` 名实不符。**重命名为 `ComfyAgentWorker`**,在 `comfy_worker.py` 模块顶 docstring 标"v2 since change comfy-agent-cli-adoption (commit XXX)";v1 HTTP 实装通过 git history 回溯(commit 292420a 之前)

公开接口签名:

```python
class ComfyAgentWorker(ComfyWorker):
    def __init__(
        self,
        scripts_dir: Path,
        python_exe: Path | None = None,
        default_lifecycle: str = "ensure_running",
        run_id: str | None = None,
        artifacts_dir: Path | None = None,
    ): ...
    def submit(self, spec: dict, *, timeout_s: float) -> list[ImageCandidate]: ...

class FakeComfyWorker(ComfyWorker):
    # 接口保持不变,scripted 队列接口稳定
    def program(self, candidates: list[ImageCandidate]) -> None: ...
    def submit(self, spec: dict, *, timeout_s: float) -> list[ImageCandidate]: ...
```

### D4 — `a2_image` FakeComfy bundle 不动

**背景:**TBD-008 之后,acceptance_report v1.3 已经把 `a2_image`(FakeComfy 4.5KB 占位图 + Anthropic vision review)的证据力修订为"占位图被拒的工作流终止路径 smoke",不算视觉 review 证据。真正的视觉 review 证据归到 `test_p2/p3/l4` 的真 PNG fixture + `probe_visual_review` 的真 provider 抽检。

**决策:**保留 `a2_image` bundle + FakeComfy 用法不动。理由:

1. 它现在守的是"工作流按 `on_reject: null` 正常终止"这条契约,这条契约本身没变
2. 删它要同步删 acceptance_report A2 的 5/5 行 → 必须改 acceptance,边际收益是负
3. FakeComfy scripted 接口本 change 不动,a2_image bundle 不需要任何修改

**`examples/comfy_local_smoke.json` 重写**(仍要做):从 inline workflow_graph 改为新协议,作为本 change 的 live smoke 入口,用 `python -m framework.run --task examples/comfy_local_smoke.json --live-llm`(配合本机已装 ComfyUI + agent CLI 配置)跑通。

### D5 — subprocess 失败模式映射

新增 4 类失败,全部映射进既有 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` 三级:

| 失败现象 | 检测点 | 映射 | FailureMode | Verdict |
|---|---|---|---|---|
| `scripts_dir` 不存在 / `python -m comfyui_api` 模块未找到 | dry-run + worker `__init__` | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback`(honour `on_fallback`,未配则终止) |
| subprocess 返回 exit code 2 + stdout `{"ok": false, "error": "Missing required param" \| "value out of range" \| "value_not_in_list"}` | `submit()` 解析 stdout | `WorkerUnsupportedResponse` | `unsupported_response` | 同上 |
| subprocess stdout 非 JSON / JSON 但缺 `outputs` 字段 | `submit()` 解析 stdout | `WorkerUnsupportedResponse` | `unsupported_response` | 同上 |
| subprocess 返回 exit code 2 + stdout `error` 含 `TimeoutError` | `submit()` 解析 stdout | `WorkerTimeout` | `worker_timeout` | `retry_same_step`(默认最多 2 次) |
| subprocess 进程被 ForgeUE 主动 kill(`asyncio.CancelledError`) | `submit()` Cancel 路径 | re-raise `CancelledError` | n/a | 走 cancel 链路 |
| 其它 exit code 2 + 未识别 error | `submit()` 解析 stdout | `WorkerError` | `worker_error` | `fallback_model` → `retry_same_step`(默认 1 次) |

关键:**所有 unsupported response 必须走 `abort_or_fallback`,绝不回 same step 重计费**(SRS FR-RUNTIME-012 已建立的契约)。本地 GPU `cost_usd=0`,但同 step 重试浪费 30-180 s wall-clock,且若失败原因是 `Missing required param` 这种 deterministic bug,重试也不会成功。

新增 fence(写在 spec 而非这里):

- `tests/unit/test_comfy_subprocess.py::test_missing_scripts_dir_raises_unsupported_response`
- `tests/unit/test_comfy_subprocess.py::test_exit2_missing_param_maps_to_unsupported`
- `tests/unit/test_comfy_subprocess.py::test_exit2_value_out_of_range_maps_to_unsupported`
- `tests/unit/test_comfy_subprocess.py::test_stdout_not_json_maps_to_unsupported`
- `tests/unit/test_comfy_subprocess.py::test_exit2_timeout_maps_to_worker_timeout`
- `tests/unit/test_comfy_subprocess.py::test_cancel_terminates_subprocess`

## Risks / Trade-offs

- **[subprocess 启动冷启动开销] →** ComfyUI agent CLI 在 lifecycle=`ensure_running` 模式下若 ComfyUI 未启,会自启(~30-90 s cold start),首次调用 step 阶段耗时上跳。**Mitigation:** dry-run 阶段调一次 `python -m comfyui_api status` 探活,如果不在线提前 emit `worker_poll` 事件让用户知道在等冷启动;`worker_timeout_s` 默认从原 60 s 调大到 300 s
- **[`shutil.copy2` 跨盘符性能] →** 用户若把 ComfyUI 装在 E: 而 ForgeUE artifacts 在 D:,copy 走 OS file system 跨设备路径,百 MB 级 mesh / 视频 workflow 可能成本不可忽略。**Mitigation:** 本 change 只覆盖图像 workflow(单图 < 5 MB),3D / 视频 workflow 接入留给后续 change 再评估 hardlink / move 优化
- **[Windows 路径分隔符] →** ComfyUI agent CLI 输出的路径是 Windows backslash,JSON parse 后是字符串,跨 `os.fspath` / `pathlib.Path` 处理时要小心。**Mitigation:** worker 内部统一 `Path(...)` 包一次,所有 path 操作走 pathlib;`tests/unit/test_comfy_subprocess.py` 加 fence 校验 mixed-separator 输入
- **[FakeComfyWorker 与新 contract 偏离] →** FakeComfyWorker scripted 接口不变,但新 bundle 协议字段 `comfy_workflow` / `comfy_params` 它不消费(它直接 dequeue 队列里的 ImageCandidate)。容易让人误以为 fake 在"按 manifest 跑"。**Mitigation:** `FakeComfyWorker.submit` 校验 `spec` 里至少有 `comfy_workflow` 字段(语义只做 schema 守门,不影响 dequeue),缺字段直接 raise `WorkerUnsupportedResponse`;在 docstring 写明"fake 不真跑 manifest,scripted 队列驱动"
- **[`config/models.yaml` 加 provider entry 触发 strict load schema] →** 已有 RegistryReferenceError 守 typo(SRS FR-COST-002),新加 `kind: subprocess_cli` 字段需要 loader 接受。**Mitigation:** loader 加新 kind 校验 + 单测覆盖
- **[CHANGELOG / acceptance_report drift] →** SRS §5.3 + FR-WORKER-001 描述变更,acceptance FR-WORKER-001 验收行的"`comfy_worker.py` + `test_comfy_http_unsupported`"指向的测试文件被重写。**Mitigation:** 走 `/forgeue:change-doc-sync` Documentation Sync Gate 强制扫 10 文档

## Migration Plan

本 change 是 BREAKING change,无 feature flag 渐进路径。部署步骤:

1. **代码改动一次提交一个 commit:**
   - commit 1:`config/models.yaml` 加 `comfy_api` provider entry + loader schema 接受 `subprocess_cli` kind + 单测
   - commit 2:`ComfyAgentWorker` 实装(rename `HTTPComfyWorker`,内部改 subprocess) + dry-run 探活
   - commit 3:executor `_resolve_spec` 读新字段(`comfy_workflow` / `comfy_params` / `comfy_lifecycle`)+ 旧字段 `workflow_graph` 命中时直接 raise `WorkerUnsupportedResponse`(防漏改的 bundle 静默走错路径)
   - commit 4:`FakeComfyWorker.submit` schema 守门(校验 `comfy_workflow` 字段)
   - commit 5:`tests/unit/test_comfy_subprocess.py` 新增 + `test_comfy_http_unsupported.py` 删除
   - commit 6:`examples/comfy_local_smoke.json` 重写 + `examples/comfy/build_bundle.py` + 两份 workflow JSON 删除
   - commit 7:文档同步(SRS / HLD / LLD / CHANGELOG / acceptance_report)
2. **回滚策略:**`git revert` 上述 commit 链;v1 HTTP 实装在 commit 292420a 之前的 git history 可查
3. **验收:**
   - Level 0:`python -m pytest -q` 全绿(549 + 新 fence)
   - Level 1:`python -m pytest tests/unit/test_comfy_subprocess.py -v`
   - Level 2:本机装 ComfyUI + agent CLI 后 `python -m framework.run --task examples/comfy_local_smoke.json --live-llm` 跑通,产物落 `artifacts/<today>/<run_id>/comfy/` 子目录
4. **CHANGELOG 行示例:**
   > `comfy-agent-cli-adoption`: ComfyUI worker 协议层从 HTTP 重写为 subprocess 调用 `python -m comfyui_api`,bundle 协议从 inline `workflow_graph` 简化为 `comfy_workflow` + `comfy_params`,所有 ComfyUI 输出文件 copy 进 `artifacts/<run_id>/comfy/`。BREAKING:旧 `step.config.spec.workflow_graph` 字段废止;迁移指引见本 change 的 `tasks.md`。

## Open Questions

- **OQ-1:** `python_exe` 字段:用 `sys.executable`(ForgeUE 的 venv Python)还是 ComfyUI 自家 venv Python?ComfyUI agent CLI 文档没说,实测看是不是吃 ComfyUI 的 deps。倾向先 `sys.executable` + 文档写"如失败用 `python_exe: D:/AI/ComfyUI/venv/Scripts/python.exe` 显式指";apply 阶段确认
- **OQ-2:** `outputs.audio` / `outputs.glb` 字段:agent CLI 输出 JSON 含这两个字段(给视频 / 3D workflow 用),本 change 只接图像不读这两个,但 worker 解析时遇到 non-empty 是 raise `WorkerUnsupportedResponse` 还是静默忽略?倾向 raise(明确 scope),后续 change 接入视频 / 3D 时再放开
- **OQ-3:** ComfyUI agent CLI 的 `--project` 字段我们传 `<run_id>` 还是 ForgeUE 的 `task.project_id`?后者更语义,前者更利于事后人工对照 ComfyUI outputs 与 ForgeUE artifacts。倾向传 `<run_id>`(我们 copy 走后路径不依赖,但 ComfyUI 自家 outputs 留 `<run_id>` 子目录方便诊断)

## Resolved

- **OQ-1 → `sys.executable`**(2026-05-02)。worker 默认走 ForgeUE 自家 venv Python;`config/models.yaml` `providers.comfy_api.python_exe: null` 表示用 default;若用户实测发现 ComfyUI deps 不在 ForgeUE venv 内可显式覆盖为 `D:/AI/ComfyUI/venv/Scripts/python.exe`。dry-run 探活(任务 §3.5)若失败,error message 提示用户检查 `python_exe`
- **OQ-2 → 遇到 non-empty `outputs.audio` / `outputs.glb` 时 raise `WorkerUnsupportedResponse`**(2026-05-02)。理由:
  1. ForgeUE 三层架构(capability + executor + candidate type)把 image / mesh / audio 当独立链路,`generate_image` executor 只产 `ImageCandidate`,不该越界产 `MeshCandidate` / 音频 candidate
  2. mesh artifact 的 metadata(`format` / `poly_count` / `scale_unit` / `up_axis` / `has_uv` / `has_rig` / `texture` / `pbr` / `intended_use`)ComfyUI agent CLI JSON 完全不给,得 parse GLB 二进制 header 推断,这是独立 R&D 任务
  3. ForgeUE 已有 `HunyuanTokenhubMeshWorker` 走 Hunyuan tokenhub API 直接做 image-to-3D,acceptance 里 L4 + a2_mesh_0423 已 ✅;开第二条 ComfyUI mesh 来源涉及 capability alias 切换 / `fallback_models` 链 / cost 记账 / ADR-007 single-attempt 守门是否对本地 GPU 路径放开,是产品决策
  4. raise = 明确划线,防 image step 配错 workflow(选了 `combined_*` 这种同时出 PNG + GLB 的 manifest)时静默吞掉 GLB 输出造成"看似成功实则丢数据"
  5. 后续 change(暂定 `comfy-agent-mesh-adoption`)单独评估接入 mesh / 视频 / 音频 路径
- **OQ-3 → 传 `task.project_id`**(2026-05-02)。理由:语义对齐 —— ComfyUI agent CLI 的 `--project` 字段本意是"业务项目分组",ForgeUE 的 `task.project_id` 同义;`<run_id>` 是技术 ID 不是项目分组。事后对照 ComfyUI outputs 看 `D:/AI/ComfyUI/outputs/main/<date>/<task.project_id>/...` 一目了然。worker 已 copy 到 `artifacts/<run_id>/comfy/`,ForgeUE 侧 self-contained 不依赖 ComfyUI outputs 子目录命名
