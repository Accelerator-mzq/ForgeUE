�ɹ�: ����ֹ PID 64736 (���� PID 57704 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 57704 (���� PID 48332 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 60144 (���� PID 46352 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 46352 (���� PID 46224 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 46224 (���� PID 46588 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 46588 (���� PID 26696 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 26696 (���� PID 48332 �ӽ���)�Ľ��̡�
## Summary

审查范围聚焦 `repo-put-streaming-payload` 四件套。当前不建议 ship：核心风险不是实现细节，而是契约本身存在互相矛盾和事务边界缺口，会让后续实现者按不同文件得出不同代码。

## Findings

### [MAJOR] `copy2` / `copyfile` 决策在四件套中互相冲突

**Location**: [proposal.md:44](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:44), [design.md:199](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:199), [artifact-contract.md:159](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:159), [probe-and-validation.md:83](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:83)  
**Confidence**: 0.95

**Body**:  
proposal 仍要求 `shutil.copy2`，design 后半段和 artifact spec 又要求 `copyfile` 且明确 NOT `copy2`。测试 spec 还写了 spy `shutil.copy2`，这会让错误实现用 `copyfile` 时测试不覆盖，或让实现者按 proposal 用 `copy2`，继承 source 的只读权限 / mtime，正好违背 R5-F4 权限归一化目标。

**Recommendation**:  
把四件套统一成单一契约：只能 `shutil.copyfile(src, tmp_dest)` + `os.chmod(tmp_dest, 0o644)`。所有 `copy2` 文案、spy、测试名都改成 `copyfile`，并保留 source readonly -> dest writable 的默认 fence。

---

### [MAJOR] `os.replace` 后再 hash，会留下不可回滚的半提交窗口

**Location**: [design.md:463](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:463), [design.md:569](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:569), [design.md:590](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:590)  
**Confidence**: 0.84

**Body**:  
设计先 `os.replace(tmp_dest, abs_path)`，然后 `repo.put` 再对 final dest 执行 `hash_path`，最后才注册 `self._artifacts`。如果 replace 成功后 hash 失败，旧的 valid payload 已经被覆盖，但 metadata / Artifact 没更新；这和 design 自己在 copy failure 场景里要避免的“payload 被破坏但 hash/metadata 未更新”是同类问题。

**Recommendation**:  
把 hash 纳入 staging 阶段：对 `tmp_dest` 计算 hash 和 size，确认后再 `os.replace`，并让 backend 返回内部 `WriteResult(ref, content_hash)` 或等价机制。至少补一个 fence：模拟 `hash_path` 在 replace 后失败，断言既有 final payload 不被破坏。

---

### [MAJOR] `PayloadBackend.write` 层没有执行二选一不变量

**Location**: [design.md:540](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:540), [tasks.md:584](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:584), [tasks.md:629](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:629)  
**Confidence**: 0.86

**Body**:  
`repo.put` 明确 `value` / `source_path` 二选一，但 `FileBackend.write` source_path 分支没有拒绝同时传入 value，tasks 还大量用 `b.write(value=None, source_path=src)` 作为合法调用。由于 `value=None` 被整个设计定义为合法 payload，这等于在 backend 公共 ABC 层允许“双 payload source”，并静默忽略 value。未来绕过 repository 直接用 registry/backend 时，可能写入的不是调用方以为的 bytes。

**Recommendation**:  
在 `PayloadBackendRegistry.write` 或 `FileBackend.write` 也执行同样二选一守门。source_path backend 测试应省略 `value`，不要传 `value=None`；新增 direct-backend fence：`FileBackend.write(value=b"x", source_path=src)` 必须 raise。

---

### [MINOR] heavy fence evidence 自检命令匹配不到实际输出

**Location**: [tasks.md:1267](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1267), [tasks.md:1427](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1427), [tasks.md:1435](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1435)  
**Confidence**: 0.9

**Body**:  
测试实际打印 `[heavy-fence] RSS peak delta...`，tasks 的 evidence 断言也要求 `RSS peak delta`，但 grep 自检写成 `\[heavy-fence\] RSS delta`。archive 前自检会漏掉峰值行，导致 evidence gate 误判或被人工跳过。

**Recommendation**:  
把 grep 改成匹配 `RSS peak delta`，并让 expected output 明确必须同时出现 `PASSED` 和 peak delta 行。

---

## Verdict

needs-attention

当前四件套还不能作为可执行设计交给实现阶段。先统一 copy 契约、补齐 post-replace 失败事务边界，再收紧 backend 层二选一不变量。
