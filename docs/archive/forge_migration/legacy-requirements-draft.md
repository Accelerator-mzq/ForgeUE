# Legacy Requirements Draft 概览

LLM 抽取 + 增量 diff 的草稿。请审改 `legacy-requirements-draft.yaml` 后跑 `forge legacy-bridge extract --finalize`。

## New (10)

- `(待分配)` TBD-001 bridge_execute 模式启用 —— docs/requirements/SRS.md#TBD-001
- `(待分配)` TBD-002 远端 Audio worker 接入 —— docs/requirements/SRS.md#TBD-002
- `(待分配)` TBD-003 WS 鉴权 / 多租户 session —— docs/requirements/SRS.md#TBD-003
- `(待分配)` TBD-004 FBX self-containment 校验 —— docs/requirements/SRS.md#TBD-004
- `(待分配)` TBD-005 DashScope / Tripo3D 下辖 parser 实装 —— docs/requirements/SRS.md#TBD-005
- `(待分配)` TBD-009 ComfyUI agent CLI mesh / audio / video 接入 —— docs/requirements/SRS.md#TBD-009
- `(待分配)` TBD-010 executor 原生 async 重写 —— docs/requirements/SRS.md#TBD-010
- `(待分配)` TBD-011 ModelRegistry ProviderDef.kind schema 扩展 —— docs/requirements/SRS.md#TBD-011
- `(待分配)` TBD-012 repo.put streaming payload zero-copy —— docs/requirements/SRS.md#TBD-012
- `(待分配)` TBD-013 RemoteControl HTTP bridge —— docs/requirements/SRS.md#TBD-013

## Changed (0)

(无)

## Conflict (0)

(无)

## Vanished (0)

(无)

## Unchanged (125)

- `LR-0001` FR-WF-001 三种 RunMode 支持 —— docs/requirements/SRS.md#FR-WF-001
- `LR-0002` FR-WF-002 三模式共享同一调度器 —— docs/requirements/SRS.md#FR-WF-002
- `LR-0003` FR-WF-003 线性+分支+DAG opt-in 并发 —— docs/requirements/SRS.md#FR-WF-003
- `LR-0004` FR-WF-004 Step 支持 11 种 type —— docs/requirements/SRS.md#FR-WF-004
- `LR-0005` FR-WF-005 Step risk_level 调度按风险升序 —— docs/requirements/SRS.md#FR-WF-005
- `LR-0006` FR-WF-006 revise 回环 max_revise 超限自动终止 —— docs/requirements/SRS.md#FR-WF-006
- `LR-0007` FR-WF-007 depends_on DAG 依赖并发执行 —— docs/requirements/SRS.md#FR-WF-007
- `LR-0008` FR-LC-001 Run 严格按 9 阶段执行 —— docs/requirements/SRS.md#FR-LC-001
- `LR-0009` FR-LC-002 Dry-run Pass 零副作用预检 —— docs/requirements/SRS.md#FR-LC-002
- `LR-0010` FR-LC-003 Dry-run 失败阻断执行并置失败状态 —— docs/requirements/SRS.md#FR-LC-003
- `LR-0011` FR-LC-004 Step 完成后写 artifact_hash 和 Checkpoint —— docs/requirements/SRS.md#FR-LC-004
- `LR-0012` FR-LC-005 Resume 校验 Checkpoint artifact_hash 一致性 —— docs/requirements/SRS.md#FR-LC-005
- `LR-0013` FR-LC-006 Step 完成后 dump _artifacts.json 支持 resume —— docs/requirements/SRS.md#FR-LC-006
- `LR-0014` FR-LC-007 load_run_metadata 三道过滤 —— docs/requirements/SRS.md#FR-LC-007
- `LR-0015` FR-LC-008 find_hit 长度不等时强制 miss —— docs/requirements/SRS.md#FR-LC-008
- `LR-0016` FR-MODEL-001 三段式 YAML 模型注册 —— docs/requirements/SRS.md#FR-MODEL-001
- `LR-0017` FR-MODEL-002 models_ref alias 展开为 prepared_routes —— docs/requirements/SRS.md#FR-MODEL-002
- `LR-0018` FR-MODEL-003 多 provider 接入支持 —— docs/requirements/SRS.md#FR-MODEL-003
- `LR-0019` FR-MODEL-004 OpenAI 兼容 provider 零新代码接入 —— docs/requirements/SRS.md#FR-MODEL-004
- `LR-0020` FR-MODEL-005 非 OpenAI 协议 provider 用 adapter 接入 —— docs/requirements/SRS.md#FR-MODEL-005
- `LR-0021` FR-MODEL-006 CapabilityRouter 注册顺序 + LiteLLMAdapter 最后 —— docs/requirements/SRS.md#FR-MODEL-006
- `LR-0022` FR-MODEL-007 能力别名列表 —— docs/requirements/SRS.md#FR-MODEL-007
- `LR-0023` FR-MODEL-008 ProviderPolicy fallback_models 降级 —— docs/requirements/SRS.md#FR-MODEL-008
- `LR-0024` FR-STRUCT-001 instructor + Pydantic 结构化输出 —— docs/requirements/SRS.md#FR-STRUCT-001
- `LR-0025` FR-STRUCT-002 Schema 注册到 registry(四类) —— docs/requirements/SRS.md#FR-STRUCT-002
- `LR-0026` FR-STRUCT-003 schema 验证失败映射 retry_same_step —— docs/requirements/SRS.md#FR-STRUCT-003
- `LR-0027` FR-STRUCT-004 LiteLLM drop_params=True —— docs/requirements/SRS.md#FR-STRUCT-004
- `LR-0028` FR-COST-001 pricing block 四字段支持 —— docs/requirements/SRS.md#FR-COST-001
- `LR-0029` FR-COST-002 未知 pricing 子字段 raise RegistryReferenceError —— docs/requirements/SRS.md#FR-COST-002
- `LR-0030` FR-COST-003 BudgetTracker 三个 estimator —— docs/requirements/SRS.md#FR-COST-003
- `LR-0031` FR-COST-004 route pricing 注入 ProviderResult.raw["_route_pricing"] —— docs/requirements/SRS.md#FR-COST-004
- `LR-0032` FR-COST-005 pricing_probe dry-run + --apply + manual 保护 —— docs/requirements/SRS.md#FR-COST-005
- `LR-0033` FR-COST-006 探针后端 httpx + playwright 双路 —— docs/requirements/SRS.md#FR-COST-006
- `LR-0034` FR-COST-007 外部定价必须有来源(sourced_on + source_url 或 null) —— docs/requirements/SRS.md#FR-COST-007
- `LR-0035` FR-COST-008 所有付费 executor 写入 metrics["cost_usd"] —— docs/requirements/SRS.md#FR-COST-008
- `LR-0036` FR-COST-009 parallel_candidates 异质 route raise —— docs/requirements/SRS.md#FR-COST-009
- `LR-0037` FR-REVIEW-001 三种评审形态支持 —— docs/requirements/SRS.md#FR-REVIEW-001
- `LR-0038` FR-REVIEW-002 ReviewReport + Verdict 双独立对象同时落库 —— docs/requirements/SRS.md#FR-REVIEW-002
- `LR-0039` FR-REVIEW-003 Verdict 支持 9 种 decision —— docs/requirements/SRS.md#FR-REVIEW-003
- `LR-0040` FR-REVIEW-004 Verdict 携带 confidence 低于 pass_threshold 触发 revise —— docs/requirements/SRS.md#FR-REVIEW-004
- `LR-0041` FR-REVIEW-005 5 维评分写入 scores_by_dimension —— docs/requirements/SRS.md#FR-REVIEW-005
- `LR-0042` FR-REVIEW-006 Rubric 从 YAML 模板加载支持内置模板 —— docs/requirements/SRS.md#FR-REVIEW-006
- `LR-0043` FR-REVIEW-007 ChiefJudge 面板 asyncio.gather 并发 —— docs/requirements/SRS.md#FR-REVIEW-007
- `LR-0044` FR-REVIEW-008 Review step 透传 judge usage 到 BudgetTracker —— docs/requirements/SRS.md#FR-REVIEW-008
- `LR-0045` FR-REVIEW-009 SelectExecutor bare-approve 语义 —— docs/requirements/SRS.md#FR-REVIEW-009
- `LR-0046` FR-STORE-001 Artifact 一等公民两段式 artifact_type 双向映射 —— docs/requirements/SRS.md#FR-STORE-001
- `LR-0047` FR-STORE-002 PayloadRef 三态 inline+file 实装 blob 预留 —— docs/requirements/SRS.md#FR-STORE-002
- `LR-0048` FR-STORE-003 inline 64 KB file 500 MB 上限 —— docs/requirements/SRS.md#FR-STORE-003
- `LR-0049` FR-STORE-004 各 modality 专属 metadata 字段 —— docs/requirements/SRS.md#FR-STORE-004
- `LR-0050` FR-STORE-005 Lineage 血缘 5 字段完整 —— docs/requirements/SRS.md#FR-STORE-005
- `LR-0051` FR-STORE-006 Artifact 入 Store 前四层校验 —— docs/requirements/SRS.md#FR-STORE-006
- `LR-0052` FR-UE-001 UE Bridge 双模支持:manifest_only 与 bridge_execute —— docs/requirements/SRS.md#FR-UE-001
- `LR-0053` FR-UE-002 manifest_only 模式产出 UEAssetManifest + UEImportPlan + Evidence —— docs/requirements/SRS.md#FR-UE-002
- `LR-0054` FR-UE-003 UE 侧 run_import.py 支持贴图/静态网格/音频导入 —— docs/requirements/SRS.md#FR-UE-003
- `LR-0055` FR-UE-004 Manifest 声明 target_object_path/target_package_path 并遵循 asset_naming_policy —— docs/requirements/SRS.md#FR-UE-004
- `LR-0056` FR-UE-005 导入拓扑通过 depends_on 声明并按拓扑序执行 —— docs/requirements/SRS.md#FR-UE-005
- `LR-0057` FR-UE-006 UE 侧每次操作追加 Evidence 记录 op_id/kind/status/错误信息 —— docs/requirements/SRS.md#FR-UE-006
- `LR-0058` FR-UE-007 Bridge 禁止操作边界约束 —— docs/requirements/SRS.md#FR-UE-007
- `LR-0059` FR-UE-008 Phase C 操作默认通过 permission_policy 拒绝 —— docs/requirements/SRS.md#FR-UE-008
- `LR-0060` FR-WORKER-001 ComfyUI worker agent CLI subprocess 支持 —— docs/requirements/SRS.md#FR-WORKER-001
- `LR-0061` FR-WORKER-002 Hunyuan 3D worker tokenhub 协议支持 —— docs/requirements/SRS.md#FR-WORKER-002
- `LR-0062` FR-WORKER-003 Tripo3D worker scaffold 保留,per-task 价格 NotImplementedError 守门 —— docs/requirements/SRS.md#FR-WORKER-003
- `LR-0063` FR-WORKER-004 Mesh worker URL rank 按 strong/ok/key/other/zip 桶序,fallthrough 循环 —— docs/requirements/SRS.md#FR-WORKER-004
- `LR-0064` FR-WORKER-005 chunked_download_async() Range 续传,206+Content-Range 对齐校验 —— docs/requirements/SRS.md#FR-WORKER-005
- `LR-0065` FR-WORKER-006 Mesh worker magic bytes 二次校验 glb 分支 —— docs/requirements/SRS.md#FR-WORKER-006
- `LR-0066` FR-WORKER-007 glTF 外部 buffer 应 raise,不得静默落盘空几何 —— docs/requirements/SRS.md#FR-WORKER-007
- `LR-0067` FR-WORKER-008 data: URI scheme 识别大小写不敏感 —— docs/requirements/SRS.md#FR-WORKER-008
- `LR-0068` FR-WORKER-009 tokenhub poll 单次 /query timeout clamp —— docs/requirements/SRS.md#FR-WORKER-009
- `LR-0069` FR-WORKER-010 adapter 200+非JSON body 显式捕获并 wrap —— docs/requirements/SRS.md#FR-WORKER-010
- `LR-0070` FR-WORKER-011 audio worker baseline:ABC + AudioCandidate + 异常树 + GenerateAudioExecutor 注册 —— docs/requirements/SRS.md#FR-WORKER-011
- `LR-0071` FR-WORKER-012 video worker baseline:ABC + VideoCandidate + 异常树 + GenerateVideoExecutor + BMFF 校验 + UE bridge 映射 —— docs/requirements/SRS.md#FR-WORKER-012
- `LR-0072` FR-RUNTIME-001 BudgetTracker Run级成本累计与超额终止 —— docs/requirements/SRS.md#FR-RUNTIME-001
- `LR-0073` FR-RUNTIME-002 Anthropic Prompt Cache 支持 —— docs/requirements/SRS.md#FR-RUNTIME-002
- `LR-0074` FR-RUNTIME-003 compact_messages 自动压缩 —— docs/requirements/SRS.md#FR-RUNTIME-003
- `LR-0075` FR-RUNTIME-004 取消/超时中断 asyncio.CancelledError 传播 —— docs/requirements/SRS.md#FR-RUNTIME-004
- `LR-0076` FR-RUNTIME-005 瞬态重试 SSL EOF/超时/5xx 默认一次2s回退 —— docs/requirements/SRS.md#FR-RUNTIME-005
- `LR-0077` FR-RUNTIME-006 Checkpoint resume 按 artifact_hash 恢复 —— docs/requirements/SRS.md#FR-RUNTIME-006
- `LR-0078` FR-RUNTIME-007 失败模式映射覆盖8类FailureMode —— docs/requirements/SRS.md#FR-RUNTIME-007
- `LR-0079` FR-RUNTIME-008 TransitionPolicy.on_retry 被 retry_same_step 实际读取 —— docs/requirements/SRS.md#FR-RUNTIME-008
- `LR-0080` FR-RUNTIME-009 TransitionEngine.counters per-arun 隔离 —— docs/requirements/SRS.md#FR-RUNTIME-009
- `LR-0081` FR-RUNTIME-010 先写 cost_usd 到 exec_result.metrics 再 checkpoints.record —— docs/requirements/SRS.md#FR-RUNTIME-010
- `LR-0082` FR-RUNTIME-011 Cache-hit 路径 cost_usd 回放到 BudgetTracker 并去重 —— docs/requirements/SRS.md#FR-RUNTIME-011
- `LR-0083` FR-RUNTIME-012 UnsupportedResponse 三层 short-circuit —— docs/requirements/SRS.md#FR-RUNTIME-012
- `LR-0084` FR-OBS-001 EventBus loop-aware 线程安全 —— docs/requirements/SRS.md#FR-OBS-001
- `LR-0085` FR-OBS-002 ProgressEvent schema 覆盖多种事件类型 —— docs/requirements/SRS.md#FR-OBS-002
- `LR-0086` FR-OBS-003 WebSocket 进度推送 server 两个端点 —— docs/requirements/SRS.md#FR-OBS-003
- `LR-0087` FR-OBS-004 WS handler asyncio.wait FIRST_COMPLETED 防泄露 Subscription —— docs/requirements/SRS.md#FR-OBS-004
- `LR-0088` FR-OBS-005 OTel tracing 可选开启 —— docs/requirements/SRS.md#FR-OBS-005
- `LR-0089` FR-OBS-006 CLI --serve flag 启动 WS 服务器 —— docs/requirements/SRS.md#FR-OBS-006
- `LR-0090` NFR-PERF-001 DAG并发调度线性降低墙钟时间 —— docs/requirements/SRS.md#NFR-PERF-001
- `LR-0091` NFR-PERF-002 ChiefJudge并发让总延迟约等于最慢judge —— docs/requirements/SRS.md#NFR-PERF-002
- `LR-0092` NFR-PERF-003 多候选并行通过asyncio.gather真并发 —— docs/requirements/SRS.md#NFR-PERF-003
- `LR-0093` NFR-PERF-004 分块下载使用1MB分块 —— docs/requirements/SRS.md#NFR-PERF-004
- `LR-0094` NFR-PERF-005 全量测试套件18秒内跑完 —— docs/requirements/SRS.md#NFR-PERF-005
- `LR-0095` NFR-REL-001 所有异常映射到FailureMode+Decision不得未分类抛出 —— docs/requirements/SRS.md#NFR-REL-001
- `LR-0096` NFR-REL-002 provider_timeout默认retry_same_step→fallback_model —— docs/requirements/SRS.md#NFR-REL-002
- `LR-0097` NFR-REL-003 schema_validation_fail/worker_timeout默认retry_same_step最多2次 —— docs/requirements/SRS.md#NFR-REL-003
- `LR-0098` NFR-REL-004 budget_exceeded触发合成Verdict走TransitionEngine终止 —— docs/requirements/SRS.md#NFR-REL-004
- `LR-0099` NFR-REL-005 unsupported_response走abort_or_fallback不回same step重计费 —— docs/requirements/SRS.md#NFR-REL-005
- `LR-0100` NFR-REL-006 DAG任一step异常立刻cancel siblings并re-raise —— docs/requirements/SRS.md#NFR-REL-006
- `LR-0101` NFR-REL-007 Checkpoint支持幂等resume,hash不匹配则失败 —— docs/requirements/SRS.md#NFR-REL-007
- `LR-0102` NFR-REL-008 disk_full触发rollback→stop不继续写Artifact —— docs/requirements/SRS.md#NFR-REL-008
- `LR-0103` NFR-REL-009 DAG fan-out期间find_by_producer用list()快照,dump不吞异常 —— docs/requirements/SRS.md#NFR-REL-009
- `LR-0104` NFR-REPRO-001 seed_propagation=True时seed沿Workflow向下游传递 —— docs/requirements/SRS.md#NFR-REPRO-001
- `LR-0105` NFR-REPRO-002 model_version_lock=True时禁止版本漂移 —— docs/requirements/SRS.md#NFR-REPRO-002
- `LR-0106` NFR-REPRO-003 hash_verify_on_resume=True时resume必须hash一致 —— docs/requirements/SRS.md#NFR-REPRO-003
- `LR-0107` NFR-REPRO-004 同一Task+seed+model_version两次Run产出相同结构化Artifact —— docs/requirements/SRS.md#NFR-REPRO-004
- `LR-0108` NFR-SEC-001 API key 不得硬编码在 bundle/YAML —— docs/requirements/SRS.md#NFR-SEC-001
- `LR-0109` NFR-SEC-002 Secrets 统一管理并脱敏 —— docs/requirements/SRS.md#NFR-SEC-002
- `LR-0110` NFR-SEC-003 Trace/ProgressEvent 不含 API key 明文 —— docs/requirements/SRS.md#NFR-SEC-003
- `LR-0111` NFR-SEC-004 Dry-run Pass 校验 API key 已注入 —— docs/requirements/SRS.md#NFR-SEC-004
- `LR-0112` NFR-SEC-005 WS server 默认绑定 127.0.0.1 —— docs/requirements/SRS.md#NFR-SEC-005
- `LR-0113` NFR-OBS-001 每个 Run 有唯一 run_id —— docs/requirements/SRS.md#NFR-OBS-001
- `LR-0114` NFR-OBS-002 Step emit step_start/step_done/step_failed —— docs/requirements/SRS.md#NFR-OBS-002
- `LR-0115` NFR-OBS-003 BudgetTracker 在 RunResult.budget_summary 汇总指定字段 —— docs/requirements/SRS.md#NFR-OBS-003
- `LR-0116` NFR-OBS-004 长任务 poll emit worker_poll 事件 —— docs/requirements/SRS.md#NFR-OBS-004
- `LR-0117` NFR-MAINT-001 Codex review 修复配回归测试 —— docs/requirements/SRS.md#NFR-MAINT-001
- `LR-0118` NFR-MAINT-002 单元测试目录与 src/framework/ 并列 —— docs/requirements/SRS.md#NFR-MAINT-002
- `LR-0119` NFR-MAINT-003 总测试用例数 ≥ 491 —— docs/requirements/SRS.md#NFR-MAINT-003
- `LR-0120` NFR-MAINT-004 关键边界不得 mock —— docs/requirements/SRS.md#NFR-MAINT-004
- `LR-0121` NFR-MAINT-005 Bundle Artifact 流端到端真实对象 —— docs/requirements/SRS.md#NFR-MAINT-005
- `LR-0122` NFR-PORT-001 运行时主包纯 Python 不依赖 UE —— docs/requirements/SRS.md#NFR-PORT-001
- `LR-0123` NFR-PORT-002 CI 能在 Linux runner 跑通全量测试 —— docs/requirements/SRS.md#NFR-PORT-002
- `LR-0124` NFR-PORT-003 UE 侧最小化依赖仅 import unreal —— docs/requirements/SRS.md#NFR-PORT-003
- `LR-0125` NFR-PORT-004 文件路径避免 /tmp/ —— docs/requirements/SRS.md#NFR-PORT-004
