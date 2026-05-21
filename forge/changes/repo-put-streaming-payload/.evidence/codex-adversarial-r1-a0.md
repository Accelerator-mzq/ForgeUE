## Summary

结论是 `needs-attention`。四件套里最危险的问题不是 stream hash 本身，而是 `repo.put(source_path=...)` 的元数据哈希不是对最终落盘文件取样，且 Phase 1 明确不触达当前 video / mesh / audio / image 真实落盘路径，导致核心目标很容易“看起来完成、实际未生效”。

## Findings

### [BLOCKER] `Artifact.hash` 可能记录的是 source 文件而不是实际 artifact 文件

**Location**: [design.md:296](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:296), [design.md:301](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:301), [design.md:387](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:387)  
**Confidence**: 0.9

**Body**:  
设计先用 `src.stat().st_size` 生成 `PayloadRef.size_bytes`，再 `shutil.copy2(src, abs_path)`，但 `repo.put` 随后对 `source_path` 做 `hash_path(source_path)`。这没有保证 `source_path` 在 stat、copy、hash 三个阶段之间不变。一旦源文件被外部进程继续写入、替换、截断，或者 caller 误复用临时路径，落盘 artifact bytes、`PayloadRef.size_bytes`、`Artifact.hash` 三者可能不一致。影响是 resume drift 会把刚写入的 artifact 判为 corrupt 并跳过，或者更糟，metadata hash 对不上实际存储内容。

**Recommendation**:  
把 hash 计算改为对最终落盘路径取样：`ref = backend.write(...)` 后通过 `backend.absolute_path(ref)` 计算 `hash_path(dest)`，并让 `size_bytes` 也来自最终文件 stat。若要保留 source hash，必须显式定义 source ownership / immutability contract，并加并发变更回归测试；更简单可靠的是只信任 repository 自己写出的目标文件。

---

### [MAJOR] Phase 1 不会改善当前真实大文件 candidate 落盘内存

**Location**: [proposal.md:10](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:10), [design.md:131](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:131), [design.md:132](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:132), [tasks.md:1041](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1041)  
**Confidence**: 0.95

**Body**:  
proposal 把问题定义为 video / mesh / audio / image candidate 落盘时的全量内存驻留，但 design 明确 Phase 1 “只把接口能力建好”，executor 仍走 `repo.put(value=cand.data)`；tasks 还要求确认 mp4 路径“不触发 stream 路径”。这意味着本 change ship 后，最初列出的高价值场景仍然全量 bytes 驻留，只新增了一个目前生产路径不用的 API。

**Recommendation**:  
二选一：要么把 change 目标降级为“为后续迁移铺接口”，并把性能收益从 DoD 中移除；要么至少迁移一个最高风险路径，例如 video executor + `VideoCandidate.source_path`，让本 change 对真实 user-visible 大文件路径产生可验证收益。

---

### [MAJOR] `file/blob` drift 设计把 blob 当 file path 处理

**Location**: [proposal.md:43](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:43), [artifact-contract.md:142](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:142), [artifact-contract.md:143](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:143), [tasks.md:27](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:27)  
**Confidence**: 0.85

**Body**:  
proposal/spec 要求 `load_run_metadata` 对 `file` / `blob` 都改成 `hash_path(...)`，但 `blob` payload 的契约不是 `file_path`，而 tasks 又说 `BlobBackend.absolute_path` 抛 `NotImplementedError`。如果历史 `_artifacts.json` 或未来 stub 之外的 blob ref 进入 resume，这条设计会把 blob 走到本地路径 hash，最小结果是跳过，最坏是 load metadata 异常路径漂移。

**Recommendation**:  
把 drift 分支拆开：`file` 用 `hash_path(backend.absolute_path(ref))`；`blob` 在本 change 明确保持旧行为或显式 out-of-scope，不要写进 stream drift contract。对应 spec / tasks 也要同步删除 `file/blob` 合并表述。

---

### [MAJOR] 性能 DoD 在四件套之间互相矛盾且默认不执行

**Location**: [proposal.md:55](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:55), [probe-and-validation.md:32](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:32), [probe-and-validation.md:34](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:34), [probe-and-validation.md:36](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:36)  
**Confidence**: 0.9

**Body**:  
proposal 的成功标准是 200 MB 文件 RSS 增量 `< 10 MB`，spec 改成 `< 32 MB`，并且 heavy fence 默认 skip。对于一个以降低大文件 RSS 为核心卖点的 change，这会让默认 `pytest -q` 通过但没有证明核心性能目标；同时不同文档可以各自声称达标，验收口径不一致。

**Recommendation**:  
统一阈值，并把性能证据变成 archive 前必须产出的 evidence 文件，而不是默认跳过的可选测试。若 CI 成本太高，可以保留 opt-in，但 tasks 必须要求实施者附上一次本地 heavy fence 输出路径和机器环境说明。

---

## Verdict

`needs-attention`

当前设计不能直接 ship。至少需要修正 hash 对最终 artifact 取样、明确 blob drift 边界，并重新定义 Phase 1 的真实交付目标，否则这个 change 很可能只交付一个未被生产路径使用的 API。
