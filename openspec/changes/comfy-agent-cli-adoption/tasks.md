## 1. 准备工作与前置确认

- [ ] 1.1 确认 D:/AI/ComfyUI/scripts/ 在本机存在,`python -m comfyui_api status` 调通(印证 OQ-1 的 `sys.executable` 选择能跑通 ComfyUI deps);记录实测结果
- [x] 1.2 OQ + Decision 全部 resolved:OQ-1=`sys.executable`、OQ-2=non-empty `outputs.audio` / `outputs.glb` raise `WorkerUnsupportedResponse`、OQ-3=`--project` 传 `task.project_id`、**OQ-4 (Decision A) = lifecycle 只支持 `none`**(用户自启 ComfyUI;TBD-010 后续 change 解锁 `ensure_running`)、**OQ-5 (Decision B) = `models:` 段加虚拟 model id `comfy/local` + 新 alias `image_local`**;详细论证见 design.md `## Resolved` 段 + D6 + D7 + D-FutureScope
- [ ] 1.3 起新分支或确认在 chore/openspec-superpowers 上继续(本 change 已挂 openspec/changes/comfy-agent-cli-adoption/)

## 2. ModelRegistry 与配置(commit 1)

- [ ] 2.1 在 `config/models.yaml` `providers:` 段加 `comfy_api` entry:`kind: subprocess_cli` / `scripts_dir: "D:/AI/ComfyUI/scripts"` / `python_exe: null` / `default_lifecycle: "none"`(写死 `none`,本 change 唯一支持;不接受 `ensure_running` / `ensure_release` / `self_managed_session`)
- [ ] 2.2 在 `config/models.yaml` `models:` 段加虚拟 model id `comfy/local` entry:`provider: comfy_api` / `kind: image` / `pricing: null`(本地 GPU,无 per-call cost,FR-COST-008/009 接口仍在,值 0.0)
- [ ] 2.3 在 `config/models.yaml` `aliases:` 段加 `image_local` alias:`preferred: ["comfy/local"]` / `fallback: []`(不 fallback 到云端;策略上把本地 ComfyUI 当独立 capability)
- [ ] 2.4 在 `src/framework/config/models_yaml.py`(或对应 loader 位置) 接受 `subprocess_cli` kind,新增 ProviderEntry 字段;对未知子字段抛 `RegistryReferenceError`(对齐 pricing 段已建立的 typo-protection)
- [ ] 2.5 新增 `tests/unit/test_model_registry.py` 三 fence:`test_comfy_api_provider_subprocess_cli_kind_parses` / `test_comfy_api_unknown_subfield_raises` / `test_comfy_local_model_and_image_local_alias_resolve_via_registry`(后者守 alias `image_local` → loader 展开 → `[ResolvedRoute(model="comfy/local", kind="image", pricing=None, ...)]`)
- [ ] 2.6 commit 1:`feat(registry): accept subprocess_cli kind, register comfy_api provider + comfy/local model + image_local alias`

## 3. ComfyAgentWorker 实装(commit 2)

- [ ] 3.1 在 `src/framework/providers/workers/comfy_worker.py` 重命名 `HTTPComfyWorker` → `ComfyAgentWorker`,删除全部 HTTP 相关代码(requests / `/prompt` / `/history` / `/view`),保留 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` / `ImageCandidate` / `FakeComfyWorker`
- [ ] 3.2 实装 `ComfyAgentWorker.__init__(scripts_dir: Path, python_exe: Path | None = None, default_lifecycle: str = "none", run_id: str | None = None, project_id: str | None = None, artifacts_dir: Path | None = None)`;构造 cmd `[python_exe or sys.executable, "-m", "comfyui_api", "run", "--workflow", ..., "--params", ..., "--project", project_id, "--lifecycle", "none", "--timeout", str(timeout_s)]`;subprocess 用 `asyncio.create_subprocess_exec(..., cwd=scripts_dir, stdout=PIPE, stderr=PIPE)` + `await proc.communicate()`;**__init__ 内 assert `default_lifecycle == "none"`**(本 change 不接受其它值,TBD-010 解锁前守门)
- [ ] 3.3 `submit(spec, *, timeout_s)` 解析 stdout JSON,按 spec D5 表格映射 5 类失败:scripts_dir 缺失 / module not found → `WorkerUnsupportedResponse`;exit 2 + `Missing required` / `value out of range` / `value_not_in_list` / stdout 非 JSON / 缺 `outputs` → `WorkerUnsupportedResponse`;exit 2 + `TimeoutError` → `WorkerTimeout`;其它 exit 2 → `WorkerError`;**spec 内 `comfy_lifecycle` 非 `"none"` → raise `WorkerUnsupportedResponse`**(防 bundle 漏改);成功路径产出 `list[ImageCandidate]`(从 `outputs.images` 读 PNG bytes);**`outputs.glb` / `outputs.audio` non-empty → raise `WorkerUnsupportedResponse`**(D5 + D-RejectMeshAudio)
- [ ] 3.4 实装"copy 到项目树"逻辑:`outputs.images` 每条路径 `shutil.copy2` 到 `artifacts_dir / "comfy" / src.name`,`ImageCandidate` 的字节读自 copy 后路径(NFR-PORT-004 + A4)
- [ ] 3.5 实装 dry-run 探活 helper `ComfyAgentWorker.probe(scripts_dir: Path, python_exe: Path | None, timeout_s: float = 30.0) -> None`,跑 `python -m comfyui_api status` (timeout 30s,与 design Risk A 冷启动 30-90s 假设对齐);exit 0 = OK;其它 / timeout → raise `WorkerUnsupportedResponse(... "请先 `python -m comfyui_api serve` 启动 ComfyUI")`
- [ ] 3.6 commit 2:`feat(comfy): replace HTTPComfyWorker with ComfyAgentWorker (subprocess CLI, lifecycle=none only)`

## 4. Executor 与 spec 协议(commit 3)

- [ ] 4.1 在 `src/framework/runtime/executors/generate_image.py` 的 `_resolve_spec` 读取 `comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段;旧字段 `workflow_graph` 命中时 raise `WorkerUnsupportedResponse`(防漏改 bundle 静默走错路径);`comfy_lifecycle` 非 `"none"` 时也 raise(spec MODIFIED Requirement"Bundle requesting a non-none comfy_lifecycle is rejected")
- [ ] 4.2 在 executor 构造 `ComfyAgentWorker` 时传完整参数:`run_id=ctx.run.run_id` + `project_id=ctx.task.project_id` + `artifacts_dir=ctx.run.artifact_dir`(具体属性名实测确认)
- [ ] 4.3 dry-run 钩子:`DryRunPass` 在发现**已解析的 `prepared_routes` 含 provider=`comfy_api` 的 route**时(不是简单"step 引用 image.generation"),调 `ComfyAgentWorker.probe(...)` 探活,失败 fail Run;bundle 走 qwen / glm 等其它 image provider 时 dry-run 跳过 ComfyUI 探活
- [ ] 4.4 capability_router 新增 `subprocess_cli` 分支:`prepared_route.kind == "image"` AND `provider.kind == "subprocess_cli"` 时 dispatch 到 `ComfyAgentWorker`;注册顺序在 `LiteLLMAdapter` wildcard 之前
- [ ] 4.5 commit 3:`feat(executor+router): bundle uses comfy_workflow + comfy_params, dispatch comfy_api via subprocess_cli kind`

## 5. FakeComfyWorker schema 守门(commit 4)

- [ ] 5.1 `FakeComfyWorker.submit(spec, *, timeout_s)` 在 dequeue 之前校验 `spec` 含 `comfy_workflow`(string) + `comfy_params`(dict),缺字段 raise `WorkerUnsupportedResponse`;若 `comfy_lifecycle` 非 `"none"` 也 raise(对齐真 worker 行为)
- [ ] 5.2 更新 `FakeComfyWorker` docstring,写明"fake 不真跑 manifest,scripted 队列驱动;校验只为新 contract schema 守门,不消费 workflow 名"
- [ ] 5.3 现有依赖 FakeComfyWorker 的测试(test_p3 / a2_image bundle / examples_smoke / 其它 unit)若有调用 `program(...)` + `submit({...})` 但 spec dict 缺新字段,补上最小骨架(只为通过 schema 校验,不影响 dequeue 行为);用 grep 找全所有 call site 后批量补
- [ ] 5.4 commit 4:`feat(comfy): FakeComfyWorker enforces new spec schema (comfy_workflow + comfy_params + lifecycle=none)`

## 6. 单元测试改造(commit 5)

- [ ] 6.1 新增 `tests/unit/test_comfy_subprocess.py`,实装 spec `probe-and-validation/spec.md` 列出的全部 fence(name 列表见该 spec)。重点 fence:`test_missing_scripts_dir_raises_unsupported_response` / `test_python_module_not_found_raises_unsupported_response` / `test_exit2_missing_param_maps_to_unsupported` / `test_exit2_value_out_of_range_maps_to_unsupported` / `test_exit2_value_not_in_list_maps_to_unsupported` / `test_stdout_not_json_maps_to_unsupported` / `test_stdout_missing_outputs_field_maps_to_unsupported` / `test_exit2_timeout_maps_to_worker_timeout` / `test_exit2_unrecognised_error_maps_to_worker_error` / `test_subprocess_invocation_passes_workflow_params_lifecycle_timeout` / `test_subprocess_invocation_passes_task_project_id_as_dash_dash_project` / `test_outputs_paths_are_copied_into_run_artifact_tree` / `test_outputs_glb_non_empty_raises_unsupported_response` / `test_outputs_audio_non_empty_raises_unsupported_response` / `test_lifecycle_other_than_none_raises_unsupported_response` / `test_cancel_under_to_thread_does_not_orphan_processes`(best-effort scenario,断言 lifecycle=none 下 subprocess 自然退出无残留) / `test_dry_run_skips_probe_when_no_comfy_api_in_routes` / `test_dry_run_30s_timeout`
- [ ] 6.2 fence 用 `monkeypatch.setattr(asyncio, "create_subprocess_exec", ...)`(或 worker 内部抽个 subprocess facade 方便注入)mock subprocess 边界;不引 `requests` / `httpx`
- [ ] 6.3 删除 `tests/unit/test_comfy_http_unsupported.py`(HTTP 协议已不存在)
- [ ] 6.4 跑 `python -m pytest tests/unit/test_comfy_subprocess.py -v` 全绿
- [ ] 6.5 跑 `python -m pytest -q` 全量,**实测记录绝对总数**(不硬编码增量算式,对齐 NFR-MAINT-003 + CLAUDE.md "不硬编码测试总数;以 `python -m pytest -q` 实测为准");per-file fence 增量 = `test_comfy_subprocess.py` ~18 + `test_model_registry.py` 3 - `test_comfy_http_unsupported.py` 删除前 fence 数;实测总数与本 change 落盘前 acceptance §8.1 v1.5 基线 1144 对比,记到 §10.1 verify evidence
- [ ] 6.6 commit 5:`test(comfy): subprocess contract fences replace http unsupported fence`

## 7. examples 重写(commit 6)

- [ ] 7.1 重写 `examples/comfy_local_smoke.json`:删除 `spec.workflow_graph`,加 `spec.comfy_workflow: "GameAssets/01b_singleview_sdxl"` + `spec.comfy_params: {"text": "single oak barrel isolated white background", "seed": 7777, "width": 512, "height": 512}` + `spec.comfy_lifecycle: "none"`;**`provider_policy.models_ref: "image_local"`**(走新 alias);bundle 在 5 KB 以内
- [ ] 7.2 删除 `examples/comfy/build_bundle.py`、`examples/comfy/tavern_door.api.json`、`examples/comfy/image_z_image_turbo.json`(v1 inline-workflow helper 与原始 workflow JSON 副本);若 `examples/comfy/` 目录空了一并删
- [ ] 7.3 跑 `tests/integration/test_example_bundles_smoke.py` 全绿(自动 parametrize 收新 bundle)
- [ ] 7.4 commit 6:`examples(comfy): switch local smoke to manifest workflow + image_local alias`

## 8. 本机 live smoke 验收(可选但建议)

- [ ] 8.1 启 ComfyUI:`python -m comfyui_api serve`(自启)或确认已 online (`python -m comfyui_api status` 返 OK)
- [ ] 8.2 跑 `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id comfy_smoke_<date>`
- [ ] 8.3 验证产物落 `artifacts/<today>/comfy_smoke_<date>/comfy/<filename>.png`(in-tree);原始 ComfyUI 输出 `D:/AI/ComfyUI/outputs/main/<today>/<task.project_id>/...` 也存在(留作人工对照,不影响 ForgeUE artifact tree 自包含性)
- [ ] 8.4 lifecycle=none 模式:确认 ForgeUE 没有启动 / 关闭 ComfyUI 进程(全程由用户在终端 1 自管;ForgeUE 在终端 2 跑只调 subprocess)
- [ ] 8.5 把 live smoke 结果(命令、产物路径、duration_s、绝对 pytest 总数)记录到本 change 的 `notes/live_smoke_<date>.md`

## 9. 文档同步(commit 7,Documentation Sync Gate 强制)

- [ ] 9.1 调 `/forgeue:change-doc-sync` 跑静态扫描,获取 10 文档 [REQUIRED] / [OPTIONAL] / [SKIP] 清单
- [ ] 9.2 更新 `docs/requirements/SRS.md` §5.3 表格 ComfyUI 行(协议 HTTP → subprocess CLI,适配层 `comfy_worker.py` 类名 ComfyAgentWorker;新增"lifecycle: none only"列;新增"`comfy/local` virtual model id + `image_local` alias")+ FR-WORKER-001 描述 + 7.2 变更记录加 v1.X 行
- [ ] 9.3 更新 `docs/design/HLD.md` ComfyUI 子系统描述(协议层 subprocess CLI + lifecycle=none 范围 + project_id 分组 + virtual model id)
- [ ] 9.4 更新 `docs/design/LLD.md` ComfyUI worker 详细字段(类名 ComfyAgentWorker、构造参数完整签名、subprocess 调用 + 失败模式映射表 + cancel best-effort 语义)
- [ ] 9.5 更新 `docs/testing/test_spec.md` 索引,加 `test_comfy_subprocess.py` ~18 条 fence 描述,删 `test_comfy_http_unsupported` 行
- [ ] 9.6 更新 `docs/acceptance/acceptance_report.md`:(a) FR-WORKER-001 验收行(指向 `comfy_worker.py` ComfyAgentWorker + `test_comfy_subprocess.py`);(b) §8.1 自动化验收基线行(v1.5 = 1144 → v1.6 = **实测**,**不硬编码**预期增量);(c) 加 v1.6 变更记录行;v1.6 描述指向 OpenSpec change `comfy-agent-cli-adoption` + commit 列表
- [ ] 9.7 更新 `CHANGELOG.md` 加 `comfy-agent-cli-adoption` 条目(BREAKING:bundle workflow_graph 字段废止、lifecycle 仅 `none`;CLI 替代 HTTP;输出 copy 到项目树;新虚拟 model id `comfy/local` + alias `image_local`;参考本 change tasks.md)
- [ ] 9.8 更新 `CLAUDE.md` 提示用户本机 live smoke 前置条件:必须先启 ComfyUI(`python -m comfyui_api serve` 或自启 + `status` 验证);double-terminal 工作流;TBD-010 解锁 `ensure_running` 后此前置可删
- [ ] 9.9 `AGENTS.md` 视情况同步(若有 ComfyUI 段)
- [ ] 9.10 在 `docs/requirements/SRS.md` §7.3 未决事项表追加 `TBD-009: ComfyUI agent CLI mesh / audio / video workflow 接入(目标决议日期 = 本 change 归档后再评估)`,描述指向本 change `design.md` Resolved OQ-2 + Non-Goals 段记录的范围划线理由(三层架构 / mesh metadata 门槛 / 已有 Hunyuan tokenhub 路径)
- [ ] 9.11 在 `docs/requirements/SRS.md` §7.3 未决事项表追加 `TBD-010: GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径(orchestrator 直接 await worker.submit 不经 to_thread),取消并发 cancel 完全语义;ComfyUI lifecycle 借此扩展到 ensure_running + 主 spec provider-routing 的 lifecycle 相关 Invariant + Non-Goal 一并 MODIFIED(目标决议日期 = 用户实际使用本 change 后反馈双终端 UX 痛苦阈值或框架其它 long-task cancel use case 推动)`,描述指向本 change `design.md` D6 + D-FutureScope 段记录的 5 步 follow-on plan
- [ ] 9.12 commit 7:`docs: sync ComfyUI agent CLI adoption (CLI/lifecycle=none/virtual model id) across SRS/HLD/LLD/test/acceptance/CHANGELOG/CLAUDE`

## 10. Verify + Review + Finish

- [ ] 10.1 调 `/forgeue:change-verify`,完成 Level 0 / 1 / 2 验证(L0=`pytest -q` 实测绝对总数 + 与 v1.5 基线 1144 对比;L1=`tests/unit/test_comfy_subprocess.py`;L2=本机 live smoke 已在 §8 跑过则贴 evidence,未跑则记 SKIP + reason)
- [ ] 10.2 调 `/forgeue:change-review`(Superpowers requesting-code-review finalize + codex /codex:adversarial-review mixed scope);blocker 必须回写到 design / proposal / spec(走 drift_decision: written-back-to-* 协议)
- [ ] 10.3 调 `/forgeue:change-doc-sync` 二次确认(代码改动后 10 文档实际改了什么,对齐 §9 prediction)
- [ ] 10.4 调 `/forgeue:change-finish`(Finish Gate 中心化最后防线:12-key frontmatter 全检 / writeback 真实性 / cross-check disputed_open == 0 / openspec validate --strict)
- [ ] 10.5 调 `openspec archive comfy-agent-cli-adoption` 归档,sync delta specs 到 `openspec/specs/<capability>/spec.md`;archive 后**手动**改主 spec `provider-routing/spec.md` line 25 (Current Behavior) 把"ComfyUI HTTP"→"ComfyUI agent CLI subprocess (`ComfyAgentWorker`)"(OpenSpec MODIFIED 机制不能直接 modify Current Behavior 段);line 211 Invariants + line 229 Non-Goals **保留不动**(D6 选 A 后契约一致)
