�ɹ�: ����ֹ PID 69844 (���� PID 3188 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 3188 (���� PID 34864 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 34864 (���� PID 37072 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 37072 (���� PID 66188 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 66188 (���� PID 65892 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 51448 (���� PID 65324 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 65324 (���� PID 65892 �ӽ���)�Ľ��̡�
## Summary

Verdict 是 `needs-attention`。四件套把 Phase 1 边界说清楚了，但核心 artifact 写入失败原子性、resume 大文件 RSS 验收、`value=None` inline 契约仍存在会导致数据损坏、验收空洞或 resume 丢 artifact 的设计缺口。

## Findings

### [MAJOR] source_path 直接 copy 到 final path，没有原子提交语义

**Location**: [proposal.md:52](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:52), [design.md:184](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:184), [tasks.md:514](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:514)  
**Confidence**: 0.9

**Body**:  
proposal 还写着 `FileBackend.write` “原子性走 os.replace 同盘 fast path”，但 design D4 直接否决 `os.replace`，tasks 最终实现指令是 `shutil.copy2(src, abs_path)` 写到最终 artifact 路径。这里把“用 `os.replace(source, dest)` 移走 source”和“先 copy 到临时文件，再 `os.replace(tmp, dest)` 原子发布”混为一谈。

结果是：copy 中途磁盘满、读源文件失败、权限异常、进程中断时，final path 可能留下半截文件。更糟的是如果 artifact_id 重试/碰撞，post-copy cap 的 `abs_path.unlink()` 或失败中的覆盖可能破坏已有有效 artifact。

**Recommendation**:  
改成 `dest.parent` 下临时文件写入：`copy2(src, tmp)` → post-copy cap 校验 → `os.replace(tmp, abs_path)` → 对 final path 取 `size_bytes/hash`。异常路径只清理 `tmp`，不得删除既有 `abs_path`。补两个 fence：copy 中途异常不会留下 final partial；已有 final artifact 在失败写入后仍保留。

---

### [MAJOR] resume 大文件 RSS 契约没有被可执行验收覆盖

**Location**: [proposal.md:10](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:10), [artifact-contract.md:208](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:208), [probe-and-validation.md:29](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:29), [tasks.md:908](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:908), [tasks.md:1106](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1106)  
**Confidence**: 0.85

**Body**:  
change 的 Why 明确把 `load_run_metadata` resume 大文件全读列为目标问题，artifact-contract 也要求 200 MB video resume drift 校验 RSS `<32 MB`。但 probe spec 的 heavy RSS fence 只跑 `repo.put(source_path=...)`，Task 6 的 `load_run_metadata` 用例只写 64 KB 并 spy `hash_payload`，Task 7 的 200 MB opt-in fence 也只覆盖 put。

这会让实现通过所有列出的验收，却没有证明 resume 大文件路径真的满足 RSS 契约。spy 不等于大文件内存验收，尤其是这个 change 的目标之一就是 resume drift 不全读。

**Recommendation**:  
新增 opt-in heavy fence：构造 200 MB file artifact + `_artifacts.json`，fresh repo 执行 `load_run_metadata`，断言 RSS delta `<32 MB`，并 spy `PayloadBackendRegistry.read` / repository 绑定的 `hash_payload` 未调用。archive evidence 需要同时包含 put 和 resume 两条 heavy fence 日志；否则删除 artifact-contract 里的 resume RSS 场景。

---

### [MAJOR] `value=None` inline 契约和 resume 行为不一致

**Location**: [artifact-contract.md:83](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:83), [tasks.md:674](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:674), [tasks.md:1068](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1068), [design.md:556](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:556), [proposal.md:58](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:58), [inline_backend.py:39](D:/ClaudeProject/ForgeUE_claude/src/framework/artifact_store/payload_backends/inline_backend.py:39)  
**Confidence**: 0.9

**Body**:  
四件套把 `value=None` 明确升级为合法 inline JSON null payload，并加了 immediate `repo.read_payload()` 测试。但 tasks 又要求保留 `load_run_metadata` 上游的 `payload_present = self._registry.exists(...)` 检查；当前 `InlineBackend.exists()` 对 `inline_value is None` 返回 False。也就是说，一个按新契约合法写入并 dump 到 `_artifacts.json` 的 inline null artifact，在 resume 时会被当成 payload missing 跳过。

同时文档内部也不一致：proposal/spec 说 inline 仍走 `hash_payload(read(ref))`，design 说 inline 没有 drift 校验、直接 register。实现者无法从四件套判断正确行为。

**Recommendation**:  
先统一契约：若 `value=None` 合法，`InlineBackend.exists()` 应对 inline kind 返回 True，即使 `inline_value is None`。同时把 proposal/spec/design 对 inline drift 的描述改成同一种语义，并新增 dump/load fence：`repo.put(value=None, payload_kind=inline)` → `dump_run_metadata` → fresh repo `load_run_metadata` 后 artifact 仍存在且 payload 为 None。

---

## Verdict

`needs-attention`

这些不是命名或文档口径问题，而是 artifact store 写入/恢复的核心正确性风险。至少需要修掉原子提交设计、补齐 resume RSS evidence，并统一 inline null 的持久化语义后再进入 apply。
