# repo-put-streaming-payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use forge:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (forge v0.1 不提供 inline executing 模式,统一用 subagent 派发)

**Goal:** Phase 1 — 为 `ArtifactRepository.put` 与 `FileBackend.write` **铺设** zero-copy 源路径写入入口 + stream 哈希接口能力;`load_run_metadata` 的 file kind drift 校验改 stream。**不**改变现有 video / mesh / audio / image executor 内存行为(executor 仍走 `repo.put(value=cand.data)`,Worker / Candidate 协议保留 `data: bytes`),user-visible 大文件内存收益留 Phase 2 follow-on `worker-candidate-source-path-migration` 改 Candidate.source_path + 5 个 executor 迁移调用站点时落地。

**Architecture:** `ArtifactRepository.put` 新增可选 `source_path` 关键字参,与既有 `value` 基于 `_MISSING` sentinel 二选一(D10 允许 `value=None` 合法 inline JSON null);`FileBackend.write` 增加 zero-copy 分支:`stat.S_ISREG` regular file guard + pre-copy cap fail-fast + `shutil.copyfile(src, tmp_dest)` + `os.chmod(0o644)` 权限归一化 + post-copy cap 兜底 + `os.replace(tmp_dest, abs_path)` 原子替换 dest + 异常路径只清理 tmp(D4 atomic + R5-F3 + R5-F4);`hashing.py` 新增 `hash_path(path, *, chunk_size>0)` stream 函数;`load_run_metadata` 仅 file kind drift 校验改走 stream(blob 保旧,inline 不校验)。`PayloadBackend` ABC 同步扩 `source_path` keyword + 新增 `absolute_path` 方法,InlineBackend / BlobBackend 收到非空 `source_path` 即 raise ValueError。

**Tech Stack:** Python 3.12+ / pathlib / hashlib / shutil / pytest / pydantic / psutil(已在 deps)

**Scale mode:** **Full mode**(proposal 182 行虽 < light_threshold=200,但实际 scope 跨 6 文件 + ABC 演进 + 8 D-decision + 10+ test fence,符合 full mode "新模块 / 跨多文件 refactor / 协议变动" 适用场景,不符合 light mode "加 1 字段 / flag / 常量" 适用场景 —— 按 scope 实质判定走 full mode)

---

## File Structure

**Create:**

- `tests/unit/test_repo_put_streaming.py` — 新增专用单测文件,覆盖 zero-copy 路径正确性 / 拒签 / RSS opt-in fence

**Modify:**

- `src/framework/artifact_store/hashing.py:1-29` — 新增 `hash_path(path, *, chunk_size=8*1024*1024) -> str`;既有 `hash_payload` / `hash_inputs` 不动
- `src/framework/artifact_store/payload_backends/base.py:15-30` — `PayloadBackend.write` ABC 签名扩 `source_path` keyword;新增 `absolute_path(ref) -> Path` ABC 方法;`PayloadBackendRegistry.write` 透传 keyword
- `src/framework/artifact_store/payload_backends/file_backend.py:29-67` — `FileBackend.write` 增 source_path zero-copy 分支;实装 `absolute_path`
- `src/framework/artifact_store/payload_backends/inline_backend.py:25-40` — `InlineBackend.write` 收 source_path 时 raise ValueError;`absolute_path` 抛 ValueError(inline 无外部路径)
- `src/framework/artifact_store/payload_backends/blob_backend.py:11-23` — 同款 source_path raise;`absolute_path` 抛 NotImplementedError(stub 一致语义)
- `src/framework/artifact_store/repository.py:55-97` — `ArtifactRepository.put` 加 `source_path` 关键字 + 三 guard(二选一 / 缺一 / payload_kind 拒签)+ 哈希分两路 + backend 透传
- `src/framework/artifact_store/repository.py:201-229` — `load_run_metadata` file kind drift 校验改用 `hash_path(backend.absolute_path(ref))`
- `tests/unit/test_artifact_repository.py` — 扩 hash_path 等价性 + stream drift 校验 + spy hash_payload 未触发
- `tests/unit/test_payload_backends.py` — 扩 source_path raise / zero-copy byte-equal / cap 拒签 / absolute_path 方法

**Do not touch:**

- `src/framework/core/artifact.py`(PayloadRef schema 零变更)
- 18 处既有 `repo.put` 调用站点(executor / mock / export — 完全向后兼容)
- `src/framework/providers/workers/`(Worker Candidate 协议 Phase 1 不动,留 follow-on)

---

## Task 1: `hash_path` stream 哈希函数

- [x] task-1: hashing.py 新增 hash_path stream SHA-256 helper + 等价性 fence

**Files:**

- Modify: `src/framework/artifact_store/hashing.py:1-29`
- Test: `tests/unit/test_artifact_repository.py`(扩,新增 2-3 个 test_hash_path_* 用例)

- [ ] **Step 1: 写 failing test —— hash_path 与 hash_payload 等价性**

把以下用例追加到 `tests/unit/test_artifact_repository.py` 文件末尾:

```python
import pytest

from framework.artifact_store.hashing import hash_path, hash_payload


@pytest.mark.parametrize("size", [1, 64 * 1024, 1 * 1024 * 1024, 50 * 1024 * 1024])
def test_hash_path_equivalent_to_hash_payload(tmp_path, size):
    # 跨多个 size grade 验证 stream / value 哈希等价
    p = tmp_path / f"blob_{size}.bin"
    data = (b"\xA5" * size) if size <= 1024 * 1024 else (b"\xA5" * (size // 16)) * 16
    p.write_bytes(data)
    assert hash_path(p) == hash_payload(p.read_bytes())


def test_hash_path_chunk_size_does_not_affect_output(tmp_path):
    # 不同 chunk_size 输出 SHALL 完全一致
    p = tmp_path / "blob_chunked.bin"
    p.write_bytes(b"forge-ue-test-pattern" * 12345)  # ~258 KB
    h1 = hash_path(p, chunk_size=1024)
    h2 = hash_path(p, chunk_size=8 * 1024 * 1024)
    h3 = hash_payload(p.read_bytes())
    assert h1 == h2 == h3


@pytest.mark.parametrize("bad_chunk_size", [0, -1, -8 * 1024])
def test_hash_path_rejects_non_positive_chunk_size(tmp_path, bad_chunk_size):
    """R4-F4 fence:chunk_size <= 0 必须 raise ValueError;否则 f.read(0) 静默返
    回空 bytes,非空文件会得到 empty hash(silent corruption)。"""
    p = tmp_path / "nonempty.bin"
    p.write_bytes(b"some-content-that-must-be-hashed")
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        hash_path(p, chunk_size=bad_chunk_size)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_artifact_repository.py::test_hash_path_equivalent_to_hash_payload tests/unit/test_artifact_repository.py::test_hash_path_chunk_size_does_not_affect_output -v`
Expected: FAIL with `ImportError: cannot import name 'hash_path' from 'framework.artifact_store.hashing'`

- [ ] **Step 3: 实装 hash_path**

编辑 `src/framework/artifact_store/hashing.py`,在文件末尾(`hash_inputs` 后)追加:

```python
from pathlib import Path
import os


def hash_path(
    path: str | os.PathLike,
    *,
    chunk_size: int = 8 * 1024 * 1024,
) -> str:
    """Stream SHA-256 over file bytes.

    Output equivalent to `hash_payload(Path(path).read_bytes())` but with
    bounded RSS (chunk_size + small overhead).

    R4-F4:chunk_size <= 0 raises ValueError —— `f.read(0)` 会返回空 bytes 让
    非空文件得到 empty file hash(silent corruption)。
    """
    if chunk_size <= 0:
        raise ValueError(
            f"hash_path chunk_size must be positive, got {chunk_size}"
        )
    h = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
```

注意 `os` import 已新增,确保 `from __future__ import annotations` 在文件首部(已有);`Path` 也确认已 import(若无,加 `from pathlib import Path`)。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/unit/test_artifact_repository.py -v -k hash_path`
Expected: PASS,5 个参数化 grade + chunk_size 独立 case 全绿

- [ ] **Step 5: 跑既有用例确认无回退**

Run: `python -m pytest tests/unit/test_artifact_repository.py -v`
Expected: 既有 test_put_and_get_inline 等用例全绿,新增用例也全绿

- [ ] **Step 6: Commit**

```bash
git add src/framework/artifact_store/hashing.py tests/unit/test_artifact_repository.py
git commit -m "feat(artifact-store): add hash_path stream SHA-256 helper (TBD-012 step 1)"
```

---

## Task 2: `PayloadBackend.absolute_path` ABC 方法 + 三 backend 实装

- [x] task-2: PayloadBackend.absolute_path ABC + FileBackend 实装 + InlineBackend/BlobBackend raise

**Files:**

- Modify: `src/framework/artifact_store/payload_backends/base.py:15-30`(ABC)
- Modify: `src/framework/artifact_store/payload_backends/file_backend.py:29-67`(实装)
- Modify: `src/framework/artifact_store/payload_backends/inline_backend.py:25-40`(raise ValueError)
- Modify: `src/framework/artifact_store/payload_backends/blob_backend.py:11-23`(raise NotImplementedError)
- Test: `tests/unit/test_payload_backends.py`(扩,新增 4 个 test_*absolute_path* 用例)

- [ ] **Step 1: 写 failing test —— absolute_path 行为**

把以下用例追加到 `tests/unit/test_payload_backends.py` 文件末尾:

```python
from pathlib import Path

import pytest

from framework.artifact_store.payload_backends import (
    BlobBackend,
    FileBackend,
    InlineBackend,
)
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


def test_file_backend_absolute_path_returns_resolved(tmp_path):
    b = FileBackend(root=str(tmp_path))
    ref = PayloadRef(kind=PayloadKind.file, file_path="run-x/aid.bin", size_bytes=0)
    p = b.absolute_path(ref)
    assert isinstance(p, Path)
    # 应在 root 下且对应 ref.file_path
    assert p == (tmp_path / "run-x" / "aid.bin").resolve()


def test_inline_backend_absolute_path_raises():
    b = InlineBackend()
    ref = PayloadRef(kind=PayloadKind.inline, inline_value={"k": 1}, size_bytes=0)
    with pytest.raises(ValueError, match="inline payload has no external path"):
        b.absolute_path(ref)


def test_blob_backend_absolute_path_raises():
    b = BlobBackend()
    ref = PayloadRef(kind=PayloadKind.blob, blob_key="some-key", size_bytes=0)
    with pytest.raises(NotImplementedError):
        b.absolute_path(ref)


def test_file_backend_absolute_path_rejects_traversal(tmp_path):
    b = FileBackend(root=str(tmp_path))
    ref = PayloadRef(kind=PayloadKind.file, file_path="../escape.bin", size_bytes=0)
    with pytest.raises(ValueError, match="escapes artifact root"):
        b.absolute_path(ref)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_payload_backends.py -v -k absolute_path`
Expected: FAIL with `AttributeError: 'FileBackend' object has no attribute 'absolute_path'`

- [ ] **Step 3: 在 ABC 加 absolute_path 抽象方法**

编辑 `src/framework/artifact_store/payload_backends/base.py`,在 `PayloadBackend` 类内 `exists` 抽象方法后追加:

```python
    @abstractmethod
    def absolute_path(self, ref: PayloadRef) -> "Path":
        """Return the on-disk absolute path for *ref*.

        Only FileBackend has a meaningful implementation;
        InlineBackend SHALL raise ValueError, BlobBackend stub raises
        NotImplementedError.
        """
```

并在文件顶部 import:

```python
from pathlib import Path
```

- [ ] **Step 4: FileBackend 实装 absolute_path**

编辑 `src/framework/artifact_store/payload_backends/file_backend.py`,在 `FileBackend` 类内 `exists` 方法后追加:

```python
    def absolute_path(self, ref: PayloadRef) -> Path:
        """Return resolved absolute Path; reuses _resolve traversal guard."""
        if ref.file_path is None:
            raise ValueError("PayloadRef.file_path is None")
        return self._resolve(ref.file_path)
```

- [ ] **Step 5: InlineBackend 实装 raise ValueError**

编辑 `src/framework/artifact_store/payload_backends/inline_backend.py`,在 `InlineBackend` 类末尾追加:

```python
    def absolute_path(self, ref: PayloadRef) -> "Path":  # type: ignore[name-defined]
        raise ValueError("inline payload has no external path")
```

并在文件顶部 import:`from pathlib import Path`(若未 import)。

- [ ] **Step 6: BlobBackend 实装 raise NotImplementedError**

编辑 `src/framework/artifact_store/payload_backends/blob_backend.py`,在 `BlobBackend` 类内追加:

```python
    def absolute_path(self, ref: PayloadRef) -> "Path":  # type: ignore[name-defined]
        raise NotImplementedError("BlobBackend.absolute_path is deferred (post-MVP)")
```

并在文件顶部 import:`from pathlib import Path`(若未 import)。

- [ ] **Step 7: 跑测试确认通过**

Run: `python -m pytest tests/unit/test_payload_backends.py -v -k absolute_path`
Expected: 4 个 absolute_path 用例全绿

- [ ] **Step 8: Commit**

```bash
git add src/framework/artifact_store/payload_backends/base.py src/framework/artifact_store/payload_backends/file_backend.py src/framework/artifact_store/payload_backends/inline_backend.py src/framework/artifact_store/payload_backends/blob_backend.py tests/unit/test_payload_backends.py
git commit -m "feat(payload-backends): add absolute_path ABC method (TBD-012 step 2)"
```

---

## Task 3: `PayloadBackend.write` ABC 扩 `source_path` keyword + InlineBackend/BlobBackend raise

- [x] task-3: PayloadBackend.write ABC 签名扩 source_path keyword + Inline/Blob backend guard

**Files:**

- Modify: `src/framework/artifact_store/payload_backends/base.py:15-30`(ABC + Registry)
- Modify: `src/framework/artifact_store/payload_backends/inline_backend.py:28-34`(write 签名 + raise)
- Modify: `src/framework/artifact_store/payload_backends/blob_backend.py:16-17`(write 签名 + raise)
- Test: `tests/unit/test_payload_backends.py`(扩,新增 2 个 raise 用例)

- [ ] **Step 1: 写 failing test —— Inline/Blob raise on source_path**

把以下用例追加到 `tests/unit/test_payload_backends.py`:

```python
def test_inline_backend_write_rejects_source_path(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    b = InlineBackend()
    with pytest.raises(ValueError, match="source_path is only supported by FileBackend"):
        b.write(run_id="r", artifact_id="a", source_path=src)


def test_blob_backend_write_rejects_source_path(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    b = BlobBackend()
    with pytest.raises(ValueError, match="source_path is only supported by FileBackend"):
        b.write(run_id="r", artifact_id="a", source_path=src)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_payload_backends.py -v -k "write_rejects_source_path"`
Expected: FAIL with `TypeError: ... got an unexpected keyword argument 'source_path'`

- [ ] **Step 3: 演进 ABC 签名 + 定义 _MISSING sentinel**

编辑 `src/framework/artifact_store/payload_backends/base.py`,文件顶部加:

```python
import os
from typing import Any

# D10 D-NullValueAmbiguity 私有 sentinel — 用 identity 区分 "未传" vs "显式 None"
# (`value=None` 是合法 inline JSON null payload,既有 13 处 inline 调用契约保留)
_MISSING: Any = object()
```

改 `PayloadBackend.write` 抽象签名:

```python
    @abstractmethod
    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> PayloadRef:
        """Persist *value* (or zero-copy from *source_path* on FileBackend) and
        return a PayloadRef that can later be read back.

        Only FileBackend honors *source_path*; InlineBackend / BlobBackend raise.
        `value=_MISSING` is the unset sentinel; `value=None` is a legitimate
        inline JSON null payload (different identity, D10).
        """
```

然后改 `PayloadBackendRegistry.write` 透传:

```python
    def write(self, kind: PayloadKind, value: Any = _MISSING, **kwargs: Any) -> PayloadRef:
        return self.get(kind).write(value, **kwargs)
```

- [ ] **Step 4: InlineBackend 与 BlobBackend 同步签名 + raise**

编辑 `src/framework/artifact_store/payload_backends/inline_backend.py`,改 `write`:

```python
from framework.artifact_store.payload_backends.base import _MISSING

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
                "source_path is only supported by FileBackend, not InlineBackend"
            )
        if value is _MISSING:
            raise ValueError("InlineBackend.write requires value (got _MISSING)")
        # value 可以为 None / dict / list / int / str / bytes 等 — 都合法 inline payload
        size = _estimate_size(value)
        if size > INLINE_MAX_BYTES:
            raise PayloadTooLarge(
                f"inline payload {size} bytes exceeds cap {INLINE_MAX_BYTES}"
            )
        return PayloadRef(kind=PayloadKind.inline, inline_value=value, size_bytes=size)
```

文件顶部加 `import os`(若无)。

编辑 `src/framework/artifact_store/payload_backends/blob_backend.py`,改 `write`:

```python
from framework.artifact_store.payload_backends.base import _MISSING

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
                "source_path is only supported by FileBackend, not BlobBackend"
            )
        raise NotImplementedError("BlobBackend.write is deferred (post-MVP)")
```

文件顶部加 `import os`(若无)。

- [ ] **Step 5: 跑测试确认通过 + 既有 baseline 不回退**

Run: `python -m pytest tests/unit/test_payload_backends.py -v`
Expected: 既有用例(test_inline_roundtrip_small_json 等)全绿,新 2 个 write_rejects 用例全绿

- [ ] **Step 6: Commit**

```bash
git add src/framework/artifact_store/payload_backends/base.py src/framework/artifact_store/payload_backends/inline_backend.py src/framework/artifact_store/payload_backends/blob_backend.py tests/unit/test_payload_backends.py
git commit -m "feat(payload-backends): add source_path keyword to write ABC (TBD-012 step 3)"
```

---

## Task 4: `FileBackend.write` source_path zero-copy 分支

- [x] task-4: FileBackend.write 加 source_path zero-copy 分支(copy2 + stat cap 校验)

**Files:**

- Modify: `src/framework/artifact_store/payload_backends/file_backend.py:47-57`(write 分支)
- Test: `tests/unit/test_payload_backends.py`(扩,新增 byte-equal / cap 拒签 fence)

- [ ] **Step 1: 写 failing test —— zero-copy 分支正确性**

把以下用例追加到 `tests/unit/test_payload_backends.py`:

```python
import os
import shutil
from unittest.mock import patch


def test_file_backend_zero_copy_byte_equal(tmp_path):
    # source_path 路径与 value 路径落盘 bytes SHALL 完全相等
    src = tmp_path / "source.bin"
    payload = b"forge-zero-copy-payload" * 1024  # ~24 KB
    src.write_bytes(payload)
    b = FileBackend(root=str(tmp_path / "store"))
    ref = b.write(  # R6-F3:不传 value(留 _MISSING),只传 source_path
        run_id="r1", artifact_id="aid_zc", suffix=".bin",
        source_path=src,
    )
    assert ref.kind == PayloadKind.file
    # D9 D-HashSource-vs-Dest invariant:size_bytes 取 dest stat,不取 source pre-copy stat
    dest_abs = b.absolute_path(ref)
    assert ref.size_bytes == dest_abs.stat().st_size
    # byte-equal scenario 下 source size == dest size,但 invariant 锁 dest
    assert ref.size_bytes == len(payload)
    assert ref.file_path == "r1/aid_zc.bin"
    written = dest_abs.read_bytes()
    assert written == payload


def test_file_backend_zero_copy_cap_rejection_without_read(tmp_path):
    # 超 cap 的 source_path 在 stat 阶段拒签,不调用 shutil.copyfile
    src = tmp_path / "huge.bin"
    # 创建 sparse file 超 FILE_MAX_BYTES=500MB(实测分配 1 byte)
    from framework.artifact_store.payload_backends.file_backend import FILE_MAX_BYTES
    with src.open("wb") as f:
        f.seek(FILE_MAX_BYTES + 1)
        f.write(b"\x00")
    b = FileBackend(root=str(tmp_path / "store"))
    with patch("framework.artifact_store.payload_backends.file_backend.shutil.copyfile") as spy:
        from framework.artifact_store.payload_backends.base import PayloadTooLarge
        with pytest.raises(PayloadTooLarge):
            b.write(run_id="r", artifact_id="aid_huge", source_path=src)
        assert not spy.called, "copyfile SHALL NOT be invoked when cap rejected"


def test_file_backend_zero_copy_missing_source_raises(tmp_path):
    b = FileBackend(root=str(tmp_path / "store"))
    with pytest.raises(FileNotFoundError):
        b.write(run_id="r", artifact_id="aid", source_path=tmp_path / "absent.bin")


def test_file_backend_zero_copy_rejects_directory_source(tmp_path):
    """R4-F3 D-RegularFileGuard fence:source_path 是目录时拒签(stat 返回值但
    S_ISREG False)。"""
    src_dir = tmp_path / "a_directory"
    src_dir.mkdir()
    b = FileBackend(root=str(tmp_path / "store"))
    with pytest.raises(ValueError, match="must be a regular file"):
        b.write(run_id="r", artifact_id="aid", source_path=src_dir)


def test_file_backend_write_enforces_mutex_at_backend_layer(tmp_path):
    """R6-F3 D-BackendMutexGuard fence:FileBackend.write 直接调用(绕过 repo.put)
    时也必须执行 value/source_path 二选一守门,避免 direct backend 调用静默忽略
    value 写入与调用方预期不符的 bytes。"""
    src = tmp_path / "src.bin"
    src.write_bytes(b"from_source")
    b = FileBackend(root=str(tmp_path / "store"))

    # 同时传 value + source_path → raise
    with pytest.raises(ValueError, match="mutually exclusive"):
        b.write(value=b"x", run_id="r", artifact_id="aid", source_path=src)

    # value=None(显式)+ source_path → 也算 "已传 value",同样 raise
    with pytest.raises(ValueError, match="mutually exclusive"):
        b.write(value=None, run_id="r", artifact_id="aid2", source_path=src)

    # 两者都缺 → raise(_MISSING + source_path=None)
    with pytest.raises(ValueError, match="requires either value or source_path"):
        b.write(run_id="r", artifact_id="aid3")


def test_file_backend_zero_copy_normalizes_permissions(tmp_path):
    """R5-F4 D-PermissionNormalize fence:source 只读时 dest 应仍可读写
    (copyfile 不复制 mtime / 权限,显式 chmod 0o644 归一化)。"""
    import sys
    src = tmp_path / "readonly_source.bin"
    src.write_bytes(b"payload-from-readonly-source")
    # POSIX:只读 source(0o444);Windows 用 stat.S_IREAD attribute
    if sys.platform != "win32":
        src.chmod(0o444)  # readonly
    b = FileBackend(root=str(tmp_path / "store"))
    ref = b.write(run_id="r", artifact_id="aid_ro", suffix=".bin", source_path=src)
    dest_abs = b.absolute_path(ref)
    # dest 应可读 + 可写(POSIX 0o644 = owner rw + others r;Windows 默认 NTFS 写权限)
    assert dest_abs.read_bytes() == b"payload-from-readonly-source"
    # 重复写同 artifact_id 也应该成功(dest 可被 overwrite,不被 source 只读位污染)
    new_src = tmp_path / "rewrite_source.bin"
    new_src.write_bytes(b"rewritten-payload")
    ref2 = b.write(run_id="r", artifact_id="aid_ro", suffix=".bin", source_path=new_src)
    assert b.absolute_path(ref2).read_bytes() == b"rewritten-payload"


def test_file_backend_zero_copy_failure_preserves_existing_dest(tmp_path):
    """R4-F1 D-Atomic fence:copy2 抛异常时既有 final_dest 上的 valid payload
    不被破坏,tmp 文件清理。"""
    # 先用 value 路径在 final_dest 写一个 valid payload
    b = FileBackend(root=str(tmp_path / "store"))
    existing = b"existing-valid-payload-do-not-corrupt"
    ref_old = b.write(
        value=existing, run_id="r", artifact_id="aid_atomic", suffix=".bin",
    )
    dest_abs = b.absolute_path(ref_old)
    assert dest_abs.read_bytes() == existing

    # 再用 source_path 路径写同 artifact_id,但 monkeypatch copyfile 抛异常
    src = tmp_path / "new_source.bin"
    src.write_bytes(b"new-payload-that-should-not-overwrite")
    with patch(
        "framework.artifact_store.payload_backends.file_backend.shutil.copyfile",
        side_effect=OSError("simulated disk full mid-copy"),
    ):
        with pytest.raises(OSError, match="simulated disk full"):
            b.write(
                value=None, run_id="r", artifact_id="aid_atomic", suffix=".bin",
                source_path=src,
            )

    # 关键 invariant:既有 valid payload 未被覆盖 + 没有 .part.* tmp 残留
    assert dest_abs.read_bytes() == existing, "既有 valid payload 不应被破坏(atomic)"
    tmp_files = list(dest_abs.parent.glob(f"{dest_abs.name}.part.*"))
    assert tmp_files == [], f"tmp 文件应被清理,但找到:{tmp_files}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_payload_backends.py -v -k zero_copy`
Expected: FAIL —— 第一个用例报 `_coerce_bytes` 把 `None` 转 bytes 失败(`json.dumps(None)` 实际能跑但 size 不对)或类似

- [ ] **Step 3: 实装 FileBackend.write zero-copy 分支**

编辑 `src/framework/artifact_store/payload_backends/file_backend.py`,完整替换 `write` 方法:

```python
from framework.artifact_store.payload_backends.base import _MISSING

    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> PayloadRef:
        rel = f"{run_id}/{artifact_id}{suffix}"
        abs_path = self._resolve(rel)
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # R6-F3 D-BackendMutexGuard:backend 层守二选一,作为 repo.put 次级 fence
        if value is not _MISSING and source_path is not None:
            raise ValueError(
                "FileBackend.write: value and source_path are mutually exclusive"
            )
        if value is _MISSING and source_path is None:
            raise ValueError(
                "FileBackend.write: requires either value or source_path"
            )

        if source_path is not None:
            # Zero-copy 分支(D1 source_path + D4 D-Atomic + R4-F3 regular file guard)
            import stat as _stat
            import uuid
            src = Path(source_path)
            src_stat = src.stat()  # raises FileNotFoundError if absent
            # R4-F3 D-RegularFileGuard:拒目录 / FIFO / device / socket;symlink follow
            if not _stat.S_ISREG(src_stat.st_mode):
                raise ValueError(
                    f"source_path must be a regular file, "
                    f"got mode 0o{src_stat.st_mode:o} ({src})"
                )
            # Pre-copy fail-fast cap 校验
            if src_stat.st_size > FILE_MAX_BYTES:
                raise PayloadTooLarge(
                    f"file payload {src_stat.st_size} bytes exceeds cap {FILE_MAX_BYTES}"
                )
            # Atomic write(D4 D-Atomic R4-F1):copy2 到同目录 tmp → 验证 → os.replace
            # 原子替换 dest。failure 路径清理 tmp,既有 abs_path 上 valid payload 不破坏
            tmp_dest = abs_path.with_name(
                f"{abs_path.name}.part.{os.getpid()}.{uuid.uuid4().hex[:8]}"
            )
            try:
                # R5-F4 D-PermissionNormalize:用 copyfile(不复制 source metadata)
                # + 显式 chmod 归一化权限,避免 source 只读位污染 artifact store
                shutil.copyfile(src, tmp_dest)
                os.chmod(tmp_dest, 0o644)
                # D9 D-HashSource-vs-Dest:size_bytes 取 dest stat,与 hash 同源
                # Post-copy race window 兜底:source 在 stat / copy 之间被并发写大
                dest_size = tmp_dest.stat().st_size
                if dest_size > FILE_MAX_BYTES:
                    raise PayloadTooLarge(
                        f"file payload {dest_size} bytes (post-copy) exceeds cap {FILE_MAX_BYTES}"
                    )
                os.replace(tmp_dest, abs_path)  # 同盘 atomic; tmp 文件已被替换
            except BaseException:
                tmp_dest.unlink(missing_ok=True)
                raise
            return PayloadRef(
                kind=PayloadKind.file,
                file_path=rel,
                size_bytes=dest_size,
            )

        # Value 分支:source_path 为空时必须有 value(repo.put 已守门,backend 兜底)
        if value is _MISSING:
            raise ValueError("FileBackend.write requires value or source_path")

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

文件顶部 import 增补:

```python
import shutil
```

(`os` / `Path` 已有)

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/unit/test_payload_backends.py -v`
Expected: 既有用例 + 3 个 zero_copy 用例全绿

- [ ] **Step 5: Commit**

```bash
git add src/framework/artifact_store/payload_backends/file_backend.py tests/unit/test_payload_backends.py
git commit -m "feat(file-backend): add source_path zero-copy branch (TBD-012 step 4)"
```

---

## Task 5: `ArtifactRepository.put` 接 `source_path` + 二选一守门

- [x] task-5: ArtifactRepository.put 接 source_path keyword + 二选一守门 + hash 分两路

**Files:**

- Modify: `src/framework/artifact_store/repository.py:55-97`(put 方法)
- Create: `tests/unit/test_repo_put_streaming.py`(新文件)

- [ ] **Step 1: 写 failing test —— 完整 zero-copy 写入 + 拒签**

新建 `tests/unit/test_repo_put_streaming.py`:

```python
"""TBD-012 repo.put streaming zero-copy 路径单元 fence."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.artifact_store.hashing import hash_path, hash_payload
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind


def _video_type() -> ArtifactType:
    return ArtifactType(modality="video", shape="mp4", display_name="video_asset")


def _producer() -> ProducerRef:
    return ProducerRef(run_id="r1", step_id="s1", provider="test", model="zero-copy")


@pytest.fixture
def repo(tmp_path: Path) -> ArtifactRepository:
    reg = get_backend_registry(artifact_root=str(tmp_path / "store"))
    return ArtifactRepository(backend_registry=reg)


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    src = tmp_path / "video.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\xA5" * (8 * 1024 * 1024 - 16))
    return src


def test_zero_copy_writes_byte_equal_and_hash_match(repo, source_file):
    art = repo.put(
        artifact_id="aid_video",
        source_path=source_file,
        artifact_type=_video_type(),
        role=ArtifactRole.intermediate,
        format="mp4",
        mime_type="video/mp4",
        payload_kind=PayloadKind.file,
        producer=_producer(),
        file_suffix=".mp4",
    )
    # D9 D-HashSource-vs-Dest invariant:hash / size_bytes 同源 dest 文件
    backend = repo.backend_registry.get(PayloadKind.file)
    dest_abs = backend.absolute_path(art.payload_ref)

    assert art.payload_ref.kind == PayloadKind.file
    assert art.payload_ref.size_bytes == dest_abs.stat().st_size
    assert art.hash == hash_path(dest_abs)
    # byte-equal scenario 下 source / dest hash 应一致(双 assert 提示 invariant)
    assert hash_path(dest_abs) == hash_path(source_file)
    # 落盘 bytes 与 source 完全一致
    written = dest_abs.read_bytes()
    assert written == source_file.read_bytes()


def test_value_and_source_path_mutually_exclusive(repo, source_file):
    with pytest.raises(ValueError, match="mutually exclusive"):
        repo.put(
            artifact_id="aid",
            value=b"x",
            source_path=source_file,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
        )


def test_neither_value_nor_source_path_raises(repo):
    with pytest.raises(ValueError, match="requires either value or source_path"):
        repo.put(
            artifact_id="aid",
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
        )


def test_explicit_value_none_preserved_as_inline_null_payload(repo):
    """R2-F3 D10 D-NullValueAmbiguity fence:value=None 是合法 inline JSON null payload,
    不应被误判为"未传"(后者用 _MISSING sentinel 区分,基于 identity 比较)。"""
    from framework.artifact_store.hashing import hash_payload
    inline_type = ArtifactType(
        modality="text", shape="structured", display_name="null_payload",
    )
    art = repo.put(
        artifact_id="aid_null",
        value=None,  # 显式 None — 合法 JSON null
        artifact_type=inline_type,
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=_producer(),
    )
    assert art.payload_ref.kind == PayloadKind.inline
    assert art.payload_ref.inline_value is None
    assert art.hash == hash_payload(None)  # 稳定 sha256 hex
    # 回归:从 store 读回也是 None
    assert repo.read_payload("aid_null") is None


def test_source_path_requires_file_kind(repo, source_file):
    with pytest.raises(ValueError, match="payload_kind=file"):
        repo.put(
            artifact_id="aid",
            source_path=source_file,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.inline,
            producer=_producer(),
        )


def test_zero_copy_uses_hash_path_not_hash_payload(repo, source_file):
    # spy hash_payload 不被触发(否则会全读)
    import framework.artifact_store.repository as repo_mod
    with patch.object(repo_mod, "hash_payload", side_effect=AssertionError(
        "hash_payload SHALL NOT be invoked on source_path branch"
    )):
        art = repo.put(
            artifact_id="aid_video2",
            source_path=source_file,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
            file_suffix=".mp4",
        )
    # D9 invariant:hash 取 dest 文件;byte-equal scenario 下 source / dest hash 一致
    backend = repo.backend_registry.get(PayloadKind.file)
    dest_abs = backend.absolute_path(art.payload_ref)
    assert art.hash == hash_path(dest_abs)


def test_source_modified_between_stat_and_copy_hashes_dest_not_source(repo, tmp_path):
    """F1 codex finding fence:source 在 stat / copy 之间被并发改时,Artifact.hash
    与 size_bytes 必须对最终 dest 落盘文件取样,**不**对原始 source 取样。"""
    src = tmp_path / "racing.bin"
    original = b"original-payload-A" * 1024  # 18 KB
    modified = b"modified-payload-B" * 768   # 13.5 KB (不同 size + 不同 bytes)
    src.write_bytes(original)

    # 用 monkeypatch 模拟 shutil.copyfile 在 stat 完成后、真正落盘前 source 被改
    import shutil as _shutil
    real_copyfile = _shutil.copyfile

    def racing_copyfile(s, d, **kwargs):
        # stat 已经记了 source 原始 size_bytes;现在 source 被外部进程改
        src.write_bytes(modified)
        return real_copyfile(s, d, **kwargs)

    import framework.artifact_store.payload_backends.file_backend as fb_mod
    with patch.object(fb_mod.shutil, "copyfile", side_effect=racing_copyfile):
        art = repo.put(
            artifact_id="aid_race",
            source_path=src,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
            file_suffix=".mp4",
        )

    backend = repo.backend_registry.get(PayloadKind.file)
    dest_abs = backend.absolute_path(art.payload_ref)

    # Invariant:hash / size_bytes 都对 dest 取样(post-copy = modified bytes 落盘)
    assert dest_abs.read_bytes() == modified, "落盘 bytes 应是 copy 时刻的 source(modified)"
    assert art.hash == hash_path(dest_abs), "Artifact.hash 必须等于 dest hash"
    assert art.payload_ref.size_bytes == dest_abs.stat().st_size, (
        "PayloadRef.size_bytes 必须等于 dest size,不是 pre-copy stat 的 source size"
    )
    # 强 invariant:hash 不是 original source 的 hash(尽管 stat 时 source 是 original)
    assert art.hash != hash_payload(original), "hash 不应来自被替换前的 source 内容"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_repo_put_streaming.py -v`
Expected: 全部 FAIL —— `repo.put` 未接 `source_path` keyword,会报 `TypeError: put() got an unexpected keyword argument 'source_path'`

- [ ] **Step 3: 演进 ArtifactRepository.put**

编辑 `src/framework/artifact_store/repository.py`,完整替换 `put` 方法签名与实现(line 55-97):

```python
    def put(
        self,
        *,
        artifact_id: str,
        value: Any = _MISSING,
        source_path: str | os.PathLike | None = None,
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
        """Persist the payload, compute hash, and register the Artifact.

        Either *value* (any type, including None for inline JSON null) OR
        *source_path* MUST be provided (mutually exclusive, D10 sentinel-based).
        *source_path* requires payload_kind == PayloadKind.file.
        """
        # D10 D-NullValueAmbiguity:基于 _MISSING identity 比较,允许 value=None
        if value is _MISSING and source_path is None:
            raise ValueError("repo.put requires either value or source_path")
        if value is not _MISSING and source_path is not None:
            raise ValueError("repo.put: value and source_path are mutually exclusive")
        if source_path is not None and payload_kind != PayloadKind.file:
            raise ValueError(
                f"repo.put: source_path requires payload_kind=file (got {payload_kind!r})"
            )

        # 落盘(backend 透传 source_path keyword)
        ref = self._registry.write(
            payload_kind, value,
            run_id=producer.run_id, artifact_id=artifact_id, suffix=file_suffix,
            source_path=source_path,
        )

        # 哈希(分两路:source_path 走 stream 取 dest / value 走全量)
        # D9 D-HashSource-vs-Dest:source_path 路径下 hash 取「最终落盘 dest 文件」,
        # 不取 source 文件,避免 stat / copy / hash 三阶段间 source 被并发改导致漂移
        if source_path is not None:
            dest_abs = self._registry.get(payload_kind).absolute_path(ref)
            content_hash = hash_path(dest_abs)
        else:
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

文件顶部 import 增补:

```python
import os
from framework.artifact_store.hashing import hash_path, hash_payload
from framework.artifact_store.payload_backends.base import _MISSING
```

(`hash_payload` 既有 import 保留,新增 `hash_path` 并入同一 import 行;`os` 加到顶部 import 区;`_MISSING` D10 sentinel 从 base.py 导入共享 identity)

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/unit/test_repo_put_streaming.py -v`
Expected: 5 个用例全绿(byte_equal + 3 个拒签 + spy hash_payload 未触发)

- [ ] **Step 5: 跑 ArtifactRepository 既有 baseline 确认无回退**

Run: `python -m pytest tests/unit/test_artifact_repository.py -v`
Expected: 全绿(既有 test_put_and_get_inline / lineage / variant 等用例 + Task 1 新增 hash_path 用例)

- [ ] **Step 6: Commit**

```bash
git add src/framework/artifact_store/repository.py tests/unit/test_repo_put_streaming.py
git commit -m "feat(repository): add source_path keyword to repo.put (TBD-012 step 5)"
```

---

## Task 6: `load_run_metadata` drift 校验改 stream

- [x] task-6: load_run_metadata 中 **仅 file kind** drift 校验改用 hash_path stream;blob kind 保旧行为(D-DriftScope R3-F4 拍板)

**Files:**

- Modify: `src/framework/artifact_store/repository.py:201-229`(load_run_metadata 中 drift 块)
- Test: `tests/unit/test_artifact_repository.py`(扩,新增 stream drift fence)

- [ ] **Step 1: 写 failing test —— drift 校验走 hash_path 不走 hash_payload**

把以下用例追加到 `tests/unit/test_artifact_repository.py`:

```python
from unittest.mock import patch


def test_load_metadata_uses_stream_hash_for_file_kind(repo, tmp_path):
    # 写一个 file artifact,dump metadata,然后另起 repo 跑 load_run_metadata
    # spy hash_payload 不被 file kind 路径触发
    src = tmp_path / "raw.bin"
    src.write_bytes(b"forge-drift-test" * 4096)  # 64 KB
    art = repo.put(
        artifact_id="aid_drift",
        source_path=src,
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r_drift", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )
    run_dir = tmp_path / "run_dir"
    repo.dump_run_metadata(run_id="r_drift", run_dir=run_dir)

    # 另起一个 repo 跑 load
    fresh_reg = get_backend_registry(artifact_root=str(tmp_path / "store_dup"))
    # 关键:落盘文件在 tmp_path/store/r_drift/aid_drift.bin,fresh repo 用 store_dup
    # → exists() 返回 False,跳过 drift 校验。改用同一 store:
    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    # 清空 in-memory artifacts 强制走 load 路径
    fresh._artifacts.clear()

    import framework.artifact_store.repository as repo_mod
    with patch.object(
        repo_mod, "hash_payload",
        side_effect=AssertionError("hash_payload SHALL NOT be invoked on file kind drift check"),
    ):
        n = fresh.load_run_metadata(run_id="r_drift", run_dir=run_dir)
    assert n == 1
    assert "aid_drift" in fresh._artifacts


def test_load_metadata_rejects_corrupted_file_stream(repo, tmp_path):
    # 落盘后改 file bytes,load_run_metadata 应通过 stream hash 检出 drift 并 skip
    src = tmp_path / "good.bin"
    src.write_bytes(b"good-original-data" * 1024)
    art = repo.put(
        artifact_id="aid_corrupt",
        source_path=src,
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r_corrupt", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )
    run_dir = tmp_path / "run_dir_corrupt"
    repo.dump_run_metadata(run_id="r_corrupt", run_dir=run_dir)

    # 篡改落盘文件
    backend = repo.backend_registry.get(PayloadKind.file)
    on_disk = backend.absolute_path(art.payload_ref)
    on_disk.write_bytes(b"TAMPERED")

    # fresh repo load — drift 应拒
    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()
    n = fresh.load_run_metadata(run_id="r_corrupt", run_dir=run_dir)
    assert n == 0
    assert "aid_corrupt" not in fresh._artifacts


def test_load_metadata_blob_kind_preserves_legacy_behavior(repo, tmp_path):
    """R3-F4 D-DriftScope fence:blob kind drift 校验保旧行为(走
    self._registry.read + hash_payload),NOT 走 hash_path / absolute_path 路径。
    当 BlobBackend stub raise NotImplementedError 时 continue 兜底,语义无变化。"""
    # 手工拼一个 blob kind 的 _artifacts.json entry(BlobBackend stub 无 write)
    from framework.core.artifact import Artifact, ArtifactType, PayloadRef, ProducerRef, Lineage, ValidationRecord
    from framework.core.enums import ArtifactRole, PayloadKind
    import json

    run_dir = tmp_path / "run_dir_blob"
    run_dir.mkdir(parents=True, exist_ok=True)
    blob_art_dict = {
        "artifact_id": "aid_blob",
        "artifact_type": {"modality": "image", "shape": "raster", "display_name": "x"},
        "role": "intermediate",
        "format": "bin",
        "mime_type": "application/octet-stream",
        "payload_ref": {"kind": "blob", "blob_key": "s3://stub/key", "size_bytes": 0},
        "schema_version": "1.0.0",
        "hash": "0" * 64,
        "producer": {"run_id": "r_blob", "step_id": "s1", "provider": "t", "model": "m"},
        "lineage": {},
        "metadata": {},
        "validation": {"status": "pending"},
        "tags": [],
        "created_at": "2026-05-21T10:00:00+00:00",
    }
    (run_dir / "_artifacts.json").write_text(
        json.dumps([blob_art_dict], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()
    # spy hash_path 不应被 blob 路径触发(blob 走 hash_payload 旧路径)
    import framework.artifact_store.repository as repo_mod
    with patch.object(
        repo_mod, "hash_path",
        side_effect=AssertionError("hash_path SHALL NOT be invoked on blob kind drift"),
    ):
        n = fresh.load_run_metadata(run_id="r_blob", run_dir=run_dir)
    # BlobBackend stub.exists() / read() 都抛 NotImplementedError → continue → n=0
    # 关键不是 n 的值,是 hash_path spy 没被触发(D-DriftScope)
    assert n == 0
    assert "aid_blob" not in fresh._artifacts
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_artifact_repository.py -v -k "load_metadata"`
Expected: 第一个 spy 用例 FAIL —— `load_run_metadata` 当前走 `hash_payload(self._registry.read(ref))`,触发 spy 的 AssertionError;第二个用例可能 PASS(corrupt 拒签语义已对)但要确保走 stream 路径

- [ ] **Step 3: 实装 stream drift 校验(D-DriftScope:仅 file kind 改 stream,blob 保旧)**

编辑 `src/framework/artifact_store/repository.py`,定位 `load_run_metadata` 方法内的 drift 校验块(约 line 220-226),完整替换:

```python
            # For external-bytes payloads, verify the bytes haven't drifted
            # since the dump (overwrite, partial write, manual edit).
            # D-DriftScope (R3-F4):仅 file kind 改 stream;blob kind 保旧行为
            # (BlobBackend stub 未实装,既有 self._registry.read(ref) 抛
            # NotImplementedError 被 catch → continue 兜底,语义无变化)。
            # 不要把 blob 字面合并到 hash_path 路径,因 BlobBackend.absolute_path 也
            # raise NotImplementedError → 不可达分支误导实现者。
            if art.payload_ref.kind == _PayloadKind.file:
                # File-kind stream drift:hash_path(absolute_path),不全读;
                # 8 MB chunks → bounded RSS even for large video / mesh artifacts
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
                # Blob-kind 保旧行为:既有 self._registry.read(ref) 抛
                # NotImplementedError 被 catch → continue。BlobBackend 实装后
                # (follow-on `blob-backend-streaming-implementation`)再设计
                # drift 策略(可能走 etag / Last-Modified header,不是本地全 hash)
                try:
                    current = self._registry.read(art.payload_ref)
                except Exception:
                    continue
                if hash_payload(current) != art.hash:
                    continue
            # inline 路径不变(既有实现下面段未触及)
```

注意:旧的 `try: current = self._registry.read(art.payload_ref) ... if hash_payload(current) != art.hash: continue` 块整段删除替换;`payload_present` 检查(`self._registry.exists(art.payload_ref)`)保留在更上一段不动。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/unit/test_artifact_repository.py -v -k "load_metadata"`
Expected: 两个用例全绿(spy 不再触发 + corrupt 拒签语义保留)

- [ ] **Step 5: 跑 ArtifactRepository 既有 baseline + integration test resume case**

Run: `python -m pytest tests/unit/test_artifact_repository.py tests/integration/test_resume_paths.py -v` (后者若存在;否则只跑 unit)
Expected: 全绿

- [ ] **Step 6: Commit**

```bash
git add src/framework/artifact_store/repository.py tests/unit/test_artifact_repository.py
git commit -m "refactor(repository): stream-hash file/blob drift check in load_run_metadata (TBD-012 step 6)"
```

---

## Task 7: 200 MB RSS opt-in heavy fence

- [x] task-7: 200 MB zero-copy RSS 增量 opt-in fence(FORGEUE_RUN_HEAVY_FENCE=1)

**Files:**

- Modify: `tests/unit/test_repo_put_streaming.py`(扩,新增 opt-in heavy fence)

- [ ] **Step 1: 写 opt-in heavy fence**

把以下用例追加到 `tests/unit/test_repo_put_streaming.py`:

```python
@pytest.mark.skipif(
    os.environ.get("FORGEUE_RUN_HEAVY_FENCE") != "1",
    reason="FORGEUE_RUN_HEAVY_FENCE not set — opt-in heavy RSS fence",
)
def test_zero_copy_rss_bounded_200mb(tmp_path):
    """200 MB zero-copy 路径 RSS 增量 < 32 MB(D-FenceOpt-in)。

    Opt-in via FORGEUE_RUN_HEAVY_FENCE=1 — 200MB 临时文件创建 / 拷贝 / hash
    在 CI 慢,默认 skip;开发者 / 验收手动跑过守门 zero-copy 实质行为。
    """
    import psutil
    process = psutil.Process()

    # 创建 200 MB 源文件(分块写,避免一次性 200 MB in-memory)
    src = tmp_path / "big.bin"
    chunk = b"\xA5" * (8 * 1024 * 1024)
    with src.open("wb") as f:
        for _ in range(25):  # 25 * 8MB = 200 MB
            f.write(chunk)

    # R5-F2 D-PeakRSSSampling:后台 thread 100ms 采样 RSS 取 max,捕获瞬时峰值;
    # 否则 only before/after 两点采样会漏掉中间瞬时 200 MB buffer 后释放的场景
    import threading
    import time as _time
    rss_before = process.memory_info().rss
    rss_peak = rss_before
    stop_sampling = threading.Event()

    def _sample_peak():
        nonlocal rss_peak
        while not stop_sampling.is_set():
            try:
                rss_peak = max(rss_peak, process.memory_info().rss)
            except psutil.Error:
                break
            _time.sleep(0.05)  # 50ms 间隔,覆盖 zero-copy 内部短暂 buffer

    sampler = threading.Thread(target=_sample_peak, daemon=True)
    sampler.start()
    try:
        reg = get_backend_registry(artifact_root=str(tmp_path / "store"))
        repo = ArtifactRepository(backend_registry=reg)
        art = repo.put(
            artifact_id="aid_big",
            source_path=src,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
            file_suffix=".mp4",
        )
    finally:
        stop_sampling.set()
        sampler.join(timeout=2.0)

    rss_after = process.memory_info().rss
    rss_delta_mb = (rss_after - rss_before) / (1024 * 1024)
    rss_peak_delta_mb = (rss_peak - rss_before) / (1024 * 1024)
    rss_before_mb = rss_before / (1024 * 1024)
    rss_after_mb = rss_after / (1024 * 1024)
    rss_peak_mb = rss_peak / (1024 * 1024)

    # R2-F4 + R5-F2 D-PeakRSSSampling:输出 peak RSS 而非只输出 before/after delta
    # 让 archive 前 `pytest -s | tee evidence.log` 捕获的日志包含真实峰值数值
    print(
        f"\n[heavy-fence] RSS peak delta: {rss_peak_delta_mb:.2f} MB "
        f"(threshold < 32 MB; rss_before={rss_before_mb:.1f} MB, "
        f"rss_peak={rss_peak_mb:.1f} MB, rss_after={rss_after_mb:.1f} MB, "
        f"end_delta={rss_delta_mb:.2f} MB, payload=200 MB)"
    )

    assert art.payload_ref.size_bytes == 200 * 1024 * 1024
    # R5-F2:核心断言基于 peak,end_delta 仅诊断信息;peak < 32 MB 保证整个调用
    # 期间没有出现过 200 MB 全量内存驻留(即使瞬时释放也会被 peak 抓到)
    assert rss_peak_delta_mb < 32, (
        f"zero-copy RSS peak delta {rss_peak_delta_mb:.2f} MB exceeds 32 MB fence "
        f"(rss_before={rss_before_mb:.1f} MB, rss_peak={rss_peak_mb:.1f} MB, "
        f"rss_after={rss_after_mb:.1f} MB)"
    )
```

- [ ] **Step 2: 跑测试确认默认 skip**

Run: `python -m pytest tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb -v`
Expected: SKIPPED,reason 包含 `FORGEUE_RUN_HEAVY_FENCE not set`

- [ ] **Step 3: opt-in 跑确认 pass(本地手动)**

Run(PowerShell):
```powershell
$env:FORGEUE_RUN_HEAVY_FENCE = "1"
python -m pytest tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb -v
Remove-Item Env:\FORGEUE_RUN_HEAVY_FENCE
```

Run(Git-Bash):
```bash
FORGEUE_RUN_HEAVY_FENCE=1 python -m pytest tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb -v
```

Expected: PASS,RSS delta 报告 < 32 MB

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_repo_put_streaming.py
git commit -m "test(repo-put-streaming): add opt-in 200MB RSS fence (TBD-012 step 7)"
```

---

## Task 8: pytest baseline + comfy_local_smoke_video 端到端冒烟

- [x] task-8: pytest baseline 不回退 + mock_linear 冒烟 + 可选 comfy video live + forge validate

**Files:**

- 无新增 / 修改,纯 verification

- [ ] **Step 1: 跑 baseline pytest -q 确认 1190+ 无回退**

Run: `python -m pytest -q`
Expected:
- 既有 1190+ 用例全绿
- 新增用例:Task 1 (2) + Task 2 (4) + Task 3 (2) + Task 4 (3) + Task 5 (5) + Task 6 (2) + Task 7 (1 skip default) ≈ **+19 个 test case**,passed count 增加 ~18(heavy fence 默认 skip)

若有 fail / error 回看对应 task。

- [ ] **Step 2: 离线 mock 冒烟 examples/mock_linear.json(快)**

Run:
```bash
python -m framework.run --task examples/mock_linear.json --run-id tbd012_mock --artifact-root ./demo_artifacts/tbd012
```
Expected: 退出码 0;产物在 `./demo_artifacts/tbd012/<today>/tbd012_mock/`;无 `repo.put` 相关报错

- [ ] **Step 3:(可选,手动)live ComfyUI 端到端冒烟 video pipeline**

前提:终端 1 已起 `python -m factory_v3 serve`,ComfyUI 暖机完成。

Run(Git-Bash;终端 2):
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
export FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input
python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id tbd012_video --artifact-root ./demo_artifacts/tbd012
```

Expected:
- ~7 分钟生成完成
- 产物 `./demo_artifacts/tbd012/<today>/tbd012_video/<video_artifact_id>.mp4` 存在,大小 5-15 MB
- `_artifacts.json` 中 video artifact 的 hash 与 `python -c "from framework.artifact_store.hashing import hash_path; print(hash_path('<mp4 path>'))"` 输出一致
- **Phase 1 关键确认:executor 仍走 `value=cand.data` 路径**(Worker 协议未变),所以 mp4 路径下 `repo.put` 内 hash 计算仍走 `hash_payload(value)`,**不**触发 stream 路径 —— 这是 design D-WorkerCandidateMigration Phase 1 的预期行为

冒烟完毕停 ComfyUI:终端 1 跑 `python -m factory_v3 stop`(沿 feedback_test_should_release_resources 偏好)。

- [ ] **Step 4:(若 step 3 跳过)用 unit 路径补冒烟**

若不愿跑 7 分钟 live ComfyUI,可用以下 unit 替代证明 `_artifacts.json` 与 stream drift 协作:

Run: `python -m pytest tests/unit/test_artifact_repository.py -v -k "load_metadata or hash_path"`
Expected: 全绿

- [ ] **Step 5: 跑 forge validate 确认 4 件套合规**

Run: `node "C:/Users/mzq/.claude/plugins/cache/accelerator-mzq-forge/forge/4.0.0/scripts/run-forge.mjs" validate repo-put-streaming-payload`
Expected: exit 0,无 anchor / YAML / spec 缺失报错

- [ ] **Step 6: Final commit(若有未 commit 的 demo evidence 不进库,只留 plan / spec /源码修改)**

```bash
git status  # 确认只有目标文件
git log --oneline -8  # 应看到 Task 1-7 的 7 个 commit
```

无新代码改动则跳过此 step。

---

## Documentation Sync

archive 前同步检查以下 docs/ 五件套,确认 zero-copy + stream hashing 不留 doc drift:

- [ ] `docs/requirements/SRS.md` §3.6 FR-STORE-* 系列 —— 是否需要加一条 FR-STORE-007 (or 等效编号) 描述 zero-copy 写入入口?若 SRS 段落已表达"`repo.put` 接 payload"足够抽象 → 不动;若显式描述 `value: Any` → 加一句 "Repository SHALL 接受 `source_path` 可选关键字以走 zero-copy 落盘"。
- [ ] `docs/design/HLD.md` §4 / §D.2 —— payload backend layout 段落,加一句 FileBackend zero-copy 分支 + ABC 演进(`source_path` keyword + `absolute_path` 方法)。
- [ ] `docs/design/LLD.md` §F0-3 —— `Repository.put` 签名与 hash 计算路径(value 路径走 `hash_payload`、source_path 路径走 `hash_path(dest)` 而非 `hash_path(source)` per D-HashSource-vs-Dest);加 `hash_path` 函数描述。
- [ ] `docs/testing/test_spec.md` —— 加新增 fence 用例编号:
  - test_repo_put_streaming.py × 6(含 heavy fence 1 opt-in)
  - test_artifact_repository.py 扩 × 4
  - test_payload_backends.py 扩 × 7
  - 合计 +17 个 case(opt-in 1 个不计入默认 1190+ baseline 增量)
- [ ] `docs/acceptance/acceptance_report.md` —— FR-STORE-* 状态矩阵若有,加一行验收记录(TBD-012 closed)。

## Archive 前必产 Evidence(F4 codex writeback)

`archive_summary` 写入前,implementer / verifier 必须本地跑过一次 heavy fence
并把输出保存为 evidence 文件(走 `forge/changes/repo-put-streaming-payload/.evidence/`):

- [ ] **跑 heavy fence 并捕获输出**:

  PowerShell:
  ```powershell
  $env:FORGEUE_RUN_HEAVY_FENCE = "1"
  python -m pytest tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb -v -s `
    | Tee-Object -FilePath "forge/changes/repo-put-streaming-payload/.evidence/heavy-fence-rss-200mb.log"
  Remove-Item Env:\FORGEUE_RUN_HEAVY_FENCE
  ```

  Git-Bash:
  ```bash
  FORGEUE_RUN_HEAVY_FENCE=1 python -m pytest \
    tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb -v -s \
    | tee forge/changes/repo-put-streaming-payload/.evidence/heavy-fence-rss-200mb.log
  ```

- [ ] **附机器环境说明到 evidence**:在 `heavy-fence-rss-200mb.log` 末尾追加:

  ```bash
  echo "---machine env---" >> forge/changes/repo-put-streaming-payload/.evidence/heavy-fence-rss-200mb.log
  uname -a >> ... || systeminfo | head -10 >> ...  # Windows
  python --version >> ...
  echo "free RAM:" && free -h >> ... 2>/dev/null || systeminfo | grep -E "Total Physical|Available Physical" >> ...
  ```

- [ ] **断言**:`heavy-fence-rss-200mb.log` 必须满足全部:
  - 含 `PASSED` 行(测试通过)
  - 含 `[heavy-fence] RSS peak delta: <N.NN> MB (threshold < 32 MB; ...)` 行
    (R2-F4 + R5-F2 测试 pass 路径 print,确保 evidence 包含真实 peak 数值,不只
    PASSED 标签)
  - `<N.NN>` < 32(与 `specs/probe-and-validation.md` peak fence 阈值对齐)
  - **若实际 delta 接近阈值(> 24 MB)**:在 evidence 文件顶部加 NOTE 段说明机器
    内存压力 / Python 进程 fixed overhead 等可能原因,以便 archive review 判断
  - **grep 自检命令**(archive 前可直接跑):
    ```bash
    grep -E "PASSED|\[heavy-fence\] RSS peak delta" forge/changes/repo-put-streaming-payload/.evidence/heavy-fence-rss-200mb.log
    ```
    应同时输出两行。

---

## Apply 阶段产出(/forge:apply 2026-05-21 完成)

```yaml
applied_commits:
  - task-1: ec42d34  # feat(artifact-store): add hash_path stream SHA-256 helper (GREEN)
  - task-2: 4a1d2d6  # feat(payload-backends): add absolute_path ABC method (GREEN)
  - task-3: 3c1168f  # feat(payload-backends): add source_path keyword + _MISSING sentinel to write ABC (GREEN)
  - task-4: efb694b  # feat(file-backend): implement source_path zero-copy branch (GREEN)
  - task-5: 616bcba  # feat(repository): add source_path keyword to repo.put with D9 hash-dest semantics (GREEN)
  - task-6: f662ef3  # refactor(repository): stream hash file kind drift in load_run_metadata (GREEN)
  - task-7: f3808e6  # test(repo-put-streaming): add opt-in 200MB RSS heavy fence (single)
  - task-8: a7b6253  # docs(propose): task-8 verify done + sync proposal §影响模块 含 D10 validator 微调
final_head: a7b6253
pause_decisions:
  - paused_at: 2026-05-21T22:05:00Z
    task_ref: tasks.md#task-5
    issue_summary: |
      Task 5 subagent 实施 D10 D-NullValueAmbiguity spec 时发现 PayloadRef._validate_exclusive 旧守门
      `inline_value is None` 拒签会让 spec R2-F3 scenario `test_explicit_value_none_preserved_as_inline_null_payload`
      失败;proposal §影响模块 之前写 src/framework/core/artifact.py "不影响(PayloadRef schema 零变更)"。
      subagent 自行做了 1 行 condition 微调 `"inline_value" not in self.model_fields_set`。
    chosen_option: 4
    notes: |
      User option=4 (Other 等价 option=1):接受 fix(D10 spec 要求 + backward compatible — 既有 18 处
      inline 调用 grep 0 命中 value=None),Task 8 verification 阶段回写 proposal §影响模块 把
      artifact.py 加进 ABC 跟进改动段(commit a7b6253)。PayloadRef 字段结构零变更,仅 validator 微调。
```
