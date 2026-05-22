# FOR-14 Metadata Integrity Implementation Plan（实施计划）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `_artifacts.json` 增加伴生 checksum integrity 文件,让 resume 在 metadata 被改坏时 fail-fast。

**Architecture:** 把 `_artifacts.json` 视为 resume cache 的可信根,在 `ArtifactRepository` 内集中写入和校验 `_artifacts.integrity.json`。旧 run 无 integrity 文件时保持兼容;新 run 有 integrity 文件时先校验,再进入既有已存在 id / backend exists / file/blob hash drift 三道过滤。

**Tech Stack:** Python 3.12 stdlib(`json`, `Path`),现有 `hash_path`,Pydantic Artifact model,pytest,项目现有 docs/backlog 发布门。

---

## File Structure

- Modify: `src/framework/artifact_store/repository.py`
  - 增加 `_ARTIFACTS_FILENAME` / `_ARTIFACTS_INTEGRITY_FILENAME` / `_ARTIFACTS_INTEGRITY_SCHEMA_VERSION` / `_ARTIFACTS_INTEGRITY_ALGORITHM` 常量。
  - 增加 `ArtifactMetadataIntegrityError`。
  - 增加 `_write_metadata_integrity(...)` 和 `_verify_metadata_integrity(...)`。
  - `dump_run_metadata()` 写完 `_artifacts.json` 后写 integrity。
  - `load_run_metadata()` 在解析 Artifact 前校验 integrity。

- Modify: `tests/unit/test_artifact_repository.py`
  - 新增 FOR-14 回归测试,覆盖正常 dump/load、inline tamper、artifact_id tamper、坏 integrity JSON、legacy 无 integrity 兼容。

- Modify during document-release closeout:
  - `docs/contracts/artifact-contract/spec.md`
  - `docs/contracts/runtime-core/spec.md`
  - `docs/requirements/SRS.md`
  - `docs/testing/test_spec.md`
  - `docs/acceptance/acceptance_report.md`
  - `docs/backlog/active.md`
  - `docs/backlog/archived.md`
  - `CHANGELOG.md`

- Create verification evidence:
  - `demo_artifacts/2026-05-23/adhoc/for14_metadata_integrity/evidence.md`

---

### Task 1: 写 FOR-14 失败测试

**Files:**
- Modify: `tests/unit/test_artifact_repository.py`

- [ ] **Step 1: 增加测试 imports**

在文件顶部 import 区补 `json`,并从 repository 模块导入新异常。实现前这个 import 会失败,这是 red 阶段的预期。

```python
import json
```

```python
from framework.artifact_store.repository import ArtifactMetadataIntegrityError
```

- [ ] **Step 2: 添加测试 helper 和 dump integrity 测试**

在 `test_repo_put_blob_source_path_persists_payload` 后追加:

```python
def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_dump_run_metadata_writes_integrity_file(repo: ArtifactRepository, tmp_path: Path):
    """FOR-14:dump _artifacts.json 后必须写伴生 integrity 文件。"""
    repo.put(
        artifact_id="aid_integrity_1",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_integrity", step_id="s1"),
    )
    repo.put(
        artifact_id="aid_integrity_2",
        value={"x": 2},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_integrity", step_id="s2"),
    )

    run_dir = tmp_path / "run_dir_integrity"
    dumped = repo.dump_run_metadata(run_id="r_integrity", run_dir=run_dir)

    artifacts_path = run_dir / "_artifacts.json"
    integrity_path = run_dir / "_artifacts.integrity.json"
    integrity = _read_json(integrity_path)

    assert dumped == 2
    assert artifacts_path.is_file()
    assert integrity_path.is_file()
    assert integrity == {
        "schema_version": "1.0",
        "artifacts_file": "_artifacts.json",
        "algorithm": "sha256",
        "artifacts_sha256": hash_path(artifacts_path),
        "artifact_count": 2,
        "artifact_ids": ["aid_integrity_1", "aid_integrity_2"],
    }
```

- [ ] **Step 3: 添加 fail-fast 和 legacy 兼容测试**

继续追加:

```python
def test_load_run_metadata_fails_fast_when_inline_payload_metadata_changes(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:inline payload 属于 metadata 本身,被改后 resume 必须 fail-fast。"""
    repo.put(
        artifact_id="aid_inline_tamper",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_inline_tamper", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_inline_tamper"
    repo.dump_run_metadata(run_id="r_inline_tamper", run_dir=run_dir)

    artifacts_path = run_dir / "_artifacts.json"
    data = _read_json(artifacts_path)
    data[0]["payload_ref"]["inline_value"] = {"x": 2}
    data[0]["hash"] = hash_payload({"x": 2})
    _write_json(artifacts_path, data)

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    with pytest.raises(ArtifactMetadataIntegrityError, match="hash mismatch"):
        fresh.load_run_metadata(run_id="r_inline_tamper", run_dir=run_dir)
    assert not fresh.exists("aid_inline_tamper")


def test_load_run_metadata_fails_fast_when_artifact_id_changes(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:即使 integrity hash 被同步改写,artifact_id 摘要也要挡住改名。"""
    repo.put(
        artifact_id="aid_original",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_id_tamper", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_id_tamper"
    repo.dump_run_metadata(run_id="r_id_tamper", run_dir=run_dir)

    artifacts_path = run_dir / "_artifacts.json"
    integrity_path = run_dir / "_artifacts.integrity.json"
    data = _read_json(artifacts_path)
    data[0]["artifact_id"] = "aid_renamed"
    _write_json(artifacts_path, data)

    integrity = _read_json(integrity_path)
    integrity["artifacts_sha256"] = hash_path(artifacts_path)
    _write_json(integrity_path, integrity)

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    with pytest.raises(ArtifactMetadataIntegrityError, match="artifact id list mismatch"):
        fresh.load_run_metadata(run_id="r_id_tamper", run_dir=run_dir)
    assert not fresh.exists("aid_original")
    assert not fresh.exists("aid_renamed")


def test_load_run_metadata_fails_fast_when_integrity_json_is_invalid(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:integrity 文件坏掉时不得退回 legacy 路径。"""
    repo.put(
        artifact_id="aid_bad_integrity",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_bad_integrity", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_bad_integrity"
    repo.dump_run_metadata(run_id="r_bad_integrity", run_dir=run_dir)
    (run_dir / "_artifacts.integrity.json").write_text("{not json", encoding="utf-8")

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    with pytest.raises(ArtifactMetadataIntegrityError, match="invalid JSON"):
        fresh.load_run_metadata(run_id="r_bad_integrity", run_dir=run_dir)
    assert not fresh.exists("aid_bad_integrity")


def test_load_run_metadata_legacy_without_integrity_file_still_loads(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:旧 run 没有 integrity 文件时保持兼容,且 load 不 backfill。"""
    repo.put(
        artifact_id="aid_legacy",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_legacy", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_legacy"
    repo.dump_run_metadata(run_id="r_legacy", run_dir=run_dir)
    integrity_path = run_dir / "_artifacts.integrity.json"
    integrity_path.unlink()

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    loaded = fresh.load_run_metadata(run_id="r_legacy", run_dir=run_dir)

    assert loaded == 1
    assert fresh.exists("aid_legacy")
    assert not integrity_path.exists(), "resume load 不应为 legacy run 自动 backfill"
```

- [ ] **Step 4: 运行 red 测试**

Run:

```bash
python -m pytest tests/unit/test_artifact_repository.py::test_dump_run_metadata_writes_integrity_file -q
```

Expected: FAIL,collection 阶段或执行阶段提示 `ArtifactMetadataIntegrityError` 不存在 / integrity 文件不存在。

- [ ] **Step 5: 提交 red 测试**

```bash
git add tests/unit/test_artifact_repository.py
git commit -m "test: add FOR-14 metadata integrity fences"
```

---

### Task 2: 实现 ArtifactRepository integrity writer/verifier

**Files:**
- Modify: `src/framework/artifact_store/repository.py`
- Test: `tests/unit/test_artifact_repository.py`

- [ ] **Step 1: 增加常量和异常**

在 imports 后、`class ArtifactRepository` 前加入:

```python
_ARTIFACTS_FILENAME = "_artifacts.json"
_ARTIFACTS_INTEGRITY_FILENAME = "_artifacts.integrity.json"
_ARTIFACTS_INTEGRITY_SCHEMA_VERSION = "1.0"
_ARTIFACTS_INTEGRITY_ALGORITHM = "sha256"


class ArtifactMetadataIntegrityError(RuntimeError):
    """`_artifacts.json` integrity 校验失败。"""

    def __init__(self, run_dir: Path, reason: str) -> None:
        super().__init__(f"artifact metadata integrity failed for {run_dir}: {reason}")
        self.run_dir = run_dir
        self.reason = reason
```

- [ ] **Step 2: 修改 dump/load 入口**

把硬编码 target 改为常量,并在 dump 后写 integrity:

```python
target = run_dir / _ARTIFACTS_FILENAME
data = [a.model_dump(mode="json") for a in run_arts]
target.write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
)
self._write_metadata_integrity(run_dir=run_dir, artifacts=run_arts)
return len(run_arts)
```

在 `load_run_metadata` 的 target 存在检查后、`json.loads(...)` 前加入:

```python
self._verify_metadata_integrity(run_dir=run_dir)
raw = json.loads(target.read_text(encoding="utf-8"))
```

- [ ] **Step 3: 增加 `_write_metadata_integrity`**

在 `dump_run_metadata` 和 `load_run_metadata` 之间加入:

```python
def _write_metadata_integrity(
    self,
    *,
    run_dir: Path,
    artifacts: list[Artifact],
) -> None:
    artifacts_path = run_dir / _ARTIFACTS_FILENAME
    integrity_path = run_dir / _ARTIFACTS_INTEGRITY_FILENAME
    data = {
        "schema_version": _ARTIFACTS_INTEGRITY_SCHEMA_VERSION,
        "artifacts_file": _ARTIFACTS_FILENAME,
        "algorithm": _ARTIFACTS_INTEGRITY_ALGORITHM,
        "artifacts_sha256": hash_path(artifacts_path),
        "artifact_count": len(artifacts),
        "artifact_ids": [a.artifact_id for a in artifacts],
    }
    integrity_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 4: 增加 `_verify_metadata_integrity`**

继续加入:

```python
def _verify_metadata_integrity(self, *, run_dir: Path) -> None:
    integrity_path = run_dir / _ARTIFACTS_INTEGRITY_FILENAME
    if not integrity_path.is_file():
        return

    try:
        integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactMetadataIntegrityError(
            run_dir, f"integrity file invalid JSON: {exc}"
        ) from exc

    if not isinstance(integrity, dict):
        raise ArtifactMetadataIntegrityError(
            run_dir, "integrity file must be a JSON object"
        )
    if integrity.get("schema_version") != _ARTIFACTS_INTEGRITY_SCHEMA_VERSION:
        raise ArtifactMetadataIntegrityError(
            run_dir,
            f"unsupported integrity schema_version: {integrity.get('schema_version')!r}",
        )
    if integrity.get("artifacts_file") != _ARTIFACTS_FILENAME:
        raise ArtifactMetadataIntegrityError(
            run_dir,
            f"unexpected integrity artifacts_file: {integrity.get('artifacts_file')!r}",
        )
    if integrity.get("algorithm") != _ARTIFACTS_INTEGRITY_ALGORITHM:
        raise ArtifactMetadataIntegrityError(
            run_dir,
            f"unsupported integrity algorithm: {integrity.get('algorithm')!r}",
        )

    artifacts_path = run_dir / _ARTIFACTS_FILENAME
    expected_hash = integrity.get("artifacts_sha256")
    actual_hash = hash_path(artifacts_path)
    if expected_hash != actual_hash:
        raise ArtifactMetadataIntegrityError(
            run_dir,
            f"_artifacts.json hash mismatch: expected {expected_hash!r}, got {actual_hash!r}",
        )

    try:
        artifacts_raw = json.loads(artifacts_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactMetadataIntegrityError(
            run_dir, f"_artifacts.json invalid JSON: {exc}"
        ) from exc
    if not isinstance(artifacts_raw, list):
        raise ArtifactMetadataIntegrityError(
            run_dir, "_artifacts.json must be a JSON array"
        )

    actual_ids: list[str] = []
    for entry in artifacts_raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("artifact_id"), str):
            raise ArtifactMetadataIntegrityError(
                run_dir, "_artifacts.json contains entry without string artifact_id"
            )
        actual_ids.append(entry["artifact_id"])

    if integrity.get("artifact_count") != len(artifacts_raw):
        raise ArtifactMetadataIntegrityError(
            run_dir,
            f"artifact count mismatch: expected {integrity.get('artifact_count')!r}, got {len(artifacts_raw)!r}",
        )
    if integrity.get("artifact_ids") != actual_ids:
        raise ArtifactMetadataIntegrityError(
            run_dir,
            f"artifact id list mismatch: expected {integrity.get('artifact_ids')!r}, got {actual_ids!r}",
        )
```

- [ ] **Step 5: 运行 targeted green 测试**

Run:

```bash
python -m pytest tests/unit/test_artifact_repository.py::test_dump_run_metadata_writes_integrity_file tests/unit/test_artifact_repository.py::test_load_run_metadata_fails_fast_when_inline_payload_metadata_changes tests/unit/test_artifact_repository.py::test_load_run_metadata_fails_fast_when_artifact_id_changes tests/unit/test_artifact_repository.py::test_load_run_metadata_fails_fast_when_integrity_json_is_invalid tests/unit/test_artifact_repository.py::test_load_run_metadata_legacy_without_integrity_file_still_loads -q
```

Expected: PASS。

- [ ] **Step 6: 运行 ArtifactRepository 全文件**

Run:

```bash
python -m pytest tests/unit/test_artifact_repository.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交实现**

```bash
git add src/framework/artifact_store/repository.py tests/unit/test_artifact_repository.py
git commit -m "feat: add artifact metadata integrity file"
```

---

### Task 3: 跑关联回归并补 CLI/resume 风险检查

**Files:**
- No production changes expected.
- Test: `tests/unit/test_codex_audit_fixes.py`
- Test: `tests/unit/test_repo_put_streaming.py`

- [ ] **Step 1: 跑既有 resume / streaming 回归**

Run:

```bash
python -m pytest tests/unit/test_codex_audit_fixes.py tests/unit/test_repo_put_streaming.py -q
```

Expected: PASS。重点确认:

- `test_repository_metadata_dump_and_load_roundtrip`
- `test_resume_yields_cache_hits_after_reload`
- `test_load_run_metadata_skips_missing_payload`
- `test_load_run_metadata_skips_corrupted_payload`
- `test_null_inline_payload_survives_resume`

- [ ] **Step 2: 如有 legacy 测试受 integrity 影响,只修测试 fixture**

如果旧测试手工写 `_artifacts.json` 且没有 integrity 文件,应继续通过;不要强迫 fixture 新增 integrity。若测试失败,先确认是否因为实现误把无 integrity 文件当错误。

Expected fix pattern:

```python
# legacy run: intentionally no _artifacts.integrity.json
n = repo.load_run_metadata(run_id="r_legacy", run_dir=run_dir)
assert n == 1
```

- [ ] **Step 3: 提交测试兼容修正**

只有实际修改测试 fixture 时才执行:

```bash
git add tests/unit/test_codex_audit_fixes.py tests/unit/test_repo_put_streaming.py
git commit -m "test: preserve legacy artifact metadata resume fixtures"
```

若 Step 1 直接 PASS,不创建提交。

---

### Task 4: 文档同步和 backlog closeout

**Files:**
- Modify: `docs/contracts/artifact-contract/spec.md`
- Modify: `docs/contracts/runtime-core/spec.md`
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 更新 artifact contract**

在 `docs/contracts/artifact-contract/spec.md` 的 `Requirement: Cross-process artifact metadata persistence` 段落后加入:

```markdown
## Requirement: Artifact metadata integrity fails fast on resume

系统 SHALL 在每次新写 `{run_dir}/_artifacts.json` dump 后,同步写 `{run_dir}/_artifacts.integrity.json`。integrity 文件 SHALL 记录 `schema_version="1.0"`、`artifacts_file="_artifacts.json"`、`algorithm="sha256"`、`artifacts_sha256`、`artifact_count` 和有序 `artifact_ids`。

`ArtifactRepository.load_run_metadata` 发现 `_artifacts.integrity.json` 时,SHALL 在 Artifact registration 前校验 `_artifacts.json`。hash mismatch、unsupported schema version、unexpected target file、unsupported algorithm、artifact count mismatch、artifact id list mismatch 和 invalid integrity JSON 都 SHALL 抛 `ArtifactMetadataIntegrityError`。没有 `_artifacts.integrity.json` 的 legacy run 目录 SHALL 保持既有兼容 load path,并且 resume read SHALL NOT backfill integrity 文件。
```

- [ ] **Step 2: 更新 runtime-core contract**

在 `docs/contracts/runtime-core/spec.md` 的 `Requirement: Checkpoint persistence survives cross-process resume` 后加入:

```markdown
## Requirement: Resume fails fast when artifact metadata integrity fails

系统 SHALL 把 `_artifacts.json` 视为 resume cache 可信根。若 `_artifacts.integrity.json` 存在,`ArtifactRepository.load_run_metadata` SHALL 在 `CheckpointStore.find_hit` 能观察到任何 rehydrated Artifact 前完成校验。metadata integrity failure SHALL 抛 `ArtifactMetadataIntegrityError` 并停止 resume;它 SHALL NOT 退化为 cache miss 或静默 step re-execution。
```

- [ ] **Step 3: 更新 SRS FR-LC**

在 `docs/requirements/SRS.md` 的 FR-LC 表中 FR-LC-008 后加入:

```markdown
| FR-LC-009 | 新 run 应在 `{run_dir}/_artifacts.json` 旁写 `{run_dir}/_artifacts.integrity.json`;跨进程 `--resume` 时若 integrity 文件存在,必须先校验 `_artifacts.json` hash / artifact_count / artifact_ids,失败则抛 `ArtifactMetadataIntegrityError` fail-fast,不得静默重跑 |
```

- [ ] **Step 4: 更新 test_spec**

在 `docs/testing/test_spec.md` 的 artifact repository / audit fence 区域加入 FOR-14 fence 描述,并在变更记录表末尾加入:

```markdown
| v1.11 | 2026-05-23 | 加 Linear FOR-14 `metadata-corruption-detection`:ArtifactRepository 写 `_artifacts.integrity.json` 绑定 `_artifacts.json` sha256 / artifact_count / artifact_ids;resume 发现 integrity mismatch 时 `ArtifactMetadataIntegrityError` fail-fast,legacy 无 integrity 文件保持兼容。新增 fence 覆盖 `test_artifact_repository.py`;总数以本地 `python -m pytest -q` 实测为准。 |
```

- [ ] **Step 5: 更新 acceptance_report**

在 FR-LC 矩阵中 FR-LC-008 后加入:

```markdown
| FR-LC-009 `_artifacts.json` integrity fail-fast | test_artifact_repository(FOR-14 metadata integrity fences) | ✅ |
```

在 §8 变更记录末尾加入:

```markdown
| v1.14 | 2026-05-23 | Linear FOR-14 `metadata-corruption-detection`:新增 `_artifacts.integrity.json` 伴生 checksum 文件;resume 校验 `_artifacts.json` hash / artifact_count / artifact_ids,metadata 损坏时 fail-fast。对应 fence 见 `docs/testing/test_spec.md` v1.11;总数以本地 `python -m pytest -q` 实测为准。 | ForgeUE Team |
```

- [ ] **Step 6: 更新 backlog**

从 `docs/backlog/active.md` 的 Out of Scope 移除 `2026-05-21-repo-put-streaming-payload::metadata-corruption-detection`,并在 `docs/backlog/archived.md` 增加:

```markdown
## 2026-05-23 FOR-14 completion

### `2026-05-21-repo-put-streaming-payload::metadata-corruption-detection`

- **new_status**: completed
- **reason**: `ArtifactRepository.dump_run_metadata` 现在为 `_artifacts.json` 写伴生 `_artifacts.integrity.json`;`load_run_metadata` 在发现 integrity 文件时先校验 metadata hash / artifact_count / artifact_ids,损坏时抛 `ArtifactMetadataIntegrityError` fail-fast。legacy 无 integrity 文件 run 仍兼容加载。
- **evidence**: `src/framework/artifact_store/repository.py`,
  `tests/unit/test_artifact_repository.py`,
  `docs/superpowers/specs/2026-05-23-for-14-metadata-integrity-design.md`,
  `docs/superpowers/plans/2026-05-23-for-14-metadata-integrity.md`,
  `demo_artifacts/2026-05-23/adhoc/for14_metadata_integrity/evidence.md`。
- **archived_by**: FOR-14 metadata-corruption-detection 2026-05-23
```

- [ ] **Step 7: 更新 CHANGELOG**

在 `[Unreleased]` / `Changed` 下加入:

```markdown
- **FOR-14 metadata corruption detection**:`ArtifactRepository.dump_run_metadata`
  现在在 `_artifacts.json` 旁写 `_artifacts.integrity.json`,记录 sha256 /
  artifact_count / artifact_ids;`load_run_metadata` 发现 integrity 文件时先校验,
  mismatch 抛 `ArtifactMetadataIntegrityError` fail-fast。legacy 无 integrity 文件
  run 保持兼容。同步 retired active backlog `metadata-corruption-detection`。
```

- [ ] **Step 8: 跑文档 grep**

Run:

```bash
rg -n "metadata-corruption-detection|FR-LC-009|_artifacts\\.integrity\\.json|ArtifactMetadataIntegrityError" docs CHANGELOG.md src tests
```

Expected: 命中实现、测试、contracts、SRS、test_spec、acceptance_report、CHANGELOG、backlog archived;`docs/backlog/active.md` 不再含 active FOR-14 条目。

- [ ] **Step 9: 提交文档同步**

```bash
git add docs/contracts/artifact-contract/spec.md docs/contracts/runtime-core/spec.md docs/requirements/SRS.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/backlog/active.md docs/backlog/archived.md CHANGELOG.md
git commit -m "docs: sync FOR-14 metadata integrity release notes"
```

---

### Task 5: 最终验证和证据文件

**Files:**
- Create: `demo_artifacts/2026-05-23/adhoc/for14_metadata_integrity/evidence.md`

- [ ] **Step 1: 跑 focused verification**

Run:

```bash
python -m pytest tests/unit/test_artifact_repository.py -q
python -m pytest tests/unit/test_codex_audit_fixes.py tests/unit/test_repo_put_streaming.py -q
```

Expected: 两条命令均 PASS。

- [ ] **Step 2: 跑全量测试**

Run:

```bash
python -m pytest -q
```

Expected: PASS。若出现无关 pre-existing failure,记录完整命令、失败测试名和判断依据,不要声称全量通过。

- [ ] **Step 3: 写证据文件**

Create `demo_artifacts/2026-05-23/adhoc/for14_metadata_integrity/evidence.md` with the exact command outcomes from Step 1 and Step 2:

```markdown
# FOR-14 metadata integrity evidence

Date: 2026-05-23

## Scope

- Linear: FOR-14 `metadata-corruption-detection`
- Design: `docs/superpowers/specs/2026-05-23-for-14-metadata-integrity-design.md`
- Plan: `docs/superpowers/plans/2026-05-23-for-14-metadata-integrity.md`

## Files

- `src/framework/artifact_store/repository.py`
- `tests/unit/test_artifact_repository.py`
- `docs/contracts/artifact-contract/spec.md`
- `docs/contracts/runtime-core/spec.md`
- `docs/requirements/SRS.md`
- `docs/testing/test_spec.md`
- `docs/acceptance/acceptance_report.md`
- `docs/backlog/active.md`
- `docs/backlog/archived.md`
- `CHANGELOG.md`

## Verification

- `python -m pytest tests/unit/test_artifact_repository.py -q` -> write the real PASS line from Step 1
- `python -m pytest tests/unit/test_codex_audit_fixes.py tests/unit/test_repo_put_streaming.py -q` -> write the real PASS line from Step 1
- `python -m pytest -q` -> write the real PASS line from Step 2, or the exact failure summary if a pre-existing unrelated failure remains

## Notes

- New run directories write `_artifacts.integrity.json`.
- Legacy run directories without `_artifacts.integrity.json` remain loadable.
- Integrity mismatch raises `ArtifactMetadataIntegrityError` before Artifact registration.
```

Save the evidence file only after each verification bullet contains the real observed result.

- [ ] **Step 4: 最终 git 状态检查**

Run:

```bash
git status --short
git log -5 --oneline
```

Expected: only intended tracked changes remain, plus ignored `demo_artifacts/` evidence if not tracked by git。

Do not stage `demo_artifacts/`.

---

## Self-Review

- Spec coverage:方案 2 checksum integrity 文件、fail-fast、legacy 兼容、无 backfill、file/blob drift 保持不变,分别由 Task 1-4 覆盖。
- Placeholder scan:计划内没有未填内容;证据文件步骤要求写入真实命令输出后再保存。
- Type consistency:`ArtifactMetadataIntegrityError`、`_artifacts.integrity.json`、`hash_path`、`ArtifactRepository.dump_run_metadata`、`ArtifactRepository.load_run_metadata` 与当前代码命名一致。
- Scope check:本计划只改 ArtifactRepository metadata integrity、相关测试和发布文档;不引入 HMAC/key management、不改 PayloadRef schema、不改 file/blob payload drift 行为。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-23-for-14-metadata-integrity.md`. Two execution options:

1. **Inline Execution（推荐）** - 使用 `superpowers:executing-plans` 在当前会话按任务执行,每个任务后做 checkpoint。
2. **Subagent-Driven** - 使用 `superpowers:subagent-driven-development` 分派 worker 执行任务并逐段 review。

本项目当前 ADR-014 已 retire ForgeUE-level parallel/worktree 强制层,FOR-14 写入面集中在同一小模块和文档,我推荐 Inline Execution。
