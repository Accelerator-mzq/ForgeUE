# Change Proposal: cleanup-main-spec-scenarios

## Why

ForgeUE 在 2026-04-24 引入 OpenSpec 工作流时,从 docs 五件套抽取 8 个 capability spec 到 `openspec/specs/`。抽取阶段以 Requirement 描述段落为主,**未**为每个 Requirement 写 `#### Scenario:` 块。OpenSpec 的 `--strict` validation 要求每个 Requirement 必须含至少 1 个 Scenario。本工作流债务在引入时未暴露,直到 2026-04-25 第一次走 `openspec archive add-run-comparison-baseline-regression` 才被工具抓出。

实测后果:
- `openspec validate --specs --strict` 8/8 spec 全部 FAIL
- `openspec archive` rebuild "delta + main 合并" 时跑同一 strict 校验,在 sync-specs 阶段 abort
- `add-run-comparison-baseline-regression` 实装侧已 100% 完成 + 双轮 Codex Review Gate PASS,但**结构性卡在 archive**

阻塞**不是** `add-run-comparison-baseline-regression` 自身的 hygiene 问题(它的 delta spec strict validate 早已 PASS);阻塞源是 main spec 的预存在债务。

## What Changes

- 给 `openspec/specs/{runtime-core,artifact-contract,examples-and-acceptance,probe-and-validation,provider-routing,review-engine,ue-export-bridge,workflow-orchestrator}/spec.md` 的所有缺 Scenario Requirement 补充 `#### Scenario:` 块,目标 `openspec validate --specs --strict` 8/8 PASS。
- 不新增 Requirement;不改 Requirement 标题(标识符稳定,避免破坏既有 / 未来 OpenSpec change 的引用)。
- 不修改 ForgeUE 任何运行时代码 / 测试 / docs 五件套。
- Scenario 内容必须**对齐现有源码、测试、文档或既有约定**;不引入未来能力。
- 若某 Requirement 措辞过宽 / 是流程承诺(meta-rule),先在本 change 的 delta spec 里把 Requirement 描述收紧为可验证表述,再补 Scenario。
- 主 spec 文件**不**直接修改;改动通过 delta spec + `/opsx:archive` 的 sync-specs 步骤合并。

## What this change explicitly does NOT solve

- 不引入新 capability、不新增 FR / NFR、不修改 docs 五件套。
- 不动 `add-run-comparison-baseline-regression`(它已 commit 完毕,等本 change archive 后回头继续 archive)。
- 不重写 main spec 长篇内容;只补 Scenario + 必要时收紧 Requirement 措辞。
- 不创建 `lazy-artifact-store-package-exports` follow-up(那是另一个独立 change)。
- 不绕过 `openspec validate` / `openspec archive` 的 strict 模式(用 `--no-validate` / `--skip-specs` 都会留下永久债务,违反 OpenSpec 工作流精神)。

## Modules affected

**主 spec(archive 时由 sync-specs 修改;本 change 实装阶段写 delta,不直接动主 spec)**:
- `openspec/specs/runtime-core/spec.md` (+7 Scenario)
- `openspec/specs/artifact-contract/spec.md` (+5+ Scenario)
- `openspec/specs/examples-and-acceptance/spec.md` (+7 Scenario)
- `openspec/specs/probe-and-validation/spec.md` (+10 Scenario,含 2 处措辞收紧)
- `openspec/specs/provider-routing/spec.md` (+16 Scenario,最大份)
- `openspec/specs/review-engine/spec.md` (+8 Scenario)
- `openspec/specs/ue-export-bridge/spec.md` (+8 Scenario)
- `openspec/specs/workflow-orchestrator/spec.md` (+5 Scenario)

**新增**(本 change 自己):
- `openspec/changes/cleanup-main-spec-scenarios/`(proposal / design / tasks / 8 delta specs)

## Modules NOT affected

- `src/framework/` 全部(本 change 是 doc-only / spec-only)
- `tests/` 全部(运行时行为不变,无新测试)
- `docs/` 五件套(SRS / HLD / LLD / test_spec / acceptance_report 不动)
- `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md` / `pyproject.toml` / `config/models.yaml` / `examples/` / `probes/` / `ue_scripts/`
- `openspec/changes/add-run-comparison-baseline-regression/`(该 change 已 commit + 实装完成,本 cleanup 不触动)

## Why hygiene-only

OpenSpec 是契约抽取层(`docs/ai_workflow/README.md` §1)。当 ForgeUE 主 spec 自身不通过 strict validate 时,**任何**引用 / 修改它的 OpenSpec change 都会在 archive 阶段被 sync-specs rebuild 校验阻塞。本 change 把 main spec 一次性带回 strict-clean 状态,后续所有 OpenSpec change 的 archive 路径才能稳定通过。

## Success criteria

- [ ] `openspec validate cleanup-main-spec-scenarios --strict` PASS(本 change 自身 delta spec 合规)
- [ ] 8 份 delta spec 的 MODIFIED Requirement 全部含至少 1 个 Scenario,Scenario 与 ForgeUE 源码 / 测试 / docs 现状对齐
- [ ] `openspec archive cleanup-main-spec-scenarios` 完成 sync-specs 后,主 spec 8/8 通过 `openspec validate --specs --strict`
- [ ] archive `add-run-comparison-baseline-regression` 在 cleanup archive 之后可以重新跑通,sync-specs 不再 abort
- [ ] `python -m pytest -q` 仍 848 通过(运行时行为零变更,本 change 不应引入回归)

## References

- 阻塞实测:Archive Readiness Gate 第三轮 + `/opsx:archive add-run-comparison-baseline-regression` aborted with `Validation errors in rebuilt spec for artifact-contract`
- OpenSpec 工作流权威:`docs/ai_workflow/README.md` §2(主流程)+ §4(Documentation Sync Gate)
- ForgeUE 8 个 capability spec 现状:`openspec validate --specs --strict` 8/8 FAIL
- 前置 change 已完成不阻塞:`openspec/changes/add-run-comparison-baseline-regression/`(实装侧 commit `a1bf0c4` ~ `e341b49`,Documentation Sync Gate 4 轮 + Pre-Archive Hygiene Fix 2 轮)
