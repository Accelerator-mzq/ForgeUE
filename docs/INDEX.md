# ForgeUE 文档索引

本项目采用五件套文档体系(2026-04-22 生效),下述四层中任一文档冲突时以**上位层**为准。

## 权威文档(五件套)

| 层次 | 文档 | 编号 | 用途 |
| --- | --- | --- | --- |
| 需求 | [`requirements/SRS.md`](requirements/SRS.md) | FORGEUE-SRS-001 | 功能 + 非功能 + 接口 + 约束基线(IEEE 830) |
| 概要设计 | [`design/HLD.md`](design/HLD.md) | FORGEUE-HLD-001 | 分层 / 子系统 / 对象模型概览 / 协作 |
| 详细设计 | [`design/LLD.md`](design/LLD.md) | FORGEUE-LLD-001 | 字段 / 方法 / 算法 / 异常体系 |
| 测试 | [`testing/test_spec.md`](testing/test_spec.md) | FORGEUE-TEST-001 | 543 用例索引 + fence 清单 + 覆盖矩阵 |
| 验收 | [`acceptance/acceptance_report.md`](acceptance/acceptance_report.md) | FORGEUE-ACC-001 | FR/NFR 验收状态 + 待执行项清单 |

## 层级关系

```
SRS (需求)
  │  ─────── 定义 ────────►
  ▼
HLD (概要)          对应 SRS FR/NFR
  │  ─────── 细化 ────────►
  ▼
LLD (详细)          对应 HLD 子系统
  │  ─────── 验证 ────────►
  ▼
test_spec           对应 SRS FR/NFR + LLD 算法
  │  ─────── 审收 ────────►
  ▼
acceptance_report   对应 SRS + test_spec 状态
```

## 读者建议入口

| 你是 | 从哪里开始 |
| --- | --- |
| 首次接触项目 | `requirements/SRS.md` §1-§2,再跳 `acceptance/acceptance_report.md` §3 看主线进度 |
| 需要对接某模块 | `design/HLD.md` §3 子系统表 → 对应 `design/LLD.md` 章节 |
| 评估做某个新功能 | `requirements/SRS.md` §7 未决 + `acceptance/acceptance_report.md` §6-§7 |
| 审查测试覆盖 | `testing/test_spec.md` §3-§6 |
| 了解某条修复来龙去脉 | `testing/test_spec.md` §5 fence 清单 + `archive/claude_unified_architecture_plan_v1.md` §M |

## 辅助资源

| 位置 | 用途 |
| --- | --- |
| [`api_des/`](api_des/) | 五家 provider 的 API 契约参考(GLM / Qwen / Qwen-Image(-Edit) / HunYuan) |
| [`archive/`](archive/) | 历史文档归档(plan_v1 + 评审报告 + 早期方案),仅作史料 |

## 变更管理

- 修改 SRS 需要同步检查下游 HLD/LLD/test_spec/acceptance 是否受影响
- 新增 FR → 至少一条单测 + 更新 test_spec §3 + 更新 acceptance §4
- Codex / adversarial review 每条修复 → 一条 L3 fence + 更新 test_spec §5
- 未知改动以**五件套更新 + commit** 作为变更记录,不再维护 plan_v1 §M
