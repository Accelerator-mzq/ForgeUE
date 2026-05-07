---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md
  - design.md
  - proposal.md
  - specs/ue-export-bridge/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-07T19:30:00Z
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-07T18:25:00Z
---

# fix-export-d12-and-skipped-evidence-filter Implementation Plan

> **For agentic workers**: REQUIRED SUB-SKILL: Use **`superpowers:subagent-driven-development`**(沿 ForgeUE 工作流 + memory `feedback_self_reference_overcaution.md` — 触及 framework 代码 + 多文件协调 + ~40 micro-task,非 trivial scope,subagent dispatch 标准路径)。Steps 用 checkbox(`- [ ]`)语法跟踪。详 `## Execution Mode` 段。

**Goal**: 修两个 pre-existing branch-work bug(F3+F4 from archived `2026-05-06-retire-parallel-and-worktree-fully` codex review)— F-C framework export 端违 D12 video mp4 路径分流 + F-D UE 端 run_import skipped 过滤过宽。两 bug 通过 `evidence.json` + `manifest.json` 接口耦合,合并 single change 处理 schema 演进(`Evidence.skip_reason` 字段)+ derive_drop_target helper 单源 + domain_video file_path 派生协议修订(round 1 codex F3)。

**Architecture**:
- 新增 `manifest_builder` 2 public helper:`is_manifest_importable(art) -> bool`(_KIND_MAP 单一真源,沿 D10)+ `derive_drop_target(art, *, target, run_id) -> tuple[Path, str]`(D12 路径分流 + UE naming for video,raw basename for non-video)
- `ExportExecutor._is_importable` 收敛到 `is_manifest_importable`(消除双源)
- `Evidence.skip_reason: Literal["permission_denied", "no_handler"] | None = None` schema 扩展(向后兼容)
- `evidence_writer.make_record` 加 optional kwarg + `run_import.py` filter 改 `skip_reason=="permission_denied"` 三 AND 条件
- `domain_video.import_video_entry` 删 copy/mkdir + file_path 从 source_uri 派生(沿 D6 修订)+ mismatch fence
- 6 类 unit fence test 覆盖 round 1 codex 4 finding + integration P4 fence + L2 live smoke

**Tech Stack**: Python 3.12+ stdlib(`pathlib`,`shutil`,`typing.Literal`)+ Pydantic + pytest + 既有 ForgeUE evidence/manifest framework。无新依赖。

---

## Phase Map(沿 tasks.md Phase A-E)

| Phase | tasks.md anchor | Scope | Dependency | Estimated micro-tasks | Subagent dispatch type |
|---|---|---|---|---|---|
| **A** | tasks.md#1 | F-C framework schema + drop loop(`core/ue.py` + `manifest_builder.py` + `runtime/executors/export.py`)+ unit fence | — | 12 | Implementation type 1(framework code 改)|
| **B** | tasks.md#2 | F-D UE 端 filter + simplify(`evidence_writer.py` + `run_import.py` + `domain_video.py`)+ unit fence | A | 9 | Implementation type 1(UE-side stdlib + stub-unreal 测试)|
| **C** | tasks.md#3 | Integration test 修订 + L2 live smoke(`test_p4_ue_manifest_only.py` + `comfy_local_smoke_video.json`)| B | 5 | Implementation type 4(integration)+ user-loop L2(用户开 ComfyUI 终端)|
| **D** | tasks.md#4 | Doc sync gate(10 文档静态扫 + active.md retire + tombstone)| C | 11 | Doc-sync subagent(non-implementation)|
| **E** | tasks.md#5 | Verify L0/L1/L2 + codex `/codex:review --base main` verification hook + change-review + change-finish | D | 6 | Verification + review hook(主 controller 触发)|

**Total estimated micro-tasks**: ~43

---

## Files Touched

### Framework code(本 change scope)

- **Create**: 无新文件
- **Modify**:
  - `src/framework/core/ue.py:86-97`(`Evidence` 加 `skip_reason` field)
  - `src/framework/ue_bridge/manifest_builder.py`(加 `is_manifest_importable` + `derive_drop_target` 2 public helper;`build_manifest` filter consolidate + source_uri 计算改)
  - `src/framework/runtime/executors/export.py:212-220`(`_is_importable` 收敛 `is_manifest_importable`)+ L91-125(drop loop 用 `derive_drop_target`)+ L149-158(permission denied evidence 加 skip_reason)
  - `ue_scripts/evidence_writer.py`(`make_record` 加 optional kwarg `skip_reason`)
  - `ue_scripts/run_import.py:67-73`(filter 改三 AND)+ L89-92(no-handler skipped 带 skip_reason)
  - `ue_scripts/domain_video.py:42-95`(删 copy + 删 mkdir + 加 source_uri 派生 + 加 mismatch fence)

### Tests(新增 + 修改)

- **Create**:
  - `tests/unit/test_export_video_path_split.py`(6 case;tasks.md#1.9)
  - `tests/unit/test_evidence_skip_reason.py`(3 case;tasks.md#1.10)
  - `tests/unit/test_run_import_skipped_filter.py`(2 case;tasks.md#2.5)
  - `tests/unit/test_evidence_writer_skip_reason.py`(2 case;tasks.md#2.6)
  - `tests/unit/test_domain_video_no_copy.py`(5 case;tasks.md#2.7)
- **Modify**:
  - `tests/integration/test_p4_ue_manifest_only.py`(既有 `test_p4_domain_video_*` 重命名 + 加 3 新 case;tasks.md#3.1)

### Doc sync(Phase D)

- `docs/design/LLD.md`(Evidence schema 段 + ExportExecutor + manifest_builder D12 段)
- `docs/design/HLD.md`(UE Export Bridge 章节)
- `docs/testing/test_spec.md`(新 fence 索引)
- `docs/acceptance/acceptance_report.md`(若有 video FR/NFR 状态变化)
- `README.md`(可能不需要)
- `CHANGELOG.md`(本 change 条目)
- `CLAUDE.md`(ComfyUI 接入段 video 路径表述)
- `AGENTS.md`(若有 mentions of `Content/Generated/` video 路径)
- `openspec/specs/ue-export-bridge/spec.md`(P10 archive 后 sync delta 进 main spec)
- `openspec/backlog/active.md`(retire 2 active follow-on)+ `archived.md`(2 tombstone)

---

## Execution Mode(subagent-driven dispatch policy)

按 `superpowers:subagent-driven-development` 协议:每 phase 内的实施 subtasks 派 implementer subagent;每个 implementer 完成后 spec_review subagent + code_quality_review subagent 双 review;final_review subagent 收口。

**Phase A / B / C 走 implementer subagent dispatch**(framework + UE-side code);**Phase D / E 主 controller 触发**(doc sync 涉及 cross-file 文档,doc-sync subagent 一次性扫;Phase E 是 controller 触发命令链不需 implementer)。

详 `micro_tasks.md` 内每个 micro-task 标 `Owner: <subagent | controller>` + `Type: <implementation_type_1-5 | doc-sync | verification>`。

---

## Risks Pre-implementation

| Risk | Phase | Mitigation |
|---|---|---|
| `derive_drop_target` 双源不一致(framework drop 路径 ≠ manifest source_uri)| A | manifest_builder + export.py 共调同函数;加 `test_manifest_entry_source_uri_matches_framework_drop_path` fence(tasks.md#1.9)|
| Evidence schema 字段破坏旧 fixture Pydantic load | A | `skip_reason: ... \| None = None` default + fence `test_evidence_load_legacy_no_skip_reason_field_defaults_to_none`(tasks.md#1.10)|
| domain_video file_path 派生协议修订 + mismatch fence 引入新 failed 路径 | B | 新 fence 4 case(`tests/unit/test_domain_video_no_copy.py`;tasks.md#2.7);P4 integration test 同步加 case(tasks.md#3.1)|
| video L2 live smoke 回归(模型 ~3GB / 单次 ~7 分钟)| C | L2 在 P5 verify 阶段一次跑;若回归 fail-fast 到 design 重审(沿 design.md Risks 行)|
| unsupported shape `video.webm` 在新 derive_drop_target 路径 crash export | A | round 1 codex F1 已 inline writeback fix(D10 _is_importable 收敛 _KIND_MAP);加 fence `test_export_unsupported_shape_does_not_crash_drop_loop`(tasks.md#1.9)|
| 非 video modality filename collision(同 display_name 双 artifact)| A | round 1 codex F2 已 inline writeback fix(D1 修订非 video 保 raw basename);加 fence `test_derive_drop_target_preserves_raw_filename_for_non_video`(tasks.md#1.9)|

---

## Acceptance Criteria

- [ ] tasks.md 1.1-1.10 全 pass(Phase A unit fence)
- [ ] tasks.md 2.1-2.7 全 pass(Phase B UE-side fence)
- [ ] tasks.md 3.1 integration test pass(`test_p4_ue_manifest_only.py` 新 + 修订 case)
- [ ] tasks.md 3.2 L2 live smoke 实证 framework drop 后 mp4 在 `Content/Movies/<run_id>/MS_<base>.mp4` + `.uasset` 在 `Content/Generated/<run_id>/MS_<base>.uasset` + `Content/Generated/<run_id>/` 下不再有 raw `.mp4` 垃圾
- [ ] `python -m pytest -q` 1576 → ~1594(新 18 fence case 增加;无回归)
- [ ] tasks.md 4.1-4.11 doc sync 全 pass(`forgeue_doc_sync_check.py --change` exit 0)
- [ ] `forgeue_finish_gate` 全 pass(evidence 完整性 + frontmatter 全检 + cross-check disputed_open=0 + writeback 真实性 + tasks 全 checked + `openspec validate --strict` + 4 类 v1 advisory fence + followon_continuity)
- [ ] active.md 2 entries 迁 archived.md(`fix-video-export-path-split-d12-violation` + `fix-run-import-skipped-filter-permission-only` 标 `cancelled-completed: <commit-ref>`)

---

## Self-Review

- [x] **Spec coverage**:specs/ue-export-bridge/spec.md 5 Requirements(2 ADDED:`is_manifest_importable` + `derive_drop_target`;3 修订:domain_video file_path / Evidence skip_reason / Permission tiers)全部对应 tasks.md Phase A/B 实施 micro-task。
- [x] **Placeholder scan**:无 TBD / TODO / "implement later"。
- [x] **Type consistency**:`Evidence.skip_reason: Literal["permission_denied", "no_handler"] | None = None` 在 spec / design / tasks 三处一致;`derive_drop_target(art, *, target: UEOutputTarget, run_id: str) -> tuple[Path, str]` 签名一致。
- [x] **F1-F4 round 1 codex 4 finding 全 inline writeback**:design D1/D2/D6 修订 + 新 D10;spec ADDED `is_manifest_importable` + ADDED `derive_drop_target` + MODIFIED domain_video;tasks 1.2/1.3/1.5/1.9/2.4/2.7 加 fence;cross-check disputed_open=0。
