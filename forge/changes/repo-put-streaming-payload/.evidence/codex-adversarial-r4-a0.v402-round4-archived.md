�ɹ�: ����ֹ PID 69700 (���� PID 65428 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 65428 (���� PID 35188 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 35188 (���� PID 60712 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 60712 (���� PID 37000 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 37000 (���� PID 37008 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 66404 (���� PID 63624 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 63624 (���� PID 37008 �ӽ���)�Ľ��̡�
## Summary

本 change 还不适合进入 apply/ship 阶段。主要风险不是接口意图，而是四件套内部对关键行为的契约不一致：写入原子性、`os.replace` 语义、inline drift 校验、以及 `source_path` 输入边界都没有被稳定锁死。

## Findings

### [MAJOR] `source_path` 写入的原子性与 `os.replace` 契约互相冲突

**Location**: [proposal.md:43](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:43), [proposal.md:52](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:52), [design.md:184](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:184), [tasks.md:514](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:514)  
**Confidence**: 0.9

**Body**:  
proposal 仍写着 `shutil.copy2 / os.replace`，并说同盘 fast path 用 `os.replace` 做原子性；design 又拍板“不走 `os.replace`，统一 `shutil.copy2`”，因为直接 replace source 会移走 caller 文件。tasks 最终片段则是 `shutil.copy2(src, abs_path)` 直接写 final path，只在 post-copy 超 cap 时清理。这样在 disk full、copy 中断、权限错误、source 读取失败时，final artifact path 可能残留半文件；如果复用同一个 `artifact_id`，旧的有效 payload 会先被破坏，而 metadata/hash 还没成功更新。

**Recommendation**:  
统一契约为“永不移动 source；copy 到同目录临时文件；验证 size/hash；最后 `os.replace(tmp, abs_path)` 原子替换 dest；异常清理 tmp”。同步删掉 proposal/spec 里会被理解为 `os.replace(source, dest)` 的表述。

---

### [MAJOR] inline payload 的 drift 校验语义在 proposal/spec 与 design/tasks 中相反

**Location**: [proposal.md:53](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:53), [proposal.md:58](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:58), [artifact-contract.md:203](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:203), [design.md:556](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:556), [tasks.md:1065](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1065)  
**Confidence**: 0.86

**Body**:  
proposal/spec 明确说 inline 仍走 `hash_payload(self._registry.read(...))`，且 hash 不一致应 skipped；design 的伪代码却在 inline 分支 `pass`，注释写“inline kind 没有 drift 校验”。tasks 也只加 file/blob drift fence，没有 inline tamper 用例。结果是实现者无法判断 inline `_artifacts.json` 被改但 hash 未更新时应该拒绝还是注册，可能导致 resume/checkpoint 消费与 `Artifact.hash` 不匹配的 inline payload。

**Recommendation**:  
先拍板 inline drift 是否属于本 change。若不改现状，就把 proposal/spec 的 inline hash 校验要求删掉并写成显式 non-goal；若要新增 inline drift，则 tasks 必须补 inline corrupt metadata 回归测试和兼容性说明。

---

### [MAJOR] `source_path` 非 regular file 的边界只写了期望，没有设计守门

**Location**: [artifact-contract.md:161](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:161), [design.md:373](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:373), [design.md:384](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:384), [tasks.md:474](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:474), [tasks.md:507](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:507)  
**Confidence**: 0.82

**Body**:  
spec 要求 `source_path` 不存在或不是 regular file 时拒签，但 design/tasks 只有 `src.stat().st_size` 后直接 `shutil.copy2`。`stat()` 对目录、symlink、FIFO、device 等不等于“regular file 校验”；后续 `copy2` 的行为会平台相关，最坏可阻塞或复制非预期内容。测试只覆盖 missing source，没有覆盖目录/特殊文件/ symlink policy。

**Recommendation**:  
在 cap 校验前明确 regular-file guard：例如 `src_stat = src.stat()` 后用 `stat.S_ISREG(src_stat.st_mode)`，并明确 symlink 是否允许。补目录和至少一个非 regular file fence；错误类型也要与 spec 一致。

---

### [MINOR] `hash_path(chunk_size)` 缺少非法参数守门，会静默算错 hash

**Location**: [design.md:312](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:312), [design.md:323](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:323), [artifact-contract.md:103](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:103), [tasks.md:69](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:69)  
**Confidence**: 0.95

**Body**:  
`hash_path` 暴露 `chunk_size` 给测试/调优，但伪代码直接 `f.read(chunk_size)`。如果传 `chunk_size=0`，`read(0)` 立即返回空 bytes，非空文件也会得到 empty hash，属于静默错误。现有测试只覆盖正数 chunk size。

**Recommendation**:  
定义 `chunk_size <= 0` 必须 raise `ValueError`，并补 `test_hash_path_rejects_non_positive_chunk_size`。

---

## Verdict

`needs-attention`

四件套已经把 Phase 1 范围说清楚，但关键 I/O 语义仍有互相矛盾和未守门边界。先收敛这些契约，否则 apply 阶段很容易实现出“测试看似通过、失败路径破坏 payload”的版本。
