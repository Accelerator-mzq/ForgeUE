# docs/archive/ — 历史文档归档

本目录保留项目早期方案讨论与 v1 权威文档,**不再更新**,仅作史料参考。

当前权威文档见项目根:

- `docs/requirements/SRS.md`
- `docs/design/HLD.md`
- `docs/design/LLD.md`
- `docs/testing/test_spec.md`
- `docs/acceptance/acceptance_report.md`

入口见 [`docs/INDEX.md`](../INDEX.md)。

## 归档清单

| 文件 / 目录 | 原用途 | 归档原因 |
| --- | --- | --- |
| `claude_unified_architecture_plan_v1.md` | vNext 唯一权威(§A-§N),对象模型 / Workflow / Policy / UE Bridge / EventBus / 实装快照 §M | 2026-04-22 文档重构 ADR-005:权威转为五件套,本文件作为单一真源 + 演进日志保留,不再更新 |
| `claude_cross_review_report_v1.md` | 三方案交叉评审报告(13 项必须采纳 / 12 项必须新增) | 已在 plan_v1 中合并落地 |
| `claude_independent_plan_v1.md` | Claude 独立方案 v1(PayloadRef / 两段式 type / risk_level / Dry-run / Checkpoint + hash / UE Bridge 单向写) | 已在 plan_v1 中合并 |
| `unified_architecture_vNext.md` | plan_v1 精简版 | 精简版无独立价值,随 plan_v1 一起归档 |
| `assistant_plan_bundle/` | assistant 方案包 v1(9 对象模型 / TaskType-RunMode 分离 / UEOutputTarget 前置 / CandidateSet+Candidate 双层 / 5 维 scoring / UE Bridge Inspect-Plan-Execute) | 已在 plan_v1 中合并 |

## 使用约定

- 在五件套中遇到"这个决策怎么来的"时,可在 archive 中检索背景
- **不**在 archive 中新增内容
- **不**引用 archive 作为权威出处(用五件套或源码)
