�ɹ�: ����ֹ PID 49500 (���� PID 63452 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 63452 (���� PID 42996 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 42996 (���� PID 42672 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 42672 (���� PID 63560 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 63560 (���� PID 50504 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 51812 (���� PID 17748 �ӽ���)�Ľ��̡�
�ɹ�: ����ֹ PID 17748 (���� PID 50504 �ӽ���)�Ľ��̡�
## Summary

结论是 `needs-attention`。实现层面存在一个明确 correctness bug（inline null resume 会被跳过），并且 zero-copy 的核心安全/验收边界仍有半提交窗口与缺失 evidence；如果把本 change 当作完整 TBD-012 关闭，范围也和长期需求不一致。

## Findings

### [MAJOR] inline `None` artifact 可以写入但无法 resume

**Location**: [inline_backend.py:57](/D:/ClaudeProject/ForgeUE_claude/src/framework/artifact_store/payload_backends/inline_backend.py:57), [repository.py:244](/D:/ClaudeProject/ForgeUE_claude/src/framework/artifact_store/repository.py:244), [artifact-contract.md:83](/D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/artifact-contract.md:83)  
**Confidence**: 0.95

**Body**:  
spec 明确 `value=None` 是合法 inline JSON null payload，但 `InlineBackend.exists()` 仍用 `ref.inline_value is not None` 判存在。`load_run_metadata()` 在进入 inline “直接 register”语义前统一调用 `self._registry.exists(art.payload_ref)`，因此 dump 后再 load 的 inline null artifact 会被当成 missing payload 跳过。现有测试只覆盖 `repo.put(value=None)` 不抛错，没有覆盖 dump/load resume。

**Recommendation**:  
让 inline exists 基于显式字段存在性判断，例如 `"inline_value" in ref.model_fields_set`，或在 `load_run_metadata()` 中对 inline kind 跳过 backend exists 检查；补一个 `repo.put(value=None)` → `dump_run_metadata()` → fresh repo `load_run_metadata()` 的回归测试。

---

### [MAJOR] `os.replace` 后再 hash 会留下半提交数据损坏窗口

**Location**: [file_backend.py:105](/D:/ClaudeProject/ForgeUE_claude/src/framework/artifact_store/payload_backends/file_backend.py:105), [repository.py:105](/D:/ClaudeProject/ForgeUE_claude/src/framework/artifact_store/repository.py:105), [design.md:767](/D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/design.md:767)  
**Confidence**: 0.85

**Body**:  
`FileBackend.write()` 已经 `os.replace(tmp_dest, abs_path)` 覆盖 final 文件后，`ArtifactRepository.put()` 才对 final path 执行 `hash_path()`。如果 replace 成功后 hash 失败，调用方看到 `put()` 失败，但旧的 valid payload 已经被覆盖且 Artifact metadata 没有更新。现有 atomic 测试只覆盖 `copyfile` 抛异常的 pre-replace 路径，design 也把该问题记录成 future work。

**Recommendation**:  
改为 staging-hash：在 tmp file 上完成 size/hash 校验，并通过 backend 返回 `PayloadRef + content_hash` 后再 replace；至少补一个 mock `hash_path` 抛错的测试，证明失败路径不会破坏既有 dest。

---

### [MAJOR] 实现没有接入任何生产 generator，不能作为完整 TBD-012 关闭

**Location**: [SRS.md:524](/D:/ClaudeProject/ForgeUE_claude/docs/requirements/SRS.md:524), [tasks.md:5](/D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:5), [generate_video.py:133](/D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/executors/generate_video.py:133)  
**Confidence**: 0.95

**Body**:  
长期 SRS/backlog 对 TBD-012 的描述包含 “所有 worker 路径(image / mesh / audio / video)同步迁移”，但本实现明确 Phase 1 不改变 executor 内存行为。代码中 video/audio/mesh/image/image_edit 仍分别走 `value=cand.data` 或 `value=r.data`，Candidate 仍是 `data: bytes`。这意味着真实大文件路径仍会在 worker/executor 层全读，当前测试只证明手工调用 `repo.put(source_path=...)` 有能力，不证明用户可见内存问题已解决。

**Recommendation**:  
如果本 change 只交付 Phase 1，保持 LR/TBD 打开并在 archive/acceptance 中明确 “未关闭端到端大文件内存收益”；如果要关闭 TBD-012，则需要实施 `worker-candidate-source-path-migration` 并增加 generator 级测试。

---

### [MAJOR] 核心 RSS 验收是 opt-in，且缺少要求的 evidence 文件

**Location**: [test_repo_put_streaming.py:181](/D:/ClaudeProject/ForgeUE_claude/tests/unit/test_repo_put_streaming.py:181), [tasks.md:1427](/D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/tasks.md:1427), [probe-and-validation.md:29](/D:/ClaudeProject/ForgeUE_claude/forge/changes/repo-put-streaming-payload/specs/probe-and-validation.md:29)  
**Confidence**: 0.90

**Body**:  
200MB RSS fence 默认被 `FORGEUE_RUN_HEAVY_FENCE` skip；baseline pytest 不能证明 `<32MB` peak RSS。tasks 又明确要求 archive 前生成 `.evidence/heavy-fence-rss-200mb.log`，但当前 `.evidence` 下未发现 `*heavy*` 日志。也就是说 zero-copy 最关键的验收指标没有可审计证据。

**Recommendation**:  
运行 opt-in heavy fence，保存并提交/附上要求的 evidence log；或者增加一个默认 CI 可跑的较小 peak RSS fence，避免核心性能 claim 只依赖手工步骤。

---

## Verdict

`needs-attention`

至少 inline null resume bug 和 replace 后 hash 半提交窗口需要在合并前处理；若只交付 Phase 1，也必须把 TBD-012 关闭语义和 evidence 缺口补清楚。
