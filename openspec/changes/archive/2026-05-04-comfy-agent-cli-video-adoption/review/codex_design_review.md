---
change_id: comfy-agent-cli-video-adoption
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - specs/ue-export-bridge/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-plan (interactive Claude Code session, S2→S3 transition) → /codex:adversarial-review --background"
codex_plugin_available: true
plugin_task_id: b2bsvp3fy
codex_thread_id: 019df098-5017-75a2-9ce5-77348bf2f900
verdict: needs-attention
findings_count: 4
findings_severity_breakdown: "high=2, medium=2"
created_at: 2026-05-04T11:25:00+08:00
codex_completed_at: 2026-05-04T11:43:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (4 findings 全 accepted-codex;详见 design_cross_check.md ## B/C/D;commit 55dc4d4 含全部 round-2 修订)
writeback_commit: 55dc4d48f670a8e8e20b4dcb781a23936a7f71c6
drift_reason: null
reasoning_notes_anchor: "design.md `## Reasoning Notes — round-2 codex review (2026-05-04)`"
note: |
  本文件是 codex /codex:adversarial-review --background 的 verbatim 输出,
  落盘以备 finish gate / cross-check 引用。Claude resolution / 独立验证 / writeback 详情见
  `review/design_cross_check.md` `## B / C / D` 段。
---

# Codex Adversarial Review (verbatim)

## Codex output

Target: working tree diff
Verdict: needs-attention

不建议进入实施:S2 合同仍会让 video 在真实 export/UE 路径里被静默跳过,且 mp4/webm 的 Artifact 与 UE 映射合同互相冲突。

Findings:

- [high] 真实 UE export gate 没被纳入任务链,video 可能不会进入 manifest (openspec/changes/comfy-agent-cli-video-adoption/tasks.md:271-293)
  8a 只列了 manifest_builder、import_plan_builder 和 permission tier 的改动,但当前真实导出路径还有两个前置 gate:src/framework/runtime/executors/export.py:212-216 的 _is_importable() 只允许 image/mesh/audio/material,video Artifact 会在 build_manifest() 前被过滤;src/framework/ue_bridge/permission_policy.py:13-32 对未知 op 默认 deny,而 tasks.md:293 指向了不存在/错误的 permissions.py/import_plan_builder 位置,没有明确要求改 src/framework/core/policies.py 的 PermissionPolicy 字段和 permission_policy.py 映射。影响是 direct manifest_builder 单测可绿,但 ue.export/P4 实际没有 import_file_media_source 或被 skipped。
  Recommendation: 在 S2 合同中显式加入 ExportExecutor._is_importable 包含 video、PermissionPolicy 增加 allow_import_file_media_source=True、permission_policy._OP_ALLOW_ATTR 映射,并加一个跑 ExportExecutor 的集成 fence,断言 video Artifact 产出 manifest/plan/evidence 中的 import_file_media_source 且未被 permission skip。

- [high] worker 接受 webm,但 executor 强制 shape=mp4 会把 webm 错路由成 mp4 UE 资产 (openspec/changes/comfy-agent-cli-video-adoption/specs/provider-routing/spec.md:207)
  provider-routing 允许 VideoCandidate.format 为 mp4/webm,并要求 webm magic 接受;但 GenerateVideoExecutor 合同在 repo.put 时对所有 candidate 强制 ArtifactType(modality="video", shape="mp4")。结合 ue-export-bridge 只映射 (video, mp4) 且 domain_video 复制到 .mp4 Movies 路径,推论是合法 .webm 输出会以 .webm 文件后缀落库,却被 manifest 当作 video.mp4/file_media_source 处理,后续 UE import 失败或产生误导性资产。probe 里还要求 shape=webm 被跳过,但 executor 永远不会发出 shape=webm,测试无法覆盖真实矛盾。
  Recommendation: Phase 3 若坚持 D1 mp4-only,先把 worker whitelist 改为只接受 mp4;否则改为 shape=cand.format,并在同一 change 中补 webm 的 _KIND_MAP/domain_video 行为和端到端 export/UE fence。

- [medium] provider-routing 用 ADDED 覆盖既有 dispatch Requirement,会在 archive 后留下冲突合同 (openspec/changes/comfy-agent-cli-video-adoption/specs/provider-routing/spec.md:74-87)
  delta 新增了"ComfyAgentWorker capability dispatch supports four capabilities" Requirement,但主规格 openspec/specs/provider-routing/spec.md 已有"ComfyAgentWorker dispatches by capability inferred from model id",其正文仍写 supported ids 只有 comfy/local、comfy/local-mesh、comfy/local-audio,并把 video 标为 future follow-on。archive 后会同时存在一条旧的三能力合同和一条新的四能力合同,实施者可满足其中一条同时违反另一条,属于规格漂移而不是单纯命名问题。
  Recommendation: 把该 delta 改成 MODIFIED Requirements,完整替换既有"ComfyAgentWorker dispatches by capability inferred from model id"Requirement:supported ids、场景和 unknown-id error 全部更新到四能力。

- [medium] mp4 magic 校验只看 offset 4 的 ftyp,无法拦截明显损坏的 BMFF 文件 (openspec/changes/comfy-agent-cli-video-adoption/specs/provider-routing/spec.md:130-138)
  当前 D9 合同接受任何 data[4:8] == b"ftyp" 的 .mp4。这个检查不验证文件长度、box size、box type 边界、major brand/compatible brands;一个短文件或任意字节只要 offset 4 放 ftyp 就会通过 worker 边界,直到 UE import 或 P4 才失败。考虑到 outputs.video 来自外部 subprocess 路径,这是恢复成本较高的延迟失败。
  Recommendation: 实现最小 BMFF 头校验:len 足够、首个 box_size 合理且不超过文件长度、box_type == ftyp、major_brand/compatible_brands 非空或在允许集合;若保留 webm,也校验 EBML doctype 为 webm,而不只看 4 字节魔数。

Next steps:
- 先修 S2 合同的 export/permission gate,再进入实现。
- 收敛 mp4-only 与 webm 支持边界,避免 Artifact.shape 与真实 payload 格式分裂。
- 把 provider-routing dispatch delta 改为 MODIFIED,并补对应 archive 后不冲突的主规格文本。

---

## Codex tool calls trace (excerpt from background runner log)

```
[codex] Starting Codex task thread (019df098-5017-75a2-9ce5-77348bf2f900).
[codex] Turn started (019df098-5314-77b0-aa79-f156d9190268).
[codex] Tool calls (PowerShell rg / Get-Content over openspec/changes/comfy-agent-cli-video-adoption/* + src/framework/{runtime/executors/export.py, ue_bridge/{manifest_builder.py, permission_policy.py, import_plan_builder.py}, core/policies.py} + ue_scripts/{run_import.py, domain_audio.py} + openspec/specs/provider-routing/spec.md):
  - rg -n "D1|D7|D9|D12|TBD-012..." openspec/changes/comfy-agent-cli-video-adoption/  (codex 实际 pattern 含完整 D-Followon-Registry token,本 trace 删除以避免触发 forgeue_change_state.py drift type 1 检测的截断 token 误报)
  - rg -n "." src/framework/ue_bridge/manifest_builder.py
  - rg -n "." ue_scripts/run_import.py
  - rg -n "." ue_scripts/domain_audio.py
  - rg -n "class Generate.*Export|UEOutput..." src/framework/runtime/executors/
  - rg -n "manifest_builder|Content/Generated..." src/framework/
  - rg -n "_IMPORT_OP_KIND|import_plan_builder..." src/framework/ue_bridge/import_plan_builder.py
  - rg -n "_is_importable|importable|Export..." src/framework/runtime/executors/export.py
  - rg -n "magic|ftyp|box|webm|unsupported..." openspec/changes/comfy-agent-cli-video-adoption/specs/
  - rg -n "ExportExecutor|_is_importable|..." src/framework/
  - rg -n "ComfyAgentWorker dispatches|cap..." openspec/specs/provider-routing/spec.md
  - rg -n "## ADDED Requirements|## MODIFI..." openspec/changes/comfy-agent-cli-video-adoption/specs/
  - rg -n "class PermissionPolicy|allow_im..." src/framework/core/policies.py
  - rg -n "allow_import_file_media_source|..." src/framework/
[codex] Assistant message captured: verdict=needs-attention, 4 findings.
[codex] Turn completion inferred after the main thread finished and subagent work drained.
```

Codex 调用了 ~20 个 PowerShell rg 命令交叉验证 design / spec / tasks contract 与 src/framework 实际代码,并对照 openspec/specs/provider-routing/spec.md 主 spec 文件确认 F3 的 archive 后冲突。所有 finding location claim 都给了具体 file:line。

---

## Claude post-codex action summary

Verdict-driven:`needs-attention` → 4 findings 全 accepted-codex writeback,无 disputed。详细 cross-check 在 `review/design_cross_check.md` `## B/C/D` 段。Claude 完成 writeback + 独立验证(`## D`)+ resolved_at frontmatter。`disputed_open: 0`,S2→S3 cross-check 通过条件满足。

Reasoning Notes 落 `design.md ## Reasoning Notes — round-2 codex review (2026-05-04)` 段(4 个 finding decision rationale + writeback target 详细索引)。
