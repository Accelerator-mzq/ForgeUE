---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S2
evidence_type: codex_design_review
contract_refs:
  - design.md
  - proposal.md
  - specs/ue-export-bridge/spec.md
aligned_with_contract: false
drift_decision: written-back-to-design
writeback_commit: efd2129de71c9e9f82b738d90de43373aeff4d31
drift_reason: S2 design stage round 1 codex adversarial review 4 finding(3 high F1+F2+F3 + 1 medium F4)全 accepted-codex inline writeback;F1+F2 揭示 _KIND_MAP miss + 非 video filename ue_name silent change(超 NG1);F3 暴露 latent design smell(domain_video 验证 source_uri / 引用 target_object_path 反推);F4 helper API signature naming_policy oversight。详见 review/design_cross_check.md ## B/C/D 与 notes/codex_adversarial_review_review_round1.md(verbatim)。
reasoning_notes_anchor: review/design_cross_check.md#round-summary
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
codex_session_id: 019e02f8-7c16-7c72-a3f8-5f08d46a0d68
codex_job_id: be6046t7v
created_at: 2026-05-07T18:35:00Z
runtime_enforcement_protocol_version: v1
---

# Codex Design Review — S2 stage consolidated stub

> 沿 ForgeUE protocol — S2 design review 走 codex `/codex:adversarial-review` hook;round 1 verbatim output 落 `notes/codex_adversarial_review_review_round1.md`(沿 codex command spec round counter 协议)。本文件为 S2 stage 收口 stub,disposition + Resolution 落 `review/design_cross_check.md`。

## Round Summary

| Round | Thread ID | Verdict | Findings | Disposition |
|---|---|---|---|---|
| 1 | `019e02f8-7c16-7c72-a3f8-5f08d46a0d68` | needs-attention | 4(3 P1 high + 1 P2 medium)| accepted-codex 全部 — inline writeback 修 design.md(D1+D2+D6+新 D10)+ specs/ue-export-bridge/spec.md ADDED #1 / MODIFIED domain_video + tasks.md 加 4 fence |

## Findings(高层指针)

- **F1 [P1]** `_KIND_MAP` miss 静默 skip → derive_drop_target raise ValueError → export crash(`spec.md:7-10`)
- **F2 [P1]** 非 video modality filename 改为 ue_name 是 NG1 超范围 silent change + collision 风险(`spec.md:9-14`)
- **F3 [P1]** 删 copy 后 domain_video 验证 source_uri 但 file_path 用 target_object_path 反推,二者 mismatch 时 success 但 .uasset 引用错(`spec.md:103-108`)
- **F4 [P2]** derive_drop_target API 缺 naming_policy 输入(`design.md:119-138`)

完整 finding 内容 + Recommendation + reproducibility 见 `notes/codex_adversarial_review_review_round1.md`(verbatim)。
独立 file:line verification + B/C/D Resolution 见 `review/design_cross_check.md`(`## B/C/D` 段)。
