---
change_id: retire-parallel-and-worktree-fully
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - design.md#decisions
  - tools/forgeue_finish_gate.py
  - .claude/commands/forgeue/change-apply-subagent.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-verify retire-parallel-and-worktree-fully
codex_plugin_available: true
codex_session_id: 019dfd70-e964-7c80-99bc-76204bdf9621
codex_job_id: review-mou32cf3-nofa0x
verdict: needs-attention
findings_count: 4
findings_severity:
  high: 1
  medium: 2
  low: 1
disputed_open: 0
runtime_enforcement_protocol_version: v1
review_type: codex_mixed_scope_review
review_round: 1
created_at: 2026-05-06T13:50:00Z
resolved_at: 2026-05-06T13:55:00Z
resolution_summary: 4 finding 中 F1+F2 在本 retire change scope 内,accepted-codex inline writeback 修复 change-apply-subagent.md 模板;F3+F4 是 pre-existing branch work(`5d81f13` video modality sweep + `f9fdf5e` ue_scripts domain_video),非 retire scope,标 out-of-retire-scope follow-on backlog。
---

# Codex Review — retire-parallel-and-worktree-fully (S5 verification,branch diff vs main)

Target: branch diff against main(692 files,108k insertions vs main)
Verdict: **needs-attention**(4 finding;2 in-retire-scope + 2 out-of-retire-scope)

存在会绕过 drift 门禁的模板枚举错误,以及 video 导出路径分流和 evidence 模板解析不一致等问题。它们会影响工作流门禁或新增 video 资产链路的正确性。

## Findings 摘要 + 4 row independent file:line verify

| F# | severity | claim | file:line | retire scope? | resolution |
|----|----------|-------|-----------|---------------|---|
| F1 | P1(high) | 模板含 `unresolved-permanent-drift` 让未解决 drift 绕过 archive gate | `.claude/commands/forgeue/change-apply-subagent.md:135` | ✅ in-scope(本 change P4 rewrite 引入) | accepted-codex → 改为 `disputed-permanent-drift`(finish_gate `_check_disputed_drift_*` 识别值) |
| F2 | P2(medium) | 模板用 YAML flow-style `[...]`,`_common.parse_frontmatter()` 不解析 → fence 当成 string fail | `.claude/commands/forgeue/change-apply-subagent.md:129, 143` | ✅ in-scope(本 change P4 rewrite 引入) | accepted-codex → 改为 block-list YAML 形式 |
| F3 | P2(medium) | video 加进通用 importable whitelist 后 drop loop 把 mp4 复制到 Generated/(违 D12 mp4 在 Movies、.uasset 在 Generated 路径分流) | `src/framework/runtime/executors/export.py:219` | ❌ **out-of-retire-scope**(pre-existing `5d81f13` "feat(export): sweep video modality through 4 export gates")| accepted-codex 但 NOT 在本 retire change 修;follow-on backlog `fix-video-export-path-split-d12-violation` |
| F4 | P3(low) | run_import.py 把所有 `status="skipped"` 当 PermissionPolicy deny;旧版 UE 脚本 `no UE-side handler` 等非权限 skipped 也会被静默跳过 | `ue_scripts/run_import.py:69-70` | ❌ **out-of-retire-scope**(pre-existing `f9fdf5e` "feat(ue-scripts): add domain_video.import_video_entry") | accepted-codex 但 NOT 在本 retire change 修;follow-on backlog `fix-run-import-skipped-filter-permission-only` |

## In-Retire-Scope Resolution(F1 + F2)

### F1 fix:`unresolved-permanent-drift` → `disputed-permanent-drift`

`tools/forgeue_finish_gate.py` 内 evidence frontmatter `drift_decision` enum 校验值是:
- `null` / `pending` / `written-back-to-<artifact>` / `disputed-permanent-drift`(沿 design.md §3 writeback 协议三态 + permanent drift)

`unresolved-permanent-drift` 不在 enum 内,finish_gate 对该值 silent pass(无 BLOCKER + 无 fence 校验 reason / anchor)→ 让未解决 drift 绕过 archive gate。

**Fix**:`change-apply-subagent.md:135` 模板枚举值 + `136` writeback_commit 描述同步改用 `disputed-permanent-drift`。

### F2 fix:YAML flow-style → block-list

`tools/_common.py::parse_frontmatter()` 实测仅支持 block-list YAML(每行 `- item`),不支持 flow-list(`[a, b, c]`)。`finish_gate._frontmatter_key_present()` + `_check_skill_cascade()` 都要求 list 类型,flow-list 在 parse 后是 string → fence fail。

**Fix**:`change-apply-subagent.md` 模板内 `contract_refs: [...]` + `invoked_skills: [...]` 改为 block-list 形式:

```yaml
contract_refs:
  - openspec/changes/<id>/tasks.md#X.Y
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
```

## Out-of-Retire-Scope Findings(F3 + F4)

**Why out-of-scope**:本 change `retire-parallel-and-worktree-fully` scope 是 retire ADR-011/012/013 + ledger-binding(worktree / parallel dispatch / dispatch ledger / sister skill 强制层);F3 + F4 涉及的 `src/framework/runtime/executors/export.py` + `ue_scripts/run_import.py` 是 pre-existing branch work(video modality sweep + ue_scripts domain_video,`5d81f13` + `f9fdf5e`),与 retire 协议层无关。

**Decision**:Document 为 follow-on backlog,**不**在本 retire change 内修复(沿 ForgeUE memory `feedback_partial_vs_whole_retire_audit` — 严控 retire scope 边界):

| Follow-on backlog | Source finding | Description |
|-------------------|----------------|---|
| `fix-video-export-path-split-d12-violation` | F3 | export.py 视频 modality drop loop + domain_video 路径分流冲突;违 D12 "mp4 Movies + .uasset Generated"路径协议 |
| `fix-run-import-skipped-filter-permission-only` | F4 | run_import.py 过滤 skipped op 须按错误前缀/来源,仅 honor 框架侧 PermissionPolicy 产生的 skipped |

User 可基于 follow-on backlog 走独立 change(`/opsx:propose <follow-on-id>`)处理,不阻断本 retire change archive。

## Cross-check disposition

`disputed_open: 0`(全 4 finding accepted-codex)。

In-scope F1 + F2 inline writeback 已 fix(commit 待 P5.5 包含)。
Out-of-scope F3 + F4 标 backlog 不修(follow-on change scope)。

无遗留 dispute 需要 round 2 challenge。

## Verification status

- ✅ codex S5 verification review hook done(`/codex:review --base main` job `review-mou32cf3-nofa0x`)
- ✅ Single-direction code review(沿 backbone skill `forgeue-integrated-change-workflow` codex stage hook 表;S5 verification 无 cross-check 强制)
- ✅ `disputed_open: 0` + `resolved_at` filled
- ✅ retire-scope findings(F1 + F2)inline writeback fix
- ✅ out-of-retire-scope findings(F3 + F4)标 follow-on backlog,不阻断本 retire change archive
