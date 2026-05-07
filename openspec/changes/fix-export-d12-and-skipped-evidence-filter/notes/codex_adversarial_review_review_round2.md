# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议推进实施。计划仍允许绕过真实 UE commandlet 验证,且 canonical tasks 漏掉承 round1-F3 的关键 integration fence。

Findings:
- [high] P4 真机验证被标成可选会让 UE 侧改动只靠 stub/L2 放行 (openspec/changes/fix-export-d12-and-skipped-evidence-filter/tasks.md:59-60)
  tasks 3.2 只要求 L2 live smoke 证明 framework 端落盘布局,3.3 却把 P4 真机 commandlet evidence 标成"选"。本 change 实际改 `ue_scripts/domain_video.py` 的 FileMediaSource 创建、`file_path` 设置和 no-copy 行为;L2 smoke 不执行真实 UE API,stub integration 也不能证明 UE 5.x commandlet 会正确创建/保存 .uasset。项目约定明确 stub 覆盖框架侧交付但不替代真机验证。影响是 UE 端导入在真实 commandlet 下失败时,计划仍可按 L2+pytest 绿进入 finish/archive。
  Recommendation: 把 3.3 提升为 finish 前必需 evidence:若本机有 UE 5.x,必须跑 commandlet 并落 `verification/p4_real_ue.md`;若不能跑,显式记录 user_required blocker/未完成验收,不要把 change 标为完成。
- [medium] tasks.md 漏掉承 round1-F3 的 integration mismatch fences (openspec/changes/fix-export-d12-and-skipped-evidence-filter/tasks.md:55-58)
  承 round1-F3:spec 和 micro_tasks 都要求 `test_p4_domain_video_rejects_non_d12_source_uri` 与 `test_p4_domain_video_returns_failed_on_source_target_mismatch` 守住 source_uri/target_object_path mismatch 路径,但 tasks.md 3.1 只列了重命名、framework drop、missing mp4 三项。若执行者或 finish 检查以 tasks.md 为准,关键 F3 integration fence 可被漏实现而仍勾完 3.1。
  Recommendation: 同步 tasks.md 3.1 和 execution_plan Tests 清单,明确列入这两个 P4 integration cases;若有意只保留 unit fence,必须回写 spec/micro_tasks 降级并说明为什么 integration 层不需要守门。

Next steps:
- 先修订 tasks.md / execution_plan.md / micro_tasks.md 的 Phase C 验证口径。
- 重新跑本轮 plan-stage adversarial review,确认 C.3 与 round1-F3 fences 不再漂移。
