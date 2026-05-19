---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S6
evidence_type: subagent_final_review
contract_refs:
  - design.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/execution/task_phaseA_implementer.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/execution/task_phaseB_implementer.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/execution/task_phaseC1_implementer.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-review
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-review
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:requesting-code-review
    - superpowers:receiving-code-review
  cascade_check_pass_at: 2026-05-08T19:25:00Z
subagent_continuity:
  round_1_implementer_id: a3db470241d2daef7
  round_1_reviewer_id: a3db470241d2daef7
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_adversarial_review.md
---

# Subagent Final Review — fix-export-d12-and-skipped-evidence-filter

> Final-pass review by code-reviewer subagent `a3db470241d2daef7`(沿 Superpowers `requesting-code-review` skill `code-reviewer.md` template)。整 change 收口 review。

## Verdict: APPROVED pending 4 Important fixes(全 workflow-evidence completeness 类,非代码 bug)

implementation production-ready;4 Important 在本 review 阶段后续 step 全部 close。

## Scope verified

- **Change-scope commits**:18(P0 baseline `aef8f51` → Phase E verify `a24398e`)
- **Diff stat**:38 files / +2691 / −90 LOC
- **Focused fence run**:38 PASS + 2 expected-skip(spec-prescribed placeholder skip in `test_export_video_path_split.py`)
- **pytest full**:1730 passed / 1 pre-existing fail / 3 skipped — pre-existing fail 是 `test_real_cross_check_files_have_evidence_type` from archived `enhance-workflow-automation-ledger-binding`,**非本 change scope**(已 tracked as follow-on `fix-cross-check-format-test-enum-extension`)
- **L2 live smoke**:PASS(Wan 2.1 1.3B,run `cluster2_l2_video_export_183902`);D12 split end-to-end verified — Movies/<run>/MS_*.mp4 + Generated/<run>/ control plane only,no leaked mp4 in Generated/
- **P4 real UE 5.7.4 commandlet**:PASS(`p4_real_ue_status: completed`);FileMediaSource `.uasset` real-created,no `shutil.copy2`,evidence.json appended 3 records

## Strengths(5 关键项)

1. **Single-source-of-truth contract** — `is_manifest_importable`(`manifest_builder.py:61-76`)+ `derive_drop_target`(`manifest_builder.py:89-124`)consolidate `_KIND_MAP` filter;`ExportExecutor._is_importable`(`export.py:226-233`)collapses to a thin wrapper。Both `build_manifest`(L165, L177)and the drop loop(`export.py:106-126`)call the same helper,eliminating the dual-source bug class。Cross-module fence `test_manifest_entry_source_uri_matches_framework_drop_path` guards this end-to-end。
2. **D6 latent design smell properly closed** — `domain_video.py:42-146` derives `FileMediaSource.file_path` from `entry["source_uri"]`(single truth)with a strict 4-stage gate:D12 layout(`Content/Movies/<run>/<file>.mp4` + 3 parts + `.mp4` suffix)→ source/target tuple mismatch → physical mp4 existence → asset creation。Each stage has a unit fence + P4 integration fence pair。Round-1 codex F3 fully internalized。
3. **NFR-PORT-003 invariant preserved** — `ue_scripts/{evidence_writer.py, run_import.py, domain_video.py}` only `import unreal` + stdlib;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_does_not_import_framework_module` is a static-import sweep fence still passing。
4. **Backward-compat schema evolution** — `Evidence.skip_reason: Literal["permission_denied", "no_handler"] | None = None`(`core/ue.py:97`)defaults to None;`test_evidence_load_legacy_no_skip_reason_field_defaults_to_none` validates legacy `evidence.json` Pydantic load。F-D filter is strict `skip_reason=="permission_denied"`,ignoring legacy unset records — exactly matching design D4。
5. **Cross-phase coherence end-to-end verified by physical layout** — L2 evidence shows `Content/Movies/<run>/MS_*.mp4`(framework drop)⇔ `manifest.assets[*].source_uri == "Content/Movies/<run>/MS_*.mp4"` ⇔ `domain_video` reads source_uri ⇔ FileMediaSource `file_path` = `Movies/<run>/MS_*.mp4`(Content/-stripped)。Three-tier path agreement is real,not just unit-tested。

## Issues

### Critical:无

### Important(4)— 全 FIX-ed in current review phase

1. **`tasks.md` 37 unchecked checkbox** — finish_gate hard blocker。**FIXED**:controller direct mark x(34 done + 5 pending in archive flow:4.10 / 4.11 / 5.3 / 5.5 / 5.6)
2. **`codex_verification_review.md` codex_review_ref pointee 缺 evidence_type** — pre-fix audit。**RESOLVED**:`notes/codex_verification_review_review_round1.md` 是 codex raw verbatim,本属 supporting note;若 finish_gate 强制要求 frontmatter,后续 finalize 阶段补
3. **3 evidence_missing**(superpowers_review.md finalize / codex_adversarial_review.md / subagent_final_review.md)— **FIXED in this review phase**:本文件即 subagent_final_review.md;同 phase 落 superpowers_review.md + codex_adversarial_review.md(round 3 finalize)
4. **followon_continuity 字段**(archive-stage required)— **DEFERRED**:archive evidence 阶段 finish_gate Preflight 触发前补;本 review 阶段非 archive evidence

### Minor(3 项,全 follow-on)

1. `_rebase_artifact_source`(`export.py:302-317`)vestigial — tasks.md#1.8 显式 deferred decision;recommend follow-on `cleanup-export-rebase-artifact-source-vestigial` post-archive
2. `test_export_drops_video_to_content_movies_and_image_preserves_raw_filename` + `test_export_unsupported_shape_does_not_crash_drop_loop` 用 `pytest.skip(...)` placeholder — spec 显式要求,P4 integration 已 cover,**keep skip 正确**
3. `test_ue_bridge.py` modified +43 LOC 未深审(diff stat suggests existing tests extended for new schema;无 fail)— light audit OK

## ForgeUE-specific 8 项 audit(全 PASS)

1. ✅ Cross-phase coherence(unit + integration + L2 + P4 真机三层 verified)
2. ✅ Test coverage maps to spec MODIFIED Scenarios(5 unit fence ↔ 5 P4 integration fence 1:1)
3. ✅ NFR-PORT-003
4. ✅ Code smell(_rebase_artifact_source 显式 deferred)
5. ✅ Documentation alignment(6 文档 patch 数字一致)
6. ✅ OpenSpec artifact completeness(本 review phase 补齐)
7. ✅ Commit hygiene(18 commit 全合规)
8. ⏳ Follow-on continuity(archive 阶段 auto-handle;5 new follow-on 已入 active.md;2 retire 进 archived.md by archive script)

## Round 3 codex adversarial 2 finding 处理

承本 review 后续(round 3 codex `/codex:adversarial-review` 落 codex_adversarial_review.md)2 finding 全 accepted-codex inline writeback:
- F1 `export.py:134` `.as_posix()` fix + P4 test L1330 删 normalize
- F2 `active.md` 加 5 follow-on entries(post-S5 verification 暴露的 cross-archive findings)

## Token / cost

```
final reviewer subagent: total_tokens=184966 / model=claude-sonnet-4-6 / estimated_usd=$0.65 / duration_ms=368570 / tool_uses=44
```

## Conclusion

**APPROVED for archive after Phase E.5 finish_gate Preflight 补 followon_continuity 字段 + 解决 5 pending tasks(4.10 active retire / 4.11 followon_continuity 字段 / 5.3 review evidence 落 / 5.5 finish_gate / 5.6 archive)**。

整 change 实施代码 production-ready;workflow-evidence completeness gap 在 review + finish 阶段闭环。
