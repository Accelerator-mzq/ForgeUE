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

实施:`ComfyAgentWorker._collect_outputs(stdout_json)` 解析 `outputs.images` → `shutil.copy2(src, artifacts_dir / "comfy" / src.name)` → 用新路径构造 `ImageCandidate.data` + 元数据。`artifacts_dir` 由 worker 构造时通过 `run_context` 传入。

CLI `--project` 字段传 `task.project_id`(OQ-3 决议;不是 `<run_id>`),让 ComfyUI 原始 outputs 按业务项目分组(`D:/AI/ComfyUI/outputs/main/<date>/<task.project_id>/...`)方便事后人工对照。worker 已 copy 走,ForgeUE artifact tree 不依赖 ComfyUI outputs 子目录命名。

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
| subprocess 进程自然结束(用户 cancel 后 to_thread 包装的 worker 仍在线程内跑;subprocess 自然退出 = worker 退出) | n/a(cancel 不可达 worker.submit,见 D6) | n/a | n/a | best-effort:外层 Future 已 cancel,worker 完成后 result 被丢弃 |
| 其它 exit code 2 + 未识别 error | `submit()` 解析 stdout | `WorkerError` | `worker_error` | `fallback_model` → `retry_same_step`(默认 1 次) |

关键:**所有 unsupported response 必须走 `abort_or_fallback`,绝不回 same step 重计费**(SRS FR-RUNTIME-012 已建立的契约)。本地 GPU `cost_usd=0`,但同 step 重试浪费 30-180 s wall-clock,且若失败原因是 `Missing required param` 这种 deterministic bug,重试也不会成功。

新增 fence(写在 spec 而非这里):见 `specs/probe-and-validation/spec.md` 的 fence 名单(15 条 + cancel 不可达 best-effort 守门)。

### D6 — lifecycle scope:本 change 只支持 `lifecycle=none`(用户自管 ComfyUI)

**问题来源:**codex S2→S3 design review F1 critical(2026-05-02 18:35)发现 ForgeUE orchestrator 在 `src/framework/runtime/orchestrator.py:474` 把同步 executor 包 `await asyncio.to_thread(executor.execute, ctx)`,line 286-296 注释明说 sync executors in `asyncio.to_thread` can't be interrupted。即:即便 worker 内部用 `asyncio.create_subprocess_exec` 拿 subprocess handle,上游 cancel 信号也传不到 `worker.submit`(被 to_thread 包装层吸收)。

**3 个选项 trade-off**(详见 cross-check Decision Block A):

- A:lifecycle 只支持 `none`,用户自启 ComfyUI
- B:支持 `none` + `ensure_running`,spec 写 cancel best-effort + framework 不保证清理远端 ComfyUI server
- C:重写 GenerateImageExecutor 为 async def,orchestrator 直接 await 不经 to_thread

**选 A**(2026-05-02,user 拍板):

1. 主 spec `provider-routing/spec.md:211` Invariant 本来就写"ComfyUI integration requires a user-owned local ComfyUI ... no framework-managed lifecycle";line 229 Non-Goal 同义。**A 完全延续现有 invariant,F3 (主 spec MODIFIED 范围) 在 A 下最小**,只动 line 25 Current Behavior(协议描述 HTTP→subprocess CLI),line 211/229 不动
2. F1 critical 在 A 下**完全消失**:lifecycle=none 时 agent CLI 不拉子进程(假设 ComfyUI 已由用户启好),subprocess 退出 = worker 退出,无残留;cancel 不可达只导致 worker 完成后 result 被丢弃,无孤儿进程
3. F5 在 A 下变成合理 preflight:dry-run 探活 + 30s timeout 完全可行(用户既然自启,框架探活合情合理)
4. C 是正确但超本 change scope(改框架级 executor 模型);**登记 TBD-010 到 SRS §7.3 后续 change**(见 D-FutureScope 段)

**A 的代价坦白说:**用户接 ComfyUI 第一次会踩坑,要在 CLAUDE.md / README 写明"跑前先 `python -m comfyui_api status` 确认在线,offline 用 `python -m comfyui_api serve` 启"。dry-run 探活 fail 时 error message 直接告诉用户怎么启。

### D7 — ModelRegistry 接入用虚拟 model id `comfy/local` + worker 配置走 env(round 2 修订)

**问题来源(round 1):** codex F2 high 发现 `model_registry.py:438-442` 强制 alias 引用的 model name 必须 `in models`。

**round 2 codex 揭出更深问题(F2 not-actually-fixed + G1 critical):**
- `ProviderDef` (line 117-122) 只有 `name / api_key_env / api_base` 三字段,我 round 1 在 yaml 加的 `kind: subprocess_cli` / `scripts_dir` / `python_exe` / `default_lifecycle` 全部被 `_parse_providers` (line 262-278) **silent ignore**(不报错也不存储)
- `ResolvedRoute` (line 134-142) 字段 `model / api_key_env / api_base / kind / pricing` —— **无 `provider` 字段**,我 spec 写的"用 provider.kind 给 ComfyUI 分派"和"dry-run 在 prepared_routes 找 provider=comfy_api"在现有 schema 不可实现
- `models.comfy/local` 缺 `id` 字段(line 290-293 强校验)→ load 直接 raise

**3 个选项(round 2 Decision Block F):**

- F-A:扩 `ProviderDef` 加 `kind` + extra fields;扩 `ResolvedRoute` 加 `provider_name / provider_kind` —— 范围远超本 change scope,是 framework data model refactor
- F-B:不动 schema,worker 配置走 env,executor 走 model-id-based dispatch(类比 mesh worker)
- F-C:切两个 change 串行 —— 阻塞 ≥ 1 周

**选 F-B**(2026-05-02 user 拍板,F-A 登记 TBD-011 后续 change)。具体落地:

```yaml
# config/models.yaml — 不扩 ProviderDef schema,只用占位
providers:
  comfy_api:
    api_key_env: null    # 占位:让 model 引用合法
    api_base: null       # 占位

models:
  comfy/local:
    id: "comfy/local"    # ★ REQUIRED — round 1 漏写,加上;loader 强校验
    provider: comfy_api
    kind: image
    pricing: null        # 本地 GPU 无 per-call cost,FR-COST-008/009 接口仍在值 0.0

aliases:
  image_local:
    preferred: ["comfy/local"]
    fallback: []
```

```bash
# 环境变量 — worker 配置真源(类比 API key 走 .env)
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts   # REQUIRED;dry-run 校验
FORGEUE_COMFY_PYTHON_EXE=                         # OPTIONAL;空 → sys.executable (OQ-1)
FORGEUE_COMFY_LIFECYCLE=none                      # OPTIONAL;空 → "none";本 change 仅接受 "none" (D6)
```

```python
# GenerateImageExecutor — 加 worker dispatch 分支(类比 GenerateMeshExecutor)
def _resolve_spec(spec):
    # ... 已有逻辑 ...
    pass

def execute(ctx):
    # 检测 prepared_routes 含 model == "comfy/local" → 走 worker 路径,不走 router
    if any(r.model == "comfy/local" for r in ctx.step.provider_policy.prepared_routes):
        return self._generate_via_worker(ctx)  # 新分支
    if self._should_use_api_path(ctx):
        return self._generate_via_router(ctx)  # 现有 qwen/glm 路径
    # ... fake / fallback ...

def _generate_via_worker(self, ctx):
    worker = ComfyAgentWorker(
        scripts_dir=Path(os.environ["FORGEUE_COMFY_SCRIPTS_DIR"]),
        python_exe=os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None,
        default_lifecycle=os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none"),
        run_id=ctx.run.run_id,
        project_id=ctx.task.project_id,    # F4 fix:必传
        artifacts_dir=ctx.run_dir,         # G3 fix:用 ctx.run_dir(D8 加),不是 ctx.run.artifact_dir
    )
    return self._wrap_async(worker.submit(spec, timeout_s=...))
```

```json
// examples/comfy_local_smoke.json
{
  "steps": [{
    "provider_policy": {"models_ref": "image_local"},
    "config": {
      "spec": {
        "comfy_workflow": "GameAssets/01b_singleview_sdxl",
        "comfy_params": {"text": "...", "seed": 42},
        "comfy_lifecycle": "none"
      }
    }
  }]
}
```

**理由(F-B):**

- 与 ForgeUE 现有 mesh worker 接入模式一致(`GenerateMeshExecutor` 也是直接 invoke `HunyuanTokenhubMeshWorker` 不走 adapter 链,model id prefix-based dispatch)
- 不破坏 ModelRegistry schema(零 fanout 改 callsite)
- ComfyUI 配置走 env 是 ForgeUE 现有惯例(API key 都走 env;`config/models.yaml` 只配 `api_key_env` 引用具体 key 在 .env)—— scripts_dir 类比 API key 走 env 没破坏 ADR-002 精神,只是配置载体 split (key 类型 + reference 类型)
- 后续接 ComfyUI 视频/音频走"加新 model id"模式,executor 加新分支
- F-A schema 扩展是 framework data model 改造,如果哪天没有第二个 subprocess provider 就成死投资 → 登记 TBD-011 等需求驱动

**round 1 → round 2 关键 diff:**

| 维度 | round 1(失败) | round 2(F-B 修复) |
|---|---|---|
| ProviderDef 字段 | 加 `kind / scripts_dir / python_exe / default_lifecycle`(silent ignored) | 不动,只用 `api_key_env / api_base` 占位 |
| `models.comfy/local` | 缺 `id` → load fail | `id: "comfy/local"` 必填 |
| ComfyUI worker 配置 | 从 `ProviderDef` 字段读(读不到) | 从 env vars `FORGEUE_COMFY_*` 读 |
| Router dispatch | `provider.kind == "subprocess_cli"`(prepared_routes 无 provider 字段,不可达) | executor 检测 `model == "comfy/local"`(model id-based) |
| dry-run gate | `prepared_routes 含 provider=comfy_api`(同上不可达) | `prepared_routes 含 model="comfy/local"` |

### D8 — `StepContext` 加 `run_dir: Path` 字段(G3 fix)

**问题来源:** codex round 2 G3 high 发现 `Run` 模型(`task.py:83-95`)字段 `run_id / task_id / project_id / status / started_at / ended_at / workflow_id / current_step_id / artifact_ids / checkpoint_ids / trace_id / metrics` —— **真无 `artifact_dir`**;`StepContext`(`base.py:16-24`)字段 `run / task / step / repository / inputs / upstream_artifact_ids` —— **真无 `run_dir`**。round 1 我引用的 `ctx.run.artifact_dir` 是空属性,worker 构造 AttributeError。

**3 个选项(round 2 Decision Block G):**

- G-A:`StepContext` 加 `run_dir: Path` 字段,Orchestrator 注入
- G-B:`ArtifactRepository` 暴露 `get_run_payload_dir()` 受控接口
- G-C:ComfyAgentWorker 自拼路径,`artifact_root` 走 env

**选 G-A**(2026-05-02 user 拍板)。具体落地:

```python
# src/framework/runtime/executors/base.py
@dataclass
class StepContext:
    run: Run
    task: Task
    step: Step
    repository: ArtifactRepository
    run_dir: Path                  # ★ NEW(G-A)— 由 Orchestrator 注入
    inputs: dict[str, Any] = field(default_factory=dict)
    upstream_artifact_ids: list[str] = field(default_factory=list)

# src/framework/runtime/orchestrator.py
def _build_step_context(self, step, run, task):
    return StepContext(
        run=run, task=task, step=step,
        repository=self.repository,
        run_dir=self.artifact_root / run.started_at.strftime("%Y-%m-%d") / run.run_id,
        # ... existing fields ...
    )
```

理由:
- StepContext 是 framework 级清晰边界,所有 worker 复用(mesh / future workers 也需要 in-tree copy)
- 范围适中:改 StepContext + Orchestrator 几行 + 1-2 fence(在 `runtime-core/spec.md` 新增 ADDED Requirement"StepContext exposes run_dir for in-tree artifact placement")
- G-B 增加 worker-repository 耦合(worker 现在不依赖 repository 只产 ImageCandidate)
- G-C 路径拼接散在 worker 内,framework 改 artifact 路径约定时所有 worker 跟着改

**G3 commit 2 实施 drift(2026-05-02)**:实施时发现 `StepContext` 现有 ~25+ mock callsite(`tests/integration/` + `tests/unit/`),如果加 `run_dir: Path` REQUIRED(无 default)会全部 break TypeError("missing required field")。批量 patch 25 callsite 风险大且容易出错。务实 drift 决策:`run_dir` 用 `field(default_factory=lambda: Path("."))` 给 default factory(test-mock convenience),Orchestrator `_compute_run_dir(run)` helper 在唯一 production 构造点 (`orchestrator.py` line 459)总是 inject 真路径。新 fence `test_orchestrator_compute_run_dir_uses_checkpoints_root_no_extra_date` 守 production invariant。`runtime-core/spec.md` 已 update 反映这条 drift。这是 written-back-to-spec 的 acknowledged drift,production 不受影响。

### D9 — image_local alias 加进 SRS FR-MODEL-007(H-A fix)

**问题来源:** codex round 2 G4 medium 发现 `SRS:188 FR-MODEL-007` 是固定 alias 9 项枚举(`text_cheap / text_strong / review_judge / review_judge_visual / ue5_api_assist / image_fast / image_strong / image_edit / mesh_from_image`)—— **无 `image_local`**。`tasks.md §9.2` 写更新 SRS §5.3 + FR-WORKER-001 但**漏说更新 FR-MODEL-007 alias 列表**。

**2 个选项(round 2 Decision Block H):**

- H-A:tasks §9.2 加"更新 SRS FR-MODEL-007 alias 列表加 image_local"
- H-B:不加 image_local alias,把 `comfy/local` 加进 `image_fast` fallback list

**选 H-A**(2026-05-02 user 拍板)。理由:
- image_local 是真正的新独立 capability(本地 GPU image generation),应该有自己的 alias
- SRS alias 面 9 → 10 不算大事(SRS 本来就是会随 capability 增长 grow)
- H-B 把"本地 ComfyUI 当 cloud preferred 的 fallback"语义反了 —— 本地 ComfyUI 实际比云端慢(30-180s vs 几秒)+ GPU 资源更受限;用户想用本地 ComfyUI 时他们想**显式选**,不想走 cloud fallback

## Risks / Trade-offs

- **[用户必须自启 ComfyUI](D6 后果)→** lifecycle=`none` 决策让用户跑 bundle 前必须先 `python -m comfyui_api status` 确认在线,offline 用 `python -m comfyui_api serve` 启;ComfyUI cold start ~30-90 s 由用户在自己终端等。**Mitigation:** dry-run 阶段调一次 `python -m comfyui_api status` 探活(timeout 30 s),不在线时直接 fail Run 并在 error message 中告诉用户怎么启;CLAUDE.md / README 写明前置条件;`worker_timeout_s` 默认从原 60 s 调大到 300 s(覆盖单图 30-180 s 生成)
- **[`shutil.copy2` 跨盘符性能] →** 用户若把 ComfyUI 装在 E: 而 ForgeUE artifacts 在 D:,copy 走 OS file system 跨设备路径,百 MB 级 mesh / 视频 workflow 可能成本不可忽略。**Mitigation:** 本 change 只覆盖图像 workflow(单图 < 5 MB),3D / 视频 workflow 接入留给后续 change 再评估 hardlink / move 优化
- **[`shutil.copy2` 在 async 上下文阻塞] →** worker.submit 是 async 但 `shutil.copy2` 是同步 IO;单图 < 5 MB 在 Windows 同盘 < 100 ms 在事件循环可接受;若用户 batch_size 大或跨盘性能差可能短暂阻塞 progress event 推流。**Mitigation:** 本 change 范围内不为单图优化(open question:codex W-CopyAsyncBlocking 标 medium,不阻断 S3,记 TBD-010 一并评估)
- **[Windows 路径分隔符] →** ComfyUI agent CLI 输出的路径是 Windows backslash,JSON parse 后是字符串,跨 `os.fspath` / `pathlib.Path` 处理时要小心。**Mitigation:** worker 内部统一 `Path(...)` 包一次,所有 path 操作走 pathlib;`tests/unit/test_comfy_subprocess.py` 加 fence 校验 mixed-separator 输入
- **[Cancel 不可达 worker.submit](F1 critical 后果)→** orchestrator `to_thread` 包装层吸收 cancel 信号,worker.submit 在线程内继续跑直到自然完成。**Mitigation (D6 选 A 后):** lifecycle=none 下 subprocess 自然退出 = worker 退出,无残留;无孤儿进程,result 被外层 Future 丢弃即可。spec scenario 不再宣称"cancel terminates subprocess"(改为"cancel 后 worker 完成 result 被丢弃,best-effort");C 方案(executor async 重写)登记 TBD-010 后续 change
- **[FakeComfyWorker 与新 contract 偏离] →** FakeComfyWorker scripted 接口不变,但新 bundle 协议字段 `comfy_workflow` / `comfy_params` 它不消费(它直接 dequeue 队列里的 ImageCandidate)。容易让人误以为 fake 在"按 manifest 跑"。**Mitigation:** `FakeComfyWorker.submit` 校验 `spec` 里至少有 `comfy_workflow` 字段(语义只做 schema 守门,不影响 dequeue),缺字段直接 raise `WorkerUnsupportedResponse`;在 docstring 写明"fake 不真跑 manifest,scripted 队列驱动"
- **[`config/models.yaml` 加 provider entry + 虚拟 model id;loader 已 silent-ignore unknown subfield] →** 现有 `_parse_providers` line 262-278 + `_parse_models` line 281+ 用 `cfg.get(...)` 读已知字段,unknown subfield silent ignore。本 change 加 `providers.comfy_api` 占位 + `models.comfy/local` + `aliases.image_local` 三 entry,loader 接受这些 entry 但**不**对 unknown subfield 做 strict rejection(codex round 3 H4 揭出风险:用户实例化时 instinctively 加 `providers.comfy_api.scripts_dir: ...` 会被 silent ignore,worker 后续因 env 缺失才崩)。**Mitigation:** 本 change 只加 3 fence 守 provider/model/alias 各自正向解析路径;**spec 文字明告用户"YAML unknown subfield silent ignored",worker 配置必须走 env vars `FORGEUE_COMFY_*`**;CLAUDE.md / README double-terminal note 提醒;**未来 enhancement(非本 change scope):加 strict subfield rejection 到 `_parse_providers` / `_parse_models` / `_parse_aliases`,统一 subfield allowlist 守门,登记 TBD 待评估**
- **[CHANGELOG / acceptance_report drift] →** SRS §5.3 + FR-WORKER-001 描述变更,acceptance FR-WORKER-001 验收行的"`comfy_worker.py` + `test_comfy_http_unsupported`"指向的测试文件被重写;acceptance §8.1 自动化验收基线随 fence 增量变化(以 `python -m pytest -q` 实测为准,**不**硬编码总数,对齐 NFR-MAINT-003 + CLAUDE.md 禁令)。**Mitigation:** 走 `/forgeue:change-doc-sync` Documentation Sync Gate 强制扫 10 文档;tasks §9.6 明确"实测记录"

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
- **OQ-4 (codex S2→S3 review post-resolve):** lifecycle 4 模式(`none` / `ensure_running` / `ensure_release` / `self_managed_session`)本 change 接哪些?codex F1 critical 揭出 cancel 不可达 worker.submit。3 个选项 A(只 `none`)/ B(`none` + `ensure_running`)/ C(executor async 重写)
- **OQ-5 (codex S2→S3 review post-resolve):** ComfyUI 怎么进 ModelRegistry 三段式?ComfyUI 没 model id 概念。codex F2 high 揭出 alias 必须 in models 否则 raise。2 个选项 A(加虚拟 model id `comfy/local`) / B(bundle 加新字段 bypass)

## Resolved

- **OQ-1 → `sys.executable`**(2026-05-02)。worker 默认走 ForgeUE 自家 venv Python;`config/models.yaml` `providers.comfy_api.python_exe: null` 表示用 default;若用户实测发现 ComfyUI deps 不在 ForgeUE venv 内可显式覆盖为 `D:/AI/ComfyUI/venv/Scripts/python.exe`。dry-run 探活(任务 §3.5)若失败,error message 提示用户检查 `python_exe`
- **OQ-2 → 遇到 non-empty `outputs.audio` / `outputs.glb` 时 raise `WorkerUnsupportedResponse`**(2026-05-02)。理由:
  1. ForgeUE 三层架构(capability + executor + candidate type)把 image / mesh / audio 当独立链路,`generate_image` executor 只产 `ImageCandidate`,不该越界产 `MeshCandidate` / 音频 candidate
  2. mesh artifact 的 metadata(`format` / `poly_count` / `scale_unit` / `up_axis` / `has_uv` / `has_rig` / `texture` / `pbr` / `intended_use`)ComfyUI agent CLI JSON 完全不给,得 parse GLB 二进制 header 推断,这是独立 R&D 任务
  3. ForgeUE 已有 `HunyuanTokenhubMeshWorker` 走 Hunyuan tokenhub API 直接做 image-to-3D,acceptance 里 L4 + a2_mesh_0423 已 ✅;开第二条 ComfyUI mesh 来源涉及 capability alias 切换 / `fallback_models` 链 / cost 记账 / ADR-007 single-attempt 守门是否对本地 GPU 路径放开,是产品决策
  4. raise = 明确划线,防 image step 配错 workflow(选了 `combined_*` 这种同时出 PNG + GLB 的 manifest)时静默吞掉 GLB 输出造成"看似成功实则丢数据"
  5. 后续 change(暂定 `comfy-agent-mesh-adoption`)单独评估接入 mesh / 视频 / 音频 路径
- **OQ-3 → 传 `task.project_id`**(2026-05-02)。理由:语义对齐 —— ComfyUI agent CLI 的 `--project` 字段本意是"业务项目分组",ForgeUE 的 `task.project_id` 同义;`<run_id>` 是技术 ID 不是项目分组。事后对照 ComfyUI outputs 看 `D:/AI/ComfyUI/outputs/main/<date>/<task.project_id>/...` 一目了然。worker 已 copy 到 `artifacts/<run_id>/comfy/`,ForgeUE 侧 self-contained 不依赖 ComfyUI outputs 子目录命名
- **OQ-4 → A(lifecycle 只支持 `none`)**(2026-05-02 user 拍板,详细论证见 D6)。代价:用户必须自启 ComfyUI(双终端工作流);收益:F1 critical / F3 high / F5 high 三连消除,主 spec invariant 完全保留。C 方案(executor async 重写)登记 TBD-010 后续 change(见 D-FutureScope)
- **OQ-5 → A(虚拟 model id `comfy/local`)**(2026-05-02 user 拍板,详细论证见 D7)。具体 yaml shape 与 bundle JSON 见 D7;符合 ADR-002 + FR-MODEL-001 单一真源
- **OQ-6 → F-B(env-based config + executor model-id dispatch)**(2026-05-02 round 2 user 拍板,详细论证见 D7 round 2 修订段)。round 1 D7 设计("provider.kind dispatch + ProviderDef 加 4 字段")在现有 schema 不可实现(codex round 2 F2 not-actually-fixed + G1 critical);F-A schema 扩展登记 TBD-011 后续 change
- **OQ-7 → G-A(StepContext.run_dir Orchestrator 注入)**(2026-05-02 round 2 user 拍板,详细论证见 D8)。round 1 引用的 `ctx.run.artifact_dir` 是空属性(codex round 2 G3 high);加 StepContext.run_dir 是 framework 级清晰边界,mesh / future workers 都能复用
- **OQ-8 → H-A(image_local alias 加进 SRS FR-MODEL-007)**(2026-05-02 round 2 user 拍板,详细论证见 D9)。round 1 漏写 SRS FR-MODEL-007 update task(codex round 2 G4 medium);承认 SRS alias 面 9 → 10

## D-FutureScope — 登记到 SRS §7.3 的后续 change

本 change `tasks.md §9.10` 已登记 **TBD-009: ComfyUI agent CLI mesh / audio / video workflow 接入**(对应 OQ-2 划线,见 design.md `## Resolved` 段)。

D6 决策(选 A)产生第二条 follow-up,本 change `tasks.md §9.11` 登记 **TBD-010: GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径**(executor-async-rewrite,见下方 TBD-010 段)。

OQ-6 决策(选 F-B)产生第三条 follow-up,本 change `tasks.md §9.12` 登记:

> **TBD-011: ModelRegistry schema 扩 `ProviderDef.kind` + `extra fields` + `ResolvedRoute.provider_name / provider_kind`(model-registry-provider-kind-schema 后续 change),让 subprocess / non-OpenAI provider 配置统一进 yaml 不分裂到 env**

TBD-011 触发条件:第二个 subprocess provider 出现(比如本地 SDXL / 本地 mesh worker / 第三方 CLI 工具),需要框架统一接入路径。届时新 change(`model-registry-provider-kind-schema`)需要:

1. `ProviderDef` 加 `kind: str = "openai_compatible"` + `extra: dict[str, Any] = field(default_factory=dict)`(或具体字段如 `scripts_dir`)
2. `ResolvedRoute` 加 `provider_name: str` + `provider_kind: str`
3. `_parse_providers` 接受 extra fields(strict typo 守门保留)
4. `expand_model_refs` 透传 provider info 到 ResolvedRoute
5. 改所有 callsite(30+ 处使用 ResolvedRoute / ProviderDef)
6. 改 `comfy-agent-cli-adoption` 已落地代码:`comfy_api` provider entry 从占位升级到含 `kind: subprocess_cli` + `scripts_dir`等;ComfyAgentWorker 从 env 读改成从 ProviderDef 读;dry-run + executor dispatch 从 model id-based 改回 provider.kind-based
7. CHANGELOG 记 BREAKING(env vars `FORGEUE_COMFY_*` 弃用)

**本 change 作了什么准备**(让 TBD-011 后续易做):

- ComfyUI 配置走 env(`FORGEUE_COMFY_*`)是 reversible —— TBD-011 后切回 yaml 时改 env 读取为 ProviderDef 读取即可,worker 内部接口不动
- `models.comfy/local` virtual id + `image_local` alias 不变(TBD-011 不涉及 model id 命名)
- D-FutureScope 段明确登记 TBD-009 + TBD-010 + TBD-011 三条 follow-on,后续 change 起 propose 时用此段作 input

---

### TBD-010(原 D-FutureScope 内容):

> **TBD-010: GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径(orchestrator 直接 await worker.submit 不经 to_thread),取消并发 cancel 完全语义;ComfyUI lifecycle 借此扩展到 `ensure_running` + 主 spec `provider-routing/spec.md:211` Invariant + `:229` Non-Goal 一并 MODIFIED**

TBD-010 触发条件:用户实际使用本 change 后反馈"双终端 UX 痛苦"达到一定阈值,或框架其它 use case(mesh / 视频长任务取消)推动 executor async 化。届时新 change(暂定 `executor-async-rewrite`)需要:

1. 改 `src/framework/runtime/executors/` 下所有 sync `def execute(ctx)` 为 `async def aexecute(ctx)`(影响 generate_image / generate_mesh / generate_structured / review / select / export / import 等;orchestrator.py:474 改 `await executor.aexecute(ctx)` 不经 to_thread)
2. ComfyUI worker 重新评估 lifecycle scope:`ensure_running` 加回支持(届时 cancel 可达 worker.submit,subprocess 与 ComfyUI server 进程都能干净清理)
3. 主 spec `provider-routing/spec.md:211` Invariant"ComfyUI integration requires a user-owned local ComfyUI ... no framework-managed lifecycle" → MODIFIED 为"ComfyUI integration MAY use framework-managed lifecycle (`ensure_running` / `ensure_release` / `self_managed_session`) when the executor async rewrite is deployed"
4. 主 spec `:229` Non-Goal"Framework-managed ComfyUI process lifecycle" → REMOVED(改成 supported scope)
5. 配套 fence:DAG cascade cancel 实测断言 ComfyUI subprocess 与 server 进程被清理;Windows 下 process tree cleanup 验证

**本 change 作了什么准备**(让 TBD-010 后续易做):

- `ComfyAgentWorker.submit` 内部已用 `asyncio.create_subprocess_exec`(虽然 cancel 当前不可达,但接口已 async-ready,TBD-010 后 executor 改 async 时 worker 这层不用动)
- spec ADDED Requirement"ComfyUI worker invokes the agent CLI via subprocess" 顶层文字描述了 4 个 lifecycle 模式但本 change scope 只接 `none` —— 措辞预留,TBD-010 加 `ensure_running` 时只需 MODIFIED 同 requirement,不必新增
- D6 + D7 决策段明确写 "本 change 唯一支持 `none`",后续 change 解锁时改这一处即可
