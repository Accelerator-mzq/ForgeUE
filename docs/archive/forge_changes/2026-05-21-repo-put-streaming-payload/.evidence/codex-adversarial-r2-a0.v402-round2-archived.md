## Summary

这 4 件套还不能 ship。最主要风险不是实现细节，而是契约层互相打架：`artifact-contract` 仍要求 `hash_path(source_path)` / `size_bytes=source_stat`，但 proposal/design/tasks 已改成以最终落盘 `dest` 为准；这会直接影响并发修改 source 时的 artifact 完整性判断。

## Findings

### [BLOCKER] source_path 分支的 hash/size 真源在 spec 与 design/tasks 中矛盾

**Location**: [specs/artifact-contract.md:30](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:30), [specs/artifact-contract.md:120](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:120), [design.md:235](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:235), [tasks.md:612](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:612)  
**Confidence**: 0.95

**Body**:  
`artifact-contract` 要求 `repo.put(source_path=...)` 的内容哈希走 `hash_path(source_path)`，并要求 `PayloadRef.size_bytes=<source_stat.st_size>`。但 design 的 D9 明确拍板 hash 与 size 都必须来自最终落盘 dest，tasks 也按 `hash_path(dest_abs)` 写测试。  
这不是文字小偏差。若 source 在 stat/copy/hash 三阶段间被并发修改，按 spec 实现会产生 “dest bytes / Artifact.hash / PayloadRef.size_bytes” 不一致，resume drift 校验和 checkpoint hit 都可能基于错误 hash 接受或拒绝 artifact。

**Recommendation**:  
把 `artifact-contract` 改成唯一契约：`FileBackend.write` copy 完后返回 `dest.stat().st_size`，`ArtifactRepository.put` 用 `hash_path(dest_abs)`，并删除 `hash_path(source_path)` / `source_stat.st_size` 表述；对应 Scenario 也要覆盖 source 在 copy 前后变化时 hash/size 仍与 dest 一致。

---

### [MAJOR] “Phase 1 不提供用户可见收益” 与 design/tasks 的成功目标互相冲突

**Location**: [proposal.md:25](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:25), [design.md:66](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:66), [tasks.md:5](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:5), [tasks.md:1109](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1109)  
**Confidence**: 0.9

**Body**:  
proposal 明确说 Phase 1 不迁移 video/mesh/audio/image executor，生产路径仍 `value=cand.data`，所以 user-visible 内存收益留到 Phase 2。但 design 的调用点表把 5 处 file generator 标成“本 change 受益”，tasks 的 Goal 也写“把 video / mesh / audio / image 大文件 candidate 落盘时的全量内存驻留与全量 hash 收敛到 chunk 级 RSS 增量”。同一 change 同时声称“不触达生产路径”和“生产大文件收益已达成”。  
这会让验收标准失真：默认 pytest 和 mock smoke 都可能全绿，但真实 generator 仍全读 candidate bytes，审阅者会误以为 TBD-012 已解决大文件内存问题。

**Recommendation**:  
统一 Phase 1 DoD：只声明 `repo.put(source_path=...)` opt-in 能力和 `load_run_metadata` file drift stream 化；把 5 个 generator 的“受益”改成“Phase 2 受益目标”，并把 tasks Goal 改为“不改变现有 executor 内存行为”。

---

### [MAJOR] 用 `None` 作为“未传 value”的 sentinel 会破坏 `value=None` 这个合法 Any payload

**Location**: [design.md:301](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:301), [design.md:414](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:414), [tasks.md:770](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:770), [specs/artifact-contract.md:21](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:21)  
**Confidence**: 0.85

**Body**:  
现有 `repo.put` 的 `value: Any` 是必填参数，`hash_payload(None)` 和 `InlineBackend.write(None)` 都能表达 JSON `null` 类 payload。新设计把 `value` 默认设为 `None`，再用 `if value is None and source_path is None` 判断“缺参”，这会把显式 `value=None` 误判为没传 payload。  
这违反 proposal/spec 里的“既有调用站点行为完全一致”承诺，也给后续 inline metadata / structured extraction 的 null payload 留下兼容坑。

**Recommendation**:  
引入私有 sentinel，例如 `_MISSING = object()`；签名用 `value: Any = _MISSING`，二选一判断基于 identity，而不是 `None`。同时补一个 `repo.put(value=None, payload_kind=inline)` 的回归测试，明确是否保留该行为。

---

### [MINOR] heavy fence evidence 要求包含 RSS delta，但测试计划不会在 pass 时输出 delta

**Location**: [tasks.md:1029](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1029), [tasks.md:1032](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1032), [tasks.md:1150](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1150), [tasks.md:1181](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1181)  
**Confidence**: 0.75

**Body**:  
archive 前 evidence 要求日志末尾包含 `PASSED` 行和 RSS delta `< 32 MB` 报告；但给出的测试代码只在 assert failure message 里包含 `rss_delta_mb`，pass 时没有 `print` / logging。即使用 `pytest -v -s | tee`，成功日志也不会包含实际 delta。  
这会让验收证据无法证明核心性能 fence 的数值，只能证明测试名 passed。

**Recommendation**:  
在 heavy fence 测试 pass 路径显式 `print(f"RSS delta: {rss_delta_mb:.1f} MB")`，或把 delta 写入 dedicated evidence helper；tasks 的 evidence 断言应与实际输出一致。

## Verdict

`needs-attention`

当前四件套存在契约级矛盾，会把实现者导向不同的 hash/size 语义；先统一 source/dest 真源、Phase 1 DoD 和 `None` sentinel 后再进入 apply。
