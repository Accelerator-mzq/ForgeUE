# probe-and-validation — repo-put-streaming-payload delta

> 本文件是 `probe-and-validation` capability 在 `repo-put-streaming-payload`
> (TBD-012)change 引入的行为增量:为 zero-copy / stream hashing / drift 校验路径
> 加可执行 fence 守门。每条 Requirement 首行标注 ADDED / MODIFIED。

## Source Documents

- `docs/testing/test_spec.md` —— 测试用例索引,本 change 加 fence 用例
- `docs/requirements/SRS.md` §3.6 / §4.2 NFR-PERF —— 大文件 RSS 边界
- 实现:`tests/unit/test_repo_put_streaming.py`(新增)/
  `tests/unit/test_artifact_repository.py`(扩)/
  `tests/unit/test_payload_backends.py`(扩)

## Requirement: stream / value 哈希等价 fence

**ADDED.** Pytest 套件 SHALL 包含一条单元用例,在多个 size grade
(1 byte / 64 KB / 1 MB / 50 MB)的本地临时文件上同时计算 `hash_path(p)` 与
`hash_payload(p.read_bytes())`,断言两者输出完全一致(同 hex 字符串)。

## Scenario: pytest 跑通

**Given** `tests/unit/test_artifact_repository.py::test_hash_path_equivalent_to_hash_payload`
**When** 执行 `python -m pytest tests/unit/test_artifact_repository.py
::test_hash_path_equivalent_to_hash_payload -v`
**Then** 退出码 == 0
**And** 至少覆盖 4 个 size grade(1 / 64K / 1M / 50M)

## Requirement: zero-copy RSS 增量 fence

**ADDED.** Pytest 套件 SHALL 包含一条单元用例,通过**后台采样线程**取
`psutil.Process().memory_info().rss` peak(R5-F2 D-PeakRSSSampling:50ms 间隔采样,
取调用期间 max RSS;**不**用 before/after 两点采样,会漏掉中间瞬时 200 MB buffer
后释放的假阳性场景):在一个 200 MB 临时文件上执行 `repo.put(source_path=p, ...)`
完整流程(含 hash 计算 + copyfile 落盘 + os.replace),进程 RSS **peak delta** SHALL
小于 32 MB。

该用例 SHALL 通过环境变量 `FORGEUE_RUN_HEAVY_FENCE=1` opt-in;**默认 skip**,以避免
CI / 日常 `pytest -q` 频繁创建 200 MB 临时文件影响速度。Skip 时显示 reason
`"FORGEUE_RUN_HEAVY_FENCE not set"`。

## Scenario: heavy fence opt-in 跑通

**Given** `tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb`
**When** 执行 `FORGEUE_RUN_HEAVY_FENCE=1 python -m pytest
tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb -v`
**Then** 退出码 == 0

## Scenario: 默认 skip

**Given** 环境变量未设 `FORGEUE_RUN_HEAVY_FENCE`
**When** 执行 `python -m pytest tests/unit/test_repo_put_streaming.py
::test_zero_copy_rss_bounded_200mb -v`
**Then** 该用例报告 SKIPPED,reason 包含 `"FORGEUE_RUN_HEAVY_FENCE"`

## Requirement: source_path 二选一与 payload_kind 拒签 fence

**ADDED.** Pytest 套件 SHALL 守门 5 类入参语义:
- 同时传 value 与 source_path → `pytest.raises(ValueError)`(R2-F3 D10 基于
  `_MISSING` identity 比较)
- 仅传 source_path 但 payload_kind != file → `pytest.raises(ValueError)`
- **两者都缺(省略 value 参数 + `source_path=None`)→ `pytest.raises(ValueError)`**;
  ⚠ 测试 SHALL NOT 传 `value=None` 触发该 case,因 `value=None` 是合法 inline JSON
  null payload(R2-F3 D10),正确测法是**完全省略 `value` 关键字参数**,留默认
  `_MISSING` sentinel
- **显式 `value=None` + `payload_kind=PayloadKind.inline` → 不 raise**(合法 inline
  null payload,Artifact.hash == hash_payload(None);回归既有 13 处 inline 调用契约)
- **显式 `value=None` + `source_path=<path>`** → `pytest.raises(ValueError)`(value
  is not _MISSING + source_path 非空触发互斥守门;value=None 仍算"已传 value")

## Scenario: pytest 跑通

**Given** `tests/unit/test_repo_put_streaming.py::test_value_source_path_mutually_exclusive`
**And** `tests/unit/test_repo_put_streaming.py::test_source_path_requires_file_kind`
**And** `tests/unit/test_repo_put_streaming.py::test_neither_value_nor_source_path`
**When** 执行 `python -m pytest tests/unit/test_repo_put_streaming.py -v`
**Then** 三条用例全部 PASSED

## Requirement: cap 拒签不全读 source 文件 fence

**ADDED.** Pytest 套件 SHALL 守门:当 `source_path` 指向一个 size 超过
`FILE_MAX_BYTES` 的文件时,`FileBackend.write` SHALL raise `PayloadTooLarge`,
且 SHALL NOT 调用 `Path.read_bytes()` / `shutil.copy2`(避免无意义 IO)。

实现策略:用 monkeypatch 把 `shutil.copy2` 替换成会 raise 的 spy,断言 spy 未被调用。
源文件用 sparse file(`f.seek(FILE_MAX_BYTES + 1); f.write(b"\x00")`)或
`os.posix_fallocate`(Windows 不支持,退回 sparse)以避免真分配 500 MB+ 磁盘空间。

## Scenario: pytest 跑通

**Given** `tests/unit/test_repo_put_streaming.py::test_cap_rejected_without_read`
**When** 执行 `python -m pytest tests/unit/test_repo_put_streaming.py
::test_cap_rejected_without_read -v`
**Then** 退出码 == 0
**And** spy_copy2.called == False

## Requirement: load_run_metadata stream drift fence

**ADDED.** Pytest 套件 SHALL 守门 `load_run_metadata` 在 file kind 大文件上走 stream
hash:用 `unittest.mock.patch.object` 把 **`framework.artifact_store.repository`
module 内绑定的 `hash_payload` 函数引用**替换成会 raise 的 spy(R3-F5 D-SpyTarget:
**不能** patch `framework.artifact_store.hashing.hash_payload` 源模块 —— `repository.py`
顶部 `from .hashing import hash_payload` 已经把函数绑定到 `repository_module.hash_payload`,
patch 源模块对已绑定引用无效)。断言 spy 未被调用(确认未走全读路径),hash drift 校验
仍正确通过 / 拒签。

**等价替代 fence**(更直接,与 patch 互补):spy
`framework.artifact_store.payload_backends.base.PayloadBackendRegistry.read`,
断言 file kind drift 路径下 spy 未被调用(stream 路径根本不读 payload bytes)。

## Scenario: stream drift 校验通过且不调 hash_payload

**Given** `tests/unit/test_artifact_repository.py::test_load_metadata_uses_stream_hash`
**When** 执行 `python -m pytest tests/unit/test_artifact_repository.py
::test_load_metadata_uses_stream_hash -v`
**Then** 退出码 == 0
**And** drift 通过的 entry 数 == 输入 _artifacts.json 中 file kind 条目数
**And** spy_hash_payload.called == False(file kind 路径未触发全读)

## Scenario: stream drift 拒签 corrupt 文件

**Given** 同上 fixture,但 file artifact 落盘后被 truncate 改 1 byte
**When** 执行 `load_run_metadata`
**Then** 该 entry SHALL skipped(不进 repo._artifacts)
**And** drift 通过的 entry 数 == 期望 - 1

## Non-Goals

- 不在本 change 跑端到端 P0-P4 integration test;只加单元 fence
- 不在本 change 加 ComfyUI live smoke fence —— Worker / Candidate / executor 路径不
  动(沿 proposal Out of Scope `worker-candidate-source-path-migration`)

## Validation

- 5 个新 / 扩单元用例位置(精确路径):
  - `tests/unit/test_artifact_repository.py::test_hash_path_equivalent_to_hash_payload`
  - `tests/unit/test_artifact_repository.py::test_load_metadata_uses_stream_hash`
  - `tests/unit/test_repo_put_streaming.py::test_zero_copy_rss_bounded_200mb`
    (opt-in)
  - `tests/unit/test_repo_put_streaming.py::test_value_source_path_mutually_exclusive`
  - `tests/unit/test_repo_put_streaming.py::test_source_path_requires_file_kind`
  - `tests/unit/test_repo_put_streaming.py::test_neither_value_nor_source_path`
  - `tests/unit/test_repo_put_streaming.py::test_cap_rejected_without_read`
- 集成 baseline:`python -m pytest -q` 跑全套,SHALL 不回退既有 1190+ 用例
