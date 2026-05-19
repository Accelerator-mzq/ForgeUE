---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S6
evidence_type: codex_adversarial_review
review_round: 3
note_kind: raw_verbatim
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议 ship。D12 evidence 仍在 Windows 下写出与 manifest 不同格式的路径,且 S5 review 产生的 5 个 follow-on 还没有进入 registry,archive 前审计闭环不成立。

Findings:
- [medium] 承 round1-F3: Evidence drop path 在 Windows 下不是 POSIX (src/framework/runtime/executors/export.py:134)
  `ExportExecutor` 用 `str(target_fs.relative_to(Path(target.project_root)))` 写 `Evidence.target_object_path`。在 Windows 这会产生 `Content\Movies\...`,而 manifest `source_uri` 是 `Content/Movies/...`;L2 evidence 已记录这种原始不一致,integration test 又用 `.replace("\\", "/")` 规避了断言。影响是下游审计、恢复或一致性检查按原始 JSON 比较时会误判 D12 source/drop 不一致,削弱本 change 的"单源路径"目标。
  Recommendation: 把 evidence 写入改成 `target_fs.relative_to(Path(target.project_root)).as_posix()`,并把 P4/integration 断言改为不做 slash normalize 的 raw equality。
- [medium] S5 review follow-on 没有落 registry (openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md:76-84)
  S5 codex verification review 明确列出 5 个 P2/P3 follow-on,并写着 archive 阶段要加到 `openspec/backlog/active.md`。当前 active registry 中这些 id 不存在;若按"post-archive"处理,它们不会成为 finish gate 的输入,accepted out-of-scope findings 可能在归档后丢失追踪。
  Recommendation: 在运行 finish/archive 前把这 5 个 follow-on 写入 `openspec/backlog/active.md` 并更新计数;若决定不登记,需在当前 change evidence 中写明用户级决策和原因。

Next steps:
- 修正 evidence path 序列化并补 raw POSIX 断言。
- 补齐 S5 review 产生的 5 个 follow-on registry entry 后再跑 finish gate。
