# `repo-put-streaming-payload` 设计文档

## 1. 背景与目标

backlog 入口:`forge/backlog/active.md` LR-0134 / TBD-012 —— D4 副作用 follow-on,
针对 `ArtifactRepository.put` 与 `FileBackend.write` 在大文件 payload(video / mesh /
audio / image)上的两个内存驻留点:
1. `_coerce_bytes(value)` 把整个 candidate bytes 拷一份到 in-memory bytes,再
   `abs_path.write_bytes(data)`,一次额外内存复制
2. `hash_payload(value)` 走 `_canonicalize(value)` 全量序列化 → sha256 全 buffer,
   `load_run_metadata` 的 drift 校验也走 `hash_payload(read(ref))` 全读 → 全 hash

目标:为 file backend 提供 zero-copy 源路径写入入口 + stream 哈希,把这两个内存
驻留点收敛到 chunk 级 RSS 增量。

**不在本 change 目标**:改 `PayloadRef` Pydantic schema、改 `FILE_MAX_BYTES` cap、引
入 async IO、迁移 worker 层 Candidate 协议(完整理由见 `proposal.md` Out of Scope 与
Non-Goals 段)。

## 2. 涉及 capability spec

- `artifact-contract` —— `ArtifactRepository.put` 接 zero-copy 入口 +
  `PayloadBackend.write` ABC 签名演进 + `FileBackend.write` zero-copy 分支 +
  `hashing.py` 新增 `hash_path` + `load_run_metadata` drift 校验改 stream
- `probe-and-validation` —— 加 5 个单元 fence(stream/value 哈希等价、RSS 增量、
  二选一拒签、cap 不全读、stream drift 校验)

## 3. 实现现状(代码事实清单)

### 3.1 `ArtifactRepository.put` 签名(`repository.py:55-97`)

```python
def put(
    self,
    *,
    artifact_id: str,
    value: Any,                # ← 唯一 payload source
    artifact_type: ArtifactType,
    role: ArtifactRole,
    format: str,
    mime_type: str,
    payload_kind: PayloadKind,
    producer: ProducerRef,
    schema_version: str = "1.0.0",
    lineage: Lineage | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
    validation: ValidationRecord | None = None,
    file_suffix: str = "",
) -> Artifact:
    ref = self._registry.write(
        payload_kind, value,
        run_id=producer.run_id, artifact_id=artifact_id, suffix=file_suffix,
    )
    art = Artifact(
        ...
        hash=hash_payload(value),       # ← 全量 sha256
        ...
    )
```

### 3.2 18 处 `repo.put` 调用站点 payload_kind 分布

`grep "payload_kind=PayloadKind" src/framework/runtime/executors/*.py` 结果:

| 调用站点                                        | payload_kind | 是否本 change 受益(Phase 1)| Phase 2 受益目标 |
| ----------------------------------------------- | ------------ | --------------------------- | ---------------- |
| `generate_audio.py:141`                         | `file`       | ❌(executor 仍走 `value=cand.data`)| ✅(audio 几 MB,Phase 2 迁移) |
| `generate_image.py:153`                         | `file`       | ❌(同上)                    | ✅(image 几 MB)  |
| `generate_image_edit.py:123`                    | `file`       | ❌(同上)                    | ✅(image 几 MB)  |
| `generate_mesh.py:278`                          | `file`       | ❌(同上)                    | ✅(GLB 3.5 MB+)  |
| `generate_video.py:148`                         | `file`       | ❌(同上)                    | ✅(mp4 5-15 MB)  |
| `generate_image.py:215`(bundle)                | `inline`     | ❌(JSON 小对象,never)      | ❌                |
| `generate_structured.py:138`                    | `inline`     | ❌                          | ❌                |
| `mock_executors.py:46 / 86 / 119`               | `inline` ×3  | ❌                          | ❌                |
| `review.py:359 / 387`                           | `inline` ×2  | ❌                          | ❌                |
| `select.py:98`                                  | `inline`     | ❌                          | ❌                |
| `validate.py:71`                                | `inline`     | ❌                          | ❌                |
| `export.py:337 / 367 / 403 / 439`               | `inline` ×4  | ❌                          | ❌                |

**结论**:**Phase 1 本 change 不直接迁移任何调用站点**(executor + Worker /
Candidate 协议都不动,见 D5 D-WorkerCandidateMigration);**Phase 2 受益目标 = 5 处
file generator**,follow-on `worker-candidate-source-path-migration` 落地。本 change
ship 后 user-visible 内存表现与 ship 前完全一致(零差异),这是预期行为不是缺陷。

### 3.3 `FileBackend.write` 现状(`file_backend.py:47-57`)

```python
def write(self, value: Any, *, run_id: str, artifact_id: str, suffix: str = "") -> PayloadRef:
    data = _coerce_bytes(value, suffix)              # ← 内存复制
    if len(data) > FILE_MAX_BYTES:
        raise PayloadTooLarge(...)
    rel = f"{run_id}/{artifact_id}{suffix}"
    abs_path = self._resolve(rel)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)                        # ← 再写一次
    return PayloadRef(kind=PayloadKind.file, file_path=rel, size_bytes=len(data))
```

### 3.4 `hash_payload` 与 `load_run_metadata` 现状

```python
# hashing.py:9-19
def _canonicalize(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    ...

def hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonicalize(value)).hexdigest()

# repository.py:220-226 — load_run_metadata 中 drift 校验
if art.payload_ref.kind in (_PayloadKind.file, _PayloadKind.blob):
    try:
        current = self._registry.read(art.payload_ref)     # ← read_bytes 全读
    except Exception:
        continue
    if hash_payload(current) != art.hash:                  # ← 全 hash
        continue
```

### 3.5 Worker Candidate 协议现状(`providers/workers/{audio,image,mesh,video}_worker.py`)

`AudioCandidate / ImageCandidate / MeshCandidate / VideoCandidate` 全部用
`data: bytes` 字段。ComfyUI agent CLI 路径下,worker 已经把 ComfyUI 落盘文件
`D:/AI/ComfyUI/outputs/main/...` 通过 `Path.read_bytes()` 完整读到 `data`,**source
path 信息在 worker 层就丢了**。

要把 zero-copy 推到 worker → executor → `repo.put` 整条链,需要 Worker / Candidate
协议演进(增 `source_path: str | None = None` + worker / executor 调用站点全面迁移),
scope 远超本 change 单 PR 边界 → 留 follow-on `worker-candidate-source-path-migration`。

**本 change Phase 1 边界**:只把 `repo.put` / `FileBackend` / `hashing` 的 zero-copy
能力建好;executor 仍走 `repo.put(value=cand.data)`。Phase 2 follow-on 改 worker
后,executor 迁移到 `repo.put(source_path=cand.source_path or write_tmp(cand.data))`。

## 4. 关键设计决策(D-decision 锚点)

### D1. API 形态选项与拍板

设计空间(三选一):

| 选项                                                 | Pros                                                                                  | Cons                                                                          |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **(A) 单 `put` 双参 `value` / `source_path` 二选一** | 调用站点 patch 最小(既有 18 处不动);新调用方按需传 `source_path`                    | API 签名扩了一个互斥参数,文档与 type hint 表达"二选一"需要 model_validator   |
| (B) 并存方法 `put_from_path`                         | 单一职责清晰;签名无歧义                                                              | 复制完整参数列表(13 个 keyword);两条几乎相同 method 长期同步维护成本高     |
| (C) `put(value: bytes | Path)` 自动 dispatch         | 调用方语法最自然                                                                      | type-based dispatch 模糊(`Path("foo.json")` 是 inline JSON 还是 file path?) |

**D-API 拍板:选 (A) 单 `put` 双参**。理由:
- 18 处既有调用站点零迁移成本(向后兼容)
- 新参数 `source_path: Path | str | None = None` 关键字 / 默认值 / type hint 清晰
- 二选一守门**基于 sentinel identity 比较**(D10 D-NullValueAmbiguity):`value: Any
  = _MISSING` + `if value is _MISSING and source_path is None: raise ...` /
  `if value is not _MISSING and source_path is not None: raise ...` /
  `if source_path is not None and payload_kind != PayloadKind.file: raise ...`,
  显式 ValueError 比 type dispatch 友好;**不**用 `None` 作"未传"判断,因
  `value=None` 是合法的 inline JSON null payload(既有 13 处 inline 调用契约保留)
- (B) 重复签名维护成本高,在 Pydantic / dataclass field 之外维护"两个长签名"违反
  DRY;(C) `Path("foo.json")` 二义性在 export.py 那 4 处 inline JSON 路径尤其严重
  (`payload_kind=PayloadKind.inline` + `value=dict`,但有人手滑传 `value=Path(...)`
  时会被 (C) 误判 file path)

### D2. stream hashing chunk size

**D-Chunk 拍板:8 MB(`8 * 1024 * 1024`)**。理由:
- Linux ext4 / Windows NTFS 典型 cluster size 是 4 KB;chunk 远大于 cluster → 减少
  syscall 次数
- sha256 内部 block 是 64 byte,chunk 8 MB → `chunk / 64 = 131072` 次内部 update,
  CPU cache 命中良好(8 MB 不超 LLC 在多数 x86 桌面 / 服务器)
- 32 MB / 64 MB chunk 收益边际,但内存上限抬高;1 MB chunk 多了 8× syscall 次数
- 暴露 `chunk_size` 关键字参数允许测试 / 调优

### D3. 500 MB cap 在 source_path 路径的校验时机

**D-Cap 拍板:在 `FileBackend.write` 入口处 `Path(source_path).stat().st_size`
检查,超 cap 立即 raise `PayloadTooLarge`,不调 `shutil.copy2` / `hash_path`**。
理由:
- 在拷贝 / 哈希之前拒签,避免无意义 IO + 临时 artifact 残留
- `stat` 比 `Path.is_file()` 多一次 syscall 但拿到 size 是必须的
- spy fence 在 `probe-and-validation` Requirement 守门

### D4. 写入原子性:`shutil.copy2` 到临时文件 + `os.replace` 原子替换 dest

**D-Atomic 拍板**(R4-F1 codex finding 翻转):**`shutil.copy2(src, tmp_dest)` 到
同目录临时文件 → 验证 → `os.replace(tmp_dest, abs_path)` 原子替换 dest**。理由:

- **绝对不能** `os.replace(source, dest)` 那种把 caller source 文件移走的语义 —
  调用方(executor / future worker)拥有 source 文件,backend 不得替它销毁数据
- 但**直接 `shutil.copy2(src, abs_path)` 写 final path** 在 disk full / 权限错 / 中途
  中断时会留半文件,**且会覆盖 final path 上既有的 valid payload**(同 artifact_id
  resume 场景):中断时 final_dest = 半文件,但 metadata / hash 还没更新 → 既有有效
  payload 被半破坏覆盖,下游 resume 误读 corrupt bytes
- 正确做法:**copy2 到同目录临时文件 `tmp_dest = abs_path.with_suffix(abs_path.suffix
  + ".part.<pid>.<uuid8>")` → post-copy 校验(stat / size cap)→ `os.replace(tmp_dest,
  abs_path)` 原子替换 dest**:
  - `os.replace` 同盘原子(POSIX rename(2) / NTFS MoveFileEx),失败不破坏既有 final
  - tmp 文件在同目录确保跨 device 不发生(`tmp` 跨盘会让 `os.replace` 退化非原子)
  - 异常路径:`tmp_dest.unlink(missing_ok=True)` 清理,raise 原始异常
- **`shutil.copyfile(src, tmp)`(NOT `copy2`)+ 显式 `os.chmod(tmp, 0o644)`** 权限归一化
  (R5-F4 D-PermissionNormalize):`copy2` 会保留 mtime / 权限位,**source 只读时
  dest 也只读**,后续 resume / overwrite / hash_path 读取可能因权限失败。`copyfile`
  仅复制内容不复制 metadata,加显式 chmod 让 artifact store 文件权限独立于 source
  权限位。Linux/macOS 用 0o644(owner rw + group/others r),Windows 由 NTFS ACL
  继承父目录权限(`os.chmod` 在 Windows 仅切只读位,影响有限,可按需 conditional
  skip)
- 最终 rename `os.replace(tmp, abs_path)` 只是元数据操作(同盘 atomic)

**实装伪代码**(参考 §5.3 完整版):

```python
import uuid
tmp_dest = abs_path.with_name(f"{abs_path.name}.part.{os.getpid()}.{uuid.uuid4().hex[:8]}")
try:
    shutil.copyfile(src, tmp_dest)  # R5-F4:不复制 metadata,避免 source 只读传染
    os.chmod(tmp_dest, 0o644)        # 显式权限归一化(POSIX;Windows 由 NTFS 继承)
    dest_size = tmp_dest.stat().st_size
    if dest_size > FILE_MAX_BYTES:
        raise PayloadTooLarge(...)
    os.replace(tmp_dest, abs_path)  # 原子替换 dest(R4-F1:绝不动 abs_path 内容)
except BaseException:
    tmp_dest.unlink(missing_ok=True)  # R5-F3:只清理 tmp,绝不 unlink abs_path
    raise
return PayloadRef(kind=..., file_path=rel, size_bytes=dest_size)
```

**fence 守门**:`test_repo_put_streaming.py::test_copy_failure_preserves_existing_dest`
(monkeypatch `shutil.copy2` 抛 OSError → 断言 既有 final path bytes 未被破坏 +
tmp 文件已清理;若 final path 之前不存在则不应残留半文件)。

### D5. Worker Candidate 协议是否在本 change 迁移

**D-WorkerCandidateMigration 拍板:本 change 不迁移,留 Phase 2 follow-on
`worker-candidate-source-path-migration`**。理由:
- 5 个 worker(Audio / Image / ImageEdit 复用 Image / Mesh / Video)+ ComfyUI agent
  CLI 输出解析 + 5 个 executor 调用站点 + 单测 / 集成测全套,改动面 ≈ 本 change
  3-4×
- Phase 1 不动 worker → executor 行为零变化 → 风险面只在 `repo.put` 底层(API +
  backend + hash);测试 baseline 不动
- Phase 1 完成后 `repo.put(source_path=...)` 接口就位,Phase 2 只剩 worker /
  executor 单点迁移,review 复杂度独立可控

### D6. `PayloadBackend.write` ABC 是否破坏 BlobBackend stub

**D-AbcCompat 拍板:`PayloadBackend.write` ABC 签名扩 `source_path` keyword,
InlineBackend / BlobBackend 收到非空 `source_path` 时 raise ValueError**。理由:
- ABC 统一签名,所有 backend 都接收 keyword,但只 FileBackend 实际实现 zero-copy
  分支
- InlineBackend 收 `source_path` → 语义错误(inline payload 不该有外部路径)→ raise
  ValueError 比静默 ignore 安全
- BlobBackend 是 NotImplementedError stub,raise ValueError 比 NotImplementedError
  对调用方更友好(明示语义错而非未实装)
- `PayloadBackendRegistry.write` 透传 keyword 不做 dispatch 校验,把责任下推到
  backend 自己

### D7. 测试 fence 中 200 MB 文件如何避免 CI 慢

**D-FenceOpt-in 拍板:RSS 增量 fence 用 `FORGEUE_RUN_HEAVY_FENCE=1` opt-in;
默认 skip;CI / 日常 `pytest -q` 不跑**。理由:
- 200 MB 临时文件创建 + 删除 + RSS 测量 ≈ 数秒,跑 1190+ 全套时 noticable
- opt-in 而非完全去掉:开发者 / 验收时手动跑过,守门"实际行为符合 zero-copy"
- 其他 fence(等价性 / 拒签 / drift)在 50 MB 以内文件上跑,常驻 `pytest -q`

### D8. `hash_path` 接口暴露范围

**D-HashApi 拍板:`hashing.py` 新增 `hash_path(path, *, chunk_size=...) -> str`
导出函数,与 `hash_payload(value)` 并列;`hash_inputs(*parts)` 不动**。理由:
- `hash_payload` 既有调用站点(13 处 inline + repo.put hash + checkpoint_store)
  全部走 value 路径,保留语义零迁移
- `hash_path` 新接口仅在 `repo.put` 内部 + `load_run_metadata` drift 校验内部 +
  fence 测试中调用,边界清晰
- `hash_inputs(*parts)` 用于 Checkpoint input_hash(SHA over 多个小元数据),与本
  change 无交集

### D9. `source_path` 路径下 hash 与 size_bytes 取样源

**D-HashSource-vs-Dest 拍板:hash 与 size_bytes 同源取「最终落盘 dest 文件」,
NOT 「caller 传入的 source 文件」**。`repo.put(source_path=...)` 内部:

1. `FileBackend.write` 用 `src.stat()` 取 `S_ISREG` + `st_size` 做 pre-copy 守门
   (regular file guard 见 R4-F3 + cap fail-fast,避免无意义 IO)
2. `shutil.copy2(src, tmp_dest)` 落盘到同目录临时文件(D4 D-Atomic R4-F1)
3. 验证 `tmp_dest.stat().st_size` post-copy 不超 cap;`os.replace(tmp_dest,
   abs_path)` 原子替换 dest;异常路径 `tmp_dest.unlink(missing_ok=True)` 清理
4. **`size_bytes = dest_stat.st_size`**(从 tmp_dest stat,等于 final abs_path stat;
   NOT `src_size`)— 写到 PayloadRef
5. `repo.put` 在 backend write 返回后,**`hash_path(backend.absolute_path(ref))`**
   (NOT `hash_path(source_path)`)— 写到 Artifact.hash

**理由 / 根因**(2026-05-21 codex adversarial round 1 a0 F1 finding 暴露):
- 若 hash 取 source,则 `size_bytes`(也取 source)/ `Artifact.hash`(取 source)
  与 dest 文件实际 bytes 之间存在并发写竞争窗口:caller 拥有 source 文件,在 stat
  / copy / hash 三阶段之间 source 可能被外部进程改 / 截断 / 替换 → 落盘 bytes /
  size_bytes / hash 三者不一致
- `load_run_metadata` resume drift 校验对 dest 文件取 `hash_path(absolute_path)`,
  若 Artifact.hash 来自 source(不是 dest),drift 校验把刚写入的 artifact 判
  corrupt → silently skip → CheckpointStore.find_hit 误 miss
- 取 dest 同源后,以下三者强一致 invariant:
  `PayloadRef.size_bytes == Path(dest).stat().st_size`
  `Artifact.hash == hash_path(dest)`
  落盘文件就是被 hash 的文件,resume drift 校验对称
- 多一次 `dest_size = abs_path.stat()` syscall 与 `hash_path(dest)` 替代 source 路径
  开销可忽略(stat ~microseconds,hash 在 8 MB chunk 下 IO 是主导,source vs
  dest 同盘 disk cache 命中)

**额外异常路径**(R5-F3 + D4 D-Atomic 共同约束):`FileBackend.write` 在 `copy2`
到 tmp_dest 之后再做一次 `dest_size > FILE_MAX_BYTES` 校验。pre-copy 用 src.stat
拒已知超 cap;post-copy 用 tmp_dest.stat 兜底 race window 内 source 被并发写大导
致 copy 落盘超 cap → raise PayloadTooLarge。**清理动作 SHALL `tmp_dest.unlink
(missing_ok=True)`(在 try/except BaseException 块统一执行),绝对 SHALL NOT 动
`abs_path`**(D4 atomic invariant:同 artifact_id resume 场景下 abs_path 上可能有
既有 valid payload,unlink 会破坏数据安全)。

**fence 守门**:
- `test_repo_put_streaming.py::test_source_modified_after_stat_but_before_copy`
  (opt-in heavy fence,不在默认 pytest -q):用 monkeypatch 模拟 stat / copy 之间
  source 被改;断言 Artifact.hash 与 落盘 dest 一致(NOT 与改前 source 一致),
  size_bytes 与 落盘 dest 一致。
- `test_payload_backends.py::test_post_copy_cap_overflow_preserves_existing_dest`
  (默认 pytest):monkeypatch `tmp_dest.stat` 让 post-copy size_check 触发
  PayloadTooLarge;断言既有 `abs_path` 上 valid payload 字节未变 + `.part.*` tmp
  文件已清理。

### D10. `value` 参数 "未传" 判断:`_MISSING` sentinel vs `None`

**D-NullValueAmbiguity 拍板:`value: Any = _MISSING` 用私有 sentinel,**不**用
`None` 作默认值**。`_MISSING` 在 `framework.artifact_store.payload_backends.base`
定义为 module-level `_MISSING = object()`,Repository 与三个 backend 都从 base
import 共用同一 identity。

**理由 / 根因**(2026-05-21 codex adversarial round 2 a0 F3 finding 暴露):
- 既有 `repo.put` 18 处调用站点里,`value` 是必填位置参,**没有**一处显式传 `None`,
  但既有契约**未禁止** —— `value=None` 等价 inline JSON null payload,
  `hash_payload(None)` 与 `InlineBackend.write(None)` 都已正确处理
- 新设计若把 `value: Any = None` 用作"未传"sentinel,`if value is None and
  source_path is None` 会把**显式 `value=None` 的合法调用**误判成"未传"并 raise
  ValueError → 破坏 proposal/spec 的 "既有调用站点行为完全一致" 承诺,也给后续 inline
  metadata / structured extraction 写 null payload 留下兼容坑
- 用 `_MISSING = object()` 私有 sentinel + identity 比较(`is _MISSING` / `is not
  _MISSING`)既明确区分 "未传" 与 "显式传 None",又不依赖 `Optional[T]` 这种值层
  语义,与 Python stdlib(如 `functools.lru_cache`)私有 sentinel pattern 一致

**接口变化**:
- `PayloadBackend.write(value: Any = _MISSING, ...)` ABC(base.py 顶层 import 共用)
- `PayloadBackendRegistry.write(kind, value: Any = _MISSING, **kwargs)`
- `InlineBackend / FileBackend / BlobBackend.write(value: Any = _MISSING, ...)`
- `ArtifactRepository.put(value: Any = _MISSING, source_path=None, ...)`
- 内部分发:`if value is _MISSING: # 走 source_path 分支` / `if value is not _MISSING:
  hash_payload(value)`

**fence 守门**:`test_repo_put_streaming.py::test_explicit_value_none_preserved`
(默认 pytest -q):调 `repo.put(value=None, payload_kind=inline, ...)` 应正常落盘
inline null payload(Artifact.hash == hash_payload(None));不 raise ValueError。
回归既有 inline 契约。

## 5. 接口设计

### 5.1 `framework.artifact_store.hashing`

```python
def hash_path(
    path: str | os.PathLike,
    *,
    chunk_size: int = 8 * 1024 * 1024,
) -> str:
    """Stream SHA-256 over file bytes; output equivalent to
    hash_payload(Path(path).read_bytes()).

    R4-F4:chunk_size <= 0 SHALL raise ValueError —— `f.read(0)` 返回空 bytes,
    会让非空文件得到 empty file hash(silent error)。
    """
    if chunk_size <= 0:
        raise ValueError(
            f"hash_path chunk_size must be positive, got {chunk_size}"
        )
    h = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

# 既有 hash_payload(value) / hash_inputs(*parts) 保留不动
```

### 5.2 `framework.artifact_store.payload_backends.base`

```python
# D10 D-NullValueAmbiguity 私有 sentinel — 用 identity 比较区分 "未传" vs "显式 None"
# (`value=None` 是合法 inline JSON null payload,既有 13 处 inline 调用契约保留)
_MISSING: Any = object()


class PayloadBackend(ABC):
    @abstractmethod
    def write(
        self,
        value: Any = _MISSING,                   # ← 改为可选 sentinel(D10)
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,   # ← 新增
    ) -> PayloadRef: ...


class PayloadBackendRegistry:
    def write(self, kind: PayloadKind, value: Any = _MISSING, **kwargs: Any) -> PayloadRef:
        return self.get(kind).write(value, **kwargs)
```

### 5.3 `framework.artifact_store.payload_backends.file_backend`

```python
class FileBackend(PayloadBackend):
    def write(
        self,
        value: Any = _MISSING,                   # ← D10 sentinel,与其他 backend 一致
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> PayloadRef:
        rel = f"{run_id}/{artifact_id}{suffix}"
        abs_path = self._resolve(rel)
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # R6-F3 D-BackendMutexGuard:backend 层也守 value/source_path 二选一,作 repo.put
        # 的次级 fence;direct backend 调用(绕过 repository)也保证不会双 payload source
        if value is not _MISSING and source_path is not None:
            raise ValueError(
                f"{type(self).__name__}.write: value and source_path are mutually exclusive"
            )
        if value is _MISSING and source_path is None:
            raise ValueError(
                f"{type(self).__name__}.write: requires either value or source_path"
            )

        if source_path is not None:
            # Zero-copy 分支(D4 D-Atomic + D9 D-HashSource-vs-Dest)
            import stat as _stat
            import uuid
            src = Path(source_path)
            src_stat = src.stat()  # raises FileNotFoundError if absent
            # R4-F3 D-RegularFileGuard:拒绝目录 / FIFO / device / socket;symlink
            # 由 stat() follow,实际指向必须是 regular file
            if not _stat.S_ISREG(src_stat.st_mode):
                raise ValueError(
                    f"source_path must be a regular file, got mode 0o{src_stat.st_mode:o}"
                )
            # Pre-copy cap 校验:fail-fast 拒已知超 cap 文件;真实 size_bytes 必须来自
            # dest stat(D9:source 在 stat / copy 之间可能被并发改,dest 才是落盘事实)
            if src_stat.st_size > FILE_MAX_BYTES:
                raise PayloadTooLarge(
                    f"file payload {src_stat.st_size} bytes exceeds cap {FILE_MAX_BYTES}"
                )
            # Atomic write(D4 D-Atomic R4-F1):copy2 到同目录 tmp → 验证 → os.replace
            # 原子替换 dest。Failure path 清理 tmp,不破坏既有 final_dest 上的 valid
            # payload(同 artifact_id resume 场景关键)
            tmp_dest = abs_path.with_name(
                f"{abs_path.name}.part.{os.getpid()}.{uuid.uuid4().hex[:8]}"
            )
            try:
                # R5-F4 D-PermissionNormalize:用 copyfile(不复制 metadata)+
                # 显式 chmod,避免 source 只读位传染到 artifact store
                shutil.copyfile(src, tmp_dest)
                os.chmod(tmp_dest, 0o644)
                dest_size = tmp_dest.stat().st_size
                if dest_size > FILE_MAX_BYTES:
                    # Race window:source 在 stat / copy 之间被并发写大 → tmp 超 cap
                    raise PayloadTooLarge(
                        f"file payload {dest_size} bytes (post-copy) exceeds cap {FILE_MAX_BYTES}"
                    )
                os.replace(tmp_dest, abs_path)  # 同盘 atomic; tmp 文件已不在
            except BaseException:
                tmp_dest.unlink(missing_ok=True)
                raise
            return PayloadRef(
                kind=PayloadKind.file,
                file_path=rel,
                size_bytes=dest_size,
            )

        # Value 分支(既有路径,完全保留)
        data = _coerce_bytes(value, suffix)
        if len(data) > FILE_MAX_BYTES:
            raise PayloadTooLarge(
                f"file payload {len(data)} bytes exceeds cap {FILE_MAX_BYTES}"
            )
        abs_path.write_bytes(data)
        return PayloadRef(
            kind=PayloadKind.file,
            file_path=rel,
            size_bytes=len(data),
        )
```

### 5.4 `framework.artifact_store.payload_backends.inline_backend` / `blob_backend`

```python
# 两者都从 base 导入 _MISSING + 加同款 source_path guard
from framework.artifact_store.payload_backends.base import _MISSING, PayloadBackend

def write(
    self,
    value: Any = _MISSING,
    *,
    run_id: str,
    artifact_id: str,
    suffix: str = "",
    source_path: str | os.PathLike | None = None,
) -> PayloadRef:
    if source_path is not None:
        raise ValueError(
            f"source_path is only supported by FileBackend, not {type(self).__name__}"
        )
    if value is _MISSING:
        raise ValueError(
            f"{type(self).__name__}.write requires value (got _MISSING sentinel)"
        )
    # ... 既有逻辑(InlineBackend: value=None 走 hash_payload(None) → JSON null;
    # BlobBackend stub raise NotImplementedError)
```

### 5.5 `framework.artifact_store.repository.ArtifactRepository.put`

```python
from framework.artifact_store.payload_backends.base import _MISSING


def put(
    self,
    *,
    artifact_id: str,
    value: Any = _MISSING,                                   # ← D10 sentinel,允许 value=None 合法
    source_path: str | os.PathLike | None = None,            # ← 新增
    artifact_type: ArtifactType,
    role: ArtifactRole,
    format: str,
    mime_type: str,
    payload_kind: PayloadKind,
    producer: ProducerRef,
    schema_version: str = "1.0.0",
    lineage: Lineage | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
    validation: ValidationRecord | None = None,
    file_suffix: str = "",
) -> Artifact:
    # D10 二选一守门:基于 identity 比较,允许 value=None(合法 inline JSON null)
    if value is _MISSING and source_path is None:
        raise ValueError("repo.put requires either value or source_path")
    if value is not _MISSING and source_path is not None:
        raise ValueError("repo.put: value and source_path are mutually exclusive")
    if source_path is not None and payload_kind != PayloadKind.file:
        raise ValueError(
            "repo.put: source_path requires payload_kind=file "
            f"(got {payload_kind!r})"
        )

    # 落盘(backend 透传 keyword;value=_MISSING 不传给 backend write —— backend 自己
    # 会按 source_path is not None 走 zero-copy 分支,跳过 value 处理)
    ref = self._registry.write(
        payload_kind,
        value,
        run_id=producer.run_id,
        artifact_id=artifact_id,
        suffix=file_suffix,
        source_path=source_path,
    )

    # 哈希(分两路)— D9 D-HashSource-vs-Dest:source_path 路径下 hash 取最终
    # 落盘 dest 文件,**不**取 source 文件。避免 source 在 stat / copy / hash 三阶
    # 段之间被并发写 / 截断,导致 落盘 bytes / size_bytes / hash 三者漂移,
    # resume drift 校验把刚写入的 artifact 误判 corrupt。
    # value 路径仍走 hash_payload(value)(value=None 合法 inline JSON null,
    # hash_payload(None) → 稳定 hex,D10 sentinel 区分 "未传 _MISSING" vs "显式 None")
    if source_path is not None:
        dest_abs = self._registry.get(payload_kind).absolute_path(ref)
        content_hash = hash_path(dest_abs)
    else:
        # value is not _MISSING(已通过守门),可能为任意类型含 None
        content_hash = hash_payload(value)

    art = Artifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        role=role,
        format=format,
        mime_type=mime_type,
        payload_ref=ref,
        schema_version=schema_version,
        hash=content_hash,
        producer=producer,
        lineage=lineage or Lineage(),
        metadata=metadata or {},
        tags=tags or [],
        validation=validation or ValidationRecord(status="pending"),
        created_at=datetime.now(timezone.utc),
    )
    self._artifacts[artifact_id] = art
    self._lineage.register(art)
    self._variants.register(art)
    return art
```

### 5.6 `load_run_metadata` drift 校验改 stream

```python
# repository.py:220-226 改写
# D-DriftScope 拍板(2026-05-21 codex F3):drift 校验仅对 file kind 改 stream;
# blob kind 在本 change scope **既有行为完全保留**(BlobBackend stub 未实装 →
# 既有 self._registry.read(ref) 已抛 NotImplementedError → 既有逻辑就 catch
# Exception → continue,语义无变化)。不要把 blob 字面合并到 stream drift 路径,
# 因 BlobBackend.absolute_path 也 raise NotImplementedError → 不可达分支误导
# 实现者。
if art.payload_ref.kind == _PayloadKind.file:
    # File-kind stream drift:hash_path(absolute_path),不全读
    try:
        backend = self._registry.get(_PayloadKind.file)
        abs_path = backend.absolute_path(art.payload_ref)
    except (KeyError, ValueError):
        continue
    try:
        current_hash = hash_path(abs_path)
    except (FileNotFoundError, OSError):
        continue
    if current_hash != art.hash:
        continue
elif art.payload_ref.kind == _PayloadKind.blob:
    # Blob-kind 保旧行为:既有 BlobBackend stub 已 NotImplementedError,
    # 既有 self._registry.read(ref) 既已抛异常被 catch → continue。
    # 当 BlobBackend 实装时(follow-on `blob-backend-streaming-implementation`)
    # 再决定 drift 实装策略(可能走 etag / Last-Modified header 而非全 hash)。
    try:
        current = self._registry.read(art.payload_ref)
    except Exception:
        continue
    if hash_payload(current) != art.hash:
        continue
# inline 路径不变
else:
    # inline kind 没有 drift 校验(在既有实现里 inline 直接走 register)
    pass
```

**D-AbsPath 拍板:`PayloadBackend` ABC 新增 `absolute_path(ref: PayloadRef) ->
Path` 方法,FileBackend 实装为 `self._resolve(ref.file_path)`,InlineBackend
实装为 raise(inline 无外部路径),BlobBackend stub 抛
NotImplementedError**。理由:
- 既有 `_resolve` 是 FileBackend 私有,repository 不该直接访问
- ABC 加一个 read-only path query 比直接 `cast(FileBackend, backend)._resolve(...)`
  更清晰
- `absolute_path` 不破坏既有调用站点(grep "absolute_path\|_resolve" 仅 file_backend
  内部使用)

## 6. 数据模型变更

`PayloadRef` Pydantic schema **零变更** —— `kind / inline_value / file_path /
blob_key / size_bytes` 字段保留,既有 `_artifacts.json` 序列化兼容。

新增的能力(zero-copy 写入路径 + stream hash)在 backend / hashing / repository 层
表达,不渗透到 Artifact 序列化契约。

## 7. 测试策略(完整 fence 清单)

### 7.1 新增 `tests/unit/test_repo_put_streaming.py`

| Test                                                    | 类型     | opt-in       |
| ------------------------------------------------------- | -------- | ------------ |
| `test_value_source_path_mutually_exclusive`             | 单元     | 默认         |
| `test_source_path_requires_file_kind`                   | 单元     | 默认         |
| `test_neither_value_nor_source_path`                    | 单元     | 默认         |
| `test_source_path_writes_byte_equal_with_value_path`    | 单元     | 默认         |
| `test_cap_rejected_without_read`(spy copy2)            | 单元     | 默认         |
| `test_zero_copy_rss_bounded_200mb`                      | 单元     | heavy fence  |

### 7.2 扩 `tests/unit/test_artifact_repository.py`

| Test                                              | 类型 | opt-in |
| ------------------------------------------------- | ---- | ------ |
| `test_hash_path_equivalent_to_hash_payload`       | 单元 | 默认   |
| `test_hash_path_chunk_size_does_not_affect_output`| 单元 | 默认   |
| `test_load_metadata_uses_stream_hash`(spy)       | 单元 | 默认   |
| `test_load_metadata_corrupt_file_rejected_stream` | 单元 | 默认   |

### 7.3 扩 `tests/unit/test_payload_backends.py`

| Test                                              | 类型 | opt-in |
| ------------------------------------------------- | ---- | ------ |
| `test_inline_backend_rejects_source_path`         | 单元 | 默认   |
| `test_blob_backend_rejects_source_path`           | 单元 | 默认   |
| `test_file_backend_zero_copy_byte_equal`          | 单元 | 默认   |
| `test_file_backend_zero_copy_cap_rejection`       | 单元 | 默认   |
| `test_file_backend_absolute_path_method`          | 单元 | 默认   |

### 7.4 不动的测试

- `tests/integration/test_p[0-4]_*.py`(端到端);因为 5 处 file generator
  executor 调用站点不动,行为完全等价
- `tests/unit/test_checkpoint_store.py`(checkpoint hit);hash 计算路径在 repo.put
  内,checkpoint 仍读 `Artifact.hash` 字段
- `tests/integration/test_artifact_persistence.py`(若存在)—— `_artifacts.json`
  schema 不变

## 8. 风险与缓解

| 风险                                       | 缓解                                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| 18 处既有 `repo.put` 调用静默 broken       | API 完全向后兼容(`value` 不变,`source_path=None` 缺省);grep 18 处确认无 keyword-only 强制     |
| `shutil.copy2` 跨盘性能不可控              | 文档声明同盘最优;`probe-and-validation` RSS fence opt-in 不在 CI 验证速度                       |
| `hash_path` 与 `hash_payload` 输出不一致   | `test_hash_path_equivalent_to_hash_payload` 在 4 个 size grade fence 守门                         |
| `load_run_metadata` drift 改 stream 后语义漂移 | `test_load_metadata_corrupt_file_rejected_stream` 守门 corrupt 拒签;spy hash_payload 守门未触发  |
| ABC 签名扩 keyword 破坏第三方 backend(无) | 检查 `framework.artifact_store.payload_backends/` 内只有 3 个实装,无外部插件;改动安全           |

## 9. Future Work {#forge-future-work}

```yaml
schema: forge-scope-entries/v1
anchor_id: forge-future-work
entries:
    - id: worker-candidate-source-path-migration
      category: future-work
      description: |
        Phase 2:Worker Candidate(AudioCandidate / ImageCandidate / MeshCandidate /
        VideoCandidate)协议扩 `source_path: str | None = None` 字段;ComfyUI agent
        CLI 路径下 worker 不再 `Path.read_bytes()`,而是返回 source_path;5 个
        file generator executor 切到 `repo.put(source_path=cand.source_path)`
        实现端到端 zero-copy。
      reason: |
        Phase 1(本 change)只做 `repo.put` / `FileBackend` / `hashing` 底层
        zero-copy 能力,worker 协议保持 `data: bytes` 不变,executor 调用零变化。
        Phase 2 在 Phase 1 已就位的接口上做单点迁移,review 复杂度独立可控;
        未来远端 worker(Hunyuan3D / Tripo3D / Wan video remote)是 HTTP 下载场
        景,可选维持 bytes 也可改 stream download 到临时文件再 source_path。
      priority: medium
      status: active
      triggered_by: null
      related_change: null
    - id: blob-backend-streaming-implementation
      category: future-work
      description: |
        BlobBackend MVP stub 的实装(S3 / MinIO / Azure Blob),与 source_path
        zero-copy 接口对齐。
      reason: |
        BlobBackend 当前是 NotImplementedError stub,本 change 在 ABC 上为它加了
        source_path keyword(透传 + raise),未来实装时直接走对象存储 multipart
        upload 接 source_path,接口边界已锁定。
      priority: low
      status: active
      triggered_by: null
      related_change: null
    - id: hash-path-async-variant
      category: future-work
      description: |
        `hash_path` 的 async 变体 `ahash_path(path)` 走
        `await asyncio.to_thread(hash_path, path)` 或 `aiofiles`,供未来 executor
        在不阻塞 event loop 的前提下 hash 超大文件。
      reason: |
        本 change `hash_path` 同步实现在 50 MB 以内文件上耗时 < 200 ms,executor
        await 链中可以接受。未来若引入 GB 级 video 或长片场景,可加 async 变体
        但当前无收益。
      priority: low
      status: active
      triggered_by: null
      related_change: null
    - id: repo-put-staging-hash-atomicity
      category: future-work
      description: |
        `FileBackend.write` 改为 staging-hash 模式:对 `tmp_dest` 计算 hash 与
        size 完成验证后再 `os.replace(tmp, abs_path)`,通过 `WriteResult(ref,
        content_hash)` 或等价机制把 hash 透传给 `repo.put`,消除 `os.replace`
        成功后 `hash_path(final)` 失败 → 旧 valid payload 被覆盖但 metadata 没
        更新的半提交窗口。
      reason: |
        R6-F2 codex finding 暴露(2026-05-21 round 6 adversarial review):
        当前设计先 `os.replace(tmp, abs_path)` 再 `repo.put` 对 final dest 跑
        `hash_path`,replace 后 hash 失败会让旧 valid payload 被覆盖但 Artifact
        metadata 不更新。本 change scope 内已用 R4-F1 atomic write + R5-F3
        unlink-tmp 守门 copy 失败 path,**replace 后 hash 失败的具体场景** 在
        实际系统(本地磁盘 + 小文件)概率极低(`hash_path` 失败要么是 disk
        unmount / 文件被外部进程删,要么是 OOM / FS 异常)。Staging hash 改造
        要求 backend `write` 返回类型从 `PayloadRef` 变 `WriteResult` 双件,
        repo.put 信任 backend 给的 hash 不再自己算,scope 涉及 ABC / repo /
        3 backend 实装全跟,**留 follow-on `repo-put-staging-hash-atomicity`
        看实际生产中是否真有命中 case 再动**。本 change 进 apply 时主代理对
        实施者明确该限制。
      priority: medium
      status: active
      triggered_by: codex-adversarial-round-6
      related_change: null
```

## 10. 实现顺序建议

参考 tasks.md 的细化清单。设计层面建议:

1. 先 `hash_path` + 单元 fence(纯函数,无依赖)
2. 再 `FileBackend.write` source_path 分支 + `absolute_path` 方法 +
   InlineBackend / BlobBackend guard + 单元 fence
3. 再 `ArtifactRepository.put` 接 `source_path` + `load_run_metadata` drift 改 stream
4. 最后跑 `python -m pytest -q` baseline 确认 1190+ 无回退
5. 手工冒烟:跑一次 `examples/comfy_local_smoke_video.json` 端到端确认 video
   executor 路径不受影响(Phase 1 不动 executor → 应完全无差异)
