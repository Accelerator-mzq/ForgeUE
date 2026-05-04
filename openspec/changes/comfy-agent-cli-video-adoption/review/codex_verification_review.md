---
change_id: comfy-agent-cli-video-adoption
stage: S5
evidence_type: codex_verification_review
contract_refs: [tasks.md#12.1]
aligned_with_contract: false
detected_env: claude-code
triggered_by: "/codex:review --base 5ea85ae --background"
codex_plugin_available: true
drift_decision: written-back-to-ue_scripts/run_import.py+examples/comfy_local_smoke_video.json
writeback_commit: 7a7b7dc
drift_reason: "codex review 给出 2 P2 findings:(1) run_import.py 不 honor framework PermissionPolicy(allow_import_file_media_source=False)denied op,会绕过权限创建 asset;(2) examples/comfy_local_smoke_video.json worker_timeout_s=600s 实测 896s 超时。两项都已 writeback to code(commit pending),并加 P4 stub fence test_p4_run_import_skips_permission_denied_file_media_source_op cover (1) 修复(asserts AssetTools.create_asset NEVER 被调 + skipped record 仅 1 条)"
---

# Codex Verification Review (review-mor0q6v8-2gsfxc, 2026-05-04)

## Codex Output(verbatim,沿 design.md §3 Codex Review Output Exposure Protocol)

```
# Codex Review

Target: branch diff against 5ea85ae
Verdict: needs-attention

补丁新增的视频 UE 导入路径会绕过新增权限开关，且 checked-in smoke 配置在真实默认视频工作流下容易超时。两者都是应在合并前修正的可操作问题。

Full review comments:

- [P2] Honor denied video import permissions — D:/ClaudeProject/ForgeUE_claude/ue_scripts/run_import.py:43-43
  当调用方设置 `PermissionPolicy(allow_import_file_media_source=False)` 时，`ExportExecutor` 只会在 `evidence.json` 里写一条 skipped 记录，`import_plan.json` 仍保留该 op；这里新增 UE-side handler 后，用户运行 `run_import.py` 会继续执行被策略拒绝的 video import 并创建 `FileMediaSource`。需要让 UE-side runner 跳过已被权限策略拒绝的 op，或在导出阶段不要把 denied op 交给 commandlet 执行。

- [P2] Increase the checked-in video smoke timeout — D:/ClaudeProject/ForgeUE_claude/examples/comfy_local_smoke_video.json:48-48
  在默认 Wan2.1 81 帧 / 25 steps 的 video smoke 场景下，当前 `600s` timeout 容易在冷模型加载或首轮运行时提前中止；本变更自带的 live smoke 记录同类配置约需 896s 才完成。建议把示例 timeout 提高到实际验收使用的量级（如 1800s），或同步降低示例的帧数 / steps。

Codex session ID: 019df265-06d8-7fc0-87cf-c9d37491c8bf
```

## Claude Cross-check Resolution

### P2-1 — run_import.py honor PermissionPolicy [accepted-codex]

**Verdict**:有效 finding。framework 层 `ExportExecutor` 只 emit `status="skipped"` evidence 但 `import_plan.json` 仍含该 op;UE-side commandlet 走 plan ops loop 时会执行 denied op,违反 NFR-PERMISSION-001 用户权限边界。

**Resolution(已 writeback to code)**:
- `ue_scripts/run_import.py:54-77` 加 `pre_skipped_op_ids: set[str]` 读 framework seed evidence(`status="skipped"` op_id);for op in ops 时先检查 `op["op_id"] in pre_skipped_op_ids` → continue(不调 handler,不重复写 evidence)
- 加 P4 stub fence `tests/integration/test_p4_ue_manifest_only.py::test_p4_run_import_skips_permission_denied_file_media_source_op`:asserts `_FakeAssetTools.create_asset` NEVER 被调 + evidence 仅 1 条 `import_file_media_source skipped` record(framework seed 写,run_import 不复写)
- pytest baseline:1414 → 1415 passed(+1 fence)

### P2-2 — bundle worker_timeout_s 600s 太短 [accepted-codex]

**Verdict**:有效 finding。L2 evidence(`notes/live_smoke_video_20260504.md`)实测 prompt 14:57(896s);默认 Wan2.1 81 帧 25 steps 配置下 600s 不够。

**Resolution(已 writeback to bundle)**:
- `examples/comfy_local_smoke_video.json:48` `worker_timeout_s: 600` → `1800`(对齐 L2 evidence bundle `_l2_smoke_video_bundle.json` 的 1800s 设置)
- 不缩 num_frames / steps — bundle 是 demo 默认,代表用户上手 baseline

## disputed_open: 0
