## Context

`comfy-agent-cli-adoption`(2026-05-02 归档)接入了 ComfyUI agent CLI(`python -m comfyui_api`)的 image 生成路径,框架侧确立了 `ComfyAgentWorker` subprocess 实装 + `comfy/local` 虚拟 model + `image_local` alias + `FORGEUE_COMFY_*` env vars + `_validate_outputs` image-only 守门(image-mode 拒绝 `outputs.glb / audio / video`)。

`D:/AI/ComfyUI/scripts/` 暴露的 18 个 workflow manifest 中,本地 mesh(GLB)、audio、video 三路 capability 还没接;UE 资产管线本身跨 image / mesh / audio / video。本 change 解锁 mesh capability,把 ComfyAgentWorker 从「image-only」扩到「image + mesh」。

> **Round 2 修订(codex S2 design adversarial review,2026-05-03)**:本 design 经过 codex 4 项 high/medium finding 全部 accepted-codex 后系统回写。关键架构变化:
>
> - **B1 修订**:provenance 不再走「`MeshCandidate.payload.metadata` + `PayloadRef(kind="file", file=..., metadata=...)`」(这两组字段在当前对象模型不存在);改为沿用现有 `MeshCandidate(data=bytes, metadata={...})` + `ArtifactRepository.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=".glb", metadata={"worker_metadata": dict(cand.metadata)})` 流程;in-tree path 由 `repo.put` 内部用 `<artifact_id>.glb` 命名(NFR-PORT-004 由 `FileBackend` 保证)
> - **B2 修订**:ComfyUI mesh 沿用 image-to-mesh 路径,**不**短路 `GenerateMeshExecutor._resolve_source_image(ctx)`;executor 把 source bytes 写入 in-tree input 文件后注入 `comfy_params`,再调 worker。这与 Hunyuan / Tripo3D mesh worker 模式一致(`source_image_bytes` 是 mesh worker 的核心输入)
> - **B3 修订**:ADR-007 premium 判定改用现有 `pricing.per_task_usd > 0` 字段(与 `BudgetTracker.estimate_mesh_call_cost_usd` 字段统一);**不**引入 `BudgetTracker.is_premium(route)` 新 API;判定逻辑由 `GenerateMeshExecutor` 内联
> - **B4 修订**:mesh-mode `_validate_outputs` 三段表(REQUIRED / auxiliary / rejected):`outputs.glb` REQUIRED,`outputs.images` auxiliary(允许但忽略),`outputs.audio / video` rejected。现实中 `02_mini_textured_3d_hunyuan` 等 ComfyUI mesh manifest 同时产 PNG preview + GLB,严格拒绝 PNG 会让 Phase 1 全部不可落地

约束:Windows 11 + Git-Bash + D: 盘;Python 3.12+;产物落 `./artifacts/<YYYY-MM-DD>/<run_id>/`(NFR-PORT-004 由 `repo.put` + `FileBackend` 保证);不破坏 image-mode 现有 109 fence(`tests/unit/test_comfy_subprocess.py`);不破坏 549 用例基线;新 contract 走 `/forgeue:change-doc-sync` 同步 SRS / HLD / LLD / acceptance / CHANGELOG;ADR-007 远端 Hunyuan3D mesh 严格 no-silent-retry 规则不动。

## Goals / Non-Goals

**Goals:**

- ComfyAgentWorker 守门从「image-only fail-fast」重构为「capability-aware dispatch」,Phase 1 接 image + mesh 双路
- 本地 ComfyUI mesh `pricing: null`(`per_task_usd is None or == 0`)→ 「standard retry」由 `_generate_via_comfy_worker` 内部 loop 用 `policy.max_attempts` 完成(R4-F1 修订:**不是** FailureModeMap 路由 `retry_same_step`;wrapped MeshWorkerTimeout 实际走 `mesh_worker_timeout` → `abort_or_fallback`,与远端 mesh 终态一致;internal retry exhausted = 终止);远端 Hunyuan3D `per_task_usd > 0` → 走 ADR-007 strict no-silent-retry(executor 主流程 attempts=1 强制)
- mesh 路径完整闭环:bundle 上游 image step → DAG → mesh step `_resolve_source_image` → executor 写 in-tree input 文件 → worker subprocess → outputs.glb 解析 → `MeshCandidate(data=bytes, metadata={...})` → `repo.put` 持久化 → `Artifact.metadata["worker_metadata"]` 含 manifest provenance
- **Split 决策落地**:本 design 已输出 audio / video 的 split 结论(本 change 不 land,各自 follow-on),不在 tasks / 实施阶段再扯
- Phase 1 不动 `MeshCandidate` / `ImageCandidate` / `PayloadRef` 任一 dataclass(B1 / B5 锁定)
- Phase 1 不动 `MeshWorker` / `ComfyWorker` ABC 签名(image-mode 仍 `list[ImageCandidate]`,mesh 走 ComfyAgentWorker 新 public 方法 `generate_mesh`)
- Phase 1 同步文档:SRS §7.3 TBD-009 + FR-MODEL-007 + FR-WORKER-001 + HLD ComfyUI 子系统 + ADR-007 边界形式化(`per_task_usd > 0`)+ LLD ComfyAgentWorker / GenerateMeshExecutor 字段 + CHANGELOG + acceptance_report mesh 验收行 + CLAUDE.md mesh smoke 段
- Phase 1 live smoke 在装了 ComfyUI 的本机至少跑一次 mesh manifest(L2 evidence)

**Non-Goals:**

- **不**接 audio / video capability 进本 change(D3 split 决策)
- **不**改远端 Hunyuan3D mesh 接入方式(ADR-007 + image change 已锁定)
- **不**接 ComfyUI lifecycle `ensure_running` / `ensure_release` / `self_managed_session`(TBD-010)
- **不**扩 ProviderDef schema(TBD-011)
- **不**接 `factory_v3` / `blender_pipeline`
- **不**扩 `MeshCandidate` / `ImageCandidate` 字段(provenance 走 metadata dict;B1 锁定)
- **不**扩 `PayloadRef` 字段(`file` / `metadata` 不引入;B1 锁定)
- **不**扩 `MeshWorker` ABC 加 standalone (non-image-source) 模式(本 change 沿用 image-to-mesh,follow-on change 视需要再扩)
- **不**扩 `ComfyWorker` ABC 加 mesh return 类型(mesh 走 ComfyAgentWorker 新 public 方法 `generate_mesh`,不污染 ABC)
- **不**引入 `BudgetTracker.is_premium(route)` 新 API(B3 修订:判定 `pricing.per_task_usd > 0` 由 executor 内联)
- **不**预留 `spec.outputs_kind` 显式字段(D1 决策:capability 由 model id 推断)

## Decisions

### D1 — Capability 由 model id 推断,**不**新增 `spec.outputs_kind` 字段

(与 round 1 一致,未受 codex round 2 影响)

`ComfyAgentWorker` 内部表 `_CAPABILITY_BY_MODEL_ID = {"comfy/local": "image", "comfy/local-mesh": "mesh"}`;构造时从 `model_id` 参数推断 `_capability`;unknown id raise `WorkerUnsupportedResponse`(不 fallback)。bundle 协议保持「`comfy_workflow` + `comfy_params` + `comfy_lifecycle: "none"`」三字段,无 `outputs_kind`。

### D2 — Capability-aware `_validate_outputs` 三段表(round 2 修订)

**Round 1 选项**:`_EXPECTED_OUTPUT_KEY` + `_ALL_OUTPUT_KEYS` 两段表,任何非 expected 的 non-empty 都 raise。

**Round 2 codex finding (B4)**:已归档 image change spec line 157 明确 `02_mini_textured_3d_hunyuan` 同时产 PNG preview + GLB;若 mesh-mode 严格拒绝 `outputs.images`,Phase 1 实施很可能在 `comfyui_api list` 阶段就发现没有「outputs.glb only」的 mesh manifest 可用,abort 风险高。

**Round 2 修订选项:**

- **A:** 保持 round 1 严格拒绝;实施阶段 `comfyui_api list` 找「outputs.glb only」manifest;若无 → abort change
- **B:** 三段表(REQUIRED key + auxiliary key set + rejected key set);mesh-mode `outputs.images` 列入 auxiliary,允许 non-empty 但 worker 不构造 ImageCandidate(显式忽略 + 元信息记日志)

**选 B**,理由:

1. ComfyUI mesh manifest 实际产物形态由 ComfyUI 侧定,框架侧用「严格拒绝」会被 ComfyUI 的现实形态卡死(B4 codex finding 直击)
2. mesh executor 输出是 `MeshCandidate` 列表(本 change 不打算让 ComfyUI mesh 也产 ImageCandidate),`outputs.images` 在 mesh-mode 下是 auxiliary preview,**忽略**就行,不需要塞进任何 candidate 列表
3. 三段表的 fence 表达力强:REQUIRED missing → raise;rejected non-empty → raise;auxiliary non-empty → 不 raise(可在 worker debug log 记一句 `auxiliary outputs.images count=N for diagnostics`)
4. audio / video follow-on change 同模式扩 auxiliary set(例如 mesh-mode 的 `outputs.video_preview` 也属 auxiliary),框架抽象不需要变

具体形式:

```python
class ComfyAgentWorker(ComfyWorker):
    _CAPABILITY_BY_MODEL_ID: dict[str, str] = {
        "comfy/local": "image",
        "comfy/local-mesh": "mesh",
    }
    _REQUIRED_OUTPUT_KEY: dict[str, str] = {
        "image": "images",
        "mesh": "glb",
    }
    _AUXILIARY_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
        "image": set(),                        # image-mode no auxiliary
        "mesh": {"images"},                    # mesh-mode 容忍 PNG preview
    }
    _REJECTED_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
        "image": {"glb", "audio", "video"},
        "mesh": {"audio", "video"},
    }

    def _validate_outputs(self, outputs: dict) -> None:
        cap = self._capability
        required = self._REQUIRED_OUTPUT_KEY[cap]
        if not outputs.get(required):
            raise WorkerUnsupportedResponse(
                f"capability={cap!r} requires non-empty outputs.{required}, got {outputs!r}"
            )
        rejected_present = self._REJECTED_OUTPUT_KEYS_BY_CAP[cap] & {
            k for k, v in outputs.items() if v
        }
        if rejected_present:
            raise WorkerUnsupportedResponse(
                f"capability={cap!r} got rejected non-empty outputs: {sorted(rejected_present)!r}"
            )
        # auxiliary keys: 允许 non-empty 但不消费(worker 仅 mesh REQUIRED key 落 candidate)
```

### D3 — Audio / Video **拆为独立 follow-on change**,本 change 仅接 mesh

(与 round 1 一致,未受 codex round 2 影响)

本 change scope = mesh-only;audio / video 各自开 `comfy-agent-cli-audio-adoption`(blocked-on TBD-002 通用 audio worker 契约)/ `comfy-agent-cli-video-adoption`(blocked-on 输出格式策略决策);umbrella name 保留作 split 决策的归档入口。

### D4 — ADR-007 边界用 `pricing.per_task_usd > 0` 判定(round 2 修订)

**Round 1 选项**:用 `route.pricing.input_cost_per_call >= $0.10` + 提议新 API `BudgetTracker.is_premium(route)`。

**Round 2 codex finding (B3)**:`input_cost_per_call` 字段在现有 pricing schema **不存在**;mesh pricing 用 `per_task_usd`(`config/models.yaml:30, 310`),`BudgetTracker.estimate_mesh_call_cost_usd` 也只读 `per_task_usd`(line 211-232);Hunyuan mesh `per_task_usd: 0.25`。按 round 1 字段实现,远端 Hunyuan3D 永远匹配不到 premium → ADR-007 边界永远 False → 双扣费风险回归(正是 ADR-007 起源 bug)。

**Round 2 修订选项:**

- **A:** 改用现有字段 `pricing.per_task_usd > 0`(简单,与 `estimate_mesh_call_cost_usd` 字段统一)
- **B:** 在 yaml 加显式 `models.<id>.no_silent_retry: true` 标志(显式,但需要扩 schema)
- **C:** 新增 `BudgetTracker.is_premium(route)` API + 复杂判定逻辑

**选 A**,理由:

1. 现有 `estimate_mesh_call_cost_usd(route_pricing.get("per_task_usd"))` 已经把「per_task_usd > 0」隐含等价于「per-call paid」,与 ADR-007 「贵族 API per-call cost」语义自然对齐
2. B 需要扩 ModelDef schema(添加 `no_silent_retry` 字段),与 TBD-011 的 schema 扩展耦合;本 change 想避免 schema 扩展
3. C 引入新 API 表面;判定逻辑简单(`route.pricing.get("per_task_usd", 0) > 0`)直接内联即可,API 抽象不必要
4. 阈值($0.10 round number)之争完全消失:`per_task_usd > 0` 一刀切,本地 mesh `pricing: null` → 0 → 非 premium;远端 Hunyuan `0.25` → premium

**Round 3 R2-F2 implementability 补丁**:`generate_mesh.py:80-81` 现有 `if self.capability_ref == "mesh.generation": attempts = 1` 强制对全 mesh 生效(不分本地 / 远端);本设计的「本地走 standard retry」**不**通过修改 executor 主流程实现(避免回归远端 Hunyuan / Tripo3D 的 ADR-007 enforcement),而是由 `_generate_via_comfy_worker` 内部接管自己的 retry loop(用 `policy.max_attempts`,见 D9)。executor 主流程改动仅限于「`if _should_use_comfy_worker_path(ctx): return _generate_via_comfy_worker(...) (内部已 retry); else: 走原 attempts=1 强制 + retry loop`」。

具体形式:

`provider-routing` spec 的 `Local ComfyUI mesh worker is NOT a premium API per the per_task_usd boundary` Requirement(R2-F2 实施层补充见下方 D9 + 新增 Requirement「ComfyAgentWorker exceptions wrapped to MeshWorker exceptions in _generate_via_comfy_worker」):

> 「premium mesh worker 判定:`route.pricing.per_task_usd > 0`(若 pricing 为 None 或 per_task_usd 缺失,视作 0,即非 premium)。本地 ComfyUI mesh `comfy/local-mesh` 的 `models.comfy/local-mesh.pricing: null` → 非 premium → `GenerateMeshExecutor` 走标准 retry budget。远端 Hunyuan3D `models.hunyuan_3d.pricing.per_task_usd: 0.25` → premium → ADR-007 strict no-silent-retry(`attempts=1`,失败 surface job_id)。判定由 `GenerateMeshExecutor` 内联实现:`is_premium = (route_pricing or {}).get("per_task_usd", 0) > 0`,**不**新增 `BudgetTracker.is_premium` API。」

### D5 — Mesh provenance 走 `MeshCandidate.metadata["worker_metadata"]`(round 2 修订)

**Round 1 选项**:扩 `MeshCandidate.payload.metadata` 或新增 `PayloadRef.metadata` / `PayloadRef.file` 字段。

**Round 2 codex finding (B1)**:`MeshCandidate.payload` **不存在**(实际字段是 `data/format/mime_type/poly_count/has_uv/has_rig/metadata`);`PayloadRef.file` / `PayloadRef.metadata` **不存在**(实际字段是 `kind/inline_value/file_path/blob_key/size_bytes`);`ArtifactRepository.put` 自动把 `cand.data` 写到 `<artifact_root>/<run_id>/<artifact_id>.glb`(用 artifact_id 命名,不保留原文件名)。round 1 spec 的 payload 写法 100% 实施不通。

**Round 2 修订选项:**

- **A:** 沿用现有 `MeshCandidate(data=bytes, metadata={...})` + `repo.put(metadata={"worker_metadata": dict(cand.metadata), ...})`(B1 codex recommendation)
- **B:** 新增 `PayloadRef.metadata` + `PayloadRef.file` 字段(扩 schema,影响所有 worker)
- **C:** 新增 `ArtifactRepository.register_existing_file(path, ...)` API(允许直接注册外部文件)

**选 A**,理由:

1. 与现有 `GenerateMeshExecutor.execute` 流程**完全一致**(generate_mesh.py:117-158 已经在用 `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=...)` + `metadata={"worker_metadata": dict(cand.metadata)}`)— 沿用 = 零代码增量在 executor 侧
2. B 扩 PayloadRef schema 影响范围远超本 change(touches 全部 worker / artifact path),违反「change scope 应可在 1-2 周内完成」原则
3. C 的 register-existing-file API 看似自然(避免 bytes 双拷贝),但破坏 `repo.put` 的 hash idempotent + lineage 一致性保证;且本 change 是 first-mover,设计 API 又没有第二个 caller 来证明抽象合理性
4. 文件名约定从「保留 ComfyUI 原文件名」改为「`repo.put` 自动用 `<artifact_id>.glb`」是可接受的退让:`ComfyAgentWorker.generate_mesh` 把 ComfyUI 原始文件名记到 `MeshCandidate.metadata["comfy_original_filename"]`,后续诊断仍可追溯

具体形式:

```python
# ComfyAgentWorker.generate_mesh 返回:
return [
    MeshCandidate(
        data=Path(comfy_glb_path).read_bytes(),
        format="glb",
        mime_type="model/gltf-binary",
        metadata={
            "comfy_manifest": spec["comfy_workflow"],
            "comfy_params_snapshot": dict(spec.get("comfy_params") or {}),
            "comfy_capability": "mesh",
            "comfy_original_filename": Path(comfy_glb_path).name,
        },
    )
    for comfy_glb_path in outputs["glb"]
]

# GenerateMeshExecutor._generate_via_comfy_worker 调用 worker 后:
# 直接把 candidates 喂给原 executor 的 repo.put 循环(line 114-160),
# 现有 metadata={"worker_metadata": dict(cand.metadata), ...} 自动包含 comfy provenance
```

### D6 — Live smoke manifest 名 deferred(round 2 微调)

(与 round 1 接近,B4 修订后增加要求)

实施 tasks §1.2 跑 `comfyui_api list` 拿真实 mesh manifest 列表,选一个产 `outputs.glb`(可能同时产 `outputs.images` preview,B4 修订已容忍)的 manifest 作为 live smoke 目标。**B4 修订后,manifest 不必是「`outputs.glb` only」**,只要 REQUIRED `outputs.glb` non-empty,auxiliary `outputs.images` 容忍。

**Round 2 新增要求**:tasks §1.5 加「跑 `comfyui_api params --workflow <选定 manifest>` 探明 source image input 参数 key 名(常见为 `image_path` / `input_image` / `image`),作为 §4.2 `_generate_via_comfy_worker` 的 `comfy_params[<image_param_key>]` 注入目标」。若选定 manifest 不接受 image input(纯文本 prompt → mesh),则**降级**为 D7 备选路径(见下)。

### D7 — Comfy mesh 走 image-to-mesh,executor **不**短路 `_resolve_source_image`(round 2 新增)

**Round 2 codex finding (B2)**:`GenerateMeshExecutor.execute` line 67 无条件 `_resolve_source_image(ctx)`,line 90 把 `source_image_bytes=source_bytes` 传 worker;`MeshWorker.generate` ABC 签名要求 `source_image_bytes: bytes`(`mesh_worker.py:86`)。round 1 spec / tasks 没说 ComfyUI mesh 是 image-to-mesh 还是 standalone manifest;若 standalone,executor 在 worker 调用前就 raise。

**选项:**

- **A:** ComfyUI mesh 沿用 image-to-mesh 路径;bundle 含上游 image step + DAG 依赖;executor 不短路 `_resolve_source_image`,而是把 `source_bytes` 写入 in-tree input 文件,把 path 注入 `comfy_params[<image_key>]`;调 worker 新方法 `generate_mesh(spec, source_image_path, ...)`
- **B:** ComfyUI mesh 走 standalone manifest(纯文本 prompt → mesh,无 source image);executor 加 `if _should_use_comfy_worker_path(ctx): skip _resolve_source_image` 短路;worker `generate_mesh(spec, ...)` 不接 source_image
- **C:** 给 `MeshWorker` ABC 加 standalone 模式(扩 `source_image_bytes: bytes | None = None`),Hunyuan / Tripo3D 仍要求 source image,ComfyAgentWorker 视 manifest 决定

**选 A**,理由:

1. 与 Hunyuan / Tripo3D mesh worker **模式一致**:framework 侧 mesh executor 已经 mature 支持 image-to-mesh 流程(包括 `_resolve_source_image` 的 verdict / selected_set / candidate_set / direct image 4-pass priority,见 generate_mesh.py:233-301);本 change 走 A 方案 = 零 executor 流程变化,只加 worker 分支
2. ComfyUI 实际 mesh manifest 大多是 image-to-mesh(`02_mini_textured_3d_hunyuan` 等需要 input image 才能生成 textured 3D),standalone 文本生 mesh 是少数派
3. B 的短路逻辑会让 mesh executor 内部分两种 lineage 表达(有 source / 无 source),Artifact lineage 一致性被破坏;且 `Lineage(source_artifact_ids=[], transformation_kind="image_to_3d")` 语义自相矛盾(image_to_3d 但无 source image)
4. C 扩 ABC 影响 Hunyuan / Tripo3D 现有契约,scope 远超本 change;若未来确实需要 standalone mesh worker,可在 follow-on change 中扩 ABC,本 change 不前置

具体形式(executor 侧):

```python
# generate_mesh.py:execute 流程(round 2 修订后)
def execute(self, ctx: StepContext) -> ExecutorResult:
    spec = self._resolve_spec(ctx)
    cfg = ctx.step.config
    source_bytes, source_image_artifact_id = _resolve_source_image(ctx)  # 不动

    if self._should_use_comfy_worker_path(ctx):
        candidates = self._generate_via_comfy_worker(
            ctx=ctx,
            spec=spec,
            source_image_bytes=source_bytes,            # B2 修订:仍接收 source_bytes
            source_image_artifact_id=source_image_artifact_id,
            num=num,                                    # R3-F3 修订:cfg 是 dict,沿用 executor 已有局部变量 num
            seed=cfg.get("seed"),                       # R3-F3 修订:cfg.get(...)
            timeout_s=timeout_s,                        # R3-F3 修订:沿用 executor 已有局部变量 timeout_s
        )
    else:
        # 现有 Hunyuan / Tripo3D 路径不变(走 self._worker.generate 注入 worker)
        candidates = ...

    # 后续 repo.put 循环(line 104-160)对 candidates 类型不敏感,所有 mesh worker
    # 共用同一持久化路径(D5 修订)
```

具体形式(worker 侧):

```python
# comfy_worker.py ComfyAgentWorker
def generate_mesh(
    self,
    *,
    spec: dict[str, Any],
    source_image_path: Path,           # round 2 D7:source bytes 已由 executor 写入 in-tree 文件
    num_candidates: int = 1,
    seed: int | None = None,
    timeout_s: float | None = None,
) -> list[MeshCandidate]:
    """Mesh 路径专用 public 方法,**不**走 ComfyWorker ABC `generate`(后者返回 ImageCandidate)。

    round 2 D7 修订:source_image_path 由 executor 写入 in-tree 文件(`<run_dir>/comfy/input/<sha1>.png`)
    后传入;worker 在 spec.comfy_params 中注入 image path key(具体 key 名由 manifest schema 决定)。
    """
    if self._capability != "mesh":
        raise WorkerUnsupportedResponse(...)
    enriched_spec = dict(spec)
    enriched_params = dict(spec.get("comfy_params") or {})
    image_key = self._infer_image_param_key(spec.get("comfy_workflow"))  # 见 D8
    enriched_params[image_key] = str(source_image_path)
    enriched_spec["comfy_params"] = enriched_params

    outputs = self._run_subprocess_and_validate(enriched_spec, timeout_s=timeout_s)
    # _validate_outputs 在 _run_subprocess_and_validate 内部 capability-aware,
    # mesh-mode 要求 outputs.glb non-empty,容忍 outputs.images,拒绝 audio/video
    return [
        MeshCandidate(
            data=Path(p).read_bytes(),
            format="glb",
            mime_type="model/gltf-binary",
            metadata={
                "comfy_manifest": spec["comfy_workflow"],
                "comfy_params_snapshot": enriched_params,
                "comfy_capability": "mesh",
                "comfy_original_filename": Path(p).name,
                "comfy_source_image_path": str(source_image_path),
            },
        )
        for p in outputs["glb"]
    ]
```

### D9 — ComfyWorker 异常 wrap 为 MeshWorker 异常 + 本地 mesh 自带 retry loop(round 3 新增,R2-F2 修订)

**Round 2 codex finding R2-F2**:`generate_mesh.py:80-81` 对全 `mesh.generation` 强制 `attempts=1`(本地也被强制);`generate_mesh.py:95` 只 catch `(MeshWorkerTimeout, MeshWorkerError)`,不 catch ComfyWorker 异常族 `WorkerTimeout/WorkerError/WorkerUnsupportedResponse`。round-2 spec 说本地 mesh 走 standard retry 在 implementability 层完全不可达。

**选项:**

- **A:** 改造 executor `execute()`:把 `attempts=1` 强制改为「按 pricing 判定」+ catch 两套异常族;worker dispatch 走统一 retry loop
- **B:** `_generate_via_comfy_worker` **自带内部 retry loop**(本地 mesh 用 `policy.max_attempts` + 自己 backoff);ComfyWorker 异常 wrap 为 MeshWorker 异常 后 raise(让 `FailureModeMap` 看到正确异常类型);executor `execute()` 只在 worker dispatch 之外保留原 attempts=1 强制(对远端 mesh 仍生效)
- **C:** ComfyAgentWorker 实装 `MeshWorker` ABC 接口(冒充 mesh worker)被注入 `_worker`;executor 完全不改

**选 B**,理由:

1. A 要改 executor 全 mesh.generation 路径,影响远端 Hunyuan / Tripo3D 现有契约(回归风险高);本 change scope 应限于 comfy mesh 路径
2. C 要让 ComfyAgentWorker 实装 `MeshWorker.generate(source_image_bytes=..., ...)` ABC 签名,但 ComfyAgentWorker 已经有 image-mode `generate(spec=..., num_candidates=..., ...) -> list[ImageCandidate]`(ComfyWorker ABC),签名冲突无法两继承
3. B 把所有 comfy mesh 特有逻辑(retry / 异常 wrap / source bytes 写入)集中在 `_generate_via_comfy_worker`,executor 主流程完全不动远端路径;改动范围小、可逆性强、与 ADR-007 边界判定(`per_task_usd > 0`)自然耦合(本地 retry 由本地分支自管,远端 retry 由原 executor 分支自管)

具体形式:

```python
# generate_mesh.py:_generate_via_comfy_worker(round 3 实装)

from framework.providers.workers.comfy_worker import (
    WorkerError as _ComfyWorkerError,
    WorkerTimeout as _ComfyWorkerTimeout,
    WorkerUnsupportedResponse as _ComfyWorkerUnsupportedResponse,
)

def _generate_via_comfy_worker(self, *, ctx, spec, source_image_bytes,
                               source_image_artifact_id, num, seed, timeout_s):
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        raise MeshWorkerUnsupportedResponse(
            "FORGEUE_COMFY_SCRIPTS_DIR env var unset; ..."
        )

    # source bytes → in-tree input 文件(idempotent via sha1)
    input_dir = ctx.run_dir / "comfy" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    sha1_hex = hashlib.sha1(source_image_bytes).hexdigest()[:16]
    input_path = input_dir / f"{sha1_hex}.png"
    if not input_path.exists():
        input_path.write_bytes(source_image_bytes)

    python_exe = os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None
    lifecycle = os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none")
    worker = ComfyAgentWorker(
        scripts_dir=Path(scripts_dir),
        model_id="comfy/local-mesh",
        run_id=ctx.run.run_id,
        project_id=ctx.task.project_id,
        artifacts_dir=ctx.run_dir,
        python_exe=Path(python_exe) if python_exe else None,
        default_lifecycle=lifecycle,
    )

    # 本地 comfy mesh 走 standard retry budget(pricing=None → not premium → 不强制 attempts=1)
    policy = ctx.step.retry_policy or RetryPolicy()
    attempts = max(1, policy.max_attempts)
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            candidates = worker.generate_mesh(
                spec=spec, source_image_path=input_path,
                num_candidates=num, seed=seed, timeout_s=timeout_s,
            )
            return candidates
        except _ComfyWorkerTimeout as exc:
            wrapped = MeshWorkerTimeout(str(exc))         # 异常族 wrap
            last_exc = wrapped
            if attempt + 1 >= attempts or not _should_retry(policy, wrapped):
                raise wrapped from exc
            _backoff(policy, attempt)
        except _ComfyWorkerUnsupportedResponse as exc:    # 不 retry
            raise MeshWorkerUnsupportedResponse(str(exc)) from exc
        except _ComfyWorkerError as exc:                  # 不 retry(同 _should_retry 默认)
            raise MeshWorkerError(str(exc)) from exc
    assert last_exc is not None
    raise last_exc
```

executor `execute()` 主流程改动最小,只在原 `if self.capability_ref == "mesh.generation": attempts = 1` 之前先判分支:

```python
if self._should_use_comfy_worker_path(ctx):
    candidates = self._generate_via_comfy_worker(
        ctx=ctx, spec=spec,
        source_image_bytes=source_bytes,
        source_image_artifact_id=source_image_artifact_id,
        num=num,                              # R3-F3 修订:cfg 是 dict
        seed=cfg.get("seed"),
        timeout_s=timeout_s,
    )
    # 跳过 line 80-81 attempts=1 强制 + line 86-99 retry loop(本地 retry 由 _generate_via_comfy_worker 内部完成)
else:
    # 现有远端 mesh 路径:attempts=1 强制 + line 86-99 retry loop catch (MeshWorkerTimeout, MeshWorkerError)
    policy = ctx.step.retry_policy or RetryPolicy()
    attempts = max(1, policy.max_attempts)
    if self.capability_ref == "mesh.generation":
        attempts = 1
    # ... 原 line 86-99 retry loop ...
```

异常族 wrap 让 `FailureModeMap.resolve(MeshWorkerTimeout(...))` 走标准 mesh worker 路径,与远端 Hunyuan / Tripo3D 行为一致;executor 之外的代码(orchestrator / FailureModeMap / BudgetTracker)对 ComfyWorker vs MeshWorker 无感知。

### D8 — Source image param key 推断:实施阶段对照 manifest schema 确认(round 2 新增)

**问题**:不同 ComfyUI mesh manifest 的 source image input 参数 key 名不同(`image_path` / `input_image` / `image` / `source_image` 等);worker 需要在哪里决定注入哪个 key?

**选项:**

- **A:** Worker 内部表 `_IMAGE_PARAM_KEY_BY_MANIFEST: dict[str, str]`(每个 mesh manifest 名 → image key),实施阶段对照 `comfyui_api params` 输出填表
- **B:** Bundle 显式声明 `spec.comfy_image_param_key: "<key>"`,worker 读取
- **C:** Worker 启动时调 `comfyui_api params --workflow <manifest>` 拿 schema,自动检测 image-typed 参数

**选 B**,理由:

1. A 的内部表会与 ComfyUI 侧 manifest 命名 / 参数变更紧耦合,manifest 重命名 / 加新 manifest 都要改 worker 源码
2. C 的运行时 schema 检测增加 ~1s 启动开销,且 ComfyUI agent CLI `params` 输出格式 ForgeUE 没有稳定 parser
3. B 把 image key 决策推到 bundle(谁知道 manifest 谁声明),框架不感知 manifest 内部参数语义;bundle 一处改,worker 零变化
4. 默认值:若 `spec.comfy_image_param_key` 缺失,worker 用 `"image_path"`(常见 ComfyUI mesh manifest 的 default key 名,实施 §1.3 探明确认)

具体形式:

```python
def _infer_image_param_key(self, manifest_name: str | None, spec: dict) -> str:
    return spec.get("comfy_image_param_key") or "image_path"
```

bundle 示例:

```json
{
  "spec": {
    "comfy_workflow": "Mesh/02_mini_textured_3d_hunyuan",
    "comfy_params": { "seed": 42 },
    "comfy_image_param_key": "image_path",
    "comfy_lifecycle": "none"
  }
}
```

实施 §1.3 跑 `comfyui_api params --workflow <选定 manifest>` 时若发现 image key 不是 `image_path`(例如 `input_image`),example bundle `comfy_image_param_key` 字段写 `"input_image"`。

## Risks / Trade-offs

- **[Risk] ComfyUI scripts/ 下没有可用的 mesh manifest** → Mitigation:tasks §1.2 跑 `comfyui_api list` 探明;若无 mesh manifest,本 change abort + SRS §7.3 TBD-009 行降级为「ComfyUI agent CLI 长期 image-only,mesh 走 Hunyuan3D / Tripo3D」
- **[Risk] B4 修订后 mesh-mode auxiliary `outputs.images` 不被 framework 消费,用户可能期望看到 PNG preview** → Mitigation:worker 在 `_run_subprocess_and_validate` 内部 debug log 「auxiliary outputs.images count=N at <path>」;preview 文件仍在 ComfyUI 原始 outputs 目录(`D:/AI/ComfyUI/outputs/main/<date>/<project>/`),用户可手工查;若强需求,follow-on change 加「auxiliary preview 也落 artifact」
- **[Risk] D7 image-to-mesh 路径要求 bundle 含上游 image step,但 ComfyUI 自家有些 manifest 是 standalone 文生 mesh** → Mitigation:本 change 不支持 standalone(D7 决策已说明);若 §1.2 选定 manifest 是 standalone,要么换一个 image-to-mesh manifest,要么 abort change;若 standalone 是真实需求,follow-on change 给 `MeshWorker` ABC 加 standalone 模式
- **[Risk] D8 `comfy_image_param_key` 默认 `"image_path"` 与选定 manifest 实际 key 不符** → Mitigation:tasks §1.3 强制要求实施阶段确认 key 名,bundle 显式写;若不写也用 default,subprocess 会因为 `Missing required param` raise → `WorkerUnsupportedResponse`,fail-fast 不静默
- **[Risk] D5 不保留 ComfyUI 原文件名,长期诊断「这个 GLB 来自哪个 manifest 哪次跑」靠 metadata** → Mitigation:`Artifact.metadata["worker_metadata"]` 含 `comfy_manifest` / `comfy_params_snapshot` / `comfy_original_filename` / `comfy_source_image_path` 4 key,信息密度大于 round 1 的「文件名记录」方案
- **[Risk] D4 `per_task_usd > 0` 一刀切判定,假如未来某 provider 用 `pricing.per_token_usd` 等其它字段(非 mesh per-call),边界判定漏判** → Mitigation:本 change scope 只覆盖 mesh capability;其它 capability(image / audio / video)的 ADR-007 边界由 follow-on change 各自定义
- **[Trade-off] D5 `repo.put` 用 `<artifact_id>.glb` 命名,不保留 ComfyUI 原文件名** → 接受:与现有 mesh executor 命名约定一致(Hunyuan / Tripo3D 同样不保留远端文件名),`worker_metadata.comfy_original_filename` 提供回溯
- **[Trade-off] D7 沿用 image-to-mesh 路径,bundle 必须含上游 image step,看似比 standalone manifest 配置复杂** → 接受:image-to-mesh 是 mesh worker 的主流模式(Hunyuan / Tripo3D 均如此),standalone 是少数派 + 设计成本远高于复用现有路径

## Migration Plan

(round 2 微调:沿用 D5 现有 `repo.put` 流程,不动 PayloadRef schema)

1. **bundle 协议**:`comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段不变;**新增可选字段** `comfy_image_param_key`(D8,缺省 `"image_path"`);bundle 必须含上游 image step + DAG 依赖(D7)
2. **`config/models.yaml`**:Phase 1 新增 `models.comfy/local-mesh` + `aliases.mesh_local`;`providers.comfy_api` 不动
3. **环境变量**:`FORGEUE_COMFY_*` 完全复用,无新 env var
4. **Rollback 策略**:本 change 全部改动通过 git revert 单 commit 回退;`comfy/local-mesh` model + `mesh_local` alias 移除后,任何引用它们的 bundle 立即 fail-fast(loader 报 unknown alias)
5. **tests/integration/ 现有用例**:不受影响(image-mode fence 全保留;新 mesh fence 加在 `tests/unit/test_comfy_subprocess.py` + `tests/unit/test_generate_mesh.py`)
6. **Follow-on change 衔接**:本 change archive 后,audio / video follow-on change 直接复用本 change 的 capability dispatch + 三段表 + ADR-007 边界判定模式

## Open Questions

> design 阶段以下问题已决议(✅);实施阶段需再确认(🔍)。

- ✅ Q1 capability dispatch 走 model id 推断 → D1
- ✅ Q2 守门 = 三段表(REQUIRED / auxiliary / rejected)→ D2(round 2 修订)
- ✅ Q3 scope split → D3 mesh-only
- ✅ Q4 ADR-007 边界 = `pricing.per_task_usd > 0` → D4(round 2 修订)
- ✅ Q5 `MeshCandidate` 不扩字段,provenance 走 metadata → D5(round 2 修订)
- ✅ Q6 live smoke manifest 名 → D6 实施阶段动态确认
- ✅ Q7 ComfyUI mesh = image-to-mesh,bundle 含上游 image step → D7(round 2 新增)
- ✅ Q8 source image param key bundle 显式声明 + 默认 `"image_path"` → D8(round 2 新增)
- 🔍 Q9 ComfyUI stdout 是否暴露 vertex / face count → 实施 tasks §1.5 探明;不暴露则 `MeshCandidate.poly_count = None`(沿用 dataclass default,worker 不引入 `pygltflib`)
- 🔍 Q10 选定 mesh manifest 实际 image param key 是否 `"image_path"` → 实施 tasks §1.3 跑 `comfyui_api params --workflow <manifest>` 确认;若不是,example bundle `comfy_image_param_key` 字段写实际 key
- 🔍 Q11 `tests/integration/` 是否需要新 mesh ComfyUI 端到端 fence,还是 unit fence 已足够 → 实施阶段读现有 P3 测试结构后决定;倾向新建独立 unit fence 文件,集成层 fence 视 §7 live smoke 是否需要 CI 重放决定
