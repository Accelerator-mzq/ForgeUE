# FOR-28 FBX Self-Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close FOR-28 / LR-0129 by refusing provider-returned FBX assets that reference external texture/media sidecars unless the mesh step explicitly asks for geometry-only output.

**Architecture:** Keep the change inside `src/framework/providers/workers/mesh_worker.py`. Add a dependency-free FBX self-containment predicate, wire it into `_build_candidate()`, and keep the existing fallthrough behavior: unsupported FBX tries the next ranked URL before aborting. Do not add `ufbx` / PyFBX as a hard runtime dependency.

**Tech Stack:** Python 3.12, pytest, ForgeUE mesh worker, existing `MeshWorkerUnsupportedResponse` fallthrough semantics.

---

### Task 1: RED tests for FBX self-containment

**Files:**
- Modify: `tests/unit/test_cn_image_adapters.py`
- Test: `tests/unit/test_cn_image_adapters.py`

- [ ] **Step 1: Add failing unit tests**

Add a focused `TestHunyuanMeshFbxSelfContainment` class near the existing mesh format tests:

```python
class TestHunyuanMeshFbxSelfContainment:
    def test_ascii_fbx_without_texture_filename_is_self_contained(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_fbx
        ascii_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"FBXHeaderExtension:  {\n"
            b"    FBXHeaderVersion: 1003\n"
            b"}\n"
            b"Objects:  {\n"
            b"    Model: 1, \"Model::Cube\", \"Mesh\" {}\n"
            b"}\n"
        )
        assert _is_self_contained_fbx(ascii_fbx) is True

    def test_ascii_fbx_with_texture_filename_is_not_self_contained(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_fbx
        ascii_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"Objects:  {\n"
            b"    Texture: 2, \"Texture::Wood\", \"\" {\n"
            b"        FileName: \"C:\\\\textures\\\\wood_albedo.png\"\n"
            b"        RelativeFilename: \"textures\\\\wood_albedo.png\"\n"
            b"    }\n"
            b"}\n"
        )
        assert _is_self_contained_fbx(ascii_fbx) is False

    def test_binary_fbx_with_texture_filename_marker_is_not_self_contained(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_fbx
        binary_fbx = (
            b"Kaydara FBX Binary  \x00\x1a\x00"
            + b"\x00" * 32
            + b"RelativeFilename\x00textures/wood_normal.jpg\x00"
            + b"\x00" * 32
        )
        assert _is_self_contained_fbx(binary_fbx) is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/unit/test_cn_image_adapters.py::TestHunyuanMeshFbxSelfContainment -q
```

Expected: fail because `_is_self_contained_fbx` is not defined.

### Task 2: GREEN implementation for FBX predicate

**Files:**
- Modify: `src/framework/providers/workers/mesh_worker.py`
- Test: `tests/unit/test_cn_image_adapters.py`

- [ ] **Step 1: Implement minimal predicate**

Add a small helper beside `_is_self_contained_obj()` / `_is_self_contained_gltf()`:

```python
_FBX_EXTERNAL_RESOURCE_EXTS = (
    ".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff",
    ".webp", ".exr", ".dds", ".hdr", ".psd",
)


def _is_self_contained_fbx(data: bytes) -> bool:
    """Return False when FBX bytes name texture/media sidecar files."""
    text = data.decode("utf-8", errors="ignore")
    lower_text = text.lower()
    for marker in ("filename", "relativefilename"):
        start = 0
        while True:
            pos = lower_text.find(marker, start)
            if pos == -1:
                break
            window = lower_text[pos:pos + 512]
            if any(ext in window for ext in _FBX_EXTERNAL_RESOURCE_EXTS):
                return False
            start = pos + len(marker)
    return True
```

- [ ] **Step 2: Run focused tests and verify GREEN**

Run:

```bash
python -m pytest tests/unit/test_cn_image_adapters.py::TestHunyuanMeshFbxSelfContainment -q
```

Expected: pass.

### Task 3: Wire FBX predicate into worker fallthrough

**Files:**
- Modify: `tests/unit/test_cn_image_adapters.py`
- Modify: `src/framework/providers/workers/mesh_worker.py`
- Test: `tests/unit/test_cn_image_adapters.py`

- [ ] **Step 1: Add failing runtime tests**

Extend `TestHunyuanMeshFbxSelfContainment`:

```python
    def test_build_candidate_rejects_textured_fbx_in_normal_mode(self):
        from framework.providers.workers.mesh_worker import (
            MeshWorkerUnsupportedResponse,
            _build_candidate,
        )
        textured_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"FBXHeaderExtension:  {\n    FBXHeaderVersion: 1003\n}\n"
            b"Texture: 2, \"Texture::Wood\", \"\" {\n"
            b"    FileName: \"textures/wood.png\"\n"
            b"}\n"
        )
        with pytest.raises(MeshWorkerUnsupportedResponse, match="non-self-contained .fbx"):
            _build_candidate(
                mesh_bytes=textured_fbx,
                url="https://mock/model.fbx",
                job_id="job_fbx_sidecar",
                index=0,
                requested_fmt="fbx",
                geometry_only=False,
            )

    def test_build_candidate_accepts_textured_fbx_in_geometry_only_mode(self):
        from framework.providers.workers.mesh_worker import _build_candidate
        textured_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"FBXHeaderExtension:  {\n    FBXHeaderVersion: 1003\n}\n"
            b"Texture: 2, \"Texture::Wood\", \"\" {\n"
            b"    RelativeFilename: \"textures/wood.png\"\n"
            b"}\n"
        )
        cand = _build_candidate(
            mesh_bytes=textured_fbx,
            url="https://mock/model.fbx",
            job_id="job_fbx_geometry_only",
            index=0,
            requested_fmt="fbx",
            geometry_only=True,
        )
        assert cand.format == "fbx"
        assert cand.metadata["missing_materials"] is True

    def test_worker_falls_through_when_fbx_references_external_texture(self, monkeypatch):
        import asyncio
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker

        bad_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"FBXHeaderExtension:  {\n    FBXHeaderVersion: 1003\n}\n"
            b"Texture: 2, \"Texture::Wood\", \"\" {\n"
            b"    FileName: \"textures/wood.png\"\n"
            b"}\n"
        )
        good_glb = b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 100
        url_to_bytes = {
            "https://mock/model.fbx": bad_fbx,
            "https://mock/signed-good-mesh": good_glb,
        }
        download_calls = []

        async def fake_submit(self, body, *, timeout_s):
            return "job_fbx_fallthrough"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done", "result": {
                "urls": [
                    "https://mock/model.fbx",
                    "https://mock/signed-good-mesh",
                ]
            }}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            download_calls.append(url)
            return url_to_bytes[url]

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        worker = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(worker.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "fbx", "prompt": "fbx fallthrough"},
            num_candidates=1,
            timeout_s=30.0,
        ))
        assert [c.format for c in cands] == ["glb"]
        assert download_calls == [
            "https://mock/model.fbx",
            "https://mock/signed-good-mesh",
        ]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/unit/test_cn_image_adapters.py::TestHunyuanMeshFbxSelfContainment -q
```

Expected: normal-mode rejection and fallthrough tests fail because `_build_candidate()` still accepts non-self-contained FBX.

- [ ] **Step 3: Implement `_build_candidate()` FBX branch**

Insert after OBJ handling:

```python
    if detected_fmt == "fbx" and not _is_self_contained_fbx(mesh_bytes):
        if geometry_only:
            missing_materials = True
        else:
            raise MeshWorkerUnsupportedResponse(
                f"tokenhub /3d returned a non-self-contained .fbx "
                f"for job {job_id} — FBX references external texture/media "
                f"files via FileName/RelativeFilename. Framework does not "
                f"download mesh sidecars. Use GLB, embed FBX media, or set "
                f"spec.texture=False AND spec.pbr=False for geometry-only output."
            )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/unit/test_cn_image_adapters.py::TestHunyuanMeshFbxSelfContainment -q
```

Expected: pass.

### Task 4: Documentation and backlog closeout

**Files:**
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`

- [ ] **Step 1: Update docs**

Mark TBD-004 closed with this scope: dependency-free FBX FileName/RelativeFilename sidecar detection, normal mode rejects, geometry-only mode accepts with `missing_materials=True`.

- [ ] **Step 2: Move LR-0129 from active to archived**

Remove the LR-0129 line from `docs/backlog/active.md` and add an archived tombstone for FOR-28 / LR-0129 with the test command evidence.

### Task 5: Verification

**Files:**
- Test: `tests/unit/test_cn_image_adapters.py`
- Test: relevant docs/backlog consistency checks if available

- [ ] **Step 1: Run targeted tests**

```bash
python -m pytest tests/unit/test_cn_image_adapters.py -q
```

Expected: all tests in that file pass.

- [ ] **Step 2: Run broader smoke for docs touched by requirements/backlog**

```bash
python -m pytest tests/unit/test_cn_image_adapters.py tests/unit/test_probe_framework.py -q
```

Expected: pass.

- [ ] **Step 3: Record evidence**

Use the passing command output and file links in the final response. Do not claim success without those evidence links.
