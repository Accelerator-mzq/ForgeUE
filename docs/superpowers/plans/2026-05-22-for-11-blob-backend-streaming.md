# FOR-11 Blob Backend Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a minimal BlobBackend that can stream existing files into object storage through an injected client without adding heavyweight runtime dependencies.

**Architecture:** Keep `PayloadRef` unchanged and make `BlobBackend` depend on a tiny local client protocol. The default client is an in-memory object store for deterministic MVP behavior; production S3 / MinIO / Azure adapters can later satisfy the same protocol without changing `ArtifactRepository.put`.

**Tech Stack:** Python 3.12 stdlib, Pydantic models already in `framework.core.artifact`, existing SHA-256 helpers, pytest.

---

### Task 1: BlobBackend Client Contract And Write Path

**Files:**
- Modify: `src/framework/artifact_store/payload_backends/blob_backend.py`
- Test: `tests/unit/test_payload_backends.py`

- [ ] **Step 1: Write failing tests for value and source_path writes**

Add tests that instantiate `BlobBackend(bucket="bucket", client=InMemoryBlobClient())`, write bytes through `value`, write bytes through `source_path`, and assert:
- `PayloadRef.kind == PayloadKind.blob`
- `blob_key == "bucket/<run_id>/<artifact_id><suffix>"`
- `size_bytes` equals stored byte length
- returned `content_hash` equals `hash_payload(bytes)` or `hash_path(source_path)`
- `read()` returns the stored bytes
- `exists()` returns `True`

- [ ] **Step 2: Run red tests**

Run: `python -m pytest tests/unit/test_payload_backends.py::test_blob_backend_write_bytes_roundtrip tests/unit/test_payload_backends.py::test_blob_backend_write_source_path_streams_file -q`

Expected: fail because `BlobBackend.__init__` does not accept `bucket` / `client`, and `write()` still raises `NotImplementedError`.

- [ ] **Step 3: Implement minimal client protocol**

In `blob_backend.py`, add:

```python
@dataclass
class BlobObject:
    data: bytes
    metadata: dict[str, str]


class BlobClient(Protocol):
    def upload_bytes(self, key: str, data: bytes, *, metadata: dict[str, str]) -> None: ...
    def upload_path(self, key: str, source_path: str | os.PathLike, *, metadata: dict[str, str]) -> None: ...
    def read_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class InMemoryBlobClient:
    def __init__(self) -> None:
        self._objects: dict[str, BlobObject] = {}
```

Implement methods with simple dict storage. `upload_path` reads in chunks into a `bytearray` for the MVP fake client; the production-facing no-new-dependency promise is that `BlobBackend` calls `upload_path` when `source_path` is provided, so a real adapter can multipart upload without framework changes.

- [ ] **Step 4: Implement BlobBackend.write/read/exists**

Make `BlobBackend.__init__(bucket: str = "forgeue-artifacts", client: BlobClient | None = None)`. Write to key `f"{bucket}/{run_id}/{artifact_id}{suffix}"`. Use `hash_payload(value)` for value writes and `hash_path(source_path)` for source_path writes. Return `WriteResult(PayloadRef(kind=PayloadKind.blob, blob_key=key, size_bytes=size), content_hash=content_hash)`.

- [ ] **Step 5: Run green tests**

Run the same two targeted tests. Expected: pass.

### Task 2: BlobBackend Guards And Repository Integration

**Files:**
- Modify: `src/framework/artifact_store/payload_backends/blob_backend.py`
- Modify: `tests/unit/test_payload_backends.py`
- Modify: `tests/unit/test_artifact_repository.py`

- [ ] **Step 1: Write failing guard tests**

Cover `value` and `source_path` mutual exclusion, missing payload rejection, missing source file propagation, and directory source rejection. Keep messages parallel to `FileBackend` where practical.

- [ ] **Step 2: Run red tests**

Run: `python -m pytest tests/unit/test_payload_backends.py -q`

Expected: new guard tests fail until BlobBackend has the same basic input contract as FileBackend.

- [ ] **Step 3: Add guard logic**

In `BlobBackend.write`, reject both-present and both-missing inputs, reject non-regular `source_path` with `ValueError("source_path must be a regular file")`, and let `Path.stat()` raise `FileNotFoundError` for absent files.

- [ ] **Step 4: Update repository resume blob test**

Replace the old stub-preservation test with a real blob resume test: write a blob artifact, dump `_artifacts.json`, load into a fresh repo with the same registry, and assert the artifact is registered when bytes match.

- [ ] **Step 5: Run integration unit subset**

Run: `python -m pytest tests/unit/test_payload_backends.py tests/unit/test_artifact_repository.py -q`

Expected: pass.

### Task 3: Blob Drift Detection

**Files:**
- Modify: `src/framework/artifact_store/repository.py`
- Modify: `tests/unit/test_artifact_repository.py`

- [ ] **Step 1: Write failing drift test**

Use `InMemoryBlobClient` to write a blob artifact, dump metadata, overwrite the stored object under the same key, then load metadata into a fresh repo. Assert `load_run_metadata()` returns `0` and the artifact id is not registered.

- [ ] **Step 2: Run red test**

Run: `python -m pytest tests/unit/test_artifact_repository.py::test_load_metadata_rejects_corrupted_blob_payload -q`

Expected: fail if blob drift still assumes the old stub behavior or does not compare stored bytes.

- [ ] **Step 3: Keep repository logic simple**

Use the existing blob branch in `load_run_metadata`: `current = self._registry.read(art.payload_ref)` then `hash_payload(current) != art.hash` skips the entry. Only remove obsolete comments that say BlobBackend is still a stub.

- [ ] **Step 4: Run artifact repository tests**

Run: `python -m pytest tests/unit/test_artifact_repository.py -q`

Expected: pass.

### Task 4: Documentation And Backlog Sync

**Files:**
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`
- Modify: `docs/contracts/artifact-contract.md`
- Modify: `docs/contracts/artifact-contract/spec.md`
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/design/LLD.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update docs to state BlobBackend MVP is implemented**

Move the FOR-11 backlog item from active to archived with evidence references. Replace "stub / reserved" wording with "MVP in-memory client + injectable object-store client protocol" where the docs describe current behavior.

- [ ] **Step 2: Run focused tests and docs grep**

Run:

```powershell
python -m pytest tests/unit/test_payload_backends.py tests/unit/test_artifact_repository.py tests/unit/test_repo_put_streaming.py -q
rg -n "BlobBackend.*stub|blob.*stub|blob-backend-streaming-implementation|NotImplementedError.*BlobBackend" docs src tests README.md CHANGELOG.md
```

Expected: tests pass; grep only returns archived historical references or intentionally updated tombstones.

### Task 5: Final Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused verification**

Run: `python -m pytest tests/unit/test_payload_backends.py tests/unit/test_artifact_repository.py tests/unit/test_repo_put_streaming.py -q`

Expected: pass.

- [ ] **Step 2: Run full test suite if focused tests pass**

Run: `python -m pytest -q`

Expected: pass, or report any pre-existing unrelated failures with exact evidence.

- [ ] **Step 3: Capture evidence**

Create `demo_artifacts/2026-05-22/adhoc/for11_blob_backend/evidence.md` with exact commands, outcomes, and relevant file links.

## Self-Review

- Spec coverage: FOR-11 write/read/exists/source_path/resume drift/docs/backlog all map to Tasks 1-5.
- Placeholder scan: no TBD/TODO placeholders remain in the plan body.
- Type consistency: `PayloadRef.blob_key`, `WriteResult.content_hash`, `PayloadBackend.write(... source_path=...)`, and `PayloadKind.blob` match current code.
