"""F0-2 acceptance: inline + file round-trip, 10MB image + 200 byte JSON, blob stubbed."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.artifact_store.payload_backends import (
    BlobBackend,
    FileBackend,
    InlineBackend,
    PayloadTooLarge,
    get_backend_registry,
)
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


# ---------- Inline ----------

def test_inline_roundtrip_small_json():
    b = InlineBackend()
    ref = b.write({"k": "v", "n": 3}, run_id="r1", artifact_id="a1")
    assert ref.kind == PayloadKind.inline
    assert b.read(ref) == {"k": "v", "n": 3}
    assert b.exists(ref)


def test_inline_rejects_oversized():
    b = InlineBackend()
    big = "x" * (65 * 1024)
    with pytest.raises(PayloadTooLarge):
        b.write(big, run_id="r1", artifact_id="a1")


def test_inline_200_byte_json_acceptance():
    """Plan §F0-2 acceptance: 200 byte JSON round-trips through inline."""
    b = InlineBackend()
    payload = {"field_" + str(i): i for i in range(5)}
    ref = b.write(payload, run_id="r_acc", artifact_id="tiny")
    assert ref.size_bytes < 64 * 1024
    assert b.read(ref) == payload


# ---------- File ----------

def test_file_roundtrip_bytes(tmp_path: Path):
    b = FileBackend(root=str(tmp_path))
    data = b"\x89PNG\r\n\x1a\nsomebytes"
    ref = b.write(data, run_id="run_1", artifact_id="img_1", suffix=".png")
    assert ref.kind == PayloadKind.file
    assert ref.file_path == "run_1/img_1.png"
    assert b.read(ref) == data
    assert b.exists(ref)


def test_file_roundtrip_structured_becomes_json(tmp_path: Path):
    b = FileBackend(root=str(tmp_path))
    payload = {"k": [1, 2, 3]}
    ref = b.write(payload, run_id="r1", artifact_id="spec", suffix=".json")
    raw = b.read(ref).decode("utf-8")
    assert json.loads(raw) == payload


def test_file_rejects_path_traversal(tmp_path: Path):
    b = FileBackend(root=str(tmp_path))
    data = b.write(b"x", run_id="r1", artifact_id="a", suffix=".bin")
    data.file_path = "../outside.bin"
    with pytest.raises(ValueError):
        b.read(data)


def test_file_10mb_image_acceptance(tmp_path: Path):
    """Plan §F0-2 acceptance: 10MB binary round-trips through file backend."""
    b = FileBackend(root=str(tmp_path))
    data = b"\x00" * (10 * 1024 * 1024)
    ref = b.write(data, run_id="run_acc", artifact_id="big_img", suffix=".bin")
    assert ref.size_bytes == 10 * 1024 * 1024
    read_back = b.read(ref)
    assert len(read_back) == 10 * 1024 * 1024


def test_file_rejects_over_cap(tmp_path: Path, monkeypatch):
    from framework.artifact_store.payload_backends import file_backend
    monkeypatch.setattr(file_backend, "FILE_MAX_BYTES", 1024)
    b = file_backend.FileBackend(root=str(tmp_path))
    with pytest.raises(PayloadTooLarge):
        b.write(b"x" * 2048, run_id="r1", artifact_id="a1", suffix=".bin")


# ---------- Blob stub ----------

def test_blob_not_implemented():
    b = BlobBackend()
    from framework.core.artifact import PayloadRef
    ref = PayloadRef(kind=PayloadKind.blob, blob_key="bucket/key", size_bytes=1)
    with pytest.raises(NotImplementedError):
        b.read(ref)
    with pytest.raises(NotImplementedError):
        b.write({}, run_id="r", artifact_id="a")


# ---------- Registry dispatch ----------

def test_registry_dispatch(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    inline_ref = reg.write(PayloadKind.inline, {"x": 1}, run_id="r1", artifact_id="a1")
    file_ref = reg.write(PayloadKind.file, b"hello", run_id="r1", artifact_id="a2", suffix=".txt")
    assert reg.read(inline_ref) == {"x": 1}
    assert reg.read(file_ref) == b"hello"
    assert reg.exists(inline_ref)
    assert reg.exists(file_ref)


# ---------- absolute_path ABC fence (TBD-012 step 2) ----------

def test_file_backend_absolute_path_returns_resolved(tmp_path: Path):
    """FileBackend.absolute_path 返回解析后的绝对路径,在 root 下。"""
    b = FileBackend(root=str(tmp_path))
    ref = PayloadRef(kind=PayloadKind.file, file_path="run-x/aid.bin", size_bytes=0)
    p = b.absolute_path(ref)
    assert isinstance(p, Path)
    # 应在 root 下且对应 ref.file_path
    assert p == (tmp_path / "run-x" / "aid.bin").resolve()


def test_inline_backend_absolute_path_raises():
    """InlineBackend.absolute_path 应 raise ValueError(inline 无外部路径)。"""
    b = InlineBackend()
    ref = PayloadRef(kind=PayloadKind.inline, inline_value={"k": 1}, size_bytes=0)
    with pytest.raises(ValueError, match="inline payload has no external path"):
        b.absolute_path(ref)


def test_blob_backend_absolute_path_raises():
    """BlobBackend.absolute_path 应 raise NotImplementedError(stub 一致语义)。"""
    b = BlobBackend()
    ref = PayloadRef(kind=PayloadKind.blob, blob_key="some-key", size_bytes=0)
    with pytest.raises(NotImplementedError):
        b.absolute_path(ref)


def test_file_backend_absolute_path_rejects_traversal(tmp_path: Path):
    """FileBackend.absolute_path 复用 _resolve traversal guard,拒绝路径穿越。"""
    b = FileBackend(root=str(tmp_path))
    ref = PayloadRef(kind=PayloadKind.file, file_path="../escape.bin", size_bytes=0)
    with pytest.raises(ValueError, match="escapes artifact root"):
        b.absolute_path(ref)


# ---------- source_path keyword raise fence (TBD-012 step 3) ----------

def test_inline_backend_write_rejects_source_path(tmp_path):
    """InlineBackend.write 收到 source_path 非空应 raise ValueError (D10 守门)。"""
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    b = InlineBackend()
    with pytest.raises(ValueError, match="source_path is only supported by FileBackend"):
        b.write(run_id="r", artifact_id="a", source_path=src)


def test_blob_backend_write_rejects_source_path(tmp_path):
    """BlobBackend.write 收到 source_path 非空应 raise ValueError (D10 守门)。"""
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    b = BlobBackend()
    with pytest.raises(ValueError, match="source_path is only supported by FileBackend"):
        b.write(run_id="r", artifact_id="a", source_path=src)


def test_blob_backend_write_requires_value_or_source_path():
    """Spec 与 InlineBackend 对等:value 缺失 + source_path 缺失 → ValueError,
    不是 NotImplementedError。R1-F1 BlobBackend _MISSING guard fence。"""
    b = BlobBackend()
    with pytest.raises(ValueError, match="requires value or source_path"):
        b.write(run_id="r", artifact_id="a")


# ---------- zero-copy 分支 fence (TBD-012 step 4) ----------

import os as _os
import shutil as _shutil
from unittest.mock import patch as _patch


def test_file_backend_zero_copy_byte_equal(tmp_path):
    """zero-copy 落盘 bytes 与 source 完全一致;D9 size_bytes 取 dest stat。"""
    src = tmp_path / "source.bin"
    payload = b"forge-zero-copy-payload" * 1024  # ~24 KB
    src.write_bytes(payload)
    b = FileBackend(root=str(tmp_path / "store"))
    ref = b.write(  # 不传 value(留 _MISSING),只传 source_path
        run_id="r1", artifact_id="aid_zc", suffix=".bin",
        source_path=src,
    )
    assert ref.kind == PayloadKind.file
    dest_abs = b.absolute_path(ref)
    # D9 invariant:size_bytes 取 dest stat
    assert ref.size_bytes == dest_abs.stat().st_size
    assert ref.size_bytes == len(payload)
    assert ref.file_path == "r1/aid_zc.bin"
    assert dest_abs.read_bytes() == payload


def test_file_backend_zero_copy_cap_rejection_without_read(tmp_path):
    """R4-F3 + cap pre-copy fence:超 cap source stat 阶段拒签,不调 copyfile。"""
    src = tmp_path / "huge.bin"
    from framework.artifact_store.payload_backends.file_backend import FILE_MAX_BYTES
    # sparse file (only 1 byte allocated)
    with src.open("wb") as f:
        f.seek(FILE_MAX_BYTES + 1)
        f.write(b"\x00")
    b = FileBackend(root=str(tmp_path / "store"))
    with _patch("framework.artifact_store.payload_backends.file_backend.shutil.copyfile") as spy:
        from framework.artifact_store.payload_backends.base import PayloadTooLarge
        with pytest.raises(PayloadTooLarge):
            b.write(run_id="r", artifact_id="aid_huge", source_path=src)
        assert not spy.called, "copyfile SHALL NOT be invoked when cap rejected"


def test_file_backend_zero_copy_missing_source_raises(tmp_path):
    b = FileBackend(root=str(tmp_path / "store"))
    with pytest.raises(FileNotFoundError):
        b.write(run_id="r", artifact_id="aid", source_path=tmp_path / "absent.bin")


def test_file_backend_zero_copy_rejects_directory_source(tmp_path):
    """R4-F3 D-RegularFileGuard:目录拒签。"""
    src_dir = tmp_path / "a_directory"
    src_dir.mkdir()
    b = FileBackend(root=str(tmp_path / "store"))
    with pytest.raises(ValueError, match="must be a regular file"):
        b.write(run_id="r", artifact_id="aid", source_path=src_dir)


def test_file_backend_write_enforces_mutex_at_backend_layer(tmp_path):
    """R6-F3 D-BackendMutexGuard:value/source_path 二选一守门 + 缺一守门。"""
    src = tmp_path / "src.bin"
    src.write_bytes(b"from_source")
    b = FileBackend(root=str(tmp_path / "store"))
    # 同时传 value + source_path → raise
    with pytest.raises(ValueError, match="mutually exclusive"):
        b.write(value=b"x", run_id="r", artifact_id="aid", source_path=src)
    # value=None + source_path → 仍算"已传 value",同样 raise
    with pytest.raises(ValueError, match="mutually exclusive"):
        b.write(value=None, run_id="r", artifact_id="aid2", source_path=src)
    # 两者都缺 → raise(_MISSING + source_path=None)
    with pytest.raises(ValueError, match="requires either value or source_path"):
        b.write(run_id="r", artifact_id="aid3")


def test_file_backend_zero_copy_normalizes_permissions(tmp_path):
    """R5-F4 D-PermissionNormalize:source 只读时 dest 仍可写(0o644 归一化)。"""
    import sys
    src = tmp_path / "readonly_source.bin"
    src.write_bytes(b"payload-from-readonly-source")
    if sys.platform != "win32":
        src.chmod(0o444)
    b = FileBackend(root=str(tmp_path / "store"))
    ref = b.write(run_id="r", artifact_id="aid_ro", suffix=".bin", source_path=src)
    dest_abs = b.absolute_path(ref)
    assert dest_abs.read_bytes() == b"payload-from-readonly-source"
    # 重复写同 artifact_id 也应该成功
    new_src = tmp_path / "rewrite_source.bin"
    new_src.write_bytes(b"rewritten-payload")
    ref2 = b.write(run_id="r", artifact_id="aid_ro", suffix=".bin", source_path=new_src)
    assert b.absolute_path(ref2).read_bytes() == b"rewritten-payload"


def test_file_backend_zero_copy_failure_preserves_existing_dest(tmp_path):
    """R4-F1 D-Atomic:copyfile 抛异常时既有 dest 上 valid payload 不破坏,tmp 清理。"""
    b = FileBackend(root=str(tmp_path / "store"))
    existing = b"existing-valid-payload-do-not-corrupt"
    ref_old = b.write(
        value=existing, run_id="r", artifact_id="aid_atomic", suffix=".bin",
    )
    dest_abs = b.absolute_path(ref_old)
    assert dest_abs.read_bytes() == existing

    src = tmp_path / "new_source.bin"
    src.write_bytes(b"new-payload-that-should-not-overwrite")
    with _patch(
        "framework.artifact_store.payload_backends.file_backend.shutil.copyfile",
        side_effect=OSError("simulated disk full mid-copy"),
    ):
        with pytest.raises(OSError, match="simulated disk full"):
            b.write(
                run_id="r", artifact_id="aid_atomic", suffix=".bin",
                source_path=src,
            )

    # 关键 invariant:既有 valid payload 未被覆盖 + 没有 .part.* tmp 残留
    assert dest_abs.read_bytes() == existing, "既有 valid payload 不应被破坏(atomic)"
    tmp_files = list(dest_abs.parent.glob(f"{dest_abs.name}.part.*"))
    assert tmp_files == [], f"tmp 文件应被清理,但找到:{tmp_files}"


def test_file_backend_post_copy_cap_overflow_preserves_existing_dest(tmp_path):
    """D9 + R5-F3 fence:post-copy `dest_size > FILE_MAX_BYTES` 分支触发 PayloadTooLarge 时
    既有 abs_path 上 valid payload 不破坏 + tmp 文件清理(race window 防御)。"""
    from framework.artifact_store.payload_backends.base import PayloadTooLarge
    from framework.artifact_store.payload_backends.file_backend import FILE_MAX_BYTES
    import shutil as _shutil

    b = FileBackend(root=str(tmp_path / "store"))
    # 先写一个既有 valid payload 到 abs_path
    existing = b"existing-valid-payload-do-not-corrupt"
    ref_old = b.write(value=existing, run_id="r", artifact_id="aid_postcp", suffix=".bin")
    dest_abs = b.absolute_path(ref_old)
    assert dest_abs.read_bytes() == existing

    src = tmp_path / "src.bin"
    src.write_bytes(b"normal-size-payload-pre-copy")

    # monkeypatch shutil.copyfile:在 copyfile 后把 tmp_dest 写大到超 cap,
    # 模拟 source 在 stat / copy 之间被并发扩写,落盘超 cap bytes 的 race window 场景
    real_copyfile = _shutil.copyfile

    def race_then_oversize(src_p, dst_p, **kwargs):
        # 拷贝原始 payload bytes,然后将 tmp_dest 替换为超 cap 大小内容
        real_copyfile(src_p, dst_p, **kwargs)
        with open(dst_p, "wb") as f:
            f.write(b"\x00" * (FILE_MAX_BYTES + 1))

    import framework.artifact_store.payload_backends.file_backend as fb_mod
    with _patch.object(fb_mod.shutil, "copyfile", side_effect=race_then_oversize):
        with pytest.raises(PayloadTooLarge, match="post-copy"):
            b.write(
                run_id="r", artifact_id="aid_postcp", suffix=".bin", source_path=src,
            )

    # Invariant 1:既有 valid payload 不应被破坏(D4 atomic:只改 tmp,不动 abs_path)
    assert dest_abs.read_bytes() == existing, "既有 valid payload 不应被破坏(R4-F1 atomic)"
    # Invariant 2:.part.* tmp 文件应被清理(except BaseException + unlink)
    tmp_files = list(dest_abs.parent.glob(f"{dest_abs.name}.part.*"))
    assert tmp_files == [], f"tmp 文件应被清理,但找到:{tmp_files}"
