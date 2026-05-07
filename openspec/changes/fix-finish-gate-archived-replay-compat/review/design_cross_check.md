---
change_id: fix-finish-gate-archived-replay-compat
stage: S2
evidence_type: design_cross_check
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/specs/examples-and-acceptance/spec.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/execution/execution_plan.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/execution/micro_tasks.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan fix-finish-gate-archived-replay-compat
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-plan
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-06T00:00:00Z
task_granularity: phase
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-06T00:00:00Z
---

# Design Cross-check — fix-finish-gate-archived-replay-compat (S2 plan stage)

> **协议自我保护**:本 `## A. Decision Summary` 段 SHALL 在调用 codex `/codex:adversarial-review` **之前**完成,锁定 Claude 立场。codex review 输出后再写 `## B / C / D`(逐 finding 对照 + disputed_open + 独立验证 file:line)。

---

## A. Decision Summary(Claude 立场,冻结于 codex 调用前)

### A.1 本 change 范围

- **In-scope modules**:`tools/forgeue_finish_gate.py` 单文件 2 处改动 + `tests/unit/test_forgeue_finish_gate.py` 加 7 case + `CHANGELOG.md` `[Unreleased]` Fixed 1 条。
- **Out-of-scope**:其他 `tools/*` / `src/framework/**` / `docs/` 五件套 / `openspec/specs/examples-and-acceptance/spec.md` active baseline / 其他 active change(沿 design.md Non-Goals)。

### A.2 3 D-decision 立场(Claude approve)

| D-decision | Claude 立场 | 关键 rationale |
|------------|------------|----------------|
| **D-RegexExtension** | `r"^##\s+P?(\d+)(?:\.|\s+—)\s+"` 单 regex 双格式 | 单 regex 简洁;`P?` optional 不破 active backward-compat;`(?:\.|\s+—)` non-capturing alternation 显式两选一,避免 over-permissive(如 `\W+` 通吃);capture group 永远 integer。Alternatives A/B/C 均拒绝(详 design.md)。 |
| **D-OpenSpecValidateArchiveSkip** | archive/ 路径下 skip subprocess + 写 rationale warning(**非** BLOCKER) | upstream openspec CLI 不感知 archive/ 路径 = 强制 invoke 必 fail = 噪声非真实违规;skip + warning 保留 audit trail;长期方案给上游 CLI 提 PR 留 follow-on `enhance-openspec-cli-archived-change-support`。Alternatives A/B/C/D 均拒绝(详 design.md)。 |
| **D-DispatchPathDetection** | `"archive" in Path(change_dir).parts` segment exact match | OS-aware tuple split 跨 Windows/POSIX 稳定;不 false-positive 命中 active change 名含 `archive` 子串(如假想 `add-archive-feature`);invariant 稳定性高于 `change_dir.parent.name == "archive"`。Alternatives A/B 均拒绝。 |

### A.3 Spec scenario 7 项立场

specs.md 7 scenario(`examples-and-acceptance` capability ADDED Requirements)由 Claude 立场视角:

| # | Scenario | Claude 期望行为 | 守门 case |
|---|----------|----------------|----------|
| 1 | active `## <int>. <text>` 仍命中 | regex superset 不破 baseline | `test_check_tasks_unchecked_p_prefix_optional_active_format_unchanged` |
| 2 | archived `## P<N> — <text>` 命中 | 双格式核心目标 | `test_check_tasks_unchecked_recognizes_p_prefixed_em_dash` |
| 3 | 假阴性 `## 1.5 sub-section` 不命中 | YAGNI 边界守门 | `test_check_tasks_unchecked_yagni_decimal_subsection_not_matched` |
| 4 | 假阴性 `## PX — title` 不命中 | `\d+` 至少 1 位 | `test_check_tasks_unchecked_p_non_digit_not_matched` |
| 5 | active 路径仍 invoke openspec validate | backward-compat 守门 | `test_finish_gate_invokes_openspec_validate_for_active_path` |
| 6 | archive 路径 skip + warning rationale | 核心目标 | `test_finish_gate_skips_openspec_validate_for_archive_path` |
| 7 | Path.parts 检测稳定性 | 防 false-positive 子串 | `test_archive_segment_detection_uses_path_parts_not_substring` |

### A.4 实施风险 Claude 已识别

(沿 design.md Risks/Trade-offs 表 5 条):

1. Regex corner-case 误报 → 7 case 守门,2 既有 baseline 不动
2. archive skip 掩盖 archived spec 真实损坏 → archived 是 frozen 状态损坏概率低;rationale warning 保留 audit trail
3. 双 regex 未来需扩第 3 格式 → YAGNI,single point of change
4. `Path.parts` 在 case-insensitive FS 行为? → Windows NTFS default case-insensitive;`archive` literal 是 OpenSpec 物理布局 invariant
5. 改 `_check_tasks_unchecked` 改 active false-positive? → regex superset 不破现有 PASS case

### A.5 验收标准(Claude 期望;P3 verify 阶段对账)

- L0 archived 5 change replay:`tasks_unchecked` 25 → 0(regex 双格式)+ `openspec_validate_failed` 4-5 → 0(archive segment skip)+ warnings 含 skip rationale audit trail
- L1 全套 pytest:1746(retire P5 baseline)+ 7 新 = 1753 passed + 1 pre-existing skip 不 regression + 0 failed
- 不需 L2 live LLM / ComfyUI smoke

### A.6 disputed-pending hypothesis(预 codex 可能挑战的点)

Claude 主动列出可能被 codex 挑战的点 + 立场:

- **(可能挑战)双 regex 而非显式两 regex**:codex 可能建议 `_SECTION_HEADING_RE_ACTIVE` + `_SECTION_HEADING_RE_ARCHIVED` 两独立。Claude 立场:**reject**(代码冗余无收益;single regex capture group 已足够)。
- **(可能挑战)warning 字符串 prefix `openspec_validate_skipped:` 形式**:codex 可能建议结构化字段(JSON / YAML)。Claude 立场:**partial accept**(prefix 是 audit-grep-friendly;若 codex 提议 evidence 字段化方案合理可 accept)。
- **(可能挑战)只支持 em-dash U+2014 不支持 en-dash / 半角双连字符**:codex 可能建议扩展 dash 兼容。Claude 立场:**reject**(YAGNI 边界 — 实测 archived 4 change tasks.md 仅 em-dash;不 over-permissive)。
- **(可能挑战)skip 而非升级 long-term fix**:codex 可能建议直接给 upstream openspec CLI 提 PR。Claude 立场:**accept-but-out-of-scope**(short-term mitigation 是合理的 — 跨 repo + release 节奏不可控;留 follow-on `enhance-openspec-cli-archived-change-support`)。

### A.7 锚点 + writeback 预期

本 change 实施过程不预期 writeback drift:
- design.md 3 D-decision 已写齐
- specs.md 7 scenario 已写齐(2 ADDED Requirements 各 N 个 scenario)
- tasks.md 28 task 已写齐(P0-P11)
- 实施过程暴露的 contract gap → return back to controller(implementer subagent 不自行回写;沿 D-TaskInput)

`forgeue_change_state.py --writeback-check` exit 0 应是 default;若 exit 5 → controller 处理 type 1/2/3/4 named DRIFT 并回写到 design.md / specs.md / tasks.md。

---

## B. Codex finding 对照(round 1 verbatim from `review/codex_design_review.md`)

| F# | severity | claim | file:line | Resolution | rationale |
|----|----------|-------|-----------|-----------|-----------|
| F1 | high | D-DispatchPathDetection `"archive" in change_dir.parts` 在 repo 父目录名含 `archive`(如 `tmp_path / "archive" / "repo"`)时 false-positive,active change 被误判 archived → openspec validate 静默 skip → 真 BLOCKER 漏报 | `design.md:63-71` | **accepted-codex** | controller 独立验证 `_common.archive_dir(repo) = repo / "openspec" / "changes" / "archive"`(repo-relative + segment-precise)是正确 invariant;`change_dir.is_relative_to(_common.archive_dir(repo))` 替代 substring-of-parts 检测;A.6 disputed-pending hypothesis 没预见到此场景(我只防 active change 名含 `archive` 子串,没防 repo 路径段含 `archive`)— A.6 hypothesis 修订 |
| F2 | medium | `_SELF_STAGE_SECTION_THRESHOLD = 9` 对 active `## 9. P8 Finish Gate` 与 archived `## P<N> — <text>` 语义不对齐;archived 实测 `## P9 — Documentation Sync Gate`(workflow prerequisite,应 block)与 `## P9 — MEMORY.md update(后置可选)`(self-stage 应 skip)同 P9 编号 ambiguous;threshold ≥9 把 prereq stage unchecked 项静默 skip → P0 baseline 实测可能 false PASS | `design.md:21` | **accepted-codex** | controller 独立 grep archived 4 change 实证 P9 ambiguous 真存在;新 `D-PerFormatThreshold` 决策必需(active `## N.` ≥9 + archived `## P<N>` ≥10);D-RegexExtension regex 改 `r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+"` 双 capture group 暴露 P-prefix;codex 提的 `## P9 — Finish Gate` 实际是 `## P10 — Finish Gate`(样本号偏)但论点正确 |
| F3 | medium | `test_finish_gate_skips_openspec_validate_for_archive_path` 仅 assert `openspec_validate_failed` 不在 + warning 含 prefix,**没** monkeypatch `run_openspec_validate` 验证 invocation skipped;env 无 openspec CLI 时 blocker type 是 `openspec_cli_missing`(escapes `openspec_validate_failed` assertion)→ false-pass | `micro_tasks.md:262-287` | **accepted-codex** | 既有 `test_finish_gate_invokes_openspec_validate_for_active_path` 用 monkeypatch + count == 1 是正确 pattern;镜像至 archive case count == 0 + 拒绝任何 validate-related blocker type;沿 ForgeUE TDD 纪律 |

## C. disputed_open

`disputed_open: 0`

全 3 finding accepted-codex inline writeback,无 round 2 challenge needed。S3 进入条件满足(cross-check disputed_open == 0;writeback 待 inline 完成)。

## D. 独立验证 file:line(沿 ForgeUE memory `feedback_verify_external_reviews`)

### F1 verify

- `tools/_common.py:466-467` 实证:`def archive_dir(repo: Path) -> Path: return changes_dir(repo) / "archive"`(即 `repo / "openspec" / "changes" / "archive"`,repo-relative,segment-precise)
- `tools/_common.py:484-498` 实证:`change_path(repo, change_id)` 返回**绝对**路径(active `changes_dir(repo) / change_id` / archived `archive_dir(repo) / <entry>`)
- 反推:若 `repo = /some/archive/repo`,则 active change_dir = `/some/archive/repo/openspec/changes/<id>`,`Path.parts` = `("/", "some", "archive", "repo", "openspec", "changes", "<id>")`,**含 `archive` segment** → 被误判 archived。F1 claim 真实

### F2 verify

`grep "^## P9 \|^## P10 " openspec/changes/archive/2026-05-06-*/tasks.md` 实测:
- `## P9 — Documentation Sync Gate` ✓(workflow prerequisite)
- `## P9 — MEMORY.md update + follow-on tracking(后置可选)` ✓(self-stage)
- `## P10 — Finish Gate` ✓(self-stage)
- `## P11 — Archive(用户授权 fence #1)` ✓(self-stage)

archived P9 真有 ambiguous 语义,threshold ≥9 把 doc sync gate prerequisite 静默 skip。F2 claim 真实(codex 样本号 `## P9 — Finish Gate` 偏,实际是 `## P10`,但论点正确)

### F3 verify

`tests/unit/test_forgeue_finish_gate.py:1170+`(既有 active path test)用 `monkeypatch.setattr(fg, "run_openspec_validate", _spy)` + `invoked["count"] == 1` 是正确 invocation count pattern;`micro_tasks.md:253-282` archive case 缺少同款 monkeypatch,只 assert blocker type 不在 + warning prefix 在,env 无 openspec CLI 时 false-pass。F3 claim 真实

### A.6 disputed-pending hypothesis 修订

A.6 列了 4 项可能挑战(双 regex 形态 / warning 字符串 prefix / dash 变体 / upstream PR vs skip)— **全 4 项 codex 没挑战**(说明 A.6 hypothesis 这 4 项立场守住)。但 codex F1 + F2 + F3 是 A.6 **没预见**的 3 项 — A.6 hypothesis 不完备:

- **A.6 漏 #1**:repo 路径父目录 segment 含 `archive` 的 false-positive(F1)— 我之前只考虑 active change 名含 `archive` 子串(`add-archive-feature`),没考虑 repo 整体路径 segment
- **A.6 漏 #2**:archived P-numbering 跨 change 不统一,P9 ambiguous(F2)— 我假设 archived P-num 与 active section-num 加 1 对应,实测错
- **A.6 漏 #3**:archive-skip test 的 invocation 验证强度(F3)— 我假设 blocker absence 足够,实测 env 无 CLI 会 escapes

下次 plan stage:`## A. Decision Summary` 写 disputed-pending hypothesis 时增加 path layout assumption / cross-change format invariant / test invocation count pattern 三类 audit。

