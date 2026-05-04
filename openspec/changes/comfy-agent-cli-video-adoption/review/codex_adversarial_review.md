---
change_id: comfy-agent-cli-video-adoption
stage: S6
evidence_type: codex_adversarial_review
contract_refs: [tasks.md#12.2]
aligned_with_contract: false
detected_env: claude-code
triggered_by: "/codex:adversarial-review --base 5ea85ae --background"
codex_plugin_available: true
drift_decision: written-back-to-tasks.md+notes+specs/ue-export-bridge+CLAUDE.md+AGENTS.md
writeback_commit: pending
drift_reason: "codex adversarial review (review-mor0pkxs-hxsviy) 给 3 findings:(1) [high] tasks.md §11/§11b/§12/§13 仍 unchecked + writeback_commit: pending(归档 gate 未闭合);(2) [high] specs/ue-export-bridge/spec.md:145-155 仍要求 set loop / play_on_open editor properties + 描述 AssetImportTask 路径(与 round-7 R1 实测修复 + AssetTools.create_asset 路径不一致);(3) [medium] CLAUDE.md 共享目录依赖段只登记 runner.py 没登记 round-7 R2 manifest 5-patch。三项已全 writeback to artifact"
---

# Codex Adversarial Review (review-mor0pkxs-hxsviy, 2026-05-04)

## Codex Output(verbatim,沿 design.md §3 Codex Review Output Exposure Protocol)

```
# Codex Adversarial Review

Target: branch diff against 5ea85ae
Verdict: needs-attention

不建议归档/发布。代码主链路看起来有覆盖，但变更的证据与契约层仍未闭合，尤其是 final review/finish gate 会读到未完成任务和已知 UE API 漂移。

Findings:
- [high] 归档 gate 仍有未完成任务，证据前置条件未闭合 (openspec/changes/comfy-agent-cli-video-adoption/tasks.md:521-582)
  `tasks.md` 的 §11 L2 smoke、§11b a2_video P4、§12 review hooks、§13 finish gate 仍是 `- [ ]`，但同文件 §13.2 又要求 finish gate 检查"unchecked 项 == 0"。这不是格式问题：按当前 HEAD 归档会把需要真实 L2/P4、最终 review、doc sync/finish gate 的步骤作为未完成状态带入 archive，和"final review pre-archive"的声明冲突。另一个佐证是 HEAD 中 live smoke frontmatter 仍有 `writeback_commit: pending`，说明 round-7 evidence 的提交锚点没有在目标 diff 中闭合。
  Recommendation: 把 §11/§11b/§12/§13 的实际执行结果按证据逐项 tick 或改为明确 SKIP-with-rationale，并确保 live smoke evidence 的 `writeback_commit` 是真实 commit SHA 后再跑 finish gate。

- [high] UE bridge delta spec 仍要求已实测失败的 FileMediaSource 属性设置 (openspec/changes/comfy-agent-cli-video-adoption/specs/ue-export-bridge/spec.md:145-155)
  round-7 R1 已通过 UE 5.7 commandlet 证明 `loop` / `play_on_open` 不是 `FileMediaSource` editor property，代码也改为只设置 `file_path`。但 delta spec 仍要求 `loop` / `play_on_open` 作为 editor properties，并描述 `AssetImportTask`/`FileMediaSourceFactory()` 路径，而实现是 `AssetTools.create_asset` + `FileMediaSourceFactoryNew`。如果现在 archive/sync，这个错误契约会进入主 spec，后续实现者可能按 spec 重新引入 commandlet 已经暴露的失败。
  Recommendation: 将该 spec 改成与 `ue_scripts/domain_video.py` 和 P4 evidence 一致：只 set `file_path`，`loop/play_on_open` 保留为 manifest/follow-on 字段；同步更新工厂/API 描述和测试名。

- [medium] 共享 ComfyUI 依赖文档漏登记 round-7 R2 manifest patch (CLAUDE.md:47-50)
  L2 evidence 和 design 说明，video 能跑通不仅依赖 `runner.py` 的 `outputs.video` 扩展，还依赖两份共享 ComfyUI manifest 的 5 个 VHS_VideoCombine default patches。可是 `CLAUDE.md` 的共享目录依赖段只登记了 `runner.py`，没有登记 `Vedio/Wan2.1-T2V-1.3B_native_5sec.json` 与 `Vedio/Wan2.1-T2V-1.3B_native.json` 的 patch。用户重装 ComfyUI 后按文档只保留 runner.py，仍会回到 HTTP 400 的 L2 失败路径。
  Recommendation: 在 `CLAUDE.md` 和同步的 `AGENTS.md` 共享目录依赖段显式列出两份 Wan manifest patch 及 5 个 default 字段，并标明重装 ComfyUI 时需要一并保留。

Next steps:
- 先修正 OpenSpec spec/tasks/evidence/doc sync，再重新跑 finish gate。
- 修复后再做一次只读 final adversarial review，确认没有 pending frontmatter、unchecked task 或 stale acceptance/changelog。

Codex session ID: 019df264-a332-71f3-89d8-0b61e1659fcd
```

## Claude Cross-check Resolution

### F1 — tasks.md unchecked + writeback_commit pending [accepted-codex]

**Verdict**:有效 finding。commit fe24fff 之前 §11/§11b/§12/§13 17 项 unchecked + `notes/live_smoke_video_20260504.md` writeback_commit: pending。

**Resolution(已 writeback,commit fe24fff)**:
- tasks.md §11/§11b/§12/§13 全 17 项 tick(本 conversation 实测完成:L2 video_smoke_l2_20260504_v3 + a2_video_20260504_v2 commandlet + finish gate / archive 步骤)
- `notes/live_smoke_video_20260504.md` writeback_commit `pending` → `1dfa5db`(commit 16 round-7 R1 修复 hash);git rev-parse 验证通过

### F2 — specs/ue-export-bridge/spec.md stale FileMediaSource 属性 + AssetImportTask 路径 [accepted-codex]

**Verdict**:有效 finding。spec lines 145-155 仍要求 set `loop` / `play_on_open` editor properties + 描述 `unreal.FileMediaSourceFactory()` + `unreal.AssetImportTask`,与 commit 1dfa5db round-7 R1 修复后的 `AssetTools.create_asset` + `FileMediaSourceFactoryNew` 实现 + 不 set loop/play_on_open 不一致。归档时 spec sync 会把 stale spec 带入 main `openspec/specs/ue-export-bridge`,后续实现者会按 stale spec 重新引入失败模式。

**Resolution(已 writeback to spec)**:
- `specs/ue-export-bridge/spec.md:145-155` 改为与 round-7 R1 实测 + `domain_video.py` 实现一致:
  - "Invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset(...)`" 替换 "Invoke `unreal.FileMediaSourceFactory()` + `unreal.AssetImportTask`"
  - "MUST NOT set `loop` / `play_on_open` editor properties on FileMediaSource" 替换 "Apply `import_options` ... `loop` / `play_on_open` set as editor properties"
  - 加注释 "(round-7 R1 修订:UE 5.7 commandlet 实测 `set_editor_property('loop')` 报 `Failed to find property` — 这两项是 MediaPlayer runtime properties)"
- Scenario 块加 "**`loop` / `play_on_open` editor properties are NOT set**" 显式约束

### F3 — CLAUDE.md / AGENTS.md 共享目录段漏登记 round-7 R2 manifest patch [accepted-codex]

**Verdict**:有效 finding。CLAUDE.md:47-50 + AGENTS.md:16-17 只登记 runner.py,没登记两份 Wan T2V manifest 的 5-widget default patches(round-7 R2 修复)。用户重装 ComfyUI 后只保留 runner.py 会回到 HTTP 400。

**Resolution(已 writeback to CLAUDE.md + AGENTS.md)**:
- CLAUDE.md `**ComfyUI 共享目录新增 ForgeUE 依赖**` 段加 `Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + `..._native.json` 路径登记 + 5 个 widget default patches 字段名(`frame_rate=24.0` / `loop_count=0` / `format="video/h264-mp4"` / `pingpong=false` / `save_output=true`)
- AGENTS.md `**ComfyUI 共享目录新增 ForgeUE 依赖**` 段同步登记
- 标题从 `(round-3 PF1 D-Runner-Extension)` 改为 `(round-3 PF1 D-Runner-Extension + round-7 R2)` 显式登记 round-7 R2 也是 SHARED_DIR scope

## disputed_open: 0

3 个 findings 全 accepted-codex,无 disputed-permanent-drift,无 disputed-pending。F1 已在 commit fe24fff writeback;F2 + F3 在本 commit(commit 18)writeback。
