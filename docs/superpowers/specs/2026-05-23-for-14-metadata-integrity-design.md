# FOR-14 Metadata Integrity 设计

日期:2026-05-23

Issue:Linear FOR-14 `metadata-corruption-detection`

状态:用户已确认设计方向,等待书面 spec 复审

## 问题

`_artifacts.json` 是 resume cache 的 Artifact 元数据可信根。ForgeUE 现有
`load_run_metadata` 已经能保护 file/blob payload bytes:先检查 backend 是否存在,
再检查当前 payload hash 是否等于 metadata 记录的 hash。但这不保护
`_artifacts.json` 文件本身。

当前缺口:

- Inline payload 直接存在 `_artifacts.json` 内。若有人同时改 inline value 和
  对应 hash,单文件内部仍可能看起来自洽。
- `artifact_id` / `hash` / `payload_ref` / lineage / tags / schema 字段都可能在
  resume 前被手工改动。
- 一个 schema 合法但语义被改过的 `_artifacts.json` 可能导致错误 cache hit,
  或掩盖 cache hit 消失的真实原因。

因此 FOR-14 把 `_artifacts.json` 完整性视为独立可信边界,与 file/blob payload
漂移校验分开处理。

## 决策

采用伴生 checksum 文件方案。

`ArtifactRepository.dump_run_metadata()` 写完 `{run_dir}/_artifacts.json` 后,
同步写 `{run_dir}/_artifacts.integrity.json`。resume 时,
`ArtifactRepository.load_run_metadata()` 只要发现 integrity 文件存在,就先校验
integrity,再解析 Artifact records。

integrity 不匹配时抛出专用异常 `ArtifactMetadataIntegrityError`,fail-fast。
它不静默跳过条目,也不自动退化成重新执行 step。

历史 run 目录如果只有 `_artifacts.json`、没有 integrity 文件,仍按 legacy 路径加载。
resume 读路径不得自动补写或修改历史 metadata。

## 文件格式

`_artifacts.integrity.json` 是一个小 JSON object:

```json
{
  "schema_version": "1.0",
  "artifacts_file": "_artifacts.json",
  "algorithm": "sha256",
  "artifacts_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "artifact_count": 3,
  "artifact_ids": ["a1", "a2", "a3"]
}
```

字段规则:

- `schema_version` 必须等于 `"1.0"`。
- `artifacts_file` 必须等于 `"_artifacts.json"`。
- `algorithm` 必须等于 `"sha256"`。
- `artifacts_sha256` 使用现有 bounded-RSS `hash_path` helper,对最终
  `_artifacts.json` 文件 bytes 计算。
- `artifact_count` 等于 dump 出来的 artifact 数量。
- `artifact_ids` 保留 `_artifacts.json` 中 artifact 的顺序。

这个方案绑定最终文件 bytes,不再设计每条 Artifact 的额外 canonical hash。这样更简单,
也能抓住任何手工编辑,包括空白、字段、顺序、条目和 inline payload 变化。

## 运行流程

Dump flow:

1. `dump_run_metadata(run_id, run_dir)` 通过 `find_by_producer(run_id=run_id)`
   收集当前 run 的 artifacts。
2. 按现有格式写 `_artifacts.json`。
3. 用 `hash_path` 计算写盘后的 `_artifacts.json` hash。
4. 写 `_artifacts.integrity.json`。

Load flow:

1. `_artifacts.json` 不存在时,和现状一致返回 `0`。
2. `_artifacts.integrity.json` 不存在时,走 legacy load path。
3. `_artifacts.integrity.json` 存在时,先校验 integrity。
4. 校验失败时抛 `ArtifactMetadataIntegrityError`。
5. 校验通过后,继续沿用现有三道过滤:已存在 id skip / backend `exists()` skip /
   file/blob payload hash drift skip。

`framework.run --resume` 不捕获这个新异常。CLI 应该明确失败,让操作者看到 resume
metadata 已损坏,而不是得到误导性的 cache miss。

## 范围

本次范围:

- 在 `src/framework/artifact_store/repository.py` 增加 integrity writer / verifier。
- 增加 `ArtifactMetadataIntegrityError`。
- 保持无 integrity 文件的历史 run 兼容。
- 保持现有 file/blob payload drift 校验不变。
- 增加正常 load、inline metadata tamper、`artifact_id` tamper、坏 integrity JSON、
  legacy compatibility 等回归测试。
- 实现阶段同步 artifact/runtime contracts、SRS、testing spec、acceptance report、
  CHANGELOG 和 backlog closeout。

本次不做:

- HMAC signature、hash chain、key management 或防恶意伪造。
- 自动修复损坏 metadata。
- 在 resume 读路径 backfill integrity 文件。
- 修改 `PayloadRef` schema。
- 修改 file/blob payload drift 行为。

## 错误处理

`ArtifactMetadataIntegrityError` 应包含 run directory 和简短原因,例如:

- integrity 文件不是合法 JSON
- integrity schema version 不支持
- integrity 指向的 target 文件异常
- algorithm 不是 sha256
- `_artifacts.json` hash mismatch
- artifact count mismatch
- artifact id list mismatch

这些都属于 fail-fast resume errors,因为 metadata 可信根已经不可靠。

## 测试

主要测试放在现有 ArtifactRepository 覆盖附近:

- `test_dump_run_metadata_writes_integrity_file`
- `test_load_run_metadata_verifies_integrity_before_registering`
- `test_load_run_metadata_fails_fast_when_inline_payload_metadata_changes`
- `test_load_run_metadata_fails_fast_when_artifact_id_changes`
- `test_load_run_metadata_fails_fast_when_integrity_json_is_invalid`
- `test_load_run_metadata_legacy_without_integrity_file_still_loads`

实现阶段回归命令:

```bash
python -m pytest tests/unit/test_artifact_repository.py -q
python -m pytest tests/unit/test_codex_audit_fixes.py tests/unit/test_repo_put_streaming.py -q
```

若 CLI resume 行为除异常透传外还有变更,再补最小相关 CLI 或 integration smoke。

## 验收

完成标准:

- 新 run 在 `_artifacts.json` 旁写出 `_artifacts.integrity.json`。
- 未修改 metadata 的 run 仍可 resume,并可产生 cache hit。
- 手工编辑 `_artifacts.json` 后,resume 在 Artifact registration 前失败。
- 没有 integrity 文件的旧 run 目录仍兼容。
- 现有 file/blob payload drift tests 继续通过。
- 文档和 backlog closeout 附具体证据文件链接。
