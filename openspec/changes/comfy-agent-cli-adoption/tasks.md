## 1. 准备工作与前置确认

- [ ] 1.1 确认 D:/AI/ComfyUI/scripts/ 在本机存在,`python -m comfyui_api status` 调通(印证 OQ-1 的 `sys.executable` 选择能跑通 ComfyUI deps);记录实测结果
- [x] 1.2 OQ 决策已落:OQ-1=`sys.executable`、OQ-2=non-empty `outputs.audio` / `outputs.glb` raise `WorkerUnsupportedResponse`、OQ-3=`--project` 传 `task.project_id`,见 design.md `## Resolved` 段
- [ ] 1.3 起新分支或确认在 chore/openspec-superpowers 上继续(本 change 已挂 openspec/changes/comfy-agent-cli-adoption/)

## 2. ModelRegistry 与配置(commit 1)

- [ ] 2.1 在 `config/models.yaml` `providers:` 段加 `comfy_api` entry(字段:`kind: subprocess_cli` / `scripts_dir` / `python_exe` / `default_lifecycle`)
- [ ] 2.2 在 `src/framework/config/models_yaml.py`(或对应 loader 位置) 接受 `subprocess_cli` kind,新增 ProviderEntry 字段;对未知子字段抛 `RegistryReferenceError`(对齐 pricing 段已建立的 typo-protection)
- [ ] 2.3 新增 `tests/unit/test_model_registry.py::test_comfy_api_provider_subprocess_cli_kind_parses` 与 `::test_comfy_api_unknown_subfield_raises` 守门
- [ ] 2.4 commit 1:`feat(registry): accept subprocess_cli kind for comfy_api provider`

## 3. ComfyAgentWorker 实装(commit 2)

- [ ] 3.1 在 `src/framework/providers/workers/comfy_worker.py` 重命名 `HTTPComfyWorker` → `ComfyAgentWorker`,删除全部 HTTP 相关代码(requests / `/prompt` / `/history` / `/view`),保留 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` / `ImageCandidate` / `FakeComfyWorker`
- [ ] 3.2 实装 `ComfyAgentWorker.__init__(scripts_dir, python_exe, default_lifecycle, run_id, artifacts_dir)`;构造 cmd `[python_exe or sys.executable, "-m", "comfyui_api", "run", ...]`;subprocess 用 `cwd=scripts_dir, capture_output=True, text=True, timeout=...`;asyncio 调度用 `asyncio.create_subprocess_exec` 以便 cancel 时 `terminate()`
- [ ] 3.3 `submit(spec, *, timeout_s)` 解析 stdout JSON,按 design D5 表格映射 5 类失败 + cancel 路径;每一分支 raise 对应异常类型;成功路径产出 `list[ImageCandidate]`(从 outputs.images 读 PNG bytes)
- [ ] 3.4 实装"copy 到项目树"逻辑:`outputs.images` 每条路径 `shutil.copy2` 到 `artifacts_dir / "comfy" / src.name`,`ImageCandidate` 的字节读自 copy 后路径
- [ ] 3.5 实装 dry-run 探活 helper `ComfyAgentWorker.probe(scripts_dir, python_exe, timeout_s=10)`,跑 `python -m comfyui_api status`,exit 0 = OK,其它 = raise `WorkerUnsupportedResponse`
- [ ] 3.6 commit 2:`feat(comfy): replace HTTPComfyWorker with ComfyAgentWorker (subprocess CLI)`

## 4. Executor 与 spec 协议(commit 3)

- [ ] 4.1 在 `src/framework/runtime/executors/generate_image.py` 的 `_resolve_spec` 读取 `comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段;旧字段 `workflow_graph` 命中时 raise `WorkerUnsupportedResponse`(防漏改 bundle 静默走错路径)
- [ ] 4.2 在 executor 构造 `ComfyAgentWorker` 时传 `run_id=ctx.run.run_id` + `artifacts_dir=ctx.run.artifact_dir`(具体属性名实测确认)
- [ ] 4.3 dry-run 钩子:`DryRunPass` 在发现 step 引用 `image.generation` capability 且解析到 `comfy_api` provider 时,调 `ComfyAgentWorker.probe(...)` 探活,失败 fail Run
- [ ] 4.4 commit 3:`feat(executor): bundle uses comfy_workflow + comfy_params, reject legacy workflow_graph`

## 5. FakeComfyWorker schema 守门(commit 4)

- [ ] 5.1 `FakeComfyWorker.submit(spec, *, timeout_s)` 在 dequeue 之前校验 `spec` 含 `comfy_workflow`(string) + `comfy_params`(dict),缺字段 raise `WorkerUnsupportedResponse`
- [ ] 5.2 更新 `FakeComfyWorker` docstring,写明"fake 不真跑 manifest,scripted 队列驱动;校验只为新 contract schema 守门,不消费 workflow 名"
- [ ] 5.3 现有依赖 FakeComfyWorker 的测试(test_p3 / a2_image bundle / examples_smoke / 其它 unit)若有调用 `program(...)` + `submit({...})` 但 spec dict 缺新字段,补上最小骨架(只为通过 schema 校验,不影响 dequeue 行为);用 grep 找全所有 call site 后批量补
- [ ] 5.4 commit 4:`feat(comfy): FakeComfyWorker enforces new spec schema`

## 6. 单元测试改造(commit 5)

- [ ] 6.1 新增 `tests/unit/test_comfy_subprocess.py`,实装 spec 列出的 15 条 fence(missing scripts_dir / module not found / 4 类 exit 2 error / stdout 非 JSON / 缺 outputs / TimeoutError / 未识别错误 / cancel 终止 subprocess / 调用参数(workflow+params+lifecycle+timeout 与 task.project_id) / outputs 路径被 copy 进 artifact tree / non-empty outputs.glb raise / non-empty outputs.audio raise)
- [ ] 6.2 fence 用 `monkeypatch.setattr(asyncio, "create_subprocess_exec", ...)`(或 worker 内部抽个 subprocess facade 方便注入)mock subprocess 边界;不引 `requests` / `httpx`
- [ ] 6.3 删除 `tests/unit/test_comfy_http_unsupported.py`(HTTP 协议已不存在)
- [ ] 6.4 跑 `python -m pytest tests/unit/test_comfy_subprocess.py -v` 全绿
- [ ] 6.5 跑 `python -m pytest -q` 全量,确认 549 + 12 新 fence - 1 删除 fence 用例数对得上(实测以 pytest 输出为准,不硬编码总数,对齐 NFR-MAINT-003)
- [ ] 6.6 commit 5:`test(comfy): subprocess contract fences replace http unsupported fence`

## 7. examples 重写(commit 6)

- [ ] 7.1 重写 `examples/comfy_local_smoke.json`:删除 `spec.workflow_graph`,加 `spec.comfy_workflow: "GameAssets/01b_singleview_sdxl"` + `spec.comfy_params: {"text": "...", "seed": 7777, "width": 512, "height": 512}` + `spec.comfy_lifecycle: "ensure_running"`;`provider_policy.models_ref` 走对应 capability alias;bundle 在 5 KB 以内
- [ ] 7.2 删除 `examples/comfy/build_bundle.py`、`examples/comfy/tavern_door.api.json`、`examples/comfy/image_z_image_turbo.json`(v1 inline-workflow helper 与原始 workflow JSON 副本);若 `examples/comfy/` 目录空了一并删
- [ ] 7.3 跑 `tests/integration/test_example_bundles_smoke.py` 全绿(自动 parametrize 收新 bundle)
- [ ] 7.4 commit 6:`examples(comfy): switch local smoke to manifest workflow + params`

## 8. 本机 live smoke 验收(可选但建议)

- [ ] 8.1 启 ComfyUI(自启 / `python -m comfyui_api status` 确认 online)
- [ ] 8.2 跑 `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id comfy_smoke_<date>`
- [ ] 8.3 验证产物落 `artifacts/<today>/comfy_smoke_<date>/comfy/<filename>.png`(in-tree),原始 ComfyUI 输出 `D:/AI/ComfyUI/outputs/main/<today>/comfy_smoke_<date>/...` 也存在(留作人工对照,不影响 ForgeUE artifact tree 自包含性)
- [ ] 8.4 lifecycle=ensure_running 模式下 ComfyUI 进程不被 ForgeUE 误杀(用户手动启的实例保留)
- [ ] 8.5 把 live smoke 结果(命令、产物路径、duration_s)记录到本 change 的 `notes/live_smoke_<date>.md`

## 9. 文档同步(commit 7,Documentation Sync Gate 强制)

- [ ] 9.1 调 `/forgeue:change-doc-sync` 跑静态扫描,获取 10 文档 [REQUIRED] / [OPTIONAL] / [SKIP] 清单
- [ ] 9.2 更新 `docs/requirements/SRS.md` §5.3 表格 ComfyUI 行(协议 HTTP → subprocess CLI,适配层 `comfy_worker.py` 类名 ComfyAgentWorker)+ FR-WORKER-001 描述 + 7.2 变更记录加 v1.X 行
- [ ] 9.3 更新 `docs/design/HLD.md` ComfyUI 子系统描述(协议层 + lifecycle + project 分组)
- [ ] 9.4 更新 `docs/design/LLD.md` ComfyUI worker 详细字段(类名、构造参数、subprocess 调用 + 失败模式映射表)
- [ ] 9.5 更新 `docs/testing/test_spec.md` 索引,加 12 条 `test_comfy_subprocess` fence 描述,删 `test_comfy_http_unsupported` 行
- [ ] 9.6 更新 `docs/acceptance/acceptance_report.md` FR-WORKER-001 验收行(指向 `comfy_worker.py` ComfyAgentWorker + `test_comfy_subprocess.py`)+ 加 v1.X 变更行
- [ ] 9.7 更新 `CHANGELOG.md` 加 `comfy-agent-cli-adoption` 条目(BREAKING:bundle workflow_graph 字段废止;CLI 替代 HTTP;输出 copy 到项目树;参考本 change tasks.md)
- [ ] 9.8 更新 `CLAUDE.md` 提示用户本机 live smoke 前置条件(ComfyUI 安装路径 + agent CLI doctor)
- [ ] 9.9 `AGENTS.md` 视情况同步(若有 ComfyUI 段)
- [ ] 9.10 在 `docs/requirements/SRS.md` §7.3 未决事项表追加 `TBD-009: ComfyUI agent CLI mesh / audio / video workflow 接入(目标决议日期 = 本 change 归档后再评估)`,描述指向本 change `design.md` Resolved OQ-2 + Non-Goals 段记录的范围划线理由(三层架构 / mesh metadata 门槛 / 已有 Hunyuan tokenhub 路径)
- [ ] 9.11 commit 7:`docs: sync ComfyUI agent CLI adoption across SRS/HLD/LLD/test/acceptance/CHANGELOG/CLAUDE`

## 10. Verify + Review + Finish

- [ ] 10.1 调 `/forgeue:change-verify`,完成 Level 0 / 1 / 2 验证(L0=`pytest -q`;L1=`tests/unit/test_comfy_subprocess.py`;L2=本机 live smoke 已在 §8 跑过则贴 evidence,未跑则记 SKIP + reason)
- [ ] 10.2 调 `/forgeue:change-review`(Superpowers requesting-code-review finalize + codex /codex:adversarial-review mixed scope);blocker 必须回写到 design / proposal / spec(走 drift_decision: written-back-to-* 协议)
- [ ] 10.3 调 `/forgeue:change-doc-sync` 二次确认(代码改动后 10 文档实际改了什么,对齐 §9 prediction)
- [ ] 10.4 调 `/forgeue:change-finish`(Finish Gate 中心化最后防线:12-key frontmatter 全检 / writeback 真实性 / cross-check disputed_open == 0 / openspec validate --strict)
- [ ] 10.5 调 `openspec archive comfy-agent-cli-adoption` 归档,sync delta specs 到 `openspec/specs/<capability>/spec.md`
