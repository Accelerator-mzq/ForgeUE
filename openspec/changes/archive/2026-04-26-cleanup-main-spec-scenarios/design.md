# Design: cleanup-main-spec-scenarios

本 design 假设实装阶段**逐 spec 推进**,按 `tasks.md` 顺序处理 8 份 capability spec。每份 spec 完成时跑 `openspec validate cleanup-main-spec-scenarios --strict` 校验本 change 自身,8 份全部就位后再 Codex review + archive。

---

## 1. Scenario 编写原则

### 1.1 优先最小 Scenario

绝大多数 Requirement 性质明确,从既有源码 / 测试 / docs 提炼一个 GIVEN/WHEN/THEN 即可。盘点结果约 2/3 的缺失 Requirement 适合 [Min 1]。

### 1.2 必须对齐现有事实

每条 Scenario 必须可追溯到:
- `src/framework/` 现有代码行为
- `tests/unit/` / `tests/integration/` 已有测试
- `docs/requirements/SRS.md` / `docs/design/{HLD,LLD}.md` 既有约定
- `examples/*.json` / `probes/*.py` / `ue_scripts/*.py` 现存约定

**禁止**写未来能力 / 未实装行为 / 没有测试覆盖的断言。

### 1.3 [+1] 正反例

部分 Requirement 内含"对错两侧"(例如 `Pricing probe defaults to dry-run` —— dry-run 与 `--apply` 行为不同),写两个 Scenario 让契约清晰。盘点结果约 8 处。

### 1.4 [审视] 措辞收紧

3 条 Requirement 是流程 / meta 承诺,直接写 Scenario 会失真:
- `examples-and-acceptance` "No hardcoded provider model ids" —— 措辞过宽,LIVE bundle 显式覆盖路径是合法例外,需先收紧
- `probe-and-validation` "Regression fence per review fix" —— 流程承诺,不是运行时行为
- `probe-and-validation` "Test totals are never hardcoded" —— 文档约束,不是运行时行为

处理方式:在 delta spec 的 `## MODIFIED Requirements` 中**重写** Requirement 描述为可验证表述(例如 "No hardcoded provider model ids" 改为 "Production bundles must use models_ref"),再写 Scenario。**不**改 Requirement 标题(标识符稳定)。

### 1.5 不重命名 Requirement

Requirement 名是 OpenSpec 内部标识符。本 change 全部用 `## MODIFIED Requirements` 块,**保留 Requirement 标题不变**,只修改描述段落 + 新增 Scenario。这样既不破坏 main spec 既有引用,也不破坏未来 OpenSpec change 对这些 Requirement 的 reference。

### 1.6 不直接动主 spec

**不**修改 `openspec/specs/*` 文件本身。所有改动通过 delta spec(`openspec/changes/cleanup-main-spec-scenarios/specs/<capability>/spec.md`),archive 阶段由 sync-specs 合并到主 spec。这保持 OpenSpec workflow 一致性。

### 1.7 Scenario 格式

参考 `openspec/specs/artifact-contract/spec.md` 已有 Scenario 写法:

```
#### Scenario: Short imperative title

- GIVEN <pre-condition>
- WHEN <triggering action>
- THEN <observable outcome>
- AND <secondary assertion (optional)>
```

`- GIVEN/WHEN/THEN` 单星号,无 markdown 加粗(与 `add-run-comparison-baseline-regression` 的 delta spec 风格一致,strict validate 已确认接受)。

## 2. 缺 Scenario Requirement 总览

| capability | 缺 Scenario 数 | 标记构成 |
|---|---|---|
| artifact-contract | 5 | 3 [Min 1] + 2 [+1] |
| examples-and-acceptance | 7 | 6 [Min 1] + 1 [审视] |
| probe-and-validation | 10 | 7 [Min 1] + 1 [+1] + 2 [审视] |
| provider-routing | 16 | 15 [Min 1] + 1 [+1] |
| review-engine | 8 | 8 [Min 1] |
| runtime-core | 7 | 5 [Min 1] + 2 [+1] |
| ue-export-bridge | 8 | 7 [Min 1] + 1 [+1] |
| workflow-orchestrator | 5 | 5 [Min 1] |
| **合计** | **66 Requirement** | 约 70+ Scenario(部分 [+1] 写 2 个) |

详细 Scenario 标题草案见每份 delta spec 的 "Plan" 段。

## 3. 实施节奏(逐 spec 推进)

每份 spec 一个 Task(Task 1-8),Task 内子步骤:

1. 读 `openspec/specs/<capability>/spec.md` 全文,验证 Requirement 标题 + 描述与 grep 结果一致
2. 对照源码 / 测试 / docs,为每个缺 Scenario Requirement 写 1-2 个 GIVEN/WHEN/THEN
3. 把 delta spec 的 "Plan" 段转为 `## MODIFIED Requirements` 完整块
4. 跑 `openspec validate cleanup-main-spec-scenarios --strict` —— 单 spec 完成时本 change 自身 validate 应当部分 PASS(其他未完 spec 仍报警告),全 8 份完成后 PASS
5. 跑 `python -m pytest -q`(数量以实测为准,本 change 不影响测试,作为防回归冒烟)

8 个 Task 完成后,Task 9 跑全量 validate,Task 10 走 Codex review,Task 11 archive cleanup-main-spec-scenarios,Task 12 回头 archive add-run-comparison-baseline-regression。

## 4. 文件 layout

```
openspec/changes/cleanup-main-spec-scenarios/        (本 change)
├── proposal.md
├── design.md                       (本文件)
├── tasks.md
└── specs/
    ├── artifact-contract/spec.md
    ├── examples-and-acceptance/spec.md
    ├── probe-and-validation/spec.md
    ├── provider-routing/spec.md
    ├── review-engine/spec.md
    ├── runtime-core/spec.md
    ├── ue-export-bridge/spec.md
    └── workflow-orchestrator/spec.md
```

每份 delta spec 命名与主 spec 路径对齐,内容只含 `## MODIFIED Requirements`(无 ADDED / REMOVED)。

## 5. 验证策略

- **单 task 验证**:`openspec validate cleanup-main-spec-scenarios --strict` —— 实施过程中每改完一份 delta spec 跑一次,期望逐步收敛
- **全量验证**(Task 9):
  - `openspec validate cleanup-main-spec-scenarios --strict` PASS
  - `openspec list` 显示本 change 全部 task checkbox 勾选(留 archive 阶段的 sync-specs sync-specs row 除外)
  - `python -m pytest -q` 与 cleanup 启动前基线一致,数量以实测为准(零回归)
- **archive 后验证**(Task 11 完成):
  - `openspec validate --specs --strict` 8/8 PASS(主 spec 全部带回 strict-clean 状态)
  - `openspec list` 不再含 cleanup-main-spec-scenarios(已 archived)
  - `git log --oneline` 含 archive commit

## 6. archive 后期望状态

- `openspec/specs/*/spec.md`:8 份主 spec 各自加完缺失 Scenario,strict validate PASS
- `openspec/changes/cleanup-main-spec-scenarios/`:整体移到 `openspec/changes/archive/<YYYY-MM-DD>-cleanup-main-spec-scenarios/`
- `add-run-comparison-baseline-regression` 解锁:重跑 `openspec archive add-run-comparison-baseline-regression -y` 应直接通过(因为它的 delta strict 早就 PASS,只是被 main spec rebuild 校验卡住)
- ForgeUE 运行时行为:零变化(`pytest -q` 全绿,数量以实测为准;`framework.comparison` / 其他模块代码与归档前一致)

## 7. 与既有 ADR / change 的关系

- ADR-005:plan_v1 降级归档 —— 本 cleanup 是 ADR-005 的延续(把 OpenSpec spec 层从"骨架版"升级到"strict-clean 版"),不冲突
- `add-run-comparison-baseline-regression`:本 change archive 完成后才解锁该 change 的 archive 路径
- 后续 `lazy-artifact-store-package-exports`:与本 cleanup 独立,本 cleanup 完成后再启

## 8. 非目标

- **不**修改 ForgeUE 任何运行时代码 / 测试 / docs 五件套
- **不**新增 FR / NFR
- **不**重命名 Requirement(保持标识符稳定)
- **不**触动 add-run-comparison-baseline-regression 的任何文件
- **不**新增 capability spec(8 个 capability 维持现状)
