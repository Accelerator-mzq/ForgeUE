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
