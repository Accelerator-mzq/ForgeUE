# ForgeUE 系统测试用例说明书 (System Test Specification)

| 字段 | 内容 |
| --- | --- |
| 文档编号 | FORGEUE-TEST-001 |
| 版本 | v1.0 |
| 基线日期 | 2026-04-22 |
| 文档性质 | 系统测试用例规格 |
| 上位文档 | `docs/requirements/SRS.md`、`docs/design/LLD.md` |
| 下位文档 | 源代码 `tests/` 与 `docs/acceptance/acceptance_report.md` |

---

## 1. 引言

### 1.1 编写目的

本文档规定 ForgeUE 的测试**策略、组织、用例矩阵、覆盖分析、测试环境与数据**,与 SRS 的 FR/NFR 需求条目一一追溯,为验收提供可执行的检查清单。

### 1.2 测试原则

| 原则 | 说明 |
| --- | --- |
| **测试即可执行规范** | pytest 用例本身是测试规范(2026-04-23 历史基线 549 用例,2026-04-25 加入 Run Comparison 后实测 848 用例,2026-04-27 加入 forgeue tooling fence + lazy artifact_store fence 后实测 1144 用例);本文档不重复描述每个用例的断言细节,只建立索引与矩阵 |
| **零 mock 关键边界** | download / EventBus / DAG / Budget / artifact 流端到端真实对象,不得 mock |
| **每次修复配一个 fence** | Codex / adversarial review 每条修复对应一个新回归测试 |
| **单元测试快** | `pytest -q` 全量目标 ≤ 60s(2026-04-23 历史基线 ≤15s @ 549 用例;2026-04-25 含 Run Comparison subprocess integration 后实测 ~28s @ 848 用例;2026-04-27 加入 forgeue tooling fence + lazy artifact_store subprocess fence 后实测 ~50s @ 1144 用例 —— subprocess fence 数量增加导致总时长增长,仍在 60s 软目标内) |
| **集成测试表意清晰** | 每个 P0–P4 集成测试一个闭环场景,命名与 SRS 章节对齐 |
| **fence 测试守门** | 反 fabrication / 反 regression / 反语法回退 |

### 1.3 术语

| 术语 | 说明 |
| --- | --- |
| 单元测试 | `tests/unit/*.py`,单模块行为 |
| 集成测试 | `tests/integration/*.py`,端到端场景 |
| fence 测试 | 守门类测试,检测特定修复不得再次退化 |
| fixture | 测试固定数据,含 HTML / bundle / stub 模块 |
| smoke 测试 | 冒烟测试,快速检查主干可用性 |
| stub | 假对象,替代真实依赖(如 UE `unreal` 模块) |

---

## 2. 测试策略

### 2.1 测试金字塔

```
           ┌─────────────────────────┐
           │ 手工验收(A1 UE 真机)   │   ← 验收文档管辖
           ├─────────────────────────┤
           │ Live LLM smoke(A2)     │   ← 可选,需 API key
           ├─────────────────────────┤
           │ 集成测试(详见 §2.2 表)│   ← P0-P4 + 场景级 + Run Comparison
           ├─────────────────────────┤
           │ 单元测试(详见 §2.2 表)│   ← 主体(含 Run Comparison)
           └─────────────────────────┘
```

### 2.2 测试分类

| 类别 | 目录 | 文件数 | 用例数 | 运行时间 |
| --- | --- | --- | --- | --- |
| 单元测试 | `tests/unit/` | 多个(以 `ls tests/unit/` 实查) | 以 `pytest -q tests/unit/` 实测为准 | < 15s |
| 集成测试 | `tests/integration/` | 多个(以 `ls tests/integration/` 实查) | 以 `pytest -q tests/integration/` 实测为准 | < 13s |
| **合计**(2026-04-27 实测) | — | — | **1144** | **~50s** |
| 中间基线(2026-04-25) | — | — | 848 | ~28s |
| 历史基线(2026-04-23) | — | 56 | 549 | ~18s |

### 2.3 执行方式

```bash
# 全量
python -m pytest -q

# 阶段集成
python -m pytest tests/integration/test_p{0,1,2,3,4}_*.py -v

# 指定模块单测
python -m pytest tests/unit/test_event_bus.py -v

# 手工产物落盘(不回收 tmp_path)
python -m pytest <test> --basetemp=./demo_artifacts/<name>

# CLI 离线冒烟(无需 API key)
python -m framework.run --task examples/mock_linear.json \
    --run-id demo --artifact-root ./artifacts

# CLI live smoke(需 .env 配置 provider key)
python -m framework.run --task examples/image_pipeline.json --live-llm ...
```

### 2.4 测试级别定义

| Level | 含义 |
| --- | --- |
| L0 smoke | 启动能跑,基础流程不抛异常 |
| L1 feature | 单功能正确性 |
| L2 edge | 边界 / 异常 / 错误处理 |
| L3 regression fence | 守门已修复问题不复发 |
| L4 integration | 多模块串联端到端 |

---

## 3. 单元测试用例矩阵

### 3.1 核心对象与 Schema

| 文件 | 覆盖模块 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_core_schemas.py` | `core/*.py` Pydantic 对象 | FR-STORE-*, FR-REVIEW-* | L1 | Task/Run/Artifact/Verdict 字段校验 |
| `test_model_registry.py` | `providers/model_registry.py` | FR-MODEL-001 | L1,L2 | 三段式解析、alias resolve、未知字段 raise |
| `test_registry_pricing.py` | `providers/model_registry.py` pricing 扩展 | FR-COST-001, FR-COST-002 | L1,L2 | `pricing:` block 解析、`pricing_autogen` 审计块、typo raise |
| `test_payload_backends.py` | `artifact_store/payload_backends/*` | FR-STORE-002, FR-STORE-003 | L1 | inline 64KB 上限、file 落盘、BlobBackend MVP(value/source_path/write/read/exists/guard) |
| `test_artifact_repository.py` | `artifact_store/repository.py` | FR-STORE-001, FR-STORE-002, FR-LC-009 | L1 | put / get / by_run / by_lineage + blob resume / blob drift skip / repo.put blob source_path / FOR-14 `_artifacts.integrity.json` metadata integrity fail-fast |
| `test_checkpoint_store.py` | `runtime/checkpoint_store.py` | FR-LC-004, FR-LC-005 | L1,L2 | save/load/hash verify on resume |

### 3.2 Runtime

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_scheduler_risk_ordering.py` | `runtime/scheduler.py` | FR-WF-005 | L1 | 同层按 risk_level 升序 |
| `test_dry_run_pass.py` | `runtime/dry_run_pass.py` | FR-LC-002, FR-LC-003 | L1,L2 | manifest / schema / provider / secrets 预检 |
| `test_cascade_cancel.py` | `runtime/orchestrator.py` | FR-WF-007, NFR-REL-006 | L3 | DAG retry/terminate 级联语义,`test_dag_retry_same_step_reexecutes` 守门 plan_v1 §M 第一轮修复 |
| `test_failure_mode_map.py` | `runtime/failure_mode_map.py` | FR-RUNTIME-007, FR-WORKER-011, FR-WORKER-012, NFR-REL-001 | L1,L2 | 13 类 FailureMode 分类(audio_worker_timeout / audio_worker_unsupported 自 v1.7;video_worker_timeout / video_worker_unsupported 自 v1.8)、unsupported / mesh / audio / video 子类 isinstance 优先级(D14:video 先于 audio / mesh / generic) |
| `test_transition_engine.py` | `runtime/transition_engine.py` | FR-REVIEW-003 | L1,L2 | 9 Decision 分支、revise / retry caps、abort_or_fallback honour on_fallback |
| `test_budget_tracker.py` | `runtime/budget_tracker.py` | FR-RUNTIME-001 | L1,L2 | 累计、超 cap 终止 |
| `test_budget_tracker_pricing.py` | 同上 + pricing | FR-COST-003, FR-COST-004 | L1 | 三 estimator、route_pricing 优先级 |
| `test_retry_async.py` | `providers/_retry_async.py` | FR-RUNTIME-005 | L1 | 瞬态重试成功/失败路径 |
| `test_transient_retry.py` | `providers/_retry.py` | FR-RUNTIME-005 | L1 | sync 同上 |
| `test_cancellation.py` | async 取消 | FR-RUNTIME-004, NFR-REL-006 | L2 | poll CancelledError 透传、超时 |

### 3.3 Providers

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_providers.py` | 基础注册 + 路由 | FR-MODEL-006 | L1 | wildcard 最后注册、alias 展开 |
| `test_providers_async.py` | async 四方法 | FR-MODEL-001 | L1 | acompletion / astructured / aimage / aimage_edit 契约 |
| `test_cn_image_adapters.py` | Qwen / Hunyuan Image | FR-MODEL-003, FR-WORKER-005 | L1,L2,L3 | 国内 image adapter 全路径、Range 续传、n>1 真并发 |
| `test_download_async.py` | `_download_async.py` | FR-WORKER-005, NFR-REL-* | L2,L3 | Range 强校验、200 fallback、Content-Range offset 不对齐清空重下 |
| `test_adapter_budget_clamp.py` | mesh / LiteLLM HTTP 下载 budget clamp(自 v1.6 删 ComfyUI HTTP 部分;ComfyAgentWorker subprocess.run timeout 守等价 invariant)| FR-WORKER-004, NFR-REL-* | L3 | mesh 90s clamp / LiteLLM 60s clamp |
| `test_comfy_subprocess.py` (自 v1.6;自 `executor-async-rewrite` 大幅扩充;FOR-13 delta) | ComfyAgentWorker 全 subprocess CLI contract | FR-WORKER-001(v1.6 修订), NFR-REL-005 | L1 | REQUIRED-args(project_id/artifacts_dir/lifecycle 3) + probe_sync(missing scripts_dir / module / 30s timeout / 非零 exit 4) + 7-class failure mapping(Missing param / out of range / not_in_list / non-JSON / missing outputs / TimeoutError / unrecognised 7) + argv shape(workflow+params+lifecycle+timeout / task.project_id 2)+ outputs handling(copy-to-tree / glb raise / audio raise / legacy workflow_graph rejected 4) + **async-subprocess**(asyncio.create_subprocess_exec + asyncio.wait_for 替代 subprocess.run 阻塞)+ **串行锁**(_comfy_submit_lock per-loop AsyncioLock 防并发提交乱序)+ **cancel server-side abort**(_abort_comfy_prompt /interrupt + proc.terminate 双保险)+ **sync shim**(generate_image/mesh/audio/video sync shim 经 asyncio 桥接)+ **aprobe** classmethod(async status probe + sync probe_sync 并存)+ lifecycle 集合外值 raise(4 合法值 ∪ 集合外 → WorkerUnsupportedResponse 替代原 !="none")+ FOR-13 image/mesh source_path 不全读 fence |
| `test_comfy_provider_config.py` (FOR-8 delta) | Comfy provider metadata + managed process selection | FR-WORKER-001, NFR-REL-005 | L1 | provider metadata route 判定 + spec/env/yaml lifecycle 优先级 + invalid lifecycle reject + default registry 构建 Comfy adapter + **FOR-8 multi-mode DAG lifecycle conflict fail-fast** |
| `test_cascade_cancel.py` (自 `executor-async-rewrite` TBD-010,2026-05-20) | cascade-cancel 真停 + drain timeout 明示失败 | NFR-REL-006, FR-RUNTIME-004 | L2 | cascade cancel siblings 后 join + drain;drain 超 `_CASCADE_DRAIN_TIMEOUT_S=30s` → 明示失败 not silently discard;CancelledError 直达 async executor 不被 to_thread 吞;DAG retry_same_step 在 async 路径仍可重进循环 |
| `test_comfy_lifecycle.py` (自 `executor-async-rewrite` TBD-010,2026-05-20) | ComfyLifecycleManager 三模式 + Orchestrator 集成 | FR-WORKER-001, NFR-REL-005 | L1,L2 | 三模式(`ensure_running` skip-stop / `ensure_release` stop / `self_managed_session` session-stop)+ 并发 ensure 单飞(两次并发 ensure_running 只启一个进程)+ 冷启动 cancel 不泄漏(ensure_running 未完成时 cancel → release 不遗留孤儿进程)+ `release(mode,reason)` 决策表(mode→action 映射 4 路径)+ `_release_lifecycle_bounded(timeout=30s)` 超时 warning 不 raise |
| `test_comfy_subprocess.py` **delta(async-subprocess 新增 fence,自 `executor-async-rewrite`)** | 见上行合并后描述 | — | — | 见上行 |
| `test_comfy_subprocess_audio.py` (自 v1.7;FOR-13 delta) | ComfyAgentWorker.generate_audio + _run_once_audio + 4-dict audio capability dispatch | FR-WORKER-001 / FR-WORKER-011 | L1 | capability guard(comfy/local-audio gate)+ outputs.audio missing → WorkerUnsupportedResponse + 扩展名 whitelist 拒(`flac`/`mp3`/`wav` only)+ magic bytes 二次校验(`fLaC` / `ID3` / MPEG sync / `RIFF`+`WAVE`)+ path trust-boundary(symlink / 非 file)+ AudioCandidate metadata 5 个 comfy_* 键 + per-candidate seed 偏移 + REJECTED keys(images/glb/video)互斥 + source_path 记录且不全读 payload |
| `test_generate_audio_comfy.py` (自 v1.7;FOR-13 delta) | GenerateAudioExecutor + _generate_via_comfy_worker + F2 retry/wrap + step persistence | FR-WORKER-011 | L1 | (StepType.generate, audio.t2a) registry lookup + _should_use_comfy_worker_path 判定 comfy/local-audio + F2 三-except 块(WorkerTimeout retry honoring _should_retry / WorkerUnsupportedResponse immediate raise / WorkerError immediate raise)+ ArtifactType(modality=audio, shape=waveform) + file_suffix=f".{cand.format}" + Artifact.metadata 三键(format/duration_seconds/sample_rate)+ worker_metadata 嵌套(F-Plan-R7-A single-source)+ source_path 优先落盘 |
| `test_audio_worker.py` (自 v1.7;FOR-13 delta) | AudioCandidate dataclass + AudioWorker ABC + 异常树 + FakeAudioWorker(6 fence)| FR-WORKER-011 | L1 | AudioCandidate 必填字段(data/format/metadata)+ optional source_path + format Literal whitelist + duration_seconds/sample_rate 默认 None + AudioWorkerError/Timeout/UnsupportedResponse 异常树 + FakeAudioWorker._build_minimal_flac 合成有效 FLAC bytes(`fLaC` magic + STREAMINFO) |
| `test_remote_audio_worker.py` (FOR-26) | RemoteHttpAudioWorker 通用 HTTP JSON 协议 | FR-WORKER-011 / FR-MODEL-007 | L1 | 5 用例(POST body/Authorization header/base64 payload/url download/format whitelist/magic bytes mismatch/http timeout→AudioWorkerTimeout) |
| `test_minimax_music_worker.py` (FOR-26 MiniMax follow-on) | MiniMaxMusicWorker 原生 music_generation 协议 | FR-WORKER-011 / FR-MODEL-007 | L1 | 4 用例(MiniMax 原生 payload + Bearer header + URL 下载且 metadata 去掉临时签名 query / hex 音频响应 / base_resp 非 0 → AudioWorkerUnsupportedResponse / HTTP timeout→AudioWorkerTimeout) |
| `test_run_remote_audio.py` (FOR-26) | `framework.run` env-based remote audio worker 注入 | FR-WORKER-011 | L1 | 3 用例(`FORGEUE_REMOTE_AUDIO_URL` 存在时注入 `RemoteHttpAudioWorker` 且优先于 MiniMax;仅 `MINIMAX_KEY` 存在时注入 `MiniMaxMusicWorker`;两者都未设置时保持 `_worker is None`,本地 ComfyUI 分支不受影响) |
| `test_video_worker.py` (自 v1.8;FOR-13 delta) | VideoCandidate dataclass + VideoWorker ABC + 异常树 + FakeVideoWorker(7 fence)| FR-WORKER-012 | L1 | VideoCandidate 必填字段(data/format/metadata)+ optional source_path + format Literal["mp4"] mp4-only round-2 F2 + round-3 PF3 sweep + duration_seconds/frame_count/width/height/fps 5 顶层 None defaults + VideoWorkerError/Timeout/UnsupportedResponse 异常树 + FakeVideoWorker._build_minimal_mp4 合成 32-byte BMFF strict 5-tuple-conformant ftyp box(`b"\x00\x00\x00\x20ftypisom..."`)|
| `test_step_context.py` (自 v1.6;`executor-async-rewrite` delta) | StepContext 字段 | FR-RUNTIME-* | L1 | default factory Path('.') / explicit value preserved 2 fence + **`lifecycle` 字段**(default None + ExternalProcessLifecycle 注入后可访问 2 fence) |
| `test_orchestrator.py` (自 v1.6;`executor-async-rewrite` delta;FOR-23 delta) | Orchestrator 集成 | FR-RUNTIME-*, NFR-OBS-002 | L1 | uses checkpoints._root NO extra date(round 3 H1 fix)/ falls back to Path('.') 2 fence + **lifecycle 注入**(arun 时 lifecycle manager 传入 / StepContext.lifecycle 字段填充)+ **try/finally release**(`arun` finally 分支调 `_release_lifecycle_bounded`)+ **`aclose()`**(disposal 钩子 release + cleanup)+ `step_failed` ProgressEvent 携带 `exception_type` / `failure_mode` / `decision` fence |
| `test_dry_run_pass.py` (自 `executor-async-rewrite` TBD-010,2026-05-20;FOR-22 delta) | DryRunPass.run async + aprobe + API key preflight | FR-LC-002, NFR-REL-005, NFR-SEC-004 | L1 | `DryRunPass.run` 为 `async def`(orchestrator `await dry_run_pass.run(...)` 路径)+ `aprobe` classmethod(asyncio.create_subprocess_exec + asyncio.wait_for;timeout → WorkerUnsupportedResponse)+ `probe_sync` shim 保留(sync 向后兼容;两个 classmethod 并存)+ dry-run async 集成(bundle 含 comfy/local* 时 dry-run 先 aprobe 再进主流程)+ 声明 `api_key_env` 的 provider route 缺 key 时阻断 Run |
| `test_fake_comfy_worker_schema.py` (自 v1.6) | FakeComfyWorker conditional v2 schema gate | FR-WORKER-001 | L1 | legacy passes / v2 missing comfy_params optional / non-string comfy_workflow / non-dict comfy_params / non-none lifecycle 5 fence |
| `test_model_registry.py` (delta 自 v1.6) | comfy_api placeholder + comfy_local virtual id + image_local alias | FR-MODEL-001/007 | L1 | comfy_api placeholder parses / comfy_local id missing raises / image_local alias resolves 3 fence |
| `test_tripo3d_unsupported.py` | Tripo3D 两处 unsupported | 同上 | L3 | /task 无 task_id / success 无 URL |
| `test_multi_candidate_parallel.py` | `parallel_candidates=True` | NFR-PERF-003 | L2 | asyncio.gather 真并发,墙钟验证 |
| `test_router_pricing_stash.py` | route_pricing 透传 | FR-COST-004 | L1 | `_route_pricing` 塞进 raw / usage |

### 3.4 Review Engine

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_chief_judge_parallel.py` | `chief_judge.py` panel | FR-REVIEW-007, NFR-PERF-002 | L2 | asyncio.gather 并发,墙钟 ≈ 最慢 judge |
| `test_review_budget.py` | ReviewExecutor cost 透传 | FR-REVIEW-008, FR-COST-* | L3 | usage 3-tuple 透传到 BudgetTracker |

### 3.5 Observability

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_event_bus.py` | `event_bus.py` | FR-OBS-001, FR-OBS-002 | L2,L3 | Subscription 捕获 owning loop、跨线程 hop 通过 call_soon_threadsafe、threading.Lock 保护 _subs |
| `test_progress_passthrough.py` + `test_orchestrator.py` | adapter / orchestrator → ProgressEvent | FR-OBS-002, NFR-OBS-004 | L2 | mesh/comfy poll 事件传递;Step 异常失败 emit `step_failed` 并携带异常类型 |
| `test_compactor.py` | `compactor.py` | FR-RUNTIME-003 | L1 | target_tokens 压缩、占位符插入 |
| `test_secrets.py` | `secrets.py` | NFR-SEC-002, NFR-SEC-003 | L1 | API key 脱敏 |

### 3.6 UE Bridge

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_ue_bridge.py` | `ue_bridge/*` | FR-UE-001 ~ FR-UE-008 | L1,L2 | ManifestBuilder modality 映射、PlanBuilder depends_on、Permission Phase C 默认拒绝、inspect_project / asset_exists、validate_manifest 重复路径、evidence 原子追加 |

### 3.7 Mesh / Generate

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_generate_mesh_cost.py` | `executors/generate_mesh.py` | FR-COST-003, FR-MODEL-003 | L1,L3 | mesh 从 prepared_routes 读 pricing,metrics["cost_usd"] 非 0 |

### 3.8 Pricing Probe

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_pricing_probe_framework.py` | 框架级 + scaffold fence | FR-COST-005 ~ FR-COST-007 | L1,L3 | CLI dry-run / --apply 语义、ruamel.yaml 保留注释、scaffold parser 仍 raise NotImplementedError |
| `test_pricing_parser_zhipu.py` | Zhipu parser | FR-COST-006 | L1 | GLM-4.6V 短 context tier 单价、GLM-Image 单张价 |
| `test_pricing_parser_hunyuan_3d.py` | Hunyuan 3D parser | FR-COST-006 | L1 | 15 积分 × ¥0.12/积分 = ¥1.80/次 ≈ USD 0.25 |
| `test_pricing_parser_hunyuan_image.py` | Hunyuan Image parser | FR-COST-006 | L1 | ¥0.5/张 postpaid tier |
| `test_pricing_parser_dashscope.py` | DashScope parser(6 模型) | FR-COST-006 | L1 | 精确匹配首列 + 按表头定位价格列、qwen-plus 128K tier |

### 3.9 Probe / Cleanup

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_probe_framework.py` | `probe_*.py` 的 lazy-init | NFR-MAINT-* | L3 | 无 API key 环境 import 不崩 |
| `test_pr3_cleanup_fences.py` | URL scheme 大小写 / magic gate / module-level I/O | — | L3 | PR-3 共性平移守门 |

### 3.10 Codex 21 条 audit fence(2026-04-22)

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_codex_audit_fixes.py` | 5 轮 review-fix 循环全部 fence(29 用例)| FR-LC-006~008, FR-WORKER-009~010, FR-COST-008~009, FR-RUNTIME-008~012, FR-REVIEW-009, NFR-REL-009 | L1,L2,L3 | 见下方 §5 fence 清单第三段 |

### 3.11 Run Comparison(2026-04-25,OpenSpec change `add-run-comparison-baseline-regression`)

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_run_comparison_models.py` | `RunComparisonInput` / `ArtifactDiff` / `VerdictDiff` / `MetricDiff` / `StepDiff` / `RunComparisonReport` 字段 + `model_dump_json` JSON roundtrip + `schema_version="1"` lock | — | L0 | 52 用例 |
| `test_run_comparison_loader.py` | `resolve_run_dir` 三分支 / `load_run_snapshot` 严格读 + payload byte hash recompute / 4 类异常(`RunDirNotFound` / `RunDirAmbiguous` / `RunSnapshotCorrupt` / `PayloadMissingOnDisk`)/ strict 与 non-strict 行为 / loader subprocess import-fence | — | L0 | 50 用例 |
| `test_run_comparison_diff_engine.py` | `compare()` 纯函数;artifact / verdict / metric 五层 diff taxonomy(unchanged / content_changed / metadata_only / missing / payload_missing_on_disk / decision_changed / confidence_changed / selected_candidates_changed)/ sparse `summary_counts` / lineage_delta / status_match / read-only over snapshot / diff_engine subprocess import-fence | — | L0 | 69 用例 |
| `test_run_comparison_reporter.py` | `render_json` / `render_markdown` 纯函数 + `write_reports` 唯一 I/O 边界(UTF-8 + LF)/ ASCII-only(`_ascii_safe` / `_line_safe` / `_escape_cell`)/ 固定文件名 `comparison_report.json` + `comparison_summary.md` / sparse `summary_counts` `.get(key, 0)` 守门 / reporter subprocess import-fence(直接 + lazy public export 两路)| — | L0 | 65 用例 |
| `test_run_comparison_cli.py` | argparse 11 flag → `RunComparisonInput` 映射 / exit code 0/2/3/1 / `--json-only` / `--markdown-only` 互斥 / `--quiet` stdout / `--no-hash-check` / `_safe_path_segment` / `_console_safe`(stdout/stderr ASCII-safe + 可见 `\\r` `\\n`)/ python -m subprocess / cli subprocess import-fence | — | L0 | 59 用例 |

### 3.11A Run Comparison Integration(2026-04-25)

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `tests/integration/test_run_comparison_cli.py` | 真实 subprocess `python -m framework.comparison` 端到端 / 静态 builder fixture happy path(JSON schema_version=="1" + Markdown ASCII + 三个 ArtifactDiffKind + run-level cost_usd metric diff + Markdown 关键 section 标题)/ `<repo>/demo_artifacts/` 不污染(递归快照 size + mtime_ns + cwd sibling)/ lineage_delta `transformation_kind` 端到端 round-trip / `examples/mock_linear.json` + FakeAdapter 双跑(无 `--live-llm` / 无 `--comfy-url`)/ source run dir 字节级 read-only(对应 runtime-core delta spec) | — | L0 | 4 用例 |
| `tests/fixtures/comparison/builders.py` | deterministic `build_fixture_pair(root)` / 合成日期 `2000-01-01` / 真实 Pydantic 类构造 / `hash_payload(bytes)` 真实计算 / 不依赖 `datetime.now` / `os.environ` / 网络 / provider | — | — | 公共构造 helper(被 integration test 调用)|

### 3.12 Lazy artifact_store package exports(2026-04-27,OpenSpec change `lazy-artifact-store-package-exports`)

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `tests/unit/test_artifact_store_lazy_imports.py` | PEP 562 `__getattr__` + `__dir__` lazy export 契约守门;`_run_clean_subprocess` helper 注 `PYTHONPATH=<repo>/src` env + assert `__file__` 落 working-tree(对应 S3 codex F2 finding writeback)| `openspec/specs/artifact-contract/spec.md` ADDED Requirement 4 Scenarios | L0 | **4 用例** |
|  | `test_import_artifact_store_does_not_pull_repository_or_payload_backends`(Scenario 1):subprocess `import framework.artifact_store` 后 `sys.modules` 仅含 `framework.artifact_store.hashing`,4 个 lazy submodule 不出现 | | | |
|  | `test_first_access_of_lazy_symbol_loads_submodule_and_caches`(Scenario 2):`mod.ArtifactRepository` 首次访问后 `repository in sys.modules` + 第二次访问 identity-equal(globals cache);intentional 不 assert cluster siblings absence(spec.md cluster-honest wording)| | | |
|  | `test_dir_returns_full_public_api_surface_before_any_lazy_access`(Scenario 4,S2 codex F3 `__dir__` 守门):lazy 未访问前 `dir(mod)` 含全 9 个 `__all__` 公共符号 | | | |
|  | `test_no_callsite_uses_submodule_path`(Scenario 3):repo 全扫 `(?:from|import)\s+framework\.artifact_store\.<lazy>` 形式(S6 codex F3 finding 加 import-form);`^[ \t]*` multiline anchor 防 docstring 假阳性;排除 4 类(`src/framework/artifact_store/**` 包内部 + `tests/unit/test_payload_backends.py` sub-package consumer + 本 change 目录 + bytecode)| | | |
| 收紧的既有 fence | `test_run_comparison_loader.py::TestLoaderImportFence` + `test_run_comparison_cli.py::TestCliImportFence` `_FORBIDDEN_FRAMEWORK_MODULES_*` 禁止清单从 9 prefix → 13 prefix(原 9 + `framework.artifact_store.{repository,payload_backends,lineage,variant_tracker}`);删 "transitive load is unavoidable" carve-out 段落;`comparison/cli.py` 顶 docstring 同步 trim | spec.md "Package import surface is lazy-load by default" Requirement | L0 | (no new test count;既有 fence 守紧) |

### 3.13 ComfyUI v1.7 audio capability(2026-05-03,OpenSpec change `comfy-agent-cli-audio-adoption`)

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `tests/unit/test_audio_worker.py` | AudioWorker ABC + AudioCandidate dataclass + 异常树 + FakeAudioWorker(`_build_minimal_flac` 合成有效 FLAC bytes,无第三方 codec 依赖)| FR-WORKER-011 | L0 | 6 用例(必填字段 / format Literal whitelist / duration_seconds default None / sample_rate default None / 异常 inheritance / FakeAudioWorker.generate_audio 返 list[AudioCandidate]) |
| `tests/unit/test_comfy_subprocess_audio.py` | ComfyAgentWorker.generate_audio + _run_once_audio + 4-dict audio capability(REQUIRED=audio key / REJECTED=images,glb,video / AUXILIARY=空) | FR-WORKER-001 / FR-WORKER-011 | L1 | 19 用例(capability 守门 / outputs.audio missing → unsupported / 扩展名 whitelist 拒 / magic bytes mismatch 拒 / symlink 拒 / per-candidate seed 偏移 / metadata.comfy_workflow / metadata.comfy_run_root / metadata.comfy_filename_prefix / metadata.comfy_original_filename / metadata.comfy_run_id 等 5 键) |
| `tests/unit/test_generate_audio_comfy.py` | GenerateAudioExecutor + ExecutorRegistry registration + F2 retry/wrap + persistence | FR-WORKER-011 | L1 | 14 用例((StepType.generate, audio.t2a) lookup / _should_use_comfy_worker_path 判 comfy/local-audio / F2 三-except 块(timeout retry honoring _should_retry / unsupported immediate raise / error immediate raise) / ArtifactType(modality=audio, shape=waveform) / file_suffix=f".{cand.format}" / metadata 三键 + worker_metadata 嵌套(F-Plan-R7-A single-source) / RetryPolicy.retry_on 控制 honor) |
| `tests/unit/test_failure_mode_map.py` (delta) | audio_worker_timeout / audio_worker_unsupported FailureMode + isinstance priority(audio 在 mesh / generic 之前) | FR-RUNTIME-007 / FR-WORKER-011 | L1 | +6 用例(AudioWorkerTimeout → audio_worker_timeout → abort_or_fallback / AudioWorkerUnsupportedResponse → audio_worker_unsupported → abort_or_fallback / AudioWorkerError → audio_worker_unsupported(generic 归类)/ 不命中 mesh / 不命中 generic worker_*) |
| `tests/unit/test_probe_framework.py` (delta) | probe_comfy_audio.py 顶层零副作用 + opt-in skip(`FORGEUE_PROBE_COMFY_AUDIO != "1"` 默认 skip) | FR-OBSERV-* | L0 | +2 用例(import 不触 hydrate_env / mkdir,opt-in skip 输出 SKIP marker) |
| `tests/unit/test_minimax_music_worker.py` | MiniMax music_generation 原生 worker | FR-WORKER-011 / FR-MODEL-007 | L1 | 4 用例(native POST payload + URL 下载且 metadata 去掉临时签名 query / hex response / provider error / timeout) |
| `tests/unit/test_model_registry.py` (delta) | comfy/local-audio virtual id + audio_local alias + remote/audio virtual id + audio_remote alias + minimax/music-2.6 virtual id + audio_minimax alias + image_local 仍解析(回归保护) | FR-MODEL-001/007 | L0 | audio_local 解析为 [comfy/local-audio];FOR-26 audio_remote 解析为 `ResolvedRoute(model="remote/audio", provider_kind="http", kind="audio", pricing=None)`;audio_minimax 解析为 `ResolvedRoute(model="minimax/music-2.6", provider_kind="http", api_key_env="MINIMAX_KEY")` |
| `examples/comfy_local_smoke_audio.json` | bundle JSON 三段式(task / workflow / steps)+ step.config.spec.{comfy_workflow, comfy_params, comfy_lifecycle: "none"} | FR-WORKER-011 / FR-EXAMPLES | L1 (offline) / L2 (live ComfyUI) | offline:tests/integration/test_example_bundles_smoke 收;live L2:本机跑(DEFERRED post-archive,见 change notes/live_smoke_audio_blocked_20260503.md) |
| `examples/remote_audio_smoke.json` (FOR-26) | 通用远端 audio smoke bundle(`audio.t2a` + `provider_policy.models_ref="audio_remote"`) | FR-WORKER-011 / FR-EXAMPLES | L1 offline | loader + DryRunPass 自动收;真实远端调用需用户提供 `FORGEUE_REMOTE_AUDIO_URL` / API key |
| `examples/minimax_music_smoke.json` (FOR-26 MiniMax follow-on) | MiniMax 原生 audio smoke bundle(`audio.t2a` + `provider_policy.models_ref="audio_minimax"`) | FR-WORKER-011 / FR-EXAMPLES | L1 offline | loader + DryRunPass 自动收;真实 MiniMax 调用需用户提供 `MINIMAX_KEY` |

---

## 4. 集成测试场景

### 4.1 P0–P4 主线闭环

| 文件 | RunMode | 对应需求 | 验证内容 |
| --- | --- | --- | --- |
| `test_p0_mock_linear.py` | basic_llm | FR-WF-001, FR-LC-* | 3 个 Checkpoint 落库,resume 命中 |
| `test_p1_structured_extraction.py` | basic_llm | FR-STRUCT-* | schema 合法 JSON,retry 次数 ≤ 2 |
| `test_p2_standalone_review.py` | standalone_review | FR-REVIEW-001, FR-REVIEW-002 | ReviewReport + Verdict 落库,scores_by_dimension 齐 |
| `test_p3_production_pipeline.py` | production | FR-WF-001, FR-WF-006 | prompt → review 收敛,max_revise 内 |
| `test_p4_ue_manifest_only.py` | production + ue_export | FR-UE-002, FR-UE-003 | manifest + plan + evidence 三件套落盘,stub unreal 跑通 `run_import.py` |

### 4.2 场景级

| 文件 | 对应需求 | 验证内容 |
| --- | --- | --- |
| `test_l4_image_to_3d.py` | FR-WORKER-002 | image.raster → mesh.gltf 全链 |
| `test_image_edit.py` | FR-MODEL-003 | image_edit capability |
| `test_dag_concurrency.py` | FR-WF-007, NFR-PERF-001 | `parallel_dag=True` fan-out,墙钟验证 |
| `test_ws_progress.py` | FR-OBS-003, FR-OBS-004 | WS endpoint 订阅 + 事件推送 + idle disconnect |
| `test_example_bundles_smoke.py` | FR-WF-001 | `examples/*.json` 每份 loader + Orchestrator 不抛 |
| `test_run_comparison_cli.py` | — | 4 用例;详见 §3.11A。FakeAdapter 双跑离线集成是 examples-and-acceptance delta spec Validation gate |
| `test_v2_e2e_synthetic_change.py`(自 `enhance-workflow-automation-executable-enforcement` change 起,2026-05-05;ADR-012)| D-W4-IntegrationGate(P5.5);archive 必过 gate | 11 test 全 PASS;synthetic git repo + change → W1 wrapper(创建 worktree + 13-field receipt + wrong-cwd / dirty negative)+ W3 ledger(append + verify monotonic)+ W2 actual diff(disjoint pass + overlap detected + dirty implementer detected)+ finish_gate v2 fence(unit-style import 直接 call 4 v2 fence 函数 — pass on valid v2 evidence + block on missing receipt + v1 evidence 兼容 + legacy pass-through);沿 D-W4-IntegrationGate sister skill subagent-driven-discipline §6 catalog "black-box pipeline test vacuous PASS" 教训 — 用 unit-style import 而非 subprocess 黑盒调 finish_gate(避免 early-abort 时 fence skip 导致 vacuous PASS)|
| `test_preflight_wrapper.py`(W7-a regression;自 `restore-superpowers-worktree-consent-gate` change 起,2026-05-06;ADR-013)| D-WrapperBugFixInScope(W7-a)| 20 fence 全 PASS(原 18 + W7-a 新加 2):`test_git_repo_root_from_inside_worktree_returns_main_repo`(关闭 wrapper 在 worktree 内调用时 `_git_repo_root` 走 `git rev-parse --show-toplevel` 返回 worktree 自身路径 → nested target 漏洞)+ `test_wrapper_reuse_path_works_when_invoked_from_existing_worktree`(端到端 regression:从已存在 worktree 内调 wrapper → exit 0 + receipt worktree_action="reused");沿 archived ADR-012 follow-on `enhance-workflow-automation-v2-fence-hardening` P12.8 该项拨入本 change scope |
| `test_forgeue_command_markdown.py`(ADR-013 OPT-IN narrative + sync drift;自 `restore-superpowers-worktree-consent-gate` change 起,2026-05-06)| D-RestoreConsentGate + D-ConsentOutcomeStateMachine + D-ParallelDeclineFallback | 29 fence 全 PASS(原 25 + ADR-013 新加 4):2 改 (`test_change_apply_subagent_invokes_preflight_wrapper` + `test_change_apply_parallel_invokes_preflight_wrapper` 改 OPT-IN narrative 校验)+ 3 加 (`test_apply_subagent_parallel_must_invoke_skill_using_git_worktrees` + `test_apply_subagent_parallel_preflight_outcome_capture_field` + `test_apply_parallel_decline_auto_fallback_sequential_narrative`)+ 1 P0 code_quality I-1 inline-fix `test_preflight_worktree_section_bodies_identical`(防 sister md sync drift)|
| `test_forgeue_finish_gate.py`(ADR-013 mode-conditional advisory + 2 new fences;自 `restore-superpowers-worktree-consent-gate` change 起,2026-05-06)| D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant + D-WrapperDeprecate | 131 fence 全 PASS(原 119 + ADR-013 新加 12):3 改 (`test_worktree_path_advisory_pass_through_when_no_outcome_field` + `test_worktree_path_empty_string_blocks_under_skill_worktree_mode` + `test_worktree_path_required_for_change_apply_parallel_when_skill_worktree_mode` rewrite)+ 10 加 (legacy pass-through / outcome enum / declined↔in_place / accepted→{skill,wrapper}_worktree / already_isolated rejects in_place [W6] / already_isolated requires path != main_repo [W6] / mode in_place rejects worktree_path / mode wrapper requires receipt / mode skill rejects receipt / valid full state machine + already_isolated valid path positive [P1 M-2 inline-fix])|

---

## 5. Fence 测试清单(L3 专属)

以下 fence 每条对应 plan_v1 §M 一次修复,防止回退。

| Fence | 守护修复 | 文件 |
| --- | --- | --- |
| DAG retry_same_step 被吞 | plan_v1 §M 第一轮 adv #1 | `test_cascade_cancel::test_dag_retry_same_step_reexecutes` |
| Review cost_usd 缺失 | 第一轮 | `test_review_budget` |
| Range 续传强校验 | 第一轮 adv #1 | `test_download_async::test_continue_requires_206_with_matching_offset` |
| EventBus loop-aware | 第一轮 adv #2 | `test_event_bus::test_cross_thread_publish_hops_to_owning_loop` |
| Hunyuan n>1 真并发 | 第一轮 adv #3 | `test_cn_image_adapters::test_hunyuan_aimage_n3_runs_three_submits` |
| Mesh glTF external-buffer | 第二轮 | `test_cn_image_adapters`(mesh 侧) |
| Mesh URL fallthrough | 第二轮 | 同上 |
| Mesh 多 URL 吃 budget | 第二轮 | 同上 |
| Mesh download error fallthrough | 第二轮 | 同上 |
| Mesh 空 ranked → unsupported | 第二轮 | 同上 |
| Mesh ASCII FBX 识别 | 第二轮 | 同上 |
| Mesh FBX self-containment | FOR-28 | `test_cn_image_adapters::TestHunyuanMeshFbxSelfContainment` |
| Mesh glTF parse-fail double-guard | 第二轮 | 同上 |
| `data:` URI 大小写 | 第二轮 | 同上 |
| unsupported → abort_or_fallback | 第二轮 | `test_transition_engine::test_abort_or_fallback_honours_on_fallback` |
| Probe runtime 格式检测一致 | 第二轮 | `test_probe_framework` |
| GLM probe import 副作用 | 第二轮 | `test_probe_framework::test_glm_probes_lazy_init` |
| Comfy v1.6 agent CLI subprocess(26 fence)| OpenSpec change `comfy-agent-cli-adoption`(2026-05-02)| `test_comfy_subprocess.py` |
| ComfyUI v1.7 audio capability(~30+ fence:`test_comfy_subprocess_audio` 19 + `test_generate_audio_comfy` 14 + `test_audio_worker` 6 + `test_failure_mode_map` audio 6 + `test_probe_framework` audio 2 + `test_model_registry` audio 2)| OpenSpec change `comfy-agent-cli-audio-adoption`(2026-05-03)| `test_comfy_subprocess_audio.py` / `test_generate_audio_comfy.py` / `test_audio_worker.py` / `test_failure_mode_map.py` / `test_probe_framework.py` / `test_model_registry.py` |
| ComfyUI v1.8 video capability(~70 fence:`test_artifact` 10 含 P12 regression + `test_video_worker` 7 + `test_comfy_subprocess_video` 27 含 BMFF strict 5-tuple 9 + `test_generate_video_comfy` 14 + `test_failure_mode_map` video 6 + `test_ue_bridge` video+F1 sweep 10 + `test_p4_ue_manifest_only` video stub+F1 5 + `test_probe_framework` video 2 + `test_model_registry` video 2)+ examples bundles auto-discover 3 fence | OpenSpec change `comfy-agent-cli-video-adoption`(2026-05-04)| `test_artifact.py` / `test_video_worker.py` / `test_comfy_subprocess_video.py` / `test_generate_video_comfy.py` / `test_failure_mode_map.py` / `test_ue_bridge.py` / `test_p4_ue_manifest_only.py` / `test_probe_framework.py` / `test_model_registry.py` / `test_example_bundles_smoke.py` |
| FOR-8 multi-mode Comfy DAG lifecycle conflict | Linear FOR-8 `multi-mode-comfy-dag-warning`(2026-05-22) | `test_comfy_provider_config.py::test_default_managed_process_registry_rejects_conflicting_comfy_lifecycle_modes` |
| FOR-13 worker candidate source_path migration | Linear FOR-13 `worker-candidate-source-path-migration`(2026-05-22) | `test_comfy_subprocess.py` / `test_comfy_subprocess_audio.py` / `test_comfy_subprocess_video.py` / `test_generate_mesh_comfy.py` / `test_generate_audio_comfy.py` / `test_generate_video_comfy.py` |
| F-C framework D12 video 路径分流 + F-D Evidence skip_reason filter(27 fence + 4 P4 case + 1 rewrite:`test_evidence_skip_reason` 4 + `test_export_video_path_split` 13 含 2 pytest.skip placeholder + `test_evidence_writer_skip_reason` 3 + `test_run_import_skipped_filter` 2 + `test_domain_video_no_copy` 5 + `test_p4_ue_manifest_only` 加 4 P4 + 1 既有 rewrite) | OpenSpec change `fix-export-d12-and-skipped-evidence-filter`(2026-05-08) | `test_evidence_skip_reason.py` / `test_export_video_path_split.py` / `test_evidence_writer_skip_reason.py` / `test_run_import_skipped_filter.py` / `test_domain_video_no_copy.py` / `test_p4_ue_manifest_only.py` |
| Tripo3D 两处 unsupported | 第三轮 PR-1 | `test_tripo3d_unsupported` |
| Hunyuan image submit 无 id | 第三轮 PR-1 | `test_cn_image_adapters` |
| DashScope 空 choices | 第三轮 PR-1 | `test_cn_image_adapters` |
| LiteLLM image_generation 无 data | 第三轮 PR-1 | `test_providers_async` |
| 下载 remaining budget(3 家) | 第三轮 PR-2 | `test_adapter_budget_clamp` |
| Magic bytes gate(runtime) | 第三轮 PR-3 | `test_cn_image_adapters` |
| Hunyuan image URL fallthrough | 第三轮 PR-3 | `test_cn_image_adapters` |
| HTTP URL scheme 大小写 | 第三轮 PR-3 | `test_pr3_cleanup_fences` |
| Probe lazy-init | 第三轮 PR-3 | `test_pr3_cleanup_fences` / `test_probe_framework` |
| Pricing YAML typo 子字段 raise | 第四轮 | `test_registry_pricing` |
| Route pricing 透传 raw["_route_pricing"] | 第四轮 | `test_router_pricing_stash` |
| Mesh cost 非 0 | 第四轮 | `test_generate_mesh_cost` |
| Fabricated pricing 止血 | 第五轮 | `test_registry_pricing`(YAML null + TODO) |
| Scaffold parser must raise NotImplementedError | 第五轮 | `test_pricing_probe_framework::test_every_scaffold_parser_still_raises_notimplemented` |
| Playwright 后端 + fixture | 第六轮 | `test_pricing_parser_*`(3 家)|

### Codex 21 条 audit 修复 fence(2026-04-22,5 轮 review-fix 循环)

文件统一在 `tests/unit/test_codex_audit_fixes.py`(29 用例)。

**第一轮(初始 audit,11 条 — C1 + H6 + M4 + L1)**

| Fence | 守护修复 | 测试名 |
| --- | --- | --- |
| generate_structured 重试耗尽要 raise typed exception | #R1-1(critical)| `test_generate_structured_reraises_typed_exception_after_retries` |
| 三处 `r.json()` 必须捕 `JSONDecodeError` 并 wrap unsupported | #R1-3(high)| `test_hunyuan_tokenhub_post_raises_unsupported_on_html_body` / `_qwen_dashscope_*` / `_mesh_worker_apost_*` |
| poll loop 单次 timeout clamp 到 remaining budget | #R1-4(high)| `test_hunyuan_poll_clamps_timeout_to_remaining_budget` / `test_mesh_poll_clamps_timeout_to_remaining_budget` |
| `find_hit` 长度不一致必须 miss | #R1-5(high)| `test_checkpoint_find_hit_misses_on_length_mismatch` |
| `image_edit` 必须输出 cost_usd | #R1-6(high)| `test_image_edit_emits_cost_usd` |
| `TransitionPolicy.on_retry` 必须被读 | #R1-7(medium)| `test_retry_same_step_honours_policy_on_retry` / `_falls_back_to_step_id_when_unset` |
| TransitionEngine counter per-arun 隔离 | #R1-8(medium)| `test_orchestrator_uses_fresh_transition_engine_per_arun` / `_concurrent_arun_does_not_share_counters` |
| `parallel_candidates` 异质 route 必须 raise | #R1-9(medium)| `test_generate_image_parallel_rejects_heterogeneous_models` |
| select bare-approve 全保留 | #R1-10(medium)| `test_select_bare_approve_keeps_whole_pool` |
| sync `chunked_download` dead code 已删 | #R1-11(low)| `test_sync_chunked_download_module_removed` |
| `--resume` 跨进程 ArtifactRepository 重建 | #R1-2(high)| `test_repository_metadata_dump_and_load_roundtrip` / `test_resume_yields_cache_hits_after_reload` |

**第二轮(2 条)**

| Fence | 守护修复 | 测试名 |
| --- | --- | --- |
| select bare-approve 排除显式 rejected | #R2-2 | `test_select_bare_approve_excludes_explicit_rejects` |
| `load_run_metadata` 跳过 missing payload | #R2-1 | `test_load_run_metadata_skips_missing_payload` |

**第三轮(3 条)**

| Fence | 守护修复 | 测试名 |
| --- | --- | --- |
| `cloned_for_run` 保留子类身份 | #R3-1 | `test_transition_engine_clone_preserves_subclass_and_attrs` |
| unsupported 不进 transient retry(3 处)| #R3-2 | `test_hunyuan_unsupported_response_skips_transient_retry` / `_qwen_*` / `_mesh_worker_*` |
| `find_by_producer` 并发 put 安全 | #R3-3 | `test_find_by_producer_safe_under_concurrent_put` |

**第四轮(3 条)**

| Fence | 守护修复 | 测试名 |
| --- | --- | --- |
| image executor `_should_retry` 不重试 unsupported | #R4-3 | `test_image_executor_does_not_retry_on_unsupported_response` |
| cache-hit 回放 cost 到 BudgetTracker | #R4-1(critical)| `test_orchestrator_replays_cached_cost_into_budget_tracker` |
| `load_run_metadata` 跳过 hash 漂移 payload | #R4-2 | `test_load_run_metadata_skips_corrupted_payload` |

**第五轮(2 条)**

| Fence | 守护修复 | 测试名 |
| --- | --- | --- |
| structured cost 写入 `cp.metrics` | #R5-1(critical)| `test_structured_step_persists_cost_for_resume` |
| router 在 unsupported 时不 fallback | #R5-2 | `test_router_does_not_fallback_on_unsupported_response` |

### TBD-007 mesh 重试塌缩 fence(2026-04-22,5 条 — Codex 独立 review 协助)

用户实测 1 个 mesh job 被扣 16 调用 × 20 积分 = 320 积分。Codex 独立 review 找出 4 层重试中我漏的 executor 内部循环(L2)。HYPOTHESIS probe 验证客户端断开后远端仍生成,blind retry 真双扣。

| Fence | 守护层 | 测试名 |
| --- | --- | --- |
| `_apost` 单次直发,ConnectError 不重 POST | L1 transport | `test_mesh_no_silent_retry::test_apost_no_transient_retry_on_connect_error` + `test_transient_retry::test_mesh_worker_does_NOT_retry_on_winerror_10060`(翻转)|
| `GenerateMeshExecutor` mesh.generation 短路 attempts=1,worker.generate 只调一次 | L2 executor | `test_mesh_no_silent_retry::test_executor_no_internal_retry_for_mesh_capability` + `test_l4_image_to_3d::test_mesh_executor_does_NOT_retry_on_worker_error`(翻转)|
| `MeshWorkerTimeout` → `mesh_worker_timeout` mode → `abort_or_fallback` | L3 orchestrator | `test_mesh_no_silent_retry::test_failure_mode_map_routes_mesh_timeout_to_abort` |
| `MeshWorkerError` → `mesh_worker_error` mode → `abort_or_fallback` | L3 orchestrator | `test_mesh_no_silent_retry::test_failure_mode_map_routes_mesh_error_to_abort` |
| 失败时 failure_event.context 有 job_id/worker/model + CLI stderr 提示含 probe + --resume | B2/B3 visibility | `test_mesh_failure_visibility::test_mesh_failure_event_includes_job_id_and_stderr_hint` |

### TBD-008 visual review contract fence(2026-04-22,2 新 + 3 翻转 — Codex B+C 分层采纳 + Codex Phase G R2 发现 verdict-path 优先级 bug)

Codex 独立 review 指出老 offline 测试里的 `VISUAL_A/B/C` / `ORIGINAL_/REVISED_/API_` / `fake-source-image-bytes` 伪字节,让"视觉 review"退化为"计算 image_url block 数量 / 按 candidate_id 位置打分"。本次升级用真 PNG fixture(`tests/fixtures/review_images/tavern_door_v{1,2,3}.png`)驱动,契约测试 offline 稳定,真 provider 打分归 opt-in probe。

| Fence | 守护点 | 测试名 |
| --- | --- | --- |
| P2 visual_mode 真图驱动 + 真压缩 + 按 id 打分选 winner | offline 契约(判别力 / 压缩路径 / id 解析)| `test_p2_standalone_review::test_p2_visual_mode_attaches_image_bytes_to_judge_prompt`(翻转 + Pillow importorskip gate)|
| P3 revise 路径用真图 round 1/2 区分 | offline 契约(revise 触发 / lineage 正确)| `test_p3_production_pipeline`(翻转多条,fixture 复用)|
| **L4 mesh 从 review verdict 读 selected_candidate_ids** | **真实生产路径**(image_to_3d_pipeline.json shape) | `test_l4_image_to_3d::test_l4_mesh_reads_selected_candidate_from_review_verdict`(**新增 — Codex R2 发现:此路径才是生产路径**)|
| L4 mesh 从 selected_set bundle 读 selected 图 | forward-compat(SelectExecutor 流程) | `test_l4_image_to_3d::test_l4_mesh_resolves_selected_image_from_selected_set_bundle`(新增)|
| 真 provider 打分能力(Anthropic vs GLM on 同 3 图)| 质量抽检 opt-in | `probes/provider/probe_visual_review.py`(FORGEUE_PROBE_VISUAL_REVIEW=1) |

**fixture 使用约定**:新的视觉相关测试一律走 `tests.fixtures.load_review_image(name)` helper,禁止直接内嵌 `b"\x89PNG..."` 之类的魔字节;fixture 不够用时先新增到 `tests/fixtures/review_images/`(README 记来源),不重复造。

**契约 vs 质量分层**:offline 契约测试(p2/p3/l4)用 `FakeAdapter` 脚本化打分,验 review pipeline 流水线正确性;provider 打分质量(真 Anthropic / GLM 对真图的判别)归 opt-in probe,偶发手跑对比。不把 CI 绑到外部 provider 波动。

---

## 6. 覆盖分析

### 6.1 需求覆盖矩阵(摘要)

| SRS 需求族 | 覆盖测试文件 | 状态 |
| --- | --- | --- |
| FR-WF(工作流) | integration/test_p0~p4, test_dag_concurrency, test_scheduler_risk_ordering, test_cascade_cancel | ✅ |
| FR-LC(生命周期) | test_dry_run_pass, test_checkpoint_store, test_artifact_repository(FOR-14 metadata integrity), integration/test_p0 | ✅ |
| FR-MODEL(编排) | test_model_registry, test_providers(_async), test_cn_image_adapters | ✅ |
| FR-STRUCT(结构化) | integration/test_p1 | ✅ |
| FR-REVIEW(评审) | integration/test_p2, test_chief_judge_parallel, test_review_budget | ✅ |
| FR-STORE(Artifact) | test_core_schemas, test_artifact_repository, test_payload_backends | ✅ |
| FR-UE(UE Bridge) | test_ue_bridge, integration/test_p4 | ✅(stub) |
| FR-WORKER(多模态) | test_cn_image_adapters, **test_comfy_subprocess(自 v1.6 替代 test_comfy_http_unsupported)**, test_tripo3d_unsupported, integration/test_l4 | ✅ |
| FR-RUNTIME(工程化) | test_failure_mode_map, test_transition_engine, test_budget_tracker, test_cancellation, test_transient_retry, test_retry_async, test_cascade_cancel | ✅ |
| FR-COST(定价) | test_registry_pricing, test_budget_tracker_pricing, test_router_pricing_stash, test_generate_mesh_cost, test_pricing_* | ✅ |
| FR-OBS(观测) | test_event_bus, test_progress_passthrough, test_orchestrator, test_compactor, test_secrets, integration/test_ws_progress | ✅ |

### 6.2 NFR 覆盖

| NFR 族 | 覆盖方式 |
| --- | --- |
| NFR-PERF | test_dag_concurrency(墙钟),test_chief_judge_parallel(并发),test_multi_candidate_parallel(N 候选) |
| NFR-REL | test_failure_mode_map,test_cascade_cancel,test_transition_engine |
| NFR-REPRO | test_checkpoint_store(hash verify),integration/test_p0(resume) |
| NFR-SEC | test_secrets,test_dry_run_pass |
| NFR-OBS | test_event_bus,test_progress_passthrough,test_orchestrator |
| NFR-MAINT | 所有 L3 fence 守门 + 历史基线 549 用例(491 + Codex audit fence 29 + src-layout / router-obs 根因定位 fence 6 + TBD-006 视觉 review 图像压缩 fence 10 + TBD-007 mesh 重试塌缩 fence 5 + TBD-008 visual review contract fence 2 + A1 + a2_mesh live bundle parametrize 6 自动收);**当前 2026-04-27 实测 1144 用例**(549 → 848 Run Comparison +299 → 1140 forgeue tooling +292 → 1144 lazy artifact_store +4) |
| NFR-PORT | CI 能在 Linux 跑(2026-04-23 基线 549 全绿,stub unreal 覆盖 P4 + 真机 commandlet 覆盖 A1;2026-04-25 实测 848 全绿;2026-04-27 实测 1144 全绿) |

### 6.3 未覆盖 / 部分覆盖

| 项 | 状态 | 说明 |
| --- | --- | --- |
| A1 UE 真机冒烟 | ✅ 已通过(2026-04-23,UE 5.7.4 commandlet)| stub 覆盖框架侧 offline,真机走 `UnrealEditor-Cmd.exe -ExecutePythonScript` 自动化路径(无 GUI 依赖),见 `acceptance_report §6.1` |
| Live LLM 端到端 | **手工验收** | 需 provider key,默认不在 CI 跑 |
| Pricing probe `--apply` 真跑 | **手工验收** | playwright + chromium + 供应商页面可达 |
| bridge_execute 模式 | **未启动** | §G #1 |
| Audio worker | ✅ baseline + remote HTTP + MiniMax direct 已实施 | 本地 ComfyUI audio 已 L2;FOR-26 通用 HTTP remote worker 与 MiniMax music_generation direct worker 已 L1 offline,厂商专用 ElevenLabs / AudioCraft adapter 按真实需求另立 follow-on |
| WS 鉴权 | **未启动** | 默认绑 127.0.0.1 |
| FBX self-containment | ✅ 已实施(FOR-28,dependency-free) | `TestHunyuanMeshFbxSelfContainment`:ASCII/Binary `FileName` / `RelativeFilename` sidecar 检测、普通模式 reject、geometry-only 放行、URL fallthrough |
| DashScope / Tripo3D parser 实装 | **部分** | 8 model scaffold,实装待真实用例 |

---

## 7. 测试环境

### 7.1 软件环境

| 项 | 版本 |
| --- | --- |
| Python | 3.12+ |
| pytest | 7.x+ |
| httpx | 0.27+ |
| pydantic | 2.x |
| litellm | 最新稳定 |
| instructor | 最新稳定 |
| ruamel.yaml | 0.18+ |
| playwright(可选) | 1.40+,需 `playwright install chromium` |
| UE(真机验收) | 5.3+ |

### 7.2 硬件建议

| 用途 | 要求 |
| --- | --- |
| 单元测试 | 4GB RAM,无 GPU |
| 集成测试 | 8GB RAM |
| Live LLM smoke | 外网可达 provider endpoint |
| Pricing probe --apply | 4GB+ 空闲(playwright/chromium) |
| UE 真机 | UE 5.3+ 装机,推荐 16GB RAM(已实测 UE 5.7.4 + C++ 项目 + commandlet 模式,2026-04-23) |

### 7.3 测试数据

| 位置 | 内容 |
| --- | --- |
| `tests/fixtures/pricing/*.html` | 5 家 provider 定价页真实 HTML 快照(280KB Hunyuan 3D 最大) |
| `examples/*.json` | 5 份 TaskBundle JSON |
| `src/framework/review_engine/rubric_templates/*.yaml` | 3 份 rubric |
| `config/models.yaml` | 模型注册表(测试通过 `ModelRegistry.reset()` 隔离) |
| 临时产物 | `pytest --basetemp=./demo_artifacts/<name>` 手工保留 |

### 7.4 环境变量

| Key | 用途 | 单元测试 | Live smoke |
| --- | --- | --- | --- |
| `DASHSCOPE_API_KEY` | Qwen | ❌ | ✅ |
| `HUNYUAN_API_KEY` | Hunyuan Image | ❌ | ✅ |
| `HUNYUAN_3D_KEY` | Hunyuan 3D | ❌ | ✅ |
| `GLM_API_KEY` | Zhipu | ❌ | ✅ |
| `PACKYCODE_API_KEY` | Claude via Packy | ❌ | ✅ |
| `MINIMAX_KEY` | MiniMax | ❌ | ✅ |
| `FORGEUE_RUN_FOLDER` | UE 真机 run 目录 | ❌ | ❌(UE 侧) |

---

## 8. 测试通过标准

| 级别 | 标准 |
| --- | --- |
| 单元测试 | 100% 通过(以 `pytest -q` 实测为准;**2026-05-20 实测 1179 passed / 3 skipped / 0 failed** = 549 → 848 Run Comparison +299 → 1140 forgeue tooling +292 → 1144 lazy artifact_store +4 → 1184 comfy-agent-cli +36 → 1294 audio +110 → 1414 video +120 → 1136 retire-protocol-layer -278 → 1179 executor-async-rewrite +43;历史基线 549 = 491 + audit 29 + 后续 fence 23 + A1 + a2_mesh live bundle parametrize 6)|
| 集成测试 | P0–P4 + 5 场景 + Run Comparison 全绿 |
| Fence 测试 | 每条守护修复不得回退 |
| 覆盖率 | 每条 FR 至少 1 个对应测试(矩阵 §6.1 全部 ✅) |
| 性能 | 全量 `pytest -q` 目标 ≤ 60s(历史基线 ≤15s @ 549 用例;2026-04-25 实测 ~28s @ 848 用例;2026-04-27 实测 ~50s @ 1144 用例,subprocess fence 数量增加导致 ~22s 增量,仍在 60s 软目标内)|
| 手工验收 | A1 UE 真机、A2 live LLM、A3 pricing probe 按验收文档勾选 |

---

## 9. 测试变更管理

### 9.1 新增测试触发条件

| 触发 | 行动 |
| --- | --- |
| 新增 FR / NFR | 配对至少一个单测 + 更新矩阵 §6.1 |
| Codex / adversarial review 修复 | 配对一个 L3 fence + 更新 §5 清单 |
| 新 Provider 接入 | 扩 `test_providers_async` + adapter 专属 fence |
| 新 Executor 类型 | 扩集成场景 + 对应单测 |

### 9.2 废弃测试流程

- 单元测试对应功能删除 → 同步删除测试
- Fence 测试守护的代码重写但语义不变 → 保留 fence
- 测试因环境不可达间歇性失败 → 加 `pytest.mark.skipif` + 注释说明原因

---

## 10. 附录

### 10.1 追溯矩阵

每条 SRS FR/NFR → 测试文件 → plan_v1 或 HLD/LLD 章节:见 §3、§4、§6 交叉表。

### 10.2 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-04-22 | 初始基线,491 用例索引化,fence 清单对齐 plan_v1 §M |
| v1.1 | 2026-04-22 | 加 §3.10 `test_codex_audit_fixes.py`(29 用例)+ §5 第三段 5 轮 audit fence 表;`NFR-MAINT` / `单元测试` 总数刷新到 520 |
| v1.2 | 2026-04-23 | A1 UE 真机 ⏳→✅(UE 5.7.4 commandlet 路径,§7.2 / §7.3 状态升级);A2 全集 5/5 ✅(0423 重跑 a2_char/image/review/mesh + a1_demo 含 a2_ue);新增 examples bundle `ue_export_pipeline_live.json` + `image_to_3d_pipeline_live.json`,`test_example_bundles_smoke` 自动 parametrize 收 6 用例,总数刷新到 549 |
| v1.3 | 2026-04-25 | 加 §3.11 / §3.11A Run Comparison(`tests/unit/test_run_comparison_{models,loader,diff_engine,reporter,cli}.py` 5 文件 + `tests/integration/test_run_comparison_cli.py` 1 文件 + `tests/fixtures/comparison/builders.py` deterministic builder);§4 集成测试场景表加一行 `test_run_comparison_cli.py`;OpenSpec change `add-run-comparison-baseline-regression` 实装侧 6 Task 全部完成,总数刷新到 848(基线 549 + ~299 新用例)|
| v1.4 | 2026-04-27 | 加 §3.12 Lazy artifact_store package exports(OpenSpec change `lazy-artifact-store-package-exports`):新增 `tests/unit/test_artifact_store_lazy_imports.py` 4 fence(`_run_clean_subprocess` helper + 4 spec scenario 各 1 fence);收紧 `test_run_comparison_loader.py::TestLoaderImportFence` + `test_run_comparison_cli.py::TestCliImportFence` 禁止清单(9→13 prefix);删 `comparison/cli.py` + 2 fence test 内 "transitive load is unavoidable" carve-out 段落;`§5 / §NFR-MAINT / 单元测试 / 性能 / 合计` 全部刷新实测 1144(848 → 1140 中间基线 forgeue tooling fence + 4 lazy artifact_store fence)|
| v1.5 | 2026-05-06 | 加 v3 Cryptographic Ledger Binding(OpenSpec change `enhance-workflow-automation-ledger-binding`):`tests/unit/test_dispatch_ledger.py` 28 → 47 case(P1 16 case canonical_payload / compute_hmac / compute_key_id / load_or_init_key lifecycle 6 状态 + P2 19 case cmd_append v3 11-字段 + cmd_verify ANY v3 信号 dispatch + chain HMAC + key rotation 双路径 + strict 11-field schema + archived replay path boundary);`tests/unit/test_forgeue_finish_gate.py` 138 → 168 case(P3 26 case 4 新 fence test:`_check_runtime_enforcement_protocol_version_validity` 5 + `_check_archived_replay_path_boundary` 4 + `_check_ledger_terminal_proof` 6 + `_check_ledger_forgery_resistance_consistency` 4 + dispatch_ledger v3 分支 4 + double_fence 1 + writeback_check archived_replay drift 2 + P5 codex review P1 inline writeback 4 case `_runtime_enforcement_active` accepts v1/v2/v3 + v3 evidence inherits v1 fence skill_cascade + task_granularity);`tests/integration/test_v2_e2e_synthetic_change.py` 加 `TestV3CryptographicLedger` 3 case(happy path + tail truncation negative + audit inconsistency negative);全套 pytest regression 1689 → 1743 PASS + 1 skipped + 0 failed(实测累计 v1.0-v1.5)|
| v1.6 | 2026-05-08 | 加 cluster 2 follow-on(OpenSpec change `fix-export-d12-and-skipped-evidence-filter`):F-C framework D12 video 路径分流 + Evidence skip_reason field + F-D run_import.py 三 AND filter + domain_video file_path 从 source_uri 派生 + mismatch fence。新增 5 fence test file 共 27 case(`tests/unit/test_evidence_skip_reason.py` 4 + `tests/unit/test_export_video_path_split.py` 13 含 2 pytest.skip placeholder + `tests/unit/test_evidence_writer_skip_reason.py` 3 + `tests/unit/test_run_import_skipped_filter.py` 2 + `tests/unit/test_domain_video_no_copy.py` 5)+ `tests/integration/test_p4_ue_manifest_only.py` 加 4 P4 case + 1 既有 rewrite(legacy `test_p4_domain_video_copies_mp4_to_content_movies_subdir` → `test_p4_domain_video_consumes_d12_mp4_in_place_no_copy` 契约对齐)。全套 pytest 1700 → 1727 PASS + 3 skipped + 1 pre-existing fail(`fix-cross-check-format-test-enum-extension` follow-on,无关本 change)。 |
| v1.7 | 2026-05-20 | 加 forge change `executor-async-rewrite`(TBD-010 closed):StepExecutor.execute ABC 原生 async / orchestrator 删 asyncio.to_thread / ComfyAgentWorker async-subprocess + per-loop lock + cancel /interrupt + agenerate_* 主面 + sync shim / 新 lifecycle.py(ExternalProcessLifecycle + ComfyLifecycleManager 三模式)/ Orchestrator lifecycle 持有 + try/finally + aclose() / cascade-cancel 真停 + drain 30s 明示 / DryRunPass.run async + aprobe / StepContext.lifecycle 字段 / comfy_lifecycle 四值受理。新增 fence 文件 `test_cascade_cancel.py`(真停 + drain timeout)+ `test_comfy_lifecycle.py`(三模式 + 并发单飞 + cancel 不泄漏 + release 决策表)+ `test_dry_run_pass.py`(async run + aprobe)+ delta `test_comfy_subprocess.py`(async-subprocess + 串行锁 + /interrupt cancel + aprobe + lifecycle 集合外值)+ delta `test_step_context.py`(lifecycle 字段)+ delta `test_orchestrator.py`(lifecycle 注入 + try/finally + aclose)。全套 pytest **1179 passed / 3 skipped / 0 failed**(2026-05-20 实测;baseline 1136 → 1179 net +43 新 fence)。L2 live evidence `docs/archive/forge_changes/2026-05-20-executor-async-rewrite/notes/live_smoke_lifecycle_20260520.md`。 |
| v1.8 | 2026-05-22 | 加 Linear FOR-13 `worker-candidate-source-path-migration`:Comfy image / mesh / audio / video worker 只读格式校验头并返回 `source_path`;四个 generator executor source_path 优先落盘,无 source_path 时保留 bytes 回退。新增 / 扩展 source_path fence 覆盖 `test_comfy_subprocess.py`、`test_comfy_subprocess_audio.py`、`test_comfy_subprocess_video.py`、`test_generate_mesh_comfy.py`、`test_generate_audio_comfy.py`、`test_generate_video_comfy.py`;总数以本地 `python -m pytest -q` 实测为准。 |
| v1.9 | 2026-05-22 | 加 Linear FOR-11 `blob-backend-streaming-implementation`:BlobBackend MVP 从 stub 升级为可注入 `BlobClient` protocol + 默认 `InMemoryBlobClient`;支持 value 与 source_path 写入、read/exists、blob resume drift 校验,并放开 `repo.put(source_path=..., payload_kind=blob)`。新增 / 更新 fence 覆盖 `test_payload_backends.py` 与 `test_artifact_repository.py`;总数以本地 `python -m pytest -q` 实测为准。 |
| v1.10 | 2026-05-22 | 加 Linear FOR-8 `multi-mode-comfy-dag-warning`:ManagedProcessRegistry 扫描同一 run 内所有 managed subprocess selections,多个 Comfy step lifecycle mode 不一致时 fail-fast,不再静默采用第一个 mode。新增 `test_comfy_provider_config.py::test_default_managed_process_registry_rejects_conflicting_comfy_lifecycle_modes`;总数以本地 `python -m pytest -q` 实测为准。 |
| v1.11 | 2026-05-23 | 加 Linear FOR-14 `metadata-corruption-detection`:ArtifactRepository 写 `_artifacts.integrity.json` 绑定 `_artifacts.json` sha256 / artifact_count / artifact_ids;resume 发现 integrity mismatch 时 `ArtifactMetadataIntegrityError` fail-fast,legacy 无 integrity 文件保持兼容。新增 fence 覆盖 `test_artifact_repository.py`;总数以本地 `python -m pytest -q` 实测为准。 |
| v1.12 | 2026-05-23 | 加 Linear FOR-22 + FOR-23:DryRunPass 校验显式声明的 provider `api_key_env`,缺 key 时阻断 Run;Orchestrator Step 异常失败路径 emit `step_failed` ProgressEvent 并携带 `exception_type`。新增 / 更新 fence 覆盖 `test_dry_run_pass.py` 与 `test_orchestrator.py`;总数以本地 `python -m pytest -q` 实测为准。 |

### 10.3 未决事项

| 编号 | 事项 |
| --- | --- |
| TBD-T-001 | GitHub Actions Linux CI runner(ubuntu-latest; 全量 pytest) |
| TBD-T-002 | 覆盖率工具接入(`pytest-cov` 补量化指标) |
| TBD-T-003 | Live LLM smoke 固化为可选 CI job |

---

## Level 2 — ComfyUI 真机验证(user 手工)

> **自 OpenSpec change `retire-forgeue-protocol-layer-fully`(2026-05-10)起**:Level 2 ComfyUI 验证由 user 手工跑命令矩阵;`tools/forgeue_verify.py` wrapper 已 retire。沿 `openspec/specs/probe-and-validation/spec.md` MODIFIED Requirement 工具无关 contract:**`comfy/local*` 虚拟模型 id + 禁止 `--comfy-url` flag + 禁止 LiteLLM wildcard fallback**。

### 4 Capability 命令矩阵

**默认手工 smoke 前置(lifecycle=`none`,沿 `CLAUDE.md` ComfyUI 接入段)**:
- 先确保 ComfyUI server running;本机推荐 `python -m factory_v3 serve` 启服务(detached, ~30-90s 冷启动;用户自管;`python -m factory_v3 stop` 停)
- `factory_v3 serve/stop` 只是本机 ComfyUI server lifecycle helper;ForgeUE 生成/探活/取消仍走 `python -m comfyui_api run/status/cancel`
- 然后 export env + 跑 ForgeUE

**通用 env**:
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
# FORGEUE_COMFY_PYTHON_EXE 留空 → sys.executable
# FORGEUE_COMFY_LIFECYCLE 留空 → "none"
```

| Capability | Bundle path | 额外 env | 命令 |
|---|---|---|---|
| **Image** | `examples/comfy_local_smoke.json` | (无) | `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>` |
| **Mesh** | `examples/comfy_local_smoke_mesh.json` | `FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input` | `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>` |
| **Audio** | `examples/comfy_local_smoke_audio.json` | (无) | `python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>` |
| **Video** | `examples/comfy_local_smoke_video.json` | (无) | `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>` |

### 警告:false-positive PASS 防范

- **禁止传 `--comfy-url` flag**:silently 被 `framework.run` 忽略,fallback 到 `FakeComfyWorker`(deprecated by `comfy-agent-cli-adoption` v1.6,2026-05-02 archived)。
- **禁止用走 LiteLLM wildcard 的 bundle**:silently fallback 到 `FakeComfyWorker`,verification 变 false-positive PASS(没真跑 ComfyUI subprocess)。
- **检查方法**:bundle `provider_policy.models_ref` 必须解析至 `comfy/local` / `comfy/local-mesh` / `comfy/local-audio` / `comfy/local-video` 之一(`config/models.yaml` aliases 定义);若用 `qwen/*` / `hunyuan/*` 之类 alias → 走 LiteLLMAdapter wildcard → silently fallback FakeComfyWorker。
