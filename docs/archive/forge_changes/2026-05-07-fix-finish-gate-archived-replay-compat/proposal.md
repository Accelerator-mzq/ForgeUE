## Why

`tools/forgeue_finish_gate.py` 在对 archived 历史 change 做 `D-ArchivedReplayCompat` 二次 replay 时会产生 29 个 spurious blocker(25 `tasks_unchecked` + 4 `openspec_validate_failed`),根因是两个 pre-existing tooling 缺陷:**(F-A)** `_SECTION_HEADING_RE` 仅识别 `## <int>. <text>` 格式,不认 archived 历史 change tasks.md 用的 `## P<N> — <text>` 格式(P-prefix + em-dash U+2014),导致 `## P10 — Archive` / `## P11 — Documentation Sync footer` 这类 self-stage section 不被 threshold filter 识别 → §P10/§P11 内 unchecked 行被误报;**(F-B)** `openspec validate <archive-id> --strict` 因 openspec CLI 仅识别 active `openspec/changes/<id>/` 路径而非 `openspec/changes/archive/<dated-id>/`,对每个 archived change 报 `Unknown item` 噪声 blocker。两 bug 都是 pre-existing(regex 自 commit `a4334db` 起,openspec CLI 是上游 tool design),仅在 archived replay 路径暴露,active workflow 路径不受影响,但 `D-ArchivedReplayCompat` baseline 噪声让"archived replay 全 PASS" criterion 永远 hold 不住 — `retire-parallel-and-worktree-fully` archive P0 baseline 实测被迫修正为"31 → 29 unchanged blockers" 而非 0 PASS。

## What Changes

- **`tools/forgeue_finish_gate.py:1385` `_SECTION_HEADING_RE` 扩展**:支持双格式向后兼容 — `## <int>. <text>`(active 现行)+ `## P<int> — <text>`(archived 历史,em-dash U+2014);两种格式均抽出整数 section number 用于 `_SELF_STAGE_SECTION_THRESHOLD = 9` 阈值过滤。
- **`tools/forgeue_finish_gate.py` `openspec validate` 调用路径分流**:在 archive/ 路径(`openspec/changes/archive/<dated-id>/`)下自动 skip `openspec validate <id> --strict` 并写 rationale 注释(沿 follow-on `fix-openspec-validate-archived-change-support` 短期 mitigation 路径,upstream openspec CLI patch 留为后续工作);active 路径行为不变。
- **测试矩阵增量**:`tests/unit/test_forgeue_finish_gate.py` 新增 ~3-5 case 守门两类格式识别 + archive/ 路径 openspec validate skip 行为;既有 case `test_finish_gate_skips_p8_p9_self_stage_unchecked`(active `## N.` 格式)+ `test_finish_gate_does_not_skip_pre_p8_unchecked` 保持不动,守门 backward compat。
- **CHANGELOG.md `[Unreleased]` Fixed 子段**:加 1 条记录两 bug 修复 + 关联 follow-on id(`fix-finish-gate-section-regex-for-p-prefixed` + `fix-openspec-validate-archived-change-support`)。

## Capabilities

### New Capabilities

无。本 change 不引入新 capability。

### Modified Capabilities

- `examples-and-acceptance`:`forgeue_finish_gate.py::_check_tasks_unchecked` 行为升级 — 支持 `## P<N> — <text>` 格式 section heading 识别(原仅 `## <int>. <text>`);`forgeue_finish_gate.py` openspec validate 调用 archive/ 路径分流 skip(原对 archive/ change 强制 invoke 必 fail)。两 ADDED Requirements,均守门 archived replay 路径噪声 baseline 归零。

## Impact

**代码**:
- `tools/forgeue_finish_gate.py`(单文件;`_SECTION_HEADING_RE` 1 行 + openspec validate dispatch ~5-10 行)
- `tests/unit/test_forgeue_finish_gate.py`(新增 ~3-5 case;既有 case 不动)
- `CHANGELOG.md`(`[Unreleased]` Fixed 子段 +1 条)

**docs/ 五件套**:无影响(SRS / HLD / LLD / test_spec / acceptance_report 不动 — finish_gate tooling 行为不在 contract 内 spec 化)。

**契约 / D-decision**:无新 D-decision 引入(纯 backward-compat 扩展 + 短期 mitigation skip);若未来要彻底修 F-B(给 openspec CLI 提 PR 或本地 patch)再单独 propose。

**Follow-on close**:本 change 落地后关闭以下 backlog:
- `fix-finish-gate-section-regex-for-p-prefixed`(P0 baseline 暴露,F-A)
- `fix-openspec-validate-archived-change-support`(P0 baseline 暴露,F-B 短期 mitigation;upstream openspec CLI 长期 patch 留单独 backlog `enhance-openspec-cli-archived-change-support` 若决定推上游)

**回归 / 风险**:
- Active workflow 路径不受影响(regex 扩展是 superset;openspec validate 仅在 archive/ 路径分流)
- archived 4 change replay baseline 应从 31 → ~0(2 v2 fence 已在 retire 中消失,本 change 再去掉 25 + 4 noise),`D-ArchivedReplayCompat` criterion 真正 hold
- L0 fence test + L1 pytest 全跑;不需要 L2 live LLM / ComfyUI smoke
