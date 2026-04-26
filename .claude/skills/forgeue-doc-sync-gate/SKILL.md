---
name: forgeue-doc-sync-gate
description: Documentation Sync Gate 编排器;静态扫描 10 文档 + README §4.3 提示词 + 报告落盘 + 应用 [REQUIRED]。沿 docs/ai_workflow/README.md §4 主规则不动;新增 forgeue_doc_sync_check 静态预扫描作为 §4.3 提示词的 context 输入。
license: MIT
compatibility: Requires openspec CLI + Claude Code; tools/forgeue_doc_sync_check.py(stdlib only)
metadata:
  author: forgeue
  version: "1.0"
---

ForgeUE Documentation Sync Gate 编排器。`/forgeue:change-doc-sync` command 的 backbone skill。沿 `docs/ai_workflow/README.md` §4 主规则**不动**(§4.1 必检 10 文档 / §4.2 核心原则 / §4.3 固定提示词 / §4.4 tasks.md 必含段模板);新增工具层静态预扫描衔接。

**真源**:
- `docs/ai_workflow/README.md` §4(Documentation Sync Gate 主规则,2026-04-24 起立);
- `openspec/changes/fuse-openspec-superpowers-workflow/design.md` §7(Integration);
- `tools/forgeue_doc_sync_check.py`(机器层静态扫描,P3 实装)。

## 必检 10 文档(README §4.1)

| # | 文件 | 更新触发条件 |
|---|---|---|
| 1 | `openspec/specs/*` | change 引入 / 修改 / 删除的行为 archive 后合入主 spec |
| 2 | `docs/requirements/SRS.md` | 需求 / 用户可见行为变更 |
| 3 | `docs/design/HLD.md` | 架构边界 / 模块职责变更 |
| 4 | `docs/design/LLD.md` | 接口 / 模型 / CLI entry / 文件级设计变更 |
| 5 | `docs/testing/test_spec.md` | 测试策略 / fixture / 验证矩阵变更 |
| 6 | `docs/acceptance/acceptance_report.md` | 验收状态变更(新 FR 通过 / TBD 关闭 / 真机验收达成)|
| 7 | `README.md` | 用户可见工作流 / 命令 / 入口变更 |
| 8 | `CHANGELOG.md` | 任何合并到 main 的有意义变更 |
| 9 | `CLAUDE.md` | AI 协作约定变更(Claude Code 视角)|
| 10 | `AGENTS.md` | AI 协作约定变更(其他 agent 视角)|

## 核心原则(README §4.2)

- **不机械同步**:不是每个 change 都要动 10 份;很多 change 只触动 2-3 份。
- **不更新的要记录原因**:在 `verification/doc_sync_report.md` 明确写"跳过 X 原因:本 change 未触及 Y"。
- **Drift 显式化**:docs / tests / code / CHANGELOG 冲突 → 标 `[DRIFT]`,**不自行猜测**哪个对。
- **数字以实测为准**:测试总数 / 覆盖率 / 耗时 → 以 `python -m pytest -q` 实测输出为准。
- **五件套保持长篇**:`docs/` 不因 OpenSpec 存在而被瘦身;它是长期知识库,OpenSpec 是契约抽取。

## 启发式规则(design.md §7)

- commit-touching change → CHANGELOG REQUIRED
- `src/framework/core/` 改动 → LLD REQUIRED
- 架构边界改动 → HLD REQUIRED
- 验收新通过 → acceptance_report REQUIRED
- `docs/ai_workflow/` 改动 → CLAUDE+AGENTS REQUIRED
- 无 spec delta → `openspec/specs/*` SKIP
- 无 FR/NFR 变更 → SRS SKIP
- 无 test 策略变更 → test_spec SKIP

## Steps

1. **静态扫描** — `python tools/forgeue_doc_sync_check.py --change <id> --json`(stdlib only;`sys.stdout.reconfigure(encoding="utf-8")`):
   - 扫 10 份长期文档
   - 每份打 `[REQUIRED]` / `[OPTIONAL]` / `[SKIP]` / `[DRIFT]` 标签
   - exit 0(无 DRIFT)/ 2(任一 DRIFT)/ 1(IO 异常)
   - `--json` 模式不打 ASCII 标记
   - `--dry-run` 必无副作用
2. **跑 README §4.3 提示词** — 以 tool 输出作 context;粘提示词到 agent 会话:
   - agent 输出 4 类:
     - **A. 必须更新的文档** — 文件路径 / 更新原因 / 建议修改摘要
     - **B. 不需要更新的文档** — 文件路径 / 不更新原因
     - **C. 存在 doc drift 的地方** — 冲突内容 / 涉及文件 / 建议 source-of-truth / 是否需要人工确认
     - **D. 建议 patch** — 仅修改必要文档;不机械同步;不复制 evidence 全文进 docs;不复制 docs 长文进 OpenSpec
   - **agent 在用户确认前不写文件**(README §4.3 末段约束)
3. **用户确认 [REQUIRED]** — 用户裁决后 agent 应用 patch:
   - patch 限本 change scope
   - 不机械同步;不复制 evidence 全文
   - 数字以实测为准
4. **写 doc_sync_report** — `verification/doc_sync_report.md`:
   - 12-key frontmatter(`evidence_type: doc_sync_report` / `aligned_with_contract: true` / `drift_decision: null`(若 DRIFT 0))
   - 10 文档每份 `[REQUIRED]` / `[OPTIONAL]` / `[SKIP]` / `[DRIFT]` 状态 + reason
   - REQUIRED 应用清单
   - DRIFT 0 + REQUIRED 全应用 = exit 0

## Input / Output

**Input**: change id(active OpenSpec change);user 确认动作。

**Output**:
- `verification/doc_sync_report.md`(REQUIRED 进 S8)
- console 报告(7 种 ASCII 标记;无 emoji)

## Guardrails

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**。
- **agent 在用户确认前不写文件**(README §4.3 末段)。
- **DRIFT 显式化**(README §4.2):docs / contract / specs 冲突 → 标 [DRIFT] 让用户裁决,不自行猜测。
- **不复制 evidence 全文进主 docs**:doc-sync 的源是 contract artifact + 实际 commit;evidence 不能成主 docs 的回写源。
- **数字以实测为准**:测试总数等以 `python -m pytest -q` 实测;**不硬编码**(P4 fence `test_forgeue_workflow_no_hardcoded_test_count.py` 守门)。
- **ASCII only**:console 输出 + report markdown 用 `[OK]` / `[FAIL]` / `[SKIP]` / `[WARN]` / `[DRIFT]` / `[REQUIRED]` / `[OPTIONAL]`,无 emoji(沿 ForgeUE memory `feedback_ascii_only_in_adhoc_scripts`)。

## References

- `docs/ai_workflow/README.md` §4(主规则不动)+ §4.1(10 文档)+ §4.2(核心原则)+ §4.3(固定提示词)+ §4.4(tasks.md 必含段)
- `openspec/changes/fuse-openspec-superpowers-workflow/design.md` §7(Integration)+ §5(`forgeue_doc_sync_check.py` 输出契约)
- `openspec/changes/fuse-openspec-superpowers-workflow/tasks.md` §7(P6 Documentation Sync;§7.5 12 项 checklist)
- `forgeue_integrated_ai_workflow.md` §C(Documentation Sync Gate 应用流程)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(中心化编排;本 skill 是其在 doc-sync 维度的延伸)
