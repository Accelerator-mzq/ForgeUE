# artifact-contract — repo-put-streaming-payload delta

> 本文件是 `artifact-contract` capability 在 `repo-put-streaming-payload`(TBD-012)
> change 引入的行为增量:`ArtifactRepository.put` 扩 zero-copy 源路径接口,
> `PayloadBackend.write` ABC 同步演进,`hashing.py` 新增 stream hash 函数,
> `load_run_metadata` 大文件 drift 校验改 stream。每条 Requirement 首行标注 ADDED /
> MODIFIED。

## Source Documents

- `docs/requirements/SRS.md` §3.6(FR-STORE 系列)、§4.2(NFR-PERF 大文件落盘)
- `docs/design/HLD.md` §4 / §D.2(payload backend layout)
- `docs/design/LLD.md` §F0-3(PayloadRef + Repository)
- 实现:`src/framework/artifact_store/repository.py` /
  `src/framework/artifact_store/hashing.py` /
  `src/framework/artifact_store/payload_backends/{base,file_backend,blob_backend}.py`

## Requirement: repo.put 提供 zero-copy 源路径写入入口

**ADDED.** `ArtifactRepository.put` SHALL 接受一个可选关键字参数 `source_path: str
| os.PathLike | None = None`,与既有 `value` 参数二选一。`value` 参数 SHALL 改为
`value: Any = _MISSING`,其中 `_MISSING` 是 module-private sentinel
(`_MISSING = object()`)— **不能**用 `None` 作为"未传"判断,因为 `value=None`
是合法的 inline JSON null payload(既有 13 处 inline 调用契约保留)。

二选一守门 SHALL 基于 identity 比较:
- 不传入任一(`value is _MISSING and source_path is None`)SHALL raise `ValueError`
- 同时传入两者(`value is not _MISSING and source_path is not None`)SHALL raise `ValueError`
- `source_path is not None and payload_kind not in {PayloadKind.file, PayloadKind.blob}` SHALL raise `ValueError`

当 `source_path` 不为空时(D9 D-HashSource-vs-Dest):
- `repo.put` SHALL 把 `source_path` 透传到 `PayloadBackend.write` 的同名 keyword
  参数,**不**在 ArtifactRepository 层读 bytes
- `PayloadBackend.write` SHALL 返回 `WriteResult(ref, content_hash)`,`repo.put`
  SHALL 信任该 `content_hash`,不在 `os.replace` 后对 final dest 重算 hash
- file backend 的 source_path 分支内容哈希 SHALL 走 `hash_path(tmp_dest)` 对
  **staging 临时文件** stream 取样,并且必须发生在
  `os.replace(tmp_dest, abs_path)` 之前;**不**走 `hash_path(source_path)`
  (避免 source 在 stat / copy / hash 三阶段间被并发改导致漂移)
- blob backend 的 source_path 分支 SHALL 走 `BlobClient.upload_path(...)` 上传,
  内容哈希用 `hash_path(source_path)` stream 计算,并返回
  `PayloadRef(kind=blob, blob_key=<bucket>/<run_id>/<artifact_id><suffix>)`;
  真实 S3/MinIO/Azure adapter 可在同一 protocol 下做 multipart upload
- file backend 的 `PayloadRef.size_bytes` SHALL 等于 `Path(dest_abs).stat().st_size`
  (post-copy dest stat),与 hash 同源 — `FileBackend.write` 仅在 pre-copy 用
  `src.stat()` 做 fail-fast cap 校验,最终 size_bytes 取 dest stat

当 `source_path` 为空(既有调用站点的行为)时,`repo.put` 行为 SHALL 与本 change 之
前完全一致 —— 18 处既有 `repo.put` 调用站点 SHALL 无须修改;`value=None` inline 调
用(JSON null payload)SHALL 仍合法走 `hash_payload(None)` 路径,不被误判为"未传"。

## Scenario: 单参 zero-copy 写入大 video mp4 文件,hash 与 size 取 dest

**Given** 一个 `ArtifactRepository` 与一个已落盘的 8 MB video mp4 文件 `tmp_path /
"raw_video.mp4"`,内容假设 source / dest 一致(无并发改写)
**When** 调用方执行 `repo.put(artifact_id="aid", source_path=tmp_path /
"raw_video.mp4", artifact_type=ArtifactType(modality="video", shape="mp4", ...),
payload_kind=PayloadKind.file, ...)`(value 参数缺省)
**Then** 返回的 `Artifact.payload_ref.kind == PayloadKind.file`
**And** `dest_abs = backend.absolute_path(art.payload_ref)`
**And** `Artifact.payload_ref.size_bytes == dest_abs.stat().st_size`(post-copy dest)
**And** `Artifact.hash == hash_path(dest_abs)`(SHA-256 of dest bytes,stream)
**And** byte-equal scenario 下也有 `hash_path(dest_abs) == hash_path(source_path)`
(双 assert 提示同源 invariant)
**And** `Artifact.payload_ref.file_path` 在 artifact root 内,目标文件存在且 bytes 与
源文件按字节相等

## Scenario: source 在 stat / copy 之间被并发改写,hash 与 size 仍跟随 dest

**Given** 一个 source 文件 `racing.bin` 初始内容 `original`(18 KB)
**When** 调用方执行 `repo.put(..., source_path=racing.bin, ...)`,同时在 `shutil.copy2`
开始落盘前 monkeypatch 把 source 内容改成 `modified`(13.5 KB,不同 size + 不同
bytes)
**Then** `dest_abs = backend.absolute_path(art.payload_ref)`
**And** `dest_abs.read_bytes() == modified`(落盘的是 copy 时刻的 source = modified)
**And** `Artifact.hash == hash_path(dest_abs)`,等于 `hash_payload(modified)`
**And** `Artifact.payload_ref.size_bytes == dest_abs.stat().st_size == 13 * 1024 + 824`
**And** `Artifact.hash != hash_payload(original)`(hash 不来自被替换前的 source)
**And** invariant `PayloadRef.size_bytes == Path(dest).stat().st_size` 与
`Artifact.hash == hash_path(dest)` 仍成立

## Scenario: 同时传 value 与 source_path 拒签

**Given** `ArtifactRepository`
**When** 调用 `repo.put(artifact_id="aid", value=b"data", source_path="/tmp/foo",
payload_kind=PayloadKind.file, ...)`
**Then** raise `ValueError`,信息包含 `"value and source_path are mutually exclusive"`
或语义等价提示

## Scenario: value=None 是合法 JSON null payload,不被误判未传

**Given** `ArtifactRepository`
**When** 调用 `repo.put(artifact_id="aid", value=None, payload_kind=PayloadKind.inline,
...)`(显式传 None 表达 inline JSON null)
**Then** 不 raise(`value is _MISSING` 判 False,`value=None` 通过 sentinel 守门)
**And** `Artifact.hash == hash_payload(None)`
**And** `Artifact.payload_ref.kind == PayloadKind.inline`
**And** `Artifact.payload_ref.inline_value is None`

## Scenario: source_path 与非 file payload kind 组合拒签

**Given** `ArtifactRepository`
**When** 调用 `repo.put(artifact_id="aid", source_path="/tmp/foo",
payload_kind=PayloadKind.inline, ...)`
**Then** raise `ValueError`,信息包含 `"source_path requires payload_kind=file"` 或语
义等价提示

## Requirement: hashing.py 暴露 stream 哈希 hash_path

**ADDED.** `framework.artifact_store.hashing` SHALL 暴露
`hash_path(path: str | os.PathLike, *, chunk_size: int = 8 * 1024 * 1024) -> str` 函
数(R4-F4:`chunk_size <= 0` SHALL raise `ValueError`,避免 `f.read(0)` 让非空文件得
到 empty file hash)
数,以分块流式 IO 计算文件 sha256 hex,等价于 `hashlib.sha256(open(path,
"rb").read()).hexdigest()` 的输出,但 RSS 增量 SHALL 不超过 `chunk_size + 一个 常数 small
overhead`。

既有 `hash_payload(value)` 函数 SHALL 保留 value 参数路径(inline / 13 处既有调用站点
不动)。

`hash_path` 与 `hash_payload(read_bytes(path))` 在所有合法 file payload 上 SHALL 输出
完全一致的 hex 字符串(stream / value 等价性)。

`framework.artifact_store.hashing` SHALL 额外暴露
`ahash_path(path: str | os.PathLike, *, chunk_size: int = 8 * 1024 * 1024) -> str`
async helper。`ahash_path` SHALL 通过 `asyncio.to_thread(hash_path, path, ...)`
复用同步 stream hash 语义,输出与 `hash_path(path, chunk_size=...)` 完全一致,
并原样透传 `hash_path` 的 `chunk_size <= 0` `ValueError`。

## Scenario: stream hash 与全读 hash 等价

**Given** 任意一个 1 字节到 50 MB 之间的本地文件 `p`
**When** 同时计算 `hash_path(p)` 与 `hash_payload(p.read_bytes())`
**Then** 两者输出完全相等

## Scenario: async stream hash 与 sync stream hash 等价

**Given** 任意一个本地文件 `p`
**When** 执行 `await ahash_path(p, chunk_size=...)`
**Then** 输出 SHALL 等于 `hash_path(p, chunk_size=...)`
**And** `chunk_size <= 0` SHALL 透传 `ValueError`

## Scenario: stream hash 在 200 MB 文件上内存增量受限

**Given** 一个 200 MB 的本地文件
**When** 执行 `hash_path(p)`
**Then** 进程 RSS 增量 SHALL 小于 32 MB(chunk_size 默认 8 MB,加 Python 解释器
overhead + sha256 内部状态;fence 阈值 32 MB 给运行时波动余量)

## Requirement: PayloadBackend.write ABC 接受 source_path keyword 并返回 WriteResult

**MODIFIED.** `framework.artifact_store.payload_backends.base.PayloadBackend.write`
ABC 签名 SHALL 演进为
`write(self, value: Any = _MISSING, *, run_id: str, artifact_id: str,
suffix: str = "", source_path: str | os.PathLike | None = None) -> WriteResult`
(D10 D-NullValueAmbiguity:`_MISSING` 是 `base.py` 顶层定义的私有 sentinel,
**不**用 `None` 作 "未传" 默认值,因 `value=None` 是合法 inline JSON null payload)。

`PayloadBackendRegistry.write` SHALL 把 `source_path` 透传到具体 backend,
签名同步为 `write(self, kind, value: Any = _MISSING, **kwargs) -> WriteResult`。
`WriteResult` SHALL carry exactly:
- `ref: PayloadRef`
- `content_hash: str`

`ArtifactRepository.put` SHALL 从 `WriteResult.ref` 构造 Artifact payload_ref,并从
`WriteResult.content_hash` 构造 Artifact.hash。

`InlineBackend.write` SHALL 在收到非空 `source_path` 时 raise
`ValueError("source_path is only supported by FileBackend")`。`BlobBackend.write`
SHALL 接受 `source_path`,与 `FileBackend.write` 一样执行 value/source_path 二选一
守门。Inline / File / Blob 三个 backend 都 SHALL 在收到
`value is _MISSING` 且 `source_path is None` 时 raise `ValueError`(缺参兜底,
正常情况下 repo.put 已守门,backend 是次级 fence)。

## Requirement: FileBackend.write 提供 zero-copy 落盘分支

**MODIFIED.** `FileBackend.write` SHALL 实现 source_path 分支:
- 当 `source_path` 非空时:
  1. **Regular file guard**(R4-F3):`src_stat = Path(source_path).stat()`,
     `if not stat.S_ISREG(src_stat.st_mode): raise ValueError("source_path must be a
     regular file, ...")`。目录 / FIFO / device / socket 全部拒签;symlink 由
     `Path.stat()` follow,实际指向必须 regular file
  2. **Pre-copy fail-fast cap 校验**:`src_stat.st_size > FILE_MAX_BYTES = 500 *
     1024 * 1024` → SHALL raise `PayloadTooLarge`(信息内容与 value 路径同款 wording,
     不全读 source 文件)
  3. **原子落盘**(R4-F1 D4 D-Atomic + R5-F4 D-PermissionNormalize):
     **SHALL** `shutil.copyfile(source_path, tmp_dest)`(**NOT** `copy2` — 避免
     mtime / 权限位传染,R5-F4)到同目录临时文件
     (`tmp_dest = abs_path.with_name(f"{abs_path.name}.part.<pid>.<uuid8>")`)
     + `os.chmod(tmp_dest, 0o644)` 权限归一化(POSIX;Windows 由 NTFS 继承可
     conditional skip)+ `dest_size = tmp_dest.stat().st_size` 二次校验 +
     **`content_hash = hash_path(tmp_dest)`** staging hash +
     **`os.replace(tmp_dest, abs_path)`** 原子替换 dest;**SHALL NOT** 直接
     `copyfile(src, abs_path)` 写 final path(中断会留半文件覆盖既有 valid payload)
  4. **异常清理**:`copyfile` / `hash_path(tmp_dest)` / `os.replace` 任一抛异常 SHALL `tmp_dest.unlink
     (missing_ok=True)` 清理 tmp,并 re-raise 原始异常;既有 `abs_path` 上 valid
     payload SHALL 保持未被破坏(同 artifact_id resume 场景关键)
  5. **Post-copy size 兜底**:若 `dest_size > FILE_MAX_BYTES`(race window 内
     source 被并发写大)SHALL 清理 tmp + raise `PayloadTooLarge`
- **绝对不能** `os.replace(source, dest)` 那种把 caller source 文件移走的语义 ——
  调用方拥有 source 文件,backend 不得删除 / 移走;只能 `os.replace(tmp_dest, dest)`
  替换 dest
- `source_path` 不存在 → SHALL raise `FileNotFoundError`(传播 `Path.stat()` 原生
  异常);非 regular file → SHALL raise `ValueError`(R4-F3 显式 guard)
- **返回的 `WriteResult.ref` size_bytes 来自 dest stat,与 hash 同源**(D9
  D-HashSource-vs-Dest 不可妥协 invariant):
  `PayloadRef(kind=PayloadKind.file,
  file_path=<run_id>/<artifact_id><suffix>, size_bytes=<dest_stat.st_size>)`
  —— **不**用 `<source_stat.st_size>`,否则 source 在 stat / copy 之间被并发改时,
  `PayloadRef.size_bytes` 与 `dest_abs.stat().st_size` 漂移,违反 invariant
  `PayloadRef.size_bytes == Path(dest).stat().st_size`

当 `source_path` 为空时,既有 `_coerce_bytes(value, suffix)` → `write_bytes` 路径完全
保留;`WriteResult.content_hash` SHALL 沿用旧 `repo.put` 语义走 `hash_payload(value)`。
两条分支在外部观察(落盘 bytes)上 SHALL 等价(byte-equal scenario 下 source /
dest hash / size 一致,但**契约约束 dest**)。

## Requirement: BlobBackend.write 提供对象存储 MVP 分支

**ADDED (FOR-11).** `BlobBackend` SHALL 从 `NotImplementedError` stub 升级为
MVP object-store backend:

- 暴露 `BlobClient` protocol,包含 `upload_bytes` / `upload_path` / `read_bytes`
  / `exists` 四个方法;框架默认不引入 boto3 / azure-storage-blob 等重依赖
- 暴露 `InMemoryBlobClient` 作为默认 client,供本地测试和离线 run 使用
- `BlobBackend(bucket="forgeue-artifacts", client=None)` SHALL 默认构造
  `InMemoryBlobClient`
- key 形状 SHALL 为 `<bucket>/<run_id>/<artifact_id><suffix>`,写入后返回
  `PayloadRef(kind=PayloadKind.blob, blob_key=key, size_bytes=<bytes>)`
- value 分支 SHALL 经 `_coerce_bytes(value)` 上传,`content_hash` 沿用
  `hash_payload(value)` 语义
- source_path 分支 SHALL 验证 source 是 regular file,用 `hash_path(source_path)`
  stream 计算内容 hash,再调用 `BlobClient.upload_path(...)` 上传;不存在的 source
  传播 `FileNotFoundError`,目录 / FIFO / device / socket raise `ValueError`
- `read(ref)` SHALL 通过 `BlobClient.read_bytes(ref.blob_key)` 返回 bytes,
  `exists(ref)` SHALL 通过 client 判断 object 是否存在
- `absolute_path(ref)` SHALL raise `ValueError("blob payload has no local path")`,
  因对象存储没有本地绝对路径

`ArtifactRepository.put(source_path=..., payload_kind=PayloadKind.blob)` SHALL
通过同一 registry dispatch 进入 BlobBackend,不再被 repo 入口拒签。

## Scenario: zero-copy 路径不全量驻留内存

**Given** 一个 100 MB 的本地文件 `src`
**When** 执行 `FileBackend(root=tmp).write(value=None, run_id="r", artifact_id="a",
suffix=".bin", source_path=src)`
**Then** 进程 RSS 增量 SHALL 小于 32 MB(stream copy chunk 默认实现 OS 级 buffer + 不
全读)

## Scenario: zero-copy 路径在超 cap 时拒签

**Given** 一个 大小 600 MB 的本地文件 `huge`
**When** 执行 `FileBackend(root=tmp).write(value=None, run_id="r", artifact_id="a",
source_path=huge)`
**Then** raise `PayloadTooLarge`,信息包含实际 size 与 cap

## Requirement: load_run_metadata 大文件 drift 校验改 stream(仅 file kind)

**MODIFIED.** `ArtifactRepository.load_run_metadata` 中针对 **`file` kind**
payload 的 hash drift 校验 SHALL 改用 `hash_path(backend.absolute_path(ref))` 流
式实现,**不**走既有 `hash_payload(self._registry.read(art.payload_ref))` 全读路
径。

**`blob` kind 在 FOR-11 后走 BlobBackend.read + hash_payload drift 校验**:
`current = self._registry.read(art.payload_ref)`,若 `hash_payload(current) !=
art.hash` 则 skip。Blob payload 没有本地 `absolute_path`;真实云 adapter 可在
`read_bytes` 内部用 SDK 下载 object bytes,更高级的 etag / Last-Modified 优化留
后续 adapter 层演进。

**`inline` kind 既有行为完全保留:SHALL 不做 payload drift 校验**(R4-F2
D-InlineDriftNonGoal,与 proposal §What 5 + design §5.6 一致):inline payload 跟
元数据一起 JSON 序列化到 `_artifacts.json`,**无外部 bytes 可漂移**;若 metadata
file 自身被改但 hash 未更新,这是 metadata corruption 范畴,**留 follow-on
`metadata-corruption-detection`,本 change scope 不覆盖**。inline kind SHALL
直接 `register_existing`(无 hash 比对),与本 change 引入前的既有逻辑等价。

drift 判定语义对 `file` / `blob` 保持:hash 不一致 → entry skipped;hash 一致 →
register。对 `inline` 直接 register(无判定步骤)。

## Scenario: resume 时 200 MB video drift 校验不全读

**Given** 一个 resume 场景的 `_artifacts.json` 包含一个 200 MB video mp4 artifact 元数
据,对应 file 在磁盘存在且 hash 与记录一致
**When** 执行 `repo.load_run_metadata(run_id=..., run_dir=...)`
**Then** 进程 RSS 增量 SHALL 小于 32 MB
**And** 该 artifact SHALL 被注册到 `repo._artifacts`(drift 通过)

## Non-Goals

- 不改 `PayloadRef` Pydantic schema(字段、类型、validator 保持不变;`_artifacts.json`
  跨 change 兼容)
- 不改 `FILE_MAX_BYTES = 500 * 1024 * 1024` 上限值
- 不把 `FileBackend.write` / `ArtifactRepository.put` 改成 async API;`ahash_path`
  仅作为 executor 链路可选 helper,不引入 `aiofiles`
- 不引入真实 S3/MinIO/Azure SDK adapter;FOR-11 仅实现 `BlobClient` protocol +
  默认内存 client,真实云 SDK adapter 后续按同一协议接入
- Phase 1 曾不迁移既有 `repo.put` 调用站点;FOR-13 已迁移 image / mesh /
  audio / video generator 的本地 ComfyUI source_path 路径。既有 value 路径仍完全
  向后兼容,供 fake / 远端 worker 与无 source_path 的候选对象使用。

## Validation

- 单元测试 `tests/unit/test_repo_put_streaming.py` —— 覆盖 source_path 路径正确性 +
  二选一拒签 + payload_kind 拒签 + 全部 5 个 Scenario(RSS fence 用
  `tracemalloc.get_traced_memory()` peak 或 `resource.getrusage().ru_maxrss` 增量,
  Windows 平台用 `psutil.Process().memory_info().rss` 增量)
- 单元测试 `tests/unit/test_repo_put_streaming.py::test_source_path_hash_failure_preserves_existing_dest_and_metadata`
  —— 覆盖 FOR-12 staging hash atomicity:hash 失败发生时 final payload 与旧 metadata
  保持一致,tmp 清理
- 单元测试 `tests/unit/test_artifact_repository.py` —— 扩 hash_path / hash_payload
  等价性 fence + file/blob drift 校验 fence + repo.put blob source_path fence
- 单元测试 `tests/unit/test_payload_backends.py` —— 扩 InlineBackend source_path
  拒签、BlobBackend value/source_path/write/read/exists/guard fence + FileBackend
  cap 拒签 fence
- baseline:`python -m pytest -q` 实测;既有用例 SHALL 不回退(不硬编码总数)
