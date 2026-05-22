�ɹ�: ����ֹ PID 58492 (���� PID 69808 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 69808 (���� PID 65424 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 53004 (���� PID 62552 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 62552 (���� PID 52416 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 52416 (���� PID 51524 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 51524 (���� PID 49856 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 49856 (���� PID 65424 �ӽ���)�Ľ��̡�
## Summary

结论是 `needs-attention`。四件套已经把主方向讲清楚，但仍有几个会直接影响验收可信度或数据安全的矛盾：inline drift 契约互相冲突、RSS fence 可能漏掉瞬时全量内存峰值、post-copy 超 cap 分支里出现会删除既有 payload 的错误指令。

## Findings

### [MAJOR] inline drift 语义在 proposal/design/spec 之间互相冲突

**Location**: [proposal.md:58](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/proposal.md:58), [design.md:612](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:612), [artifact-contract.md:213](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:213)  
**Confidence**: 0.9

**Body**: proposal 明确说 `inline` kind “不做 drift 校验，直接 register_existing”，design 也写 inline 没有 drift 校验；但 artifact spec 又要求 inline 仍走 `hash_payload(self._registry.read(...))`，并声明 hash 不一致要 skip。实现者无论选哪边都会违反另一份权威文档，验收也无法判断 inline metadata 被改时到底应 register 还是 skip。

**Recommendation**: 统一契约。若本 change 只处理 file kind，就把 artifact spec 的 inline 段改为“不做 payload drift 校验”，并把 metadata corruption 留在 out-of-scope；若要保留 inline hash 校验，就补 proposal/design/tasks 的 inline 场景与回归测试。

---

### [MAJOR] RSS fence 只看 before/after，无法证明没有全量内存峰值

**Location**: [probe-and-validation.md:31](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:31), [tasks.md:1196](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1196), [tasks.md:1212](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1212)  
**Confidence**: 0.85

**Body**: spec 要证明 200 MB `repo.put(source_path=...)` RSS 增量 < 32 MB，但 tasks 里的 heavy fence 只在调用前后各采一次 `psutil.Process().memory_info().rss`。如果实现中间短暂 `read_bytes()` 出 200 MB，再在返回前释放，对 before/after 采样可能仍然低于阈值，主要性能目标会被假阳性放行。

**Recommendation**: 改为 peak 采样：用子进程 `resource.getrusage().ru_maxrss`，或用后台线程高频采样 psutil 的 max RSS，Windows 下至少记录 `max_rss - baseline`。evidence 里保存 peak 数值，而不是只保存 after-before delta。

---

### [MAJOR] post-copy 超 cap 分支文档写成删除 final path，违反原子性目标

**Location**: [design.md:298](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:298), [design.md:193](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:193), [artifact-contract.md:163](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:163)  
**Confidence**: 0.9

**Body**: D4 的核心 invariant 是 copy 到 tmp 后再 `os.replace`，失败不破坏既有 final payload；但 D9 的异常说明写成 post-copy 超 cap 时“立即 `abs_path.unlink` + raise”。这个分支如果被实现者按文字执行，会在已有有效 artifact 的同 `artifact_id` retry 场景下删除 final payload，正好破坏本 change 想保护的数据安全边界。

**Recommendation**: 把 D9 文本修正为清理 `tmp_dest`，绝不 unlink `abs_path`。同时加一个 post-copy 超 cap + final 已存在的 fence，断言旧 final bytes 保留、只删除 tmp。

---

### [MAJOR] `copy2` 会把 source 权限/元数据带进 artifact store，风险未建模

**Location**: [design.md:199](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:199), [artifact-contract.md:158](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:158), [design.md:549](D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:549)  
**Confidence**: 0.8

**Body**: design 把 `shutil.copy2` 保留 mtime/权限当成优点，但 artifact store 的文件权限不应该继承 caller source。source 是只读或权限位异常时，dest 会继承这些属性；随后 `repo.put` 还要对 dest 做 `hash_path`，后续同 artifact overwrite / resume / read 也依赖 artifact store 能稳定读写。现有 plan 没有权限归一化，也没有只读 source / restrictive mode 的测试。

**Recommendation**: 使用不复制权限语义的 copy 路径，或在 `os.replace` 前后显式设置 artifact store 的标准权限。补测试覆盖只读 source、重复写同 artifact_id、写后 `hash_path(dest)` 与 resume read 都可用。

## Verdict

`needs-attention`

这些不是实现细节洁癖，而是四件套本身的契约冲突和验收盲区。先把上述边界写一致，并让 fence 真能抓到峰值内存和失败分支数据安全，再进入 apply 更稳。
