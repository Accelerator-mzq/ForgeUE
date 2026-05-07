---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S4-S5
evidence_type: subagent_code_quality_review
contract_refs:
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/tasks.md#1
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/execution/task_phaseA_implementer.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/execution/task_phaseA_spec_review.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
  cascade_check_pass_at: 2026-05-07T19:48:00Z
subagent_continuity:
  round_1_implementer_id: ad8230d84dc2f7778
  round_1_reviewer_id: a712bf08067576968
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
---

# Phase A — Code Quality Review

> Subagent dispatch report for Phase A code quality review。General-purpose subagent a712bf08067576968;返 **Approved with minor follow-ups**;2 个 Important hygiene 由 controller direct fix(trivial scope)。

## Verdict: Approved with minor follow-ups

Phase A 5 commit(`aef8f51..c06f58b`)well-scoped + well-tested + faithful to design;2 个 Important hygiene 问题 trivial,controller direct fix。

## Strengths(8 项)

1. **D10 单源契约清洁实现** — `is_manifest_importable` 一线收敛 + ExportExecutor._is_importable defer 单 import,无 duplication
2. **Defensive fall-through 守门** — `derive_drop_target` `_KIND_MAP` miss 不 raise + comment 显式 cite codex F1;fence test 覆盖
3. **D12 路径分流正确** — `kind=='file_media_source' AND modality=='video'` double-guard;non-video raw basename
4. **单源契约 framework drop ↔ manifest** — `test_manifest_entry_source_uri_matches_framework_drop_path` invariant 守门
5. **Pydantic Evidence 后向兼容** — default None + 4 fence case 全方位覆盖
6. **Commit hygiene** — 5 commit 全含 `Tasks: tasks.md#X.Y` + `Co-Authored-By` + scope 边界清晰 + 引用 codex round/finding
7. **中文注释 placement** — 每 design decision inline comment cite design number(D1/D3/D10)+ round reference
8. **Test naming self-describing** — fence test 名含期望 outcome

## Issues

### Critical:无

### Important(2)

1. **Dead code in `build_manifest`** — `manifest_builder.py:152` `errors: list[str] = []` + L201-202 `if errors: raise ManifestBuildError(...)` A.4 收敛后已 unreachable;`ManifestBuildError` 类(L130 定义)永不 raise 是真实 semantic shift,应该清理或加 reserved-for-future comment
2. **Unused import `PurePosixPath`** — `manifest_builder.py:30` 唯一调用点 A.4 替换为 `as_posix()` on `Path`,unused

### Minor(4)

1. Local import inside loop(`export.py:106` + `export.py:232`)— Python 模块缓存,cost 可忽略;trade-off 防 circular import,不必 fix
2. **`_rebase_artifact_source` 现 vestigial** — A.4 后 `build_manifest` 不再依赖 rebase artifact 的 source path;video 路径 rebase 输出 `Generated/<run>/<basename>.mp4` 与实际 drop `Movies/<run>/MS_<base>.mp4` 不一致(对 UE-side 不可见 — UE 读 manifest source_uri 而非 payload_ref;但 code-reading hazard);留 follow-on
3. **Test placeholder skip** — Phase A unit-level OK;Phase B / D 添加 integration fixture 取代;非阻塞
4. **`/tmp/x.png` default in `_mkart`** — fixture label only,never resolved against fs;harmless

## Controller-Applied Hygiene Cleanup(Important #1+#2)

按 reviewer recommendation,2 个 Important 问题由 controller direct fix(沿 memory `feedback_dont_punt_executable_tasks` — trivial scope cleanup,无设计判断,subagent dispatch 成本不合理):

- 删 `manifest_builder.py:152` `errors: list[str] = []`
- 删 `manifest_builder.py:201-202` `if errors: raise ManifestBuildError(...)`
- 决策保留 `ManifestBuildError` 类(public API symbol,reserve for future structural errors;加 reserved comment)
- 删 unused `PurePosixPath` import(`manifest_builder.py:30`)
- 重跑 fence test 期望 35 PASS + 2 skip(无回归)
- commit `chore(forgeue): A.6 manifest_builder hygiene cleanup`

详细 commit hash + 重跑结果在 implementer evidence A.6 段补 update。

## ForgeUE-specific notes

- Single-responsibility ✅:`manifest_builder.py` 3 cohesive helper(filter / path / orchestrator);`Evidence` 纯 schema container;`ExportExecutor` drop loop 线性可读
- 文件大小:`manifest_builder.py` ~296 lines after Phase A,not large
- 无新依赖:仅 reuse `pathlib.Path` + `pydantic.Literal`
- Commit scoping:A.1→A.5 each independently buildable + testable

## Phase A → Phase B 推进建议

Approved。在 controller cleanup commit 后(预期 `chore(forgeue): A.6 manifest_builder hygiene cleanup`)进 Phase B(F-D UE-side filter + simplify;tasks.md#2.1-2.7;包含 Phase A→B transitional fail 修复 path)。

## Token usage

```
input_tokens=73000 (estimated split)
output_tokens=14711 (estimated split)
total_tokens=87711 (Agent tool return — actual)
model=claude-sonnet-4-6
estimated_usd=$0.27
data_source=Agent tool total_tokens (input/output split estimated, not gate-grade)
duration_ms=121534 (2 min 1 sec)
tool_uses=17
```
