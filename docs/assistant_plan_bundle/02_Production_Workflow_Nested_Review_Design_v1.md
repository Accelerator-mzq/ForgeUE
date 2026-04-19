# Production Workflow + Nested Review 机制设计 v1

## 0. 文档目的

本文专门回答一个关键架构问题：

**ReviewNode 如何嵌到生产流里，而不是只作为独立评审模式存在。**

目标是把 Review 从“附加功能”提升为生产模式内部的正式控制节点，使其承担：

- 候选方案比较
- 质量闸门
- 自动放行/拦截
- 重试/回退/切模
- 人工升级入口

---

## 1. 核心结论

Review 不是生产流之外的外挂，而是生产流中的一种合法节点类型。
因此生产流不是：

```text
generate -> generate -> generate -> export
```

而应是：

```text
generate -> review -> transform -> review -> validate -> review -> export
```

也就是说，生产链中的关键节点之间，允许插入 Review Gate。

---

## 2. Review 的两种存在方式

### 2.1 Standalone Review

作为顶层运行模式：

- 输入：一个或多个 Candidate
- 输出：Verdict
- 适用于方案比较、资产复审、答案裁决

### 2.2 Nested Review

作为 `production` 流中的子节点：

- 输入：当前步骤产生的 CandidateSet 或单一 Artifact
- 输出：Verdict
- 直接影响后续流程转移

本文重点讨论第二种。

---

## 3. Nested Review 的职责边界

Nested Review 不负责：

- 直接生成最终资产
- 替代上游生成模型的创造性工作
- 承担 UE 编辑器执行动作

Nested Review 负责：

- 判断当前产物是否满足继续推进条件
- 在候选中选优
- 对失败结果给出流程级动作建议
- 将“评审结论”转成 `TransitionPolicy` 可消费信号

---

## 4. 生产流中适合插入 ReviewNode 的位置

### 4.1 高发散输出之后
典型场景：

- 文本描述生成后
- 概念图候选生成后
- 音乐草案生成后

原因：这些步骤通常会产生多个候选或高不确定性结果，适合立即评审选优。

### 4.2 高成本转换之前
典型场景：

- 图转 3D 之前
- 高精度贴图烘焙之前
- 长时音频后处理之前

原因：应先筛掉明显不合格候选，避免把计算资源浪费在低价值输入上。

### 4.3 导入 UE 之前
典型场景：

- 路径规范检查
- 命名检查
- 分辨率/格式检查
- 元数据完整性检查

原因：在进入 Bridge 前做最后一道质量闸门。

### 4.4 失败重试分岔点
典型场景：

- 某步生成结果低于阈值
- 模型超时或 provider 异常
- 产物缺字段或规格不合规

原因：需要评审决定是重试、切模、回退还是人工介入。

---

## 5. ReviewNode 输入模型

ReviewNode 的标准输入不应是“整段聊天上下文”，而应是标准化对象：

- 当前 Task 摘要
- 当前 Step 目标
- CandidateSet 或 Artifact
- 约束条件
- 上游关键 lineage
- 评审 rubric
- TransitionPolicy 模板

建议输入结构：

```json
{
  "task_context": {},
  "step_context": {},
  "candidate_set": {},
  "constraints": {},
  "review_rubric": {},
  "action_space": ["approve", "reject", "retry_same_step", "fallback_model", "rollback", "human_review_required"]
}
```

---

## 6. ReviewNode 输出模型

ReviewNode 输出不应只是自然语言评论，而应是结构化 Verdict。

建议输出结构：

```json
{
  "decision": "approve_one",
  "selected_artifact_ids": ["art_002"],
  "confidence": 0.81,
  "scores": {
    "constraint_fit": 8.5,
    "production_readiness": 7.8,
    "style_consistency": 8.2
  },
  "reasons": [],
  "dissent": [],
  "next_action": "continue",
  "recommended_next_step_id": "step_convert_to_mesh"
}
```

---

## 7. ReviewNode 的主要类型

### 7.1 Candidate Review
多个候选中选优。

适用：

- 多图候选
- 多音乐草案
- 多文本设定草案

输出常为：

- `approve_one`
- `approve_many`
- `reject`

### 7.2 Quality Gate Review
对单一产物做继续推进判定。

适用：

- 单张已选概念图是否可进入图转 3D
- 单段音乐是否满足最小时长与风格要求

输出常为：

- `approve`
- `revise`
- `retry_same_step`

### 7.3 Compliance Review
检查规则/格式/命名/路径/元数据等是否合规。

适用：

- UE 资源命名
- 路径是否落在允许目录
- 导入格式是否合法
- 元数据是否缺失

输出常为：

- `approve`
- `reject`
- `human_review_required`

### 7.4 Recovery Review
失败后的恢复决策节点。

适用：

- provider 连续失败
- 某类资产质量低
- 上一步输出无法被下游消费

输出常为：

- `fallback_model`
- `rollback`
- `human_review_required`

---

## 8. 典型生产流示例

### 8.1 概念图到 3D 资产链

```text
Step 1  结构化角色设定生成
  ↓
Step 2  角色概念图候选 A/B/C 生成
  ↓
Step 3  ReviewNode: 候选图评审与选优
  ↓
Step 4  图转 3D / 贴图派生
  ↓
Step 5  ReviewNode: 资产可用性检查
  ↓
Step 6  UE Asset Manifest 导出
  ↓
Step 7  ReviewNode: UE 导入前合规检查
  ↓
Step 8  Export / Bridge
```

### 8.2 音乐生产链

```text
Step 1  场景情绪与音频标签提取
  ↓
Step 2  BGM 草案生成
  ↓
Step 3  ReviewNode: 草案评分与选优
  ↓
Step 4  后处理 / 裁剪 / 元数据补全
  ↓
Step 5  ReviewNode: 时长与循环点检查
  ↓
Step 6  UE 清单输出
```

---

## 9. ReviewNode 与 TransitionPolicy 的耦合

ReviewNode 的价值不在“点评”，而在流程控制。
因此它必须把结果映射到标准 TransitionPolicy。

示例：

```json
{
  "on_decision.approve": "step_convert_to_mesh",
  "on_decision.approve_one": "step_convert_to_mesh",
  "on_decision.retry_same_step": "step_generate_concepts",
  "on_decision.fallback_model": "step_generate_concepts_fallback",
  "on_decision.rollback": "step_extract_design_spec",
  "on_decision.human_review_required": "step_human_gate"
}
```

---

## 10. ReviewNode 的评分维度设计

建议不要只用一个总分。
对于 UE 游戏资产链，更建议拆成多维评分：

- `constraint_fit`：是否满足任务约束
- `style_consistency`：是否符合整体风格
- `production_readiness`：是否适合进入下一步生产
- `technical_validity`：格式、规格、元数据是否可消费
- `risk_score`：进入下一步的风险高低

### 10.1 候选选优时
可侧重：

- 风格契合
- 可派生性
- 视觉辨识度

### 10.2 导入前检查时
可侧重：

- 规范性
- 完整性
- 格式兼容性

---

## 11. 单评审与多评审策略

### 11.1 单主审模型
优点：

- 成本低
- 流程简单
- 易于调试

适合：

- MVP 阶段
- 技术合规检查
- 规则化强的 gate

### 11.2 多模型交叉评审
优点：

- 鲁棒性更高
- 有利于发现遗漏
- 适合主观性较强的候选筛选

适合：

- 艺术风格选优
- 音乐草案比较
- 多方案设计裁决

### 11.3 主审 + 陪审混合
建议生产中常用该策略：

- 陪审负责打分与提出问题
- 主审负责汇总与发出 Verdict

---

## 12. Nested Review 的失败策略

当 Review 本身无法得出稳定结论时，不应强行推进。
建议支持以下策略：

- 二次评审
- 切换 judge 模型
- 增加 candidate metadata 后重评
- 降级到人工确认
- 回退上一步重新生成

---

## 13. 不同节点的推荐 Review 强度

### 13.1 轻量 Review
适合高频低成本节点：

- 字段检查
- 命名规则检查
- 必需元数据检查

### 13.2 中等 Review
适合中间候选选择：

- 多图选优
- 多音乐草案选优
- 设计草案选优

### 13.3 重量 Review
适合关键出口：

- 进入 UE Bridge 前
- 高成本转换前
- 最终候选发版前

---

## 14. 与人工审查的关系

Nested Review 不应试图消灭人工节点，而应减少人工节点。
建议保留 `human_gate` 作为正式 Step.type，用于：

- 低置信度裁决
- 高风险资产
- 许可/版权敏感资源
- 风格争议较大的主观结果

---

## 15. 最小可运行实现建议

MVP 阶段建议先落两类 Nested Review：

### 15.1 Candidate Review
用于多图、多音乐候选筛选。

### 15.2 Compliance Review
用于导出前检查路径、命名、格式与元数据。

并只支持以下 5 个动作：

- `continue`
- `retry_same_step`
- `fallback_model`
- `rollback`
- `human_review_required`

---

## 16. 不建议的实现方式

### 16.1 把 Review 写成 prompt 字符串拼接函数
会导致流程控制语义丢失。

### 16.2 让每个业务节点自己决定是否重试
会导致恢复策略分散，无法统一治理。

### 16.3 让 Review 直接操纵 UE 编辑器
会让评审层与执行层耦死。

---

## 17. 结论

Nested Review 的正确定位是：

- 它是 Production Workflow 中的合法节点类型
- 它是质量闸门，不只是意见输出器
- 它的结果必须转成 Verdict 与 TransitionPolicy
- 它可以决定继续、重试、切模、回退和人工升级
- 它是实现“可控生成链”的关键机制
