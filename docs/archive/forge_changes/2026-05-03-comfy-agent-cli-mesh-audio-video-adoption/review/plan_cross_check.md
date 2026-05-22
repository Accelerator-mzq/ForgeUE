---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_plan_review.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan adversarial review for OpenSpec change comfy-agent-cli-mesh-audio-video-adoption: review execution_plan.md + micro_tasks.md ...\""
plugin_task_id: bacl5q49i
detected_env: claude-code
triggered_by: "/forgeue:change-apply (S3→S4-S5 transition; Superpowers executing-plans + TDD pending)"
codex_plugin_available: true
created_at: 2026-05-03T14:29:28+08:00
resolved_at: 2026-05-03T14:50:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-plan (4 findings accepted-codex; plan-only revision — execution_plan + micro_tasks updated, contract unchanged)
writeback_commit: 0a31d20
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 plan_cross_check 在调 codex /codex:adversarial-review plan hook 之前冻结 `## A` 段,
  以避免 Claude 看完 codex finding 后回填 ## A(协议自我保护)。
  ## B / C / D 在 codex review 落盘后由 Claude 续写。
  contract_refs 含 execution_plan.md + micro_tasks.md(本 stage 主审对象)+ design/specs/tasks
  (锚点真源)。
---

# S3→S4-S5 Plan Cross-check: comfy-agent-cli-mesh-audio-video-adoption

## A. Claude's Decision Summary (frozen before codex plan review, 2026-05-03 14:29 +08:00)

> 本 stage 起草 execution_plan.md + micro_tasks.md 时 Claude 的关键判断;冻结于 codex plan review 调用之前。
> 列出每条 plan 决策的脆弱点(self-criticism),便于 codex 直接对照源码 + design.md 找漏洞。

- **P1 — Commit 顺序**(execution_plan.md "Task Map"):commit 顺序为 1=config / 2=worker / 3=executor / 4=fence / 5=examples / 6=live smoke / 7=docs。**脆弱点**:commit 2 worker 改动后,如果 commit 3 executor 还没 import worker 新方法,commit 2 head 跑 baseline 可能会因为 `ComfyAgentWorker.__init__` 多了 `model_id` 必传参数而让现有 image-mode 调用站崩(任何老调用 `ComfyAgentWorker(scripts_dir=..., run_id=..., ...)` 的 fence 会 missing keyword arg)。是否需要在 commit 2 同步更新所有现有 image-mode call sites(`generate_image.py:_generate_via_worker` + `tests/unit/test_comfy_subprocess.py` 现有 109 fence)?如果是,commit 2 范围就要扩。

- **P2 — Commit 4 fence 写在 examples bundle 之前**(execution_plan.md commit order rationale):rationale 说「fence 守门 bundle loader 行为」。**脆弱点**:但 fence 内容是 worker / executor 行为,不是 bundle loader 行为;真正守门 bundle loader 的是 `tests/integration/test_example_bundles_smoke.py`(generic structural fence),不是 `tests/unit/test_comfy_subprocess.py`。所以 commit 5 examples 加 bundle 时,真正风险是「generic loader fence 找不到新 bundle 或 prepared_routes 解析错」,而不是 unit fence。commit 顺序 4→5 仍然合理,但 rationale 不准。

- **P3 — Task 7 live smoke 在装了 ComfyUI 的本机**(micro_tasks Task 7):需要双终端 + ComfyUI 启动 + 至少 1 个 image-to-mesh manifest(产 `outputs.glb`)。**脆弱点**:Claude 跑不了这一步(无 ComfyUI 实机访问);命令 step 10 推进 S5 要求「Level 0 PASS + writeback-check exit 0」,但 Level 2 live smoke 是 tasks §9.3 + §7 的明确 step,缺 evidence 会让 finish gate(`/forgeue:change-finish`)阻断 archive。Apply 阶段的实施需要用户参与跑 live smoke。

- **P4 — Task 1.2/1.3/1.5 manifest + params 探明**(micro_tasks Task 1):同样需要 ComfyUI 本机跑 `comfyui_api list / params / run`。**脆弱点**:实施 commit 5 example bundle 之前必须确定 mesh manifest 名 + image input param key 名 + Q9 vertex/face count 暴露情况;这些都是 ComfyUI 本机依赖。Claude 可以用 placeholder 写 bundle(留 `<TBD>` 占位),但 commit 5 head 跑 `test_example_bundles_smoke.py` 会因 placeholder loader 解析错而红灯。

- **P5 — Documentation Sync Gate(Task 8)涉及 7+ 长文档**:SRS / HLD / LLD / test_spec / acceptance_report / CHANGELOG / CLAUDE / AGENTS。**脆弱点**:每个文档可能有现有结构 / 段落约定,我直接改可能与文档原有 narrative 冲突(image change archive 时遇到过类似问题需要二次同步)。Claude 应在改之前先 Read 目标段定位,不直接 Write。

- **P6 — `_generate_via_comfy_worker` 自带 retry loop 用 `ctx.step.retry_policy` 默认值**(execution_plan invariant D9):若 bundle 没声明 retry_policy,`policy = ctx.step.retry_policy or RetryPolicy()` 默认 `max_attempts=3`(stdlib 默认假设)。**脆弱点**:RetryPolicy 默认值是否真的 `3`?需要核对 `RetryPolicy` 源码;若默认是 `1`,本地 mesh 实际只跑一次,与「standard retry」语义不符。

- **P7 — `_run_subprocess_and_validate` 抽出 helper 复用 image-mode + mesh-mode**(execution_plan Task 3):image-mode 现有 subprocess 逻辑(comfy_worker.py:417-459)有自己的特殊处理(GBK encoding fallback / asyncio.create_subprocess_exec 等);抽 helper 时要保留这些。**脆弱点**:image change 归档 spec 写明 image-mode 用的是 sync `subprocess.run` with `encoding="utf-8", errors="replace"`(round 3 G11 R1 fix);若 helper 抽错,image-mode 行为会变。

- **P8 — 越界检测(命令字面要求)scope = design.md 列出的 modules**:execution_plan File Structure 列了 4 个 implementation file + 4 个 test file + 1 个 example bundle + auxiliary docs。**脆弱点**:实际实施可能发现 `framework/run.py` adapter registration 也需要改(虽然 worker 是 executor-side dispatch 不需要 router 注册,但 dry-run probe gate 在哪个文件需要确认);若超出 design scope,需要回写 design 加 file 引用。

- **P9 — Task 6 fence 总数 ~25**(execution_plan + micro_tasks):各 fence 名单已列。**脆弱点**:实施时实际 fence 数可能 ±5(fence 拆分粒度不同);execution_plan 写「~25」是 ballpark,但 tasks §6.7 fence 数会决定 baseline 实测数(549+实测增量,not 硬编码)。fence 名某些可能在实施时合并(例如三个 capability dispatch fence 合一)。

- **P10 — `notes/manifest_audit_<date>.md` 是 evidence 而非 contract**:Task 1 落 manifest_audit 文件作为探明记录。**脆弱点**:manifest 名一旦写入 example bundle + spec + fence,这就成了「事实上的契约」;若 ComfyUI 后续重命名 manifest,本 change 全部产物失效。是否应该在 design 加「manifest 名版本化」决策?当前 design 没说,默认接受这个 fragility(本地用户管 ComfyUI 自己的版本)。

- **P-SelfRiskRanking**:P1 / P3 / P4 是高风险(可能阻断实施);P5 / P6 / P7 是中风险(可能引入回归);P2 / P8 / P9 / P10 是低风险(narrative / scope 调整)。预期 codex plan review 抓 1-2 项 high(P1 commit 2 兼容性 + P3/P4 ComfyUI 实机依赖)+ 1-2 项 medium(P6 RetryPolicy 默认值 + P7 helper 抽象 risk)。

## B. Cross-check Matrix

| ID | Claude's plan choice | Codex's verdict | Codex reasoning(摘要 + file:line)| Resolution | 修复操作(plan-only writeback,**不修 contract**)|
|---|---|---|---|---|---|
| **P-F1 — commit 2 范围太窄,model_id 必填破坏现有 image-mode call sites** | micro_tasks Task 3 commit 2 文件清单只列 `comfy_worker.py`;但 model_id 必填 + commit 2 head 跑 baseline 要求(P1 self-flag 命中)| dispute (high) | 实测 `generate_image.py:278` + `test_comfy_subprocess.py:54/96/110/127` 共 5 处 call sites 用旧签名;commit 2 加 `model_id` 必填 → TypeError | **accepted-codex** | (1) 修订 micro_tasks Task 3 commit 2 范围:加 `generate_image.py` 现有 image-mode call site(line 278)同步加 `model_id="comfy/local"`;加 `tests/unit/test_comfy_subprocess.py` 现有 4 处 fixture call(line 54/96/110/127)同步加 `model_id="comfy/local"`;(2) execution_plan.md File Structure "Implementation files" 表 `comfy_worker.py` Modify 行加注「**Same commit:** 同步更新 `generate_image.py:278` + `test_comfy_subprocess.py` 4 fixture call sites 的 `model_id="comfy/local"` 参数,保证 commit 2 head 跑 baseline pass」;(3) **不**给 model_id 默认值 `"comfy/local"`(违反 D1 invariant fail-fast on unknown id) |
| **P-F2 — Task 6 fence 缺口** | Task 6.6 只列 timeout retry / abort_or_fallback / 远端 1 次调用 fence;缺 wrap unsupported / wrap generic Error / preserve __cause__ / metadata snapshot 隔离 / source path 传递 fence | dispute (high) | spec/probe-and-validation/spec.md 25-90 行 + spec/artifact-contract/spec.md 23-35 行 列了完整 fence 清单,micro_tasks Task 6 是缩略子集 | **accepted-codex** | 修订 micro_tasks Task 6:在每个 sub-step(6.1-6.7)开头加「**fence 清单真源** = `specs/probe-and-validation/spec.md` + `specs/artifact-contract/spec.md`;本 step 列出的 fence 是**示例**,实施时必须比对 spec 的 named tests 全集,逐一落 fence」;Task 6.7 总 fence 数从「~25」改为「以 spec 全集为准,实测 N 落 acceptance_report」 |
| **P-F3 — ComfyUI 实机依赖是 S5 阻断,plan 无 fallback** | Task 1 manifest 探明 + Task 5 example bundle + Task 7 live smoke + Task 9 L0/1/2 全链需要 ComfyUI host(P3 self-flag 命中)| dispute (high) | 实测 micro_tasks 上述 Task 全部依赖 ComfyUI host evidence;无 fallback 路径定义 | **accepted-codex** | (1) execution_plan.md 加新 section「## ComfyUI Host Dependency Gate」明确:Task 1.2/1.3/1.5 + Task 5(具体 manifest + params)+ Task 7(L2 evidence)是 **HARD BLOCKER**,无 ComfyUI host 不可推进;(2) 加可执行交接策略「Phase A(no-host):commit 1-4(config + worker + executor + fence)可在无 ComfyUI host 完成,fence 用 mocked subprocess;Phase B(host-required):commit 5-7(example + smoke + docs)必须 ComfyUI host 协同」;(3) **明确禁止**:用 placeholder bundle 或假 evidence 强行推进;无 host 时 S5 标 blocked,不允许 post-archive defer(命令模板 + ADR-007 类约定) |
| **P-F4 — dry-run probe gate 文件归属错** | execution_plan File Structure 列 `src/framework/run.py` OR `dry_run_pass.py`;commit 3 git add 列 `run.py` | dispute (medium) | 实测 dry-run probe `_check_comfy_reachability` 在 `dry_run_pass.py:117-148`(line 142 显式只匹配 `comfy/local`);`run.py` 不含 probe 逻辑 | **accepted-codex** | execution_plan File Structure 改:将 `src/framework/run.py 或 DryRunPass` 替换为「`src/framework/runtime/dry_run_pass.py`(`_check_comfy_reachability` 方法 line 117-148:gate 列表从 `{"comfy/local"}` 扩为 `{"comfy/local", "comfy/local-mesh"}`)」;micro_tasks Task 4.4 同步;commit 3 git add 列 `generate_mesh.py` + `dry_run_pass.py`(去掉 `run.py`)|

> **额外数据点(非 finding)**:codex 核对 `RetryPolicy.max_attempts` 默认值 = `2`(`policies.py:26`),解决我 P6 self-flag。本地 ComfyUI mesh `_generate_via_comfy_worker` 内部 retry loop 默认跑 2 次 attempts(若 bundle 不显式声明 retry_policy)。execution_plan Task 4.2 invariant table 不需要修改,P6 self-flag 关闭。

## C. Disputed Items Pending Resolution

`disputed_open: 0`。4 项 finding 全 `accepted-codex`,通过 plan-only writeback 解决。

**关键性质区分**:
- 本轮 finding 全部针对 `execution_plan.md` + `micro_tasks.md`(plan layer),**不涉及** `design.md` / specs/ / `tasks.md`(contract layer);
- 这是「plan implementability gap」而非「contract gap」;
- contract 仍是 round 1-4 收敛后状态(commit 95af4c1),不需要回写到 design / tasks / spec;
- 本轮回写只动 execution_plan + micro_tasks。

P-F3 ComfyUI 实机依赖**不是单纯的 plan 修复**,是**用户决策点**:实施 commit 5-7 必须有 ComfyUI host 配合;Claude 单独跑只能完成 commit 1-4(无 host 依赖)。本 cross-check ## D.2 给出 P-F3 的两阶段交接方案。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

| ID | Codex claim 引用 | Claude verify 命令 + 结果 | 结论 |
|---|---|---|---|
| **P-F1** | 5 个 call sites 用旧签名 | `Bash grep -n "ComfyAgentWorker(" src/framework/runtime/executors/generate_image.py tests/unit/test_comfy_subprocess.py` 命中 5 行(generate_image.py:278 + test 4 处)| **真实**:commit 2 head 必 TypeError |
| **P-F2** | Task 6.6 只列 timeout 类 fence;spec 还要求 wrap / metadata 类 fence | `Read execution/micro_tasks.md` Task 6.6 实测内容仅 timeout / abort / 远端 1 次;`Read specs/probe-and-validation/spec.md` 实测有 wrap 4 fence + metadata 多 fence | **真实**:fence 清单是缩略子集 |
| **P-F3** | Task 1/5/7/9 链 ComfyUI host 依赖 | `Read execution/micro_tasks.md` Task 1-9 实测:Task 1.2 `comfyui_api list` / Task 5.1 `<§1.2 选定的 mesh manifest>` / Task 7.3 `python -m framework.run --task ...mesh.json --live-llm` / Task 9.3 `§7 live smoke 重跑` | **真实**:无 host 不可达 S5 |
| **P-F4** | probe 在 `dry_run_pass.py:117-148`,line 142 只匹配 comfy/local | `Bash grep -n "comfy/local\|comfy_reachab" src/framework/runtime/dry_run_pass.py` 命中 line 99/102/117/124/126/142/148/166;line 142 `getattr(r, "model", None) == "comfy/local"`(单一 model id 比较,需要扩为 set membership) | **真实**:plan 文件归属错;实施目标是改 line 142 为 `in {"comfy/local", "comfy/local-mesh"}` |

### D.2 P-F3 ComfyUI host dependency 用户决策(Claude 推荐方案)

按 P-F3 finding,实施分两阶段:

**Phase A(无 ComfyUI host,Claude 可单独完成)**:
- Task 2 commit 1 — config(无依赖)
- Task 3 commit 2 — worker(包含 P-F1 修复:同步 image-mode call sites)
- Task 4 commit 3 — executor + dry-run gate(`dry_run_pass.py:142`)
- Task 6 commit 4 — fence(用 mocked subprocess,P-F2 修复后 fence 全集)
- 此 phase 完成后:`pytest -q` baseline 应升至 ~574(549 + ~25 新 fence);commit 1-4 head 全可 bisect

**Phase B(需 ComfyUI host,用户协同)**:
- Task 1.2/1.3/1.5 — manifest + image_param_key + Q9 探明(必须真机)
- Task 5 commit 5 — example bundle(用 Phase B Task 1 的真实值,**禁止** placeholder)
- Task 7 commit 6 — L2 live smoke evidence(必须真机产 GLB)
- Task 8 commit 7 — Documentation Sync Gate(可在无 host 完成,但 acceptance_report fence 数需 Phase A pytest 实测后填)
- Task 9-10 verify + archive(必须 L2 evidence 才能 finish gate PASS)

无 ComfyUI host 时,本 change S5 标 **blocked**,不允许 post-archive defer。这与 image change archive 流程一致(image change 也需要 L2 evidence,见 `live_smoke_20260503.md`)。

### D.3 Round 1 (design) vs Round 2 (plan) review pattern

- design review(R1-R4):4 轮 finding,主要是字段 / 路径 / 异常族 / 跨子系统不一致 → contract layer 修
- plan review(本轮):4 finding,主要是 commit 拆分 / fence 清单完整性 / host 依赖 / 文件归属 → plan layer 修
- 模式不同:design review 找的是「contract 与源码一致性」;plan review 找的是「plan 与 contract 一致性 + 实施可行性」
- 都印证 forgeue review-driven 协议价值:**writing 与 reviewing 分离**(Claude 写,codex 审),互相补漏
