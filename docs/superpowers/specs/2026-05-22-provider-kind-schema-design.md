# FOR-9 Provider Kind Schema 设计

## 背景

FOR-9 处理的是 ModelRegistry 的 provider schema 缺口。当前 registry 能表达模型能力 `kind`
（如 `image` / `mesh` / `audio` / `video`），但不能表达 provider 的运行类型。
这导致 ComfyUI 这类本地 subprocess provider 的配置分裂在 `FORGEUE_COMFY_*`
环境变量中，而 `config/models.yaml` 只保留了一个 `comfy_api` 占位 provider。

现有代码的直接后果是：

- `ResolvedRoute` 只携带 `model/api_key_env/api_base/kind/pricing`，没有 provider 标识。
- dry-run / executor / orchestrator 只能通过 `comfy/local*` model id 判断是否走 ComfyUI。
- `scripts_dir` / `python_exe` / lifecycle 默认值无法通过项目内 yaml 配置统一管理。

本设计采用 B 方案：把 ComfyUI provider 运行配置迁入项目内 `config/models.yaml`，
同时保留 `FORGEUE_COMFY_*` 作为兼容覆盖，避免破坏当前本机工作流。

## 目标

1. `ProviderDef` 能表达 provider 类型和运行配置。
2. `ResolvedRoute` / `PreparedRoute` 能把 provider 元数据传到运行时。
3. ComfyUI 的项目级配置统一写在 `config/models.yaml`。
4. 运行时识别 ComfyUI 时优先看 provider 元数据，不再散落硬编码 `comfy/local*` 判断。
5. 保留现有环境变量作为迁移期覆盖层。

## 非目标

1. 不实现第二个 subprocess provider。
2. 不重构完整 provider factory 或 managed process registry；FOR-7 继续独立处理。
3. 不删除 `FORGEUE_COMFY_*` 环境变量兼容逻辑。
4. 不改变 bundle 中 `provider_policy.models_ref` 的写法。
5. 不修改 ComfyUI 外部安装目录，也不删除任何本地文件。

## Schema 设计

`providers.<name>` 增加两个概念：

```yaml
providers:
  comfy_api:
    kind: subprocess
    api_key_env: null
    api_base: null
    subprocess:
      adapter: comfy_agent_cli
      scripts_dir: "D:/AI/ComfyUI/scripts"
      python_exe: null
      default_lifecycle: none
      input_dir: "D:/AI/ComfyUI/apps/official-main-git-v092/input"
      output_root: "D:/AI/ComfyUI"
```

字段含义：

- `kind`: provider 运行类型。默认值为 `openai_compat`，兼容现有 provider。
- `subprocess.adapter`: subprocess provider 的具体适配器。FOR-9 只支持 `comfy_agent_cli`。
- `subprocess.scripts_dir`: ComfyUI `scripts` 目录，等价于旧 `FORGEUE_COMFY_SCRIPTS_DIR`。
- `subprocess.python_exe`: 可选 Python 解释器，等价于旧 `FORGEUE_COMFY_PYTHON_EXE`。
- `subprocess.default_lifecycle`: 默认 lifecycle，等价于旧 `FORGEUE_COMFY_LIFECYCLE`。
- `subprocess.input_dir`: mesh source image 写入目录，等价于旧 `FORGEUE_COMFY_INPUT_DIR`。
- `subprocess.output_root`: ComfyUI 输出根路径，等价于旧 `FORGEUE_COMFY_OUTPUT_ROOT`。

`ProviderDef` 需要保留旧字段，并增加：

```python
kind: str = "openai_compat"
subprocess: ProviderSubprocessConfig | None = None
```

`ResolvedRoute` / `PreparedRoute` 增加：

```python
provider_name: str | None = None
provider_kind: str = "openai_compat"
provider_config: dict | None = None
```

`provider_config` 是传给运行时的序列化配置。对非 subprocess provider 为空。

## 配置优先级

运行时按以下顺序取值：

1. step 显式配置：`step.config.spec.comfy_lifecycle` 只覆盖 lifecycle。
2. 环境变量：`FORGEUE_COMFY_*` 作为兼容覆盖。
3. provider yaml：`prepared_routes[*].provider_config`。
4. 内建默认值：仅 `default_lifecycle` 可回退到 `none`。

如果 `scripts_dir` 缺失，ComfyUI step 仍 fail-fast。这样既允许无 ComfyUI 的 CI
做结构 dry-run，也能在真正执行本地 ComfyUI step 时清楚报错。

## 运行时设计

新增一个小 helper，集中判断 route 是否为 ComfyUI provider：

```python
def is_comfy_agent_route(route: PreparedRoute) -> bool:
    return (
        route.provider_kind == "subprocess"
        and (route.provider_config or {}).get("adapter") == "comfy_agent_cli"
    )
```

四个 executor 使用该 helper 判断是否走 ComfyAgentWorker：

- image: `GenerateImageExecutor._should_use_worker_path`
- mesh: `GenerateMeshExecutor._should_use_comfy_worker_path`
- audio: `GenerateAudioExecutor._should_use_comfy_worker_path`
- video: `GenerateVideoExecutor._should_use_comfy_worker_path`

构造 `ComfyAgentWorker` 时通过另一个 helper 解析配置：

```python
config = resolve_comfy_agent_config(route=route, spec=spec)
```

该 helper 做三件事：

1. 合并 yaml + env + step lifecycle。
2. 把 path 字符串转成 `Path`。
3. 对必填字段给出清楚错误。

`DryRunPass._check_comfy_reachability` 改为扫描 `is_comfy_agent_route(route)`。
这样新增本地 ComfyUI model id 时，不需要同步维护 dry-run 的 model id 集合。

`Orchestrator._detect_comfy_lifecycle` 也改为扫描 provider 元数据；构造
`ComfyLifecycleManager` 时使用解析后的 `scripts_dir/python_exe`。

## 错误处理

- provider `kind` 缺省为 `openai_compat`，旧 yaml 不需要改。
- `kind: subprocess` 但缺少 `subprocess.adapter` 时，registry 解析阶段报错。
- `adapter` 不是 `comfy_agent_cli` 时，registry 解析阶段报错。
- `default_lifecycle` 不在合法集合时，registry 解析阶段报错。
- ComfyUI 执行时缺少 `scripts_dir`，继续抛对应 worker unsupported 异常。
- mesh 执行时缺少 `input_dir`，继续抛对应 mesh unsupported 异常。

## 测试计划

新增或更新以下测试：

1. `tests/unit/test_model_registry.py`
   - provider `kind/subprocess` 能解析。
   - unknown provider kind 被拒绝。
   - unknown subprocess adapter 被拒绝。
   - alias 解析后的 route 带 `provider_name/provider_kind/provider_config`。
   - `as_policy_fields()` 输出能被 `PreparedRoute` 接受。

2. `tests/unit/test_registry_pricing.py`
   - pricing 透传不受 provider 元数据影响。

3. `tests/unit/test_comfy_subprocess.py`
   - image executor 能通过 provider 元数据进入 ComfyAgentWorker 路径。
   - env 覆盖 yaml 的 `scripts_dir/python_exe/default_lifecycle/output_root`。
   - yaml fallback 在 env 缺省时可用。

4. `tests/unit/test_generate_mesh_comfy.py`
   - mesh executor 从 provider config 读取 `input_dir`。
   - `FORGEUE_COMFY_INPUT_DIR` 仍能覆盖 yaml。

5. `tests/unit/test_generate_audio_comfy.py` / `tests/unit/test_generate_video_comfy.py`
   - audio/video executor 通过 provider 元数据进入 ComfyAgentWorker 路径。

6. `tests/unit/test_comfy_lifecycle.py` 或 `tests/unit/test_orchestrator.py`
   - orchestrator lifecycle manager 使用 provider config 构造。

7. `tests/integration/test_example_bundles_smoke.py`
   - 示例 bundle 的 `models_ref` 展开后仍能通过 Pydantic 校验。

## 文档更新

实现阶段需要同步更新：

- `config/models.yaml` 顶部说明和 `comfy_api` provider 示例。
- `docs/requirements/SRS.md` 的 PreparedRoute 定义、FR-WORKER-001、provider 表、FOR-9 对应条目。
- `AGENTS.md` / `CLAUDE.md` 中 ComfyUI 配置说明。
- `docs/backlog/active.md` / `docs/backlog/archived.md` 在实现完成后由 document-release 流程同步。

## 验收标准

1. `python -m pytest tests/unit/test_model_registry.py tests/unit/test_registry_pricing.py -q` 通过。
2. ComfyUI 相关 unit tests 通过。
3. 示例 bundle smoke tests 通过。
4. `python -m pytest -q` 全量通过，或在确有本机依赖限制时记录未跑原因。
5. `config/models.yaml` 成为 ComfyUI 项目级配置的主入口。
6. 代码中新增的 ComfyUI provider 判断不再依赖 `comfy/local*` model id 集合。

