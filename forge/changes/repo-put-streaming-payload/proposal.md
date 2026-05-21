# `repo-put-streaming-payload` —— `repo.put` zero-copy 接口 + stream hashing(Phase 1 铺接口)

## Why

当前 `framework.artifact_store.repository.ArtifactRepository.put()` 接收 `value: Any`,
所有 `file` payload kind 路径都走 `FileBackend._coerce_bytes(value)` → 全量驻留内存 →
`abs_path.write_bytes(data)`。同期 `framework.artifact_store.hashing.hash_payload(value)`
也走 `_canonicalize(value)` → bytes → `hashlib.sha256(bytes)` 全量内存。

这意味着每次落 video / mesh / audio / image candidate 时存在一次完整内存驻留;
`load_run_metadata` 里的 hash drift 校验(`hash_payload(read(ref))`)在 resume 大文件
artifact 时也是全读 → 全 hash。

**理论受益场景**(按 candidate 体量排序;但**本 change Phase 1 不直接迁移这些路径,
见 §What 第 8 条 Phase 边界**):
- **video mp4**(`generate_video.py:131`)— Wan 2.1 1.3B 5sec 输出 **5–15 MB**(实测 L2),
  Wan 2.2 A14B / 14B 路径数十 MB。`FILE_MAX_BYTES = 500 MB` 给的余量是为后续 V2V / 长片 +
  follow-on `comfy-video-image-sequence-adoption` 高品质路径预留的(D1 (α))。
- **mesh GLB**(`generate_mesh.py:269`)— Hunyuan3D mini-LoadImage 路径实测 ~3.5 MB,
  Hunyuan3D v2.1 完整路径 / Tripo3D 远端路径 10 MB+。
- **audio FLAC / mp3 / wav**(`generate_audio.py:128`)— Stable Audio Open / ACE-Step
  几 MB。
- **image png**(`generate_image.py:144` / `generate_image_edit.py:115`)— 几 MB。

**Phase 边界声明**(F2 codex finding writeback):本 change Phase 1 目标是
**「为 zero-copy 落盘 + stream hashing 铺接口能力」**,不直接交付 video / mesh / audio
/ image executor 的 user-visible 内存收益 —— 这 5 个 generator 仍走 `repo.put(value
=cand.data)`(由于 `AudioCandidate / ImageCandidate / MeshCandidate / VideoCandidate`
全部用 `data: bytes` 字段,ComfyUI agent CLI 路径已经 `Path.read_bytes()` 把 source
path 信息在 worker 层就丢了)。**Phase 2 follow-on `worker-candidate-source-path-
migration`** 完成 Worker / Candidate `source_path` 字段 + 5 个 executor 调用站点迁
移后,接口才被生产路径消费,user-visible 内存收益才落地。

backlog 入口:`forge/backlog/active.md` `LR-0134` / **TBD-012** —— 标注为
`enhance-workflow-automation-runtime-enforcement` D4 副作用 follow-on。

## What

1. **`PayloadRef` 数据契约保留**:`kind / inline_value / file_path / blob_key /
   size_bytes` 字段不变;**仅** API 与 backend 内部实现演进。
2. **`repo.put` 扩展接 zero-copy 路径**:新增可选参数 `source_path: str | Path | None
   = None`,与 `value` 二选一(基于 `_MISSING` sentinel identity 比较,允许 value=None
   合法 inline JSON null payload — D10)。当传 `source_path` 且 `payload_kind ==
   PayloadKind.file` 时,走 `shutil.copyfile` 到同目录 tmp + `os.chmod(tmp, 0o644)`
   权限归一化(R5-F4)+ `os.replace(tmp, dest)` 原子替换 dest 不全量读入内存
   (D4 D-Atomic);`size_bytes` 走 dest stat、`hash` 走 `hash_path(dest)` stream
   实现(D9 D-HashSource-vs-Dest 同源 invariant)。
   API 选项(A 双参 / B 新增 `put_from_path` / C union 自动 dispatch)三选一,由
   `design.md` 显式拍板(D1 选 A)。
3. **stream hashing 同期实装**:`framework.artifact_store.hashing` 新增 `hash_path(path,
   *, chunk_size=8*1024*1024) -> str`(`chunk_size <= 0` raise ValueError —
   R4-F4);`hash_payload(value)` 既有 value 路径保留(inline backend / 18 处
   `repo.put` 中 13 处 inline payload 都还走它)。
4. **`FileBackend.write` 扩展接 source_path**:`_coerce_bytes` 仅在 value 路径走;
   `source_path` 路径走 `stat.S_ISREG` regular file guard(R4-F3)+ pre-copy
   `Path.stat().st_size` + `FILE_MAX_BYTES` cap fail-fast + `shutil.copy2(src, tmp)`
   + post-copy dest size guard + `os.replace(tmp, abs_path)` 原子替换 dest +
   异常清理 tmp(D4 R4-F1 atomic write)。
5. **`load_run_metadata` hash drift 校验改 stream**:**仅** `file` kind 走
   `hash_path(backend.absolute_path(ref))` 而非 `hash_payload(read(ref))`。
   `blob` kind 保旧行为(`hash_payload(read(ref))` — BlobBackend stub 未实装,既
   有逻辑已通过 `except Exception: continue` 兜底,本 change 不动 blob 路径,
   blob stream drift 留 follow-on `blob-backend-streaming-implementation`)。
   `inline` kind **既有行为完全保留:不做 drift 校验,直接 `register_existing`**
   (R4-F2 D-InlineDriftNonGoal:`_artifacts.json` 中 inline payload 跟元数据一起
   序列化,inline payload 没有外部 bytes 可漂移;若 metadata file 本身被改但
   hash 未更新,这是 metadata corruption 范畴,不是 payload drift,本 change scope 不
   覆盖,留 follow-on `metadata-corruption-detection`)。
6. **5 处 file generator 是否同步迁移 worker 层 → executor → `repo.put(source_path=)`**:
   由 design.md `D-WorkerCandidateMigration` 拍板(Phase 1 仅 backend / API,Phase 2 留
   follow-on `worker-candidate-source-path-migration` 改 Candidate.source_path);本 change
   默认走 **Phase 1**。
7. **回归测试**:新增 `tests/unit/test_repo_put_streaming.py` + 扩
   `test_artifact_store.py` + 扩 `test_payload_backends.py`,守门 zero-copy 路径正确性 +
   stream hash 与 value hash 等价性 + cap 校验 + drift detect。

成功判定标准(Phase 1 范围,**不**含 user-visible 内存收益 — 留 Phase 2):
- **接口能力 fence**(opt-in,`FORGEUE_RUN_HEAVY_FENCE=1` heavy fence):
  `repo.put(source_path=...)` 路径在 200 MB 测试文件上 RSS 增量 < **32 MB**(单一阈值,
  与 `specs/probe-and-validation.md` `## Requirement: zero-copy RSS 增量 fence` 对齐;
  archive 前必须附本地跑过的 heavy fence 输出 + 机器环境说明作 evidence)
- **stream / value 等价性 fence**(默认 `pytest -q` 跑):`hash_path(p)` 在所有现有
  file payload 上与 `hash_payload(read_bytes(p))` 输出完全一致
- **hash / size_bytes 同源 invariant**(F1 codex writeback):`Artifact.hash ==
  hash_path(dest)` 且 `PayloadRef.size_bytes == Path(dest).stat().st_size`,两者都
  来自最终落盘 dest 文件,**不**来自 caller 传入的 source 文件(避免 source 在 stat
  / copy / hash 三阶段间被并发改导致漂移)
- 现有 1190+ pytest baseline 不回退
- 5 处 file generator 单测 / 集成测全绿(Phase 1 不动 worker / executor 调用站点,
  保持向后兼容;本 change ship 后 user-visible 表现完全无差异 — 这是预期,不是缺陷)

## Scope

In-scope:
- `src/framework/artifact_store/repository.py` —— `ArtifactRepository.put`,
  `load_run_metadata` hash drift 校验
- `src/framework/artifact_store/hashing.py` —— 新增 `hash_path`
- `src/framework/artifact_store/payload_backends/base.py` —— `PayloadBackend.write`
  ABC 签名演进(加 keyword-only `source_path`)
- `src/framework/artifact_store/payload_backends/file_backend.py` —— `FileBackend.write`
  zero-copy 分支
- `tests/unit/test_artifact_store.py` / `tests/unit/test_payload_backends.py` /
  新增 `tests/unit/test_repo_put_streaming.py`
- 文档同步:`docs/design/LLD.md` §F0-3(PayloadRef + Repository)/ `docs/design/HLD.md`
  §D.2(payload backend layout)/ `docs/testing/test_spec.md` 加 fence 用例 /
  `docs/requirements/SRS.md` 若有相关 FR 引用

## Out of Scope {#forge-oos}

```yaml
schema: forge-scope-entries/v1
anchor_id: forge-oos
entries:
    - id: inline-blob-backend-streaming
      category: out-of-scope
      description: |
        InlineBackend 与 BlobBackend 的 stream / zero-copy 改造。
      reason: |
        InlineBackend 限 64 KB cap,inline payload 本质就是嵌入到 PayloadRef
        随 Artifact 元数据流转(JSON 序列化),无 file 系统侧落盘 → zero-copy
        无意义;BlobBackend MVP 未实装(NotImplementedError stub),先实装 stream
        路径只会增加未来 S3 / MinIO 适配成本。
      priority: low
      status: active
      triggered_by: null
      related_change: null
    - id: metadata-corruption-detection
      category: out-of-scope
      description: |
        `_artifacts.json` metadata file 本身被改(inline payload bytes 与 hash
        漂移、artifact_id 重命名、payload_ref schema downgrade 等)的检测与恢复。
      reason: |
        本 change 仅做 file kind 外部 payload bytes 的 drift 校验(stream
        改造),inline payload 跟 metadata 一起序列化,无外部 bytes 可漂移
        (R4-F2 D-InlineDriftNonGoal)。metadata 自身完整性(JSON 签名 / hash
        chain / Pydantic schema_version 兼容)是独立子问题,需配合 LiveMarker /
        SignedManifest 等,scope 远超本 change。
      priority: low
      status: active
      triggered_by: null
      related_change: null
    - id: dryrunpass-lineage-variant-streaming
      category: out-of-scope
      description: |
        DryRunPass / Lineage / VariantTracker 等 artifact_store 周边模块改造。
      reason: |
        这些模块只引用 Artifact 元数据(artifact_id / hash / payload_ref),
        不读写 payload bytes;与 zero-copy 收益场景零交集。
      priority: low
      status: active
      triggered_by: null
      related_change: null
    - id: worker-candidate-source-path-migration
      category: out-of-scope
      description: |
        Worker layer(AudioWorker / ImageWorker / MeshWorker / VideoWorker /
        ComfyAgentWorker)的 Candidate dataclass 扩 `source_path` 字段 + 5 处
        executor 迁移到 `repo.put(source_path=...)` 路径。
      reason: |
        本 change Phase 1 仅做 backend / API 改造,Worker / Candidate 协议保留
        `data: bytes` 不变。迁移 Worker 层需要触及 ComfyUI agent CLI 输出解析
        (现在直接读到 bytes 丢弃 source path)+ 5 处 executor 调用站点 + Audio
        / Mesh / Video / Image worker 单测全套,scope 超 1 个 change 边界。
        Phase 2 follow-on `worker-candidate-source-path-migration` 处理。
      priority: medium
      status: active
      triggered_by: null
      related_change: null
```

## Non-Goals {#forge-non-goals}

```yaml
schema: forge-scope-entries/v1
anchor_id: forge-non-goals
entries:
    - id: change-payload-ref-schema
      category: non-goal
      description: |
        改 PayloadRef 字段结构(增 / 删 / 重命名 kind / file_path / inline_value
        / blob_key / size_bytes 之一)。
      reason: |
        PayloadRef 是 Artifact 序列化契约的一部分,改它会破坏所有持久化的
        `_artifacts.json` 与下游 resume / checkpoint 兼容。zero-copy 完全可在
        既有契约上通过 API 层与 backend 内部实现达成;无需契约变更。
      priority: null
      status: active
      triggered_by: null
      related_change: null
    - id: increase-file-max-bytes-cap
      category: non-goal
      description: |
        把 `FILE_MAX_BYTES = 500 * 1024 * 1024` 上限调高(到 1 GB / 2 GB / 无 cap)。
      reason: |
        500 MB cap 是 §D.2 既定边界,zero-copy 收益场景是「常见 5–50 MB 文件下
        减少一次内存驻留」,不是「支持更大文件」;改 cap 需要单独评估 UE 端
        import / disk 占用 / 网络传输影响,scope 完全不重叠。
      priority: null
      status: active
      triggered_by: null
      related_change: null
    - id: introduce-async-io
      category: non-goal
      description: |
        把 `FileBackend.write` / `hash_path` 改成 async(`aiofiles` /
        `asyncio.to_thread`)。
      reason: |
        TBD-010 executor-async-rewrite 已经把 executor 转 async-native;
        `repo.put` 是 executor 内 await 链中的同步小段(IO-bound,但 stream copy
        即使阻塞也不超过几百毫秒)。引入 aiofiles 增加依赖面 + 与同步
        `hash_payload` 不一致,先保持同步实现。
      priority: null
      status: active
      triggered_by: null
      related_change: null
```

## 影响模块

**核心改动**:
- `src/framework/artifact_store/repository.py` — `put()` 签名扩 `source_path` +
  `_MISSING` sentinel + 哈希分两路;`load_run_metadata` 中 file kind drift 走 stream
- `src/framework/artifact_store/hashing.py` — 新增 `hash_path(path, *, chunk_size)`
- `src/framework/artifact_store/payload_backends/base.py` — `PayloadBackend.write`
  ABC 签名加 `source_path` keyword + 新增 `absolute_path` 抽象方法 + 顶层导出 `_MISSING`
  sentinel;`PayloadBackendRegistry.write` 透传 keyword
- `src/framework/artifact_store/payload_backends/file_backend.py` — `write()` 增
  zero-copy 分支(pre/post-copy cap 校验 + size_bytes 取 dest stat 同源)+ 实装
  `absolute_path`

**ABC 跟进改动**(In-scope,签名同步必需):
- `src/framework/artifact_store/payload_backends/inline_backend.py` — `write` 签名
  加 `source_path` 参数 + raise ValueError(非 file backend 不支持 source_path);
  `absolute_path` raise ValueError(inline 无外部路径)。**不**做 stream / zero-copy 内
  部实现(沿 Out of Scope `inline-blob-backend-streaming`)
- `src/framework/artifact_store/payload_backends/blob_backend.py` — 同款 ABC 签名
  跟进 + raise;`absolute_path` raise NotImplementedError(stub 与 `write` 一致语义)。
  drift 校验 blob kind 保旧行为(本 change 不改 BlobBackend 内部,留 follow-on
  `blob-backend-streaming-implementation`)

**不影响**:
- `src/framework/artifact_store/lineage.py` / `variant_tracker.py`(不读写 payload bytes)
- 18 处既有 `repo.put` 调用站点(向后兼容,`_MISSING` sentinel 保 18 处行为完全等价)
- `src/framework/providers/workers/` Worker / Candidate 协议(Phase 1 不动,留
  follow-on `worker-candidate-source-path-migration`)
- `src/framework/runtime/executors/` 5 个 file generator 调用站点(Phase 1 行为完全
  无变化)
