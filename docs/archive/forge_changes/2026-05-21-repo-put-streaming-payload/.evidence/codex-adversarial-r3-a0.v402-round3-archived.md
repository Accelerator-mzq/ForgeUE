�ɹ�: ����ֹ PID 70484 (���� PID 60688 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 60688 (���� PID 61780 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 61780 (���� PID 66264 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 66264 (���� PID 59992 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 59992 (���� PID 56604 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 46320 (���� PID 55836 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 55836 (���� PID 56604 �ӽ���)�Ľ��̡�
## Summary

结论是 `needs-attention`。四件套里有多处合同级矛盾，尤其是 `_MISSING` vs `None`、dest vs source 取样、blob drift scope，这些会让实现者按不同文件得到互相冲突的代码路径与测试目标。

## Findings

### [MAJOR] `_MISSING` 与 `None` 的 API 合同互相冲突

**Location**: [artifact-contract.md:22](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:22), [artifact-contract.md:132](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:132), [probe-and-validation.md:59](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:59), [design.md:362](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:362)  
**Confidence**: 0.95

**Body**:  
spec 前半明确要求 `value: Any = _MISSING`，且 `value=None` 是合法 inline JSON null；但同一 spec 后面又把 `PayloadBackend.write` 写成 `value: Any = None`。`probe-and-validation` 还把“两者都缺”写成 `value=None, source_path=None` 应 raise，这正好和 `value=None` 合法场景冲突。实现者按这些要求写测试，会把合法 null payload 错判为缺参，破坏向后兼容。

**Recommendation**:  
所有 repo/backend 签名统一写成 `_MISSING` sentinel；“两者都缺”测试必须省略 `value` 参数，而不是传 `value=None`；`design.md` 的 `FileBackend.write` 示例也改成 `_MISSING`。

---

### [MAJOR] `size_bytes` 来源在 source 与 dest 之间摇摆，破坏 D9 invariant

**Location**: [artifact-contract.md:34](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:34), [artifact-contract.md:155](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:155), [design.md:237](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:237)  
**Confidence**: 0.9

**Body**:  
D9 设计要求 hash 与 `size_bytes` 都来自最终落盘 dest，避免 source 在 stat/copy/hash 之间变化导致 metadata 和真实文件不一致。但 artifact spec 后面又要求 `PayloadRef(... size_bytes=<source_stat.st_size>)`。这会把并发改写 source 的 race window 重新引入：dest 实际 bytes、`PayloadRef.size_bytes`、`Artifact.hash` 可能不再同源，resume drift 可能把刚写入的 artifact 判坏或放过坏数据。

**Recommendation**:  
spec 中 `FileBackend.write` 的返回合同必须改为 `size_bytes=<dest_stat.st_size>`；保留 source stat 只用于 pre-copy cap fail-fast；把 source-race 测试列为默认 fence，而不是只靠文字约定。

---

### [MAJOR] proposal 把 inline/blob 标成“不影响”，但设计和任务又要求必须修改

**Location**: [proposal.md:198](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:198), [design.md:205](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:205), [tasks.md:26](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:26)  
**Confidence**: 0.88

**Body**:  
proposal 明确说“不影响 `inline_backend.py` / `blob_backend.py`”，但 design D6 和 tasks 又要求这两个 backend 改签名、加 `source_path` guard、加 `absolute_path` 实现。ABC 签名演进不是可选项；如果实现者按 proposal scope 不碰 inline/blob，运行时可能出现抽象类未实现、unexpected keyword、或 registry 透传失败。

**Recommendation**:  
把 `inline_backend.py` 和 `blob_backend.py` 明确列入 In-scope；把 Out of Scope 改成“不做 stream/zero-copy 内部实现”，而不是“不影响文件”。

---

### [MAJOR] blob drift scope 在 design/spec 与 tasks 之间冲突

**Location**: [proposal.md:53](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:53), [design.md:522](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:522), [tasks.md:891](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:891), [tasks.md:990](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:990)  
**Confidence**: 0.85

**Body**:  
proposal/spec/design 都说 drift stream 只改 `file`，`blob` 保旧行为；但 tasks 的 Task 6 标题和代码把 `file/blob` 合并进 `absolute_path + hash_path` 分支。当前 BlobBackend 是 stub 时可能只是 continue，但这会把未来对象存储 blob 错误建模成本地 absolute path，并且和明确 out-of-scope 的 blob streaming 直接冲突。

**Recommendation**:  
tasks.md 按 design 5.6 改成 `if file -> hash_path(absolute_path)`，`elif blob -> 保旧 read + hash_payload`；补一个 blob 行为不变的单元 fence，防止实现阶段误改 scope。

---

### [MAJOR] drift fence 的 monkeypatch 目标写错，可能无法证明“不走全读”

**Location**: [probe-and-validation.md:87](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:87), [probe-and-validation.md:90](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:90), [tasks.md:935](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:935)  
**Confidence**: 0.8

**Body**:  
probe spec 要 monkeypatch `hashing.hash_payload` 来证明 `load_run_metadata` 没走全读。但 tasks 自己在实现说明里是从 repository module 导入并使用 `hash_payload`，测试也 patch `repo_mod.hash_payload`。如果按 spec patch 源模块，repository 里已绑定的函数引用不会被拦住，旧的全读路径仍可能通过这个 fence。

**Recommendation**:  
probe spec 明确 patch `framework.artifact_store.repository.hash_payload`，或更直接 spy `PayloadBackendRegistry.read` 在 file kind drift 上不被调用；把这个要求和 tasks 保持一致。

## Verdict

`needs-attention`

这些不是措辞问题，而是会直接改变 API 兼容性、metadata 正确性、scope 边界和验证可信度的矛盾。建议先修正四件套，再进入 apply。
