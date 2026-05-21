## Summary

整体结论：`repo-put-streaming-payload-propose` 现在不应进入实现。最大问题是 Phase 1 的目标、验收口径和实际收益路径不一致：设计承认 worker/executor 仍然全量读 bytes，但 proposal 又把 video/mesh/audio/image candidate 落盘内存优化作为成功目标。

## Findings

### [MAJOR] Phase 1 不会解决 change 宣称的主要大文件内存问题

**Location**: [proposal.md:46](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:46), [proposal.md:54](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:54), [design.md:120](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:120), [design.md:131](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:131)  
**Confidence**: 0.92

**Body**:  
proposal 的 Why 把 video/mesh/audio/image candidate 落盘全量内存驻留列为核心问题，并把 `repo.put(source_path=...)` 的 200 MB RSS 增量作为成功标准。但 design 同时明确当前 `AudioCandidate / ImageCandidate / MeshCandidate / VideoCandidate` 全部是 `data: bytes`，ComfyUI 路径已经 `Path.read_bytes()`，source path 在 worker 层丢失；Phase 1 又明确“不迁移 worker / executor”。这意味着真实受影响的 5 个 generator 在本 change 后仍然继续持有完整 bytes，核心内存问题不会消失，只是新增了一个暂时未接入主路径的 API。

**Recommendation**:  
二选一：要么把 worker/executor `source_path` 迁移纳入本 change 的 ship scope，并把成功标准绑定到 5 个 generator；要么把 proposal 降级为“底层预备 API”，移除“candidate 落盘内存问题已解决”的目标和 200 MB 主验收口径。

---

### [MAJOR] 哈希 source 而不是落盘目标会制造不可检测的 artifact hash/bytes 不一致

**Location**: [design.md:293](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:293), [design.md:301](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:301), [design.md:385](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:385), [artifact-contract.md:28](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:28)  
**Confidence**: 0.86

**Body**:  
设计流程是 `FileBackend.write(source_path)` 先 `shutil.copy2(src, abs_path)`，然后 `ArtifactRepository.put` 再 `hash_path(source_path)`。如果 source 文件在 copy 期间或 copy 之后被 producer 清理、覆盖、继续写入，Artifact.hash 记录的是 source 的后续状态，而 `payload_ref.file_path` 指向的是 copy 出来的目标文件。结果是 artifact 首次注册成功，但 resume drift 校验会认为落盘文件 corrupt 并跳过，或者更糟糕地让调试者看到 hash 与实际 artifact bytes 不一致。

**Recommendation**:  
`repo.put` 应在 backend 返回 `PayloadRef` 后对目标 artifact path 做 `hash_path(backend.absolute_path(ref))`，或让 `FileBackend.write` 在复制到最终文件后返回目标 path/内容 hash。验收测试应覆盖“copy 后修改 source，artifact hash 仍匹配目标文件”。

---

### [MAJOR] drift 校验规范互相矛盾，实现者无法判断 inline/blob 应该怎么处理

**Location**: [design.md:417](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:417), [design.md:433](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:433), [artifact-contract.md:142](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:142), [artifact-contract.md:147](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:147)  
**Confidence**: 0.83

**Body**:  
design 说 file/blob 通过 `backend.absolute_path(ref)` 走 stream，inline “没有 drift 校验”。但 artifact-contract 又要求 file/blob 使用 private `_resolve(...)`，并要求 inline 仍走 `hash_payload(self._registry.read(...))`。这不是文字差异，而是行为契约冲突：一个实现会跳过 inline drift，一个实现会新增 inline hash 校验；一个实现依赖 ABC `absolute_path`，另一个实现越过 backend 抽象访问 `_resolve`。后续实现、测试和 review 会各自按不同权威解释，容易造成 spec 通过但设计偏离。

**Recommendation**:  
统一为一个契约：file kind 使用公开 `backend.absolute_path(ref)` 后 `hash_path(abs_path)`；blob stub 明确本 change 不支持 stream drift 或保留现状；inline 是否 drift 校验必须单独拍板，并让 design/spec/tasks 三处完全一致。

---

### [MINOR] RSS 成功阈值在 proposal、spec、tasks 中不一致

**Location**: [proposal.md:54](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:54), [artifact-contract.md:86](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:86), [probe-and-validation.md:31](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:31), [tasks.md:929](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:929)  
**Confidence**: 0.78

**Body**:  
proposal 的成功判定是 200 MB 文件 RSS 增量 `< 10 MB`，artifact-contract / probe spec / tasks 实际 fence 是 `< 32 MB`。这会导致实现验收时出现“按 tasks/spec 通过、按 proposal 失败”的状态，尤其这个 change 的核心卖点就是内存上限。

**Recommendation**:  
选定唯一阈值并解释来源。若 32 MB 是实际可测阈值，就把 proposal 的 `< 10 MB` 改掉；若 10 MB 是硬目标，测试 fence 必须按 10 MB 守门。

---

## Verdict

`needs-attention`

当前 4 件套存在目标与 Phase 1 范围不匹配、hash 正确性风险和规范冲突。先修正文档契约与验收标准，再进入实现。
