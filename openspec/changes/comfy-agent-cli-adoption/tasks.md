## 1. 准备工作与前置确认

- [ ] 1.1 确认 D:/AI/ComfyUI/scripts/ 在本机存在,`python -m comfyui_api status` 调通(印证 OQ-1 的 `sys.executable` 选择能跑通 ComfyUI deps);记录实测结果
- [x] 1.2 OQ + Decision 全部 resolved:OQ-1=`sys.executable`、OQ-2=non-empty `outputs.audio` / `outputs.glb` raise `WorkerUnsupportedResponse`、OQ-3=`--project` 传 `task.project_id`、OQ-4 (Decision A) = lifecycle 只支持 `none`、OQ-5 (Decision B) = `models:` 段加虚拟 model id `comfy/local` + 新 alias `image_local`、**OQ-6 (Decision F round 2) = F-B (env-based config + executor model-id dispatch),不动 ProviderDef schema;F-A schema 扩展登记 TBD-011**、**OQ-7 (Decision G round 2) = G-A (StepContext 加 run_dir 字段, Orchestrator 注入)**、**OQ-8 (Decision H round 2) = H-A (image_local alias 加进 SRS FR-MODEL-007)**;详细论证见 design.md `## Resolved` 段 + D6 + D7 (round 2 修订段) + D8 + D9 + D-FutureScope (TBD-009/010/011)
- [ ] 1.3 起新分支或确认在 chore/openspec-superpowers 上继续(本 change 已挂 openspec/changes/comfy-agent-cli-adoption/)

## 2. ModelRegistry config + env vars 约定(commit 1)

- [ ] 2.1 在 `config/models.yaml` `providers:` 段加 `comfy_api` entry,**只用 ProviderDef-supported 字段**:`api_key_env: null` + `api_base: null`(占位让 model 引用合法;ComfyUI worker 配置不进 yaml,见 §2.4 走 env)。**不**加 `kind` / `scripts_dir` / `python_exe` / `default_lifecycle` 字段(round 1 加这些会被 `_parse_providers` line 262-278 silent ignore — round 2 codex G1 揭出)
- [ ] 2.2 在 `config/models.yaml` `models:` 段加虚拟 model id `comfy/local` entry,**必填 `id` 字段**:`id: "comfy/local"` + `provider: comfy_api` + `kind: image` + `pricing: null`(本地 GPU,无 per-call cost,FR-COST-008/009 接口仍在,值 0.0;round 1 漏写 `id` 字段会让 `_parse_models` line 290-293 raise — round 2 codex F2 揭出)
- [ ] 2.3 在 `config/models.yaml` `aliases:` 段加 `image_local` alias:`preferred: ["comfy/local"]` + `fallback: []`
- [ ] 2.4 文档 ComfyUI worker env vars 约定(README 或 CLAUDE.md):`FORGEUE_COMFY_SCRIPTS_DIR`(REQUIRED;dry-run 校验)+ `FORGEUE_COMFY_PYTHON_EXE`(OPTIONAL,空 → `sys.executable`)+ `FORGEUE_COMFY_LIFECYCLE`(OPTIONAL,空 → `"none"`;本 change 仅接受 `"none"`,其它值 raise `WorkerUnsupportedResponse`);`.env.example` 加这三行作占位
- [ ] 2.5 新增 `tests/unit/test_model_registry.py` 三 fence:`test_comfy_api_provider_placeholder_parses`(确认 `api_key_env: null + api_base: null` 占位被接受) / `test_comfy_local_model_id_missing_raises`(确认 `models.comfy/local` 缺 `id` 时 `_parse_models` raise `ValueError`)/ `test_image_local_alias_resolves_via_registry`(确认 alias `image_local` 展开为含 `comfy/local` 的 ResolvedRoute,字段 `model="comfy/local"` / `kind="image"` / `pricing=None`)
- [ ] 2.6 commit 1:`feat(registry): register comfy_api placeholder + comfy/local virtual model + image_local alias (env-based worker config per OQ-6)`

## 3. ComfyAgentWorker 实装 — 配置走 env(commit 2)

- [ ] 3.1 在 `src/framework/providers/workers/comfy_worker.py` 重命名 `HTTPComfyWorker` → `ComfyAgentWorker`,删除全部 HTTP 相关代码(requests / `/prompt` / `/history` / `/view`),保留 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` / `ImageCandidate` / `FakeComfyWorker`
- [ ] 3.2 实装 `ComfyAgentWorker.__init__(*, scripts_dir: Path, run_id: str, project_id: str, artifacts_dir: Path, python_exe: Path | None = None, default_lifecycle: str = "none")`(**keyword-only 签名;required 在 default 之前以满足 Python 语法** — round 3 codex H3 fix:round 2 把 required 放在 default 之后是 SyntaxError at import time);`run_id` / `project_id` / `artifacts_dir` 全部 REQUIRED 不可 None(round 2 codex F4 / G3 fix);`__init__` 内 `if project_id is None or not project_id: raise WorkerUnsupportedResponse(...)` + 同样校验 `artifacts_dir is not None and Path(artifacts_dir).is_dir()`;`assert default_lifecycle == "none"`(D6 守门);构造 cmd `[python_exe or sys.executable, "-m", "comfyui_api", "run", ...]`;subprocess 用 `asyncio.create_subprocess_exec(..., cwd=scripts_dir, stdout=PIPE, stderr=PIPE)` + `await proc.communicate()`
- [ ] 3.3 `submit(spec, *, timeout_s)` 解析 stdout JSON,按 spec D5 表格 + round 2 修正映射 7 类失败:env unset / scripts_dir 缺失 / module not found / project_id None / artifacts_dir None / 4 类 exit 2 stdout error / stdout 非 JSON / 缺 `outputs` / TimeoutError / 未识别 → 对应异常类型;**`comfy_lifecycle` 非 `"none"` → raise `WorkerUnsupportedResponse`**;成功路径产出 `list[ImageCandidate]`(从 `outputs.images` 读 PNG bytes);**`outputs.glb` / `outputs.audio` non-empty → raise `WorkerUnsupportedResponse`**
- [ ] 3.4 实装"copy 到项目树"逻辑:`outputs.images` 每条路径 `shutil.copy2` 到 `artifacts_dir / "comfy" / src.name`,`ImageCandidate` 的字节读自 copy 后路径(NFR-PORT-004 + A4)
- [ ] 3.5 实装 dry-run 探活 helper **`ComfyAgentWorker.probe_sync(scripts_dir: Path, python_exe: Path | None, timeout_s: float = 30.0) -> None`** classmethod,**用 `subprocess.run([py, "-m", "comfyui_api", "status"], cwd=scripts_dir, timeout=timeout_s, capture_output=True, text=True)` (NOT `asyncio.create_subprocess_exec` + `asyncio.run`)** — round 3 plan codex P2 fix:`DryRunPass.run` (`src/framework/runtime/dry_run_pass.py:49`) 是 sync method,在 `orchestrator.py:124` 被 sync 调用但 orchestrator.arun 已在 event loop 内 — 嵌套 `asyncio.run` 必崩 `RuntimeError("cannot be called from a running event loop")`;exit 0 = OK;其它 / timeout → raise `WorkerUnsupportedResponse(... "请先 'python -m comfyui_api serve' 启动 ComfyUI 或确认 FORGEUE_COMFY_SCRIPTS_DIR 设置正确")`。**注:async `ComfyAgentWorker.submit` 不变(step 阶段调,经 `_generate_via_worker` 内 `asyncio.run(...)` bridge 调用);只 dry-run preflight 用 sync `probe_sync` 变体。**
- [ ] 3.6 commit 2:`feat(comfy): replace HTTPComfyWorker with ComfyAgentWorker (subprocess CLI, env-based config, REQUIRED project_id+artifacts_dir, lifecycle=none only)`

## 4. Executor + DryRunPass + worker dispatch(commit 3)

- [ ] 4.1 在 `src/framework/runtime/executors/generate_image.py` 的 `_resolve_spec` 读取 `comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段;旧字段 `workflow_graph` 命中时 raise `WorkerUnsupportedResponse`;`comfy_lifecycle` 非 `"none"` 也 raise
- [ ] 4.2 在 `GenerateImageExecutor.execute` 加 worker dispatch 分支:**检测 `prepared_routes` 含 `model == "comfy/local"`时,调新方法 `_generate_via_worker(ctx, spec)` 而不走 `_generate_via_router`**(G2 fix:round 1 没加分支,所有 image step 都走 router 导致 comfy_workflow 不会进 worker);`_should_use_api_path` 改为 `_should_use_router_path`(语义清晰)+ 新增 `_should_use_worker_path` 检测 `comfy/local`
- [ ] 4.3 实装 `_generate_via_worker(ctx, spec)`(**SYNC method,内部用 `asyncio.run(...)` bridge 调 async worker,镜像 `_generate_via_router` 已有 pattern at `generate_image.py:295`** — round 3 codex H2 fix:round 2 spec 写 `await worker.submit` 在 sync executor 内是无效 Python):
  ```python
  def _generate_via_worker(self, ctx, spec, timeout_s):
      async def _aworker_call():
          worker = ComfyAgentWorker(
              scripts_dir=Path(os.environ["FORGEUE_COMFY_SCRIPTS_DIR"]),
              run_id=ctx.run.run_id,
              project_id=ctx.task.project_id,
              artifacts_dir=ctx.run_dir,
              python_exe=Path(os.environ["FORGEUE_COMFY_PYTHON_EXE"]) if os.environ.get("FORGEUE_COMFY_PYTHON_EXE") else None,
              default_lifecycle=os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none"),
          )
          return await worker.submit(spec, timeout_s=timeout_s)
      return asyncio.run(_aworker_call())
  ```
  从 env 读 `FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_PYTHON_EXE` / `FORGEUE_COMFY_LIFECYCLE` → 构造 `ComfyAgentWorker`(keyword-only 签名,F4+G3 fix:`project_id` REQUIRED 来自 `ctx.task.project_id`,`artifacts_dir` REQUIRED 来自 `ctx.run_dir` 不是 `ctx.run.artifact_dir`);包装 result 为 `ExecutorResult(artifacts=[...], metrics={"cost_usd": 0.0, "chosen_model": "comfy/local", "_route_pricing": None})`(FR-COST 接口保留)
- [ ] 4.4 dry-run 钩子:`DryRunPass` 在发现**已解析的 `prepared_routes` 含 `model == "comfy/local"` 的 route**时(用 model id 而非 provider 信息因为 ResolvedRoute 没 provider 字段 — round 2 G1 limitation),**直接 sync 调** `ComfyAgentWorker.probe_sync(scripts_dir=Path(os.environ["FORGEUE_COMFY_SCRIPTS_DIR"]), python_exe=Path(os.environ["FORGEUE_COMFY_PYTHON_EXE"]) if os.environ.get("FORGEUE_COMFY_PYTHON_EXE") else None, timeout_s=30.0)`(round 3 plan codex P2 fix:**NOT** `asyncio.run(probe(...))`,因为 `DryRunPass.run` 是 sync 在 event loop 内被调用,嵌套 asyncio.run 会 `RuntimeError`),失败 fail Run + error message 包含"`python -m comfyui_api serve` 启动 + 检查 FORGEUE_COMFY_SCRIPTS_DIR";env unset 时直接 raise `WorkerUnsupportedResponse`(不跑 probe)
- [ ] 4.5 commit 3:`feat(executor+dryrun): GenerateImageExecutor dispatches comfy/local routes to ComfyAgentWorker (worker path, not router); DryRunPass conditional probe`

## 5. StepContext.run_dir 注入(commit 4 — 新 G3 fix)

- [ ] 5.1 在 `src/framework/runtime/executors/base.py` 给 `StepContext` 加新字段 `run_dir: Path`(REQUIRED,not Optional;放 `repository` 后 `inputs` 前以保持构造参数顺序兼容)
- [ ] 5.2 在 `src/framework/runtime/orchestrator.py` 加 helper method `_compute_run_dir(self, run: Run) -> Path`:`root = getattr(self.checkpoints, "_root", None); if root is None: raise RuntimeError("CheckpointStore._root not set"); return Path(root) / run.run_id`(round 3 codex H1 fix:round 2 写 `self.artifact_root / date / run_id` **错两次** — Orchestrator 没 `self.artifact_root` 字段,且 `framework.run` `--artifact-root` 默认已 date-bucketed `artifacts/<today>/`,line 149 用 `artifact_root / args.run_id` 不加额外 date 段,所以 run_dir 不能加额外 date)。`Orchestrator._post_step` line 627 已经用 `getattr(self.checkpoints, "_root", None)` 拿 root 给 `dump_run_metadata`,沿用同一来源以保持一致。在所有构造 `StepContext` 处(grep `StepContext(`)注入 `run_dir=self._compute_run_dir(run)`
- [ ] 5.3 现有所有 executor(`generate_image` / `generate_mesh` / `generate_structured` / `review` / `select` / `export` / `import` 等)如果有 mock StepContext 的测试,补 `run_dir=tmp_path` 字段;grep `StepContext(` in tests/ 找全 callsite
- [ ] 5.4 新增 `tests/unit/test_step_context.py::test_step_context_run_dir_required`(确认 `StepContext(...)` 不传 run_dir 时 dataclass raise) + `tests/unit/test_orchestrator.py::test_orchestrator_injects_run_dir_into_step_context`(确认 Orchestrator 构造 StepContext 时 run_dir 是 `artifact_root/<date>/<run_id>/`)
- [ ] 5.5 commit 4:`feat(runtime-core): StepContext exposes run_dir; Orchestrator injects artifact_root/<date>/<run_id>/`

## 6. FakeComfyWorker schema 守门(commit 5)

- [ ] 6.1 `FakeComfyWorker.submit(spec, *, timeout_s)` 在 dequeue 之前校验 `spec` 含 `comfy_workflow`(string) + `comfy_params`(dict),缺字段 raise `WorkerUnsupportedResponse`;若 `comfy_lifecycle` 非 `"none"` 也 raise(对齐真 worker 行为)
- [ ] 6.2 更新 `FakeComfyWorker` docstring,写明"fake 不真跑 manifest,scripted 队列驱动;校验只为新 contract schema 守门,不消费 workflow 名"
- [ ] 6.3 现有依赖 FakeComfyWorker 的测试(test_p3 / a2_image bundle / examples_smoke / 其它 unit)若有调用 `program(...)` + `submit({...})` 但 spec dict 缺新字段,补上最小骨架(只为通过 schema 校验,不影响 dequeue 行为);用 grep 找全所有 call site 后批量补
- [ ] 6.4 commit 5:`feat(comfy): FakeComfyWorker enforces new spec schema (comfy_workflow+params+lifecycle=none)`

## 7. 单元测试改造(commit 6)

- [ ] 7.1 新增 `tests/unit/test_comfy_subprocess.py`,实装 spec `probe-and-validation/spec.md` 列出的全部 fence。重点 fence(post-round-2 update):
  - `test_missing_scripts_dir_raises_unsupported_response` / `test_python_module_not_found_raises_unsupported_response`
  - `test_env_unset_raises_unsupported_response`(NEW)
  - `test_project_id_none_raises_unsupported_response_at_init`(NEW — F4 fix)
  - `test_artifacts_dir_none_raises_unsupported_response_at_init`(NEW — G3 fix)
  - `test_exit2_missing_param_maps_to_unsupported` / `test_exit2_value_out_of_range_maps_to_unsupported` / `test_exit2_value_not_in_list_maps_to_unsupported`
  - `test_stdout_not_json_maps_to_unsupported` / `test_stdout_missing_outputs_field_maps_to_unsupported`
  - `test_exit2_timeout_maps_to_worker_timeout` / `test_exit2_unrecognised_error_maps_to_worker_error`
  - `test_subprocess_invocation_passes_workflow_params_lifecycle_timeout`
  - `test_subprocess_invocation_passes_task_project_id_as_dash_dash_project`(F4 fix verify)
  - `test_outputs_paths_are_copied_into_run_artifact_tree`
  - `test_outputs_glb_non_empty_raises_unsupported_response` / `test_outputs_audio_non_empty_raises_unsupported_response`
  - `test_lifecycle_other_than_none_raises_unsupported_response`
  - `test_cancel_under_to_thread_does_not_orphan_processes`
  - `test_dry_run_skips_probe_when_no_comfy_local_in_routes`(G1 limitation:gate by model id)
  - `test_dry_run_30s_timeout`
  - `test_executor_dispatches_comfy_local_to_worker_not_router`(NEW — G2 fix)
  - `test_comfy_agent_worker_reads_env_config`(NEW — F-B fix:scripts_dir / python_exe / lifecycle 来自 env)
- [ ] 7.2 fence 用 `monkeypatch.setattr(asyncio, "create_subprocess_exec", ...)` + `monkeypatch.setenv(...)` 设置 env vars + mock `_should_use_worker_path` / `_generate_via_worker`;不引 `requests` / `httpx`
- [ ] 7.3 删除 `tests/unit/test_comfy_http_unsupported.py`(HTTP 协议已不存在)
- [ ] 7.4 跑 `python -m pytest tests/unit/test_comfy_subprocess.py -v` 全绿
- [ ] 7.5 跑 `python -m pytest -q` 全量,**实测记录绝对总数**(不硬编码增量算式,对齐 NFR-MAINT-003 + CLAUDE.md "不硬编码测试总数;以 `python -m pytest -q` 实测为准");per-file fence 增量 = `test_comfy_subprocess.py` ~22 + `test_model_registry.py` 3 + `test_step_context.py` 1 + `test_orchestrator.py` 1 - `test_comfy_http_unsupported.py` 删除前 fence 数;实测总数与本 change 落盘前 acceptance §8.1 v1.5 基线 1144 对比,记到 §11.1 verify evidence
- [ ] 7.6 commit 6:`test(comfy+runtime): subprocess + env config + worker dispatch + StepContext.run_dir fences (~27 total) replace HTTP unsupported fence`

## 8. examples 重写(commit 7)

- [ ] 8.1 重写 `examples/comfy_local_smoke.json`:删除 `spec.workflow_graph`,加 `spec.comfy_workflow: "GameAssets/01b_singleview_sdxl"` + `spec.comfy_params: {"text": "single oak barrel isolated white background", "seed": 7777, "width": 512, "height": 512}` + `spec.comfy_lifecycle: "none"`;**`provider_policy.models_ref: "image_local"`**(走新 alias);bundle 在 5 KB 以内
- [ ] 8.2 删除 `examples/comfy/build_bundle.py`、`examples/comfy/tavern_door.api.json`、`examples/comfy/image_z_image_turbo.json`(v1 inline-workflow helper 与原始 workflow JSON 副本);若 `examples/comfy/` 目录空了一并删
- [ ] 8.3 跑 `tests/integration/test_example_bundles_smoke.py` 全绿(自动 parametrize 收新 bundle)
- [ ] 8.4 commit 7:`examples(comfy): switch local smoke to manifest workflow + image_local alias`

## 9. 本机 live smoke 验收(可选但建议)

- [ ] 9.1 启 ComfyUI:`python -m comfyui_api serve`(自启)或确认已 online (`python -m comfyui_api status` 返 OK)
- [ ] 9.2 在 shell 设 env vars:`export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`(其它两个保持默认)
- [ ] 9.3 跑 `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id comfy_smoke_<date>`
- [ ] 9.4 验证产物落 `artifacts/<today>/comfy_smoke_<date>/comfy/<filename>.png`(in-tree);原始 ComfyUI 输出 `D:/AI/ComfyUI/outputs/main/<today>/<task.project_id>/...` 也存在(留作人工对照,不影响 ForgeUE artifact tree 自包含性)
- [ ] 9.5 lifecycle=none 模式:确认 ForgeUE 没有启动 / 关闭 ComfyUI 进程(全程由用户在终端 1 自管;ForgeUE 在终端 2 跑只调 subprocess)
- [ ] 9.6 把 live smoke 结果(命令、产物路径、duration_s、绝对 pytest 总数)记录到本 change 的 `notes/live_smoke_<date>.md`

## 10. 文档同步(commit 8,Documentation Sync Gate 强制)

- [ ] 10.1 调 `/forgeue:change-doc-sync` 跑静态扫描,获取 10 文档 [REQUIRED] / [OPTIONAL] / [SKIP] 清单
- [ ] 10.2 更新 `docs/requirements/SRS.md`:(a) §5.3 表格 ComfyUI 行(协议 HTTP → subprocess CLI,适配层 `comfy_worker.py` 类名 ComfyAgentWorker;新增"lifecycle: none only"列);(b) FR-WORKER-001 描述;(c) **FR-MODEL-007 alias 列表加 `image_local`**(round 2 G4 fix — H-A 决议);(d) §7.2 变更记录加 v1.X 行
- [ ] 10.3 更新 `docs/design/HLD.md` ComfyUI 子系统描述(协议层 subprocess CLI + lifecycle=none 范围 + project_id 分组 + virtual model id `comfy/local` + alias `image_local` + env vars 配置)
- [ ] 10.4 更新 `docs/design/LLD.md` ComfyUI worker 详细字段(类名 ComfyAgentWorker、构造参数完整签名 含 REQUIRED project_id/artifacts_dir、subprocess + 失败模式映射表 + cancel best-effort 语义 + env vars 读取);加 StepContext.run_dir 字段说明
- [ ] 10.5 更新 `docs/testing/test_spec.md` 索引,加 `test_comfy_subprocess.py` ~22 条 fence 描述 + `test_step_context.py` + `test_orchestrator.py::test_orchestrator_injects_run_dir_into_step_context` fence,删 `test_comfy_http_unsupported` 行
- [ ] 10.6 更新 `docs/acceptance/acceptance_report.md`:(a) FR-WORKER-001 验收行(指向 `comfy_worker.py` ComfyAgentWorker + `test_comfy_subprocess.py`);(b) §8.1 自动化验收基线行(v1.5 = 1144 → v1.6 = **实测**,**不硬编码**预期增量);(c) 加 v1.6 变更记录行;v1.6 描述指向 OpenSpec change `comfy-agent-cli-adoption` + commit 列表
- [ ] 10.7 更新 `CHANGELOG.md` 加 `comfy-agent-cli-adoption` 条目(BREAKING:bundle workflow_graph 字段废止、lifecycle 仅 `none`、新虚拟 model id `comfy/local` + alias `image_local`、ComfyUI worker 配置走 env `FORGEUE_COMFY_*`、StepContext 加 run_dir 字段;CLI 替代 HTTP;输出 copy 到项目树;参考本 change tasks.md)
- [ ] 10.8 更新 `CLAUDE.md` 提示用户本机 live smoke 前置条件:(a) 必须先启 ComfyUI;(b) 设 env var `FORGEUE_COMFY_SCRIPTS_DIR`;(c) double-terminal 工作流;TBD-010 / TBD-011 解锁后此前置可调整
- [ ] 10.9 `AGENTS.md` 视情况同步(若有 ComfyUI 段)
- [ ] 10.10 在 `docs/requirements/SRS.md` §7.3 未决事项表追加 `TBD-009: ComfyUI agent CLI mesh / audio / video workflow 接入(目标决议日期 = 本 change 归档后再评估)`,描述指向本 change `design.md` Resolved OQ-2 + Non-Goals 段
- [ ] 10.11 在 `docs/requirements/SRS.md` §7.3 未决事项表追加 `TBD-010: GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径,取消并发 cancel 完全语义;ComfyUI lifecycle 借此扩展到 ensure_running + 主 spec provider-routing 的 lifecycle 相关 Invariant + Non-Goal 一并 MODIFIED(目标决议日期 = 用户实际使用本 change 后反馈双终端 UX 痛苦阈值或框架其它 long-task cancel use case 推动)`,描述指向本 change `design.md` D6 + D-FutureScope 段
- [ ] 10.12 **NEW (round 2 G1+F2+F5 fix follow-on)**:在 `docs/requirements/SRS.md` §7.3 未决事项表追加 `TBD-011: ModelRegistry schema 扩 ProviderDef.kind + extra fields + ResolvedRoute.provider_name/provider_kind(model-registry-provider-kind-schema 后续 change),让 subprocess / non-OpenAI provider 配置统一进 yaml 不分裂到 env(目标决议日期 = 第二个 subprocess provider 出现时;比如本地 SDXL / 第三方 CLI 工具 / 本地 mesh worker)`,描述指向本 change `design.md` D7 round 2 修订段 + D-FutureScope TBD-011 段
- [ ] 10.13 commit 8:`docs: sync ComfyUI agent CLI adoption (env-based config + worker dispatch + StepContext.run_dir + image_local alias) across SRS/HLD/LLD/test/acceptance/CHANGELOG/CLAUDE`

## 11. Verify + Review + Finish

- [ ] 11.1 调 `/forgeue:change-verify`,完成 Level 0 / 1 / 2 验证(L0=`pytest -q` 实测绝对总数 + 与 v1.5 基线 1144 对比;L1=`tests/unit/test_comfy_subprocess.py` + `test_step_context.py`;L2=本机 live smoke 已在 §9 跑过则贴 evidence,未跑则记 SKIP + reason)
- [ ] 11.2 调 `/forgeue:change-review`(Superpowers requesting-code-review finalize + codex /codex:adversarial-review mixed scope);blocker 必须回写到 design / proposal / spec(走 drift_decision: written-back-to-* 协议)
- [ ] 11.3 调 `/forgeue:change-doc-sync` 二次确认(代码改动后 10 文档实际改了什么,对齐 §10 prediction)
- [ ] 11.4 调 `/forgeue:change-finish`(Finish Gate 中心化最后防线:12-key frontmatter 全检 / writeback 真实性 / cross-check disputed_open == 0 / openspec validate --strict)
- [ ] 11.5 调 `openspec archive comfy-agent-cli-adoption` 归档,sync delta specs 到 `openspec/specs/<capability>/spec.md`(provider-routing + artifact-contract + examples-and-acceptance + probe-and-validation + runtime-core 五个 capability);archive 后**手动**改主 spec `provider-routing/spec.md` line 25 (Current Behavior) 把"ComfyUI HTTP"→"ComfyUI agent CLI subprocess (`ComfyAgentWorker`)"(OpenSpec MODIFIED 机制不能直接 modify Current Behavior 段);line 211 Invariants + line 229 Non-Goals **保留不动**(D6 选 A 后契约一致)
