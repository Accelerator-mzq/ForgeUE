---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_plan_review.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan adversarial review for OpenSpec change comfy-agent-cli-audio-adoption: review execution_plan.md + micro_tasks.md ...\""
plugin_task_id: b4gbt5ero
detected_env: claude-code
triggered_by: "/forgeue:change-apply (S3→S4-S5 transition; Superpowers executing-plans + TDD pending)"
codex_plugin_available: true
created_at: 2026-05-03T19:53:16+08:00
resolved_at: 2026-05-03T20:25:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: pending-user-authorization-then-writeback (6 findings accepted-codex; writeback action items in ## B Resolution)
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 plan_cross_check 在调 codex /codex:adversarial-review plan hook 之前冻结 `## A` 段,
  以避免 Claude 看完 codex finding 后回填 ## A(协议自我保护)。
  ## B / C / D 在 codex review 落盘后由 Claude 续写。
  contract_refs 含 execution_plan.md + micro_tasks.md(本 stage 主审对象)+ design/specs/tasks
  (锚点真源)。Round-1 codex design review 已收敛(commit a12e307);本 plan review 主审
  「plan-vs-contract 一致性」+「commit 顺序 / fence 写法 / 越界风险」。
---

# S3→S4-S5 Plan Cross-check: comfy-agent-cli-audio-adoption

## A. Claude's Decision Summary (frozen before codex plan review, 2026-05-03 19:53 +08:00)

> 本 stage 起草 execution_plan.md + micro_tasks.md 时 Claude 的关键判断;冻结于 codex plan review 调用之前。
> 列出每条 plan 决策的脆弱点(self-criticism),便于 codex 直接对照源码 + design.md 找漏洞。

- **P1 — Commit 顺序的 head-baseline 风险**(execution_plan.md File Structure + micro_tasks.md Commit 1-13):commit 1 = AudioWorker baseline 新建(audio_worker.py 完整文件)→ commit 2 = ModelRegistry config → commit 3 = ComfyAgentWorker 4-dict 扩 audio + generate_audio + magic bytes → commit 4 = GenerateAudioExecutor + ExecutorRegistry 注册 → commit 5 = FailureModeMap → commit 6 = DryRunPass → commit 7 = examples bundle → commit 8 = probe → commit 9-12 = docs → commit 13 = L2 evidence。**脆弱点**:commit 1 head 跑 `pytest -q` baseline 不退化要求 audio_worker.py + test_audio_worker.py 5 fence 全 green;但 commit 1 内部 import `from framework.providers.workers.audio_worker import AudioCandidate, AudioWorker` 需要 `__init__.py` 暴露(否则 import 链断)— Phase 1 mesh `mesh_worker.py` 已经 import 暴露,我**没**在 micro_tasks 显式列出「修改 `src/framework/providers/workers/__init__.py` 暴露 audio_worker 符号」task;若实际项目 `__init__.py` 未自动 re-export,commit 1 head 红灯。

- **P2 — Commit 3 ComfyAgentWorker 加 audio 4-dict 与现有 image+mesh fence 兼容性**(micro_tasks 3.1-3.4):commit 3 编辑 `comfy_worker.py` 4 dict 加 audio entry;**脆弱点**:`__init__` 守门 line 367 错误消息当前是 `f"expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)} (audio / video are follow-on changes; see SRS TBD-009)"` — 加 audio 后,`sorted(...)` 会自动 list 3 个 ids,但**括号注释「audio / video are follow-on」过期**(audio 已加),需要更新为「video 仍 follow-on」。我**没**在 micro_tasks 显式列出「更新 `__init__` 守门错误消息括号注释」micro task;commit 3 head fence `test_unknown_model_id_raises_at_init_lists_audio_in_supported` 可能因消息字面过期而需要修。

- **P3 — Commit 4 与 Step model 真实字段对齐(F1 round-1 修订后的实施验证)**:micro_tasks 4.1a `step_type = StepType.generate, capability_ref = "audio.t2a"`。**脆弱点**:Phase 1 mesh `generate_mesh.py:66-67` 用 `step_type` 作为类属性是确认存在的,但 `ExecutorRegistry.register(executor)` 实际签名(`base.py:69 if executor.capability_ref is None: ... else self._exact[(executor.step_type, executor.capability_ref)] = executor`)读类属性,这意味着 GenerateAudioExecutor 实例化时类属性已经必须存在 — 我**没**确认 `ExecutorRegistry` 是否有「register 时 capability_ref 不能为空字符串」校验;若有,`capability_ref = ""` 触发 wildcard 而非 audio.t2a 精确匹配,bug 不会被 fence catch。

- **P4 — Commit 4 ExecutorRegistry 注册位置**(micro_tasks 4.3):「编辑 `src/framework/run.py` `ExecutorRegistry` setup 段加 `registry.register(GenerateAudioExecutor(...))`」。**脆弱点**:我**没**实际 grep `framework.run` 看 `GenerateImageExecutor` / `GenerateMeshExecutor` 当前 register 位置 + 构造参数;若 mesh executor 是 `GenerateMeshExecutor(mesh_worker=injected_remote_worker)`(pattern b 注入构造),那 audio executor 是否也需要构造时注入(remote AudioCraft worker 当前 None)?Phase 1 mesh executor 实际构造可能比我假设的 `GenerateAudioExecutor(...)` 更复杂。

- **P5 — Commit 4 step.config / step.retry_policy 字段读法不一致**(micro_tasks 4.1c + 4.1d):4.1c `_generate_via_comfy_worker` 写 `policy = ctx.step.retry_policy`(顶层字段 per task.py:37);4.1d `execute` 写 `cfg = ctx.step.config or {}` + `num = int(cfg.get("num_candidates", 1))` + `timeout_s = float(cfg.get("policy", {}).get("timeout_seconds", 300))`。**脆弱点**:我**两处用了不同字段** — `retry_policy` 顶层 vs `config.policy.timeout_seconds`;若 Phase 1 mesh 实际全用顶层 `retry_policy.{max_attempts, timeout_seconds}`(后者也存在于 RetryPolicy schema),则 commit 4 实施时混用两路会让 fence `test_local_comfy_audio_executor_calls_worker_generate_audio_max_attempts_times_on_timeout` 与实际行为不一致。需要 grep `generate_mesh.py` 实际读法验证。

- **P6 — Commit 4 持久化字段**(micro_tasks 4.1d):`repo.put(file_suffix=f".{cand.format}", metadata={"format": cand.format, "duration_seconds": cand.duration_seconds, "sample_rate": cand.sample_rate, "worker_metadata": dict(cand.metadata), ...})`。**脆弱点**:`...` 省略号覆盖了 lineage / variant_kind 等字段;Phase 1 mesh 实际 `repo.put` call site 在 `generate_mesh.py:117-158` — 我**没**核对 audio 路径的 lineage(`source_artifact_ids` 取什么?audio 没上游,应该是 `[]` 或 `[ctx.step.step_id]`?)+ `transformation_kind`(类比 mesh `image_to_3d`,audio 应该是 `text_to_audio` 还是别的?)。这两个字段在 micro_tasks 4.1d 实施时容易错填(audio 没 source artifact 但 lineage 模型可能要求 transformation_kind 非空)。

- **P7 — Commit 5 FailureModeMap priority**(micro_tasks 5.2):「audio wrapped exception 优先匹配(在 generic ComfyWorker / WorkerTimeout 之前)」。**脆弱点**:我**没**检查 Phase 1 mesh `failure_mode_map.py:from_exception` 实装的 isinstance 判定顺序;若 mesh exception 当前在「在 generic 之前」位置,audio 应该在 mesh 之前还是之后?是否需要 audio + mesh 同优先级(各自独立分类)+ generic 兜底?micro_tasks 5.2 没明确这个 ordering 细节,implementation 时可能凭直觉摆顺序导致 fence 5.3f `test_failure_mode_map_audio_takes_priority_over_generic_worker_exception` 没覆盖到真实 priority 错配。

- **P8 — Commit 7 examples bundle JSON 真实 schema 验证**(micro_tasks 7.1):`step_id="audio_t2a" / type="generate" / capability_ref="audio.t2a" / provider_policy={...} / retry_policy={...} / depends_on=[] / config={spec:..., num_candidates:1, seed:42}`。**脆弱点**:我**没**实际 cat `examples/comfy_local_smoke.json` 或 `examples/comfy_local_smoke_mesh.json` 看真实 bundle 顶层结构(`task_id` / `project_id` / `workflow.{workflow_id, name, version, entry_step_id, step_ids, steps[]}` 是不是全 required?字段名是否一致?)。Phase 1 image / mesh bundle 真实写法可能与我 micro_tasks 7.1 的模板有微差,implementation 时容易踩 schema mismatch。

- **P9 — Commit 8 probe_comfy_audio.py 模块顶层零副作用 + opt-in**(micro_tasks 8.1-8.2):沿 Phase 1 mesh probe 模式;**脆弱点**:我**没**实际看 Phase 1 `probes/provider/probe_comfy_mesh.py`(若存在)或其它 provider probe 的实际结构;若 Phase 1 用了某个 helper(`probes/_output.probe_output_dir(tier, name)`),audio probe 应沿用而非自造。模块顶层零副作用守门是 L3 fence `test_glm_probes_have_no_import_side_effects` 自动覆盖,但 probe 内部 `main()` 实装的 lazy-init pattern 我没明确写。

- **P10 — fence 数估算 +45 vs Phase 1 +40**(execution_plan.md "Total fence delta estimate"):fence delta 比 Phase 1 mesh +40 多 5,主因 F5 magic bytes 7 fence + F2 三 except 块 1 fence + audio_worker baseline 5 fence。**脆弱点**:实际 fence 数会随实施细节浮动;若 commit 1-8 head fence 数低于估算,可能漏 fence 守门;若高于估算,可能某个 fence 双重覆盖。**不**硬编码 NFR-MAINT-003 总数(沿 CLAUDE.md 禁令);实测以 `pytest -q` 输出为准。

- **P11 — L2 evidence non-blocking decision**(execution_plan.md Critical Path §5):「§11 L2 evidence 需要用户启 ComfyUI server + Stable Audio Open 模型权重缓存,**non-blocking** for archive(沿 Phase 1 mesh 模式;若 user 不能跑 L2,留 evidence pending marker,archive 时不阻断)」。**脆弱点**:Phase 1 mesh L2 evidence 实际是「partial → full」两阶段(round 5 D10 user 授权方案 A 后才 full pass GLB 3.5MB);archive 在 full pass 之前完成?还是 L2 full pass 后才 archive?我**没**核对 Phase 1 archive timestamp vs L2 full pass timestamp。若 Phase 1 实际是「L2 partial 即 archive,full pass evidence 后补 backfill commit」,本 change 沿用合理;若 Phase 1 实际是「L2 full pass 才 archive」,本 change 不能 non-blocking。

- **P12 — F4 round-1 probe 仅 static read,实测推到 §1.5b implementation 阶段**(notes/audio_subprocess_probe_20260503.md OQ-1/2/3 + execution_plan.md File Structure §11):round-1 通过 `runner.py::extract_outputs` 静态阅读 RESOLVED OQ-1/2/3,但 `python -m comfyui_api run` 实测没跑(server offline)。**脆弱点**:静态阅读源码与实际 stdout JSON 形态可能不完全一致(尤其 `outputs.audio` 是绝对路径 vs 相对 `D:/AI/ComfyUI/outputs/main/<date>/<project>/...` 的路径解析协议;runner.py:31 `COMFYUI_OUTPUT_ROOT = Path(r"D:\AI\ComfyUI\outputs\main")` 暗示**相对路径**输出会被 `extract_outputs` 拼到该 root)— 我 `notes/...md` OQ-1 写「string list of **absolute paths**」是基于 line 224 `images.append(path)` 推断,但没核对 `path` 上游是 `_node_id, node_out` 的字段,可能仍是相对路径。implementation §4.2 写「`outputs.audio` 是 absolute paths string list,**不**需要拼根目录」可能错。

- **P13 — F5 magic bytes 校验 false-negative 风险**(execution_plan.md File Structure 行 + micro_tasks 3.5c-iii):MP3 magic 我列了 4 种 sync byte(`0xFF 0xFB / 0xFA / 0xF3 / 0xF2`),但 MPEG-2.5 layer III sync 是 `0xFF 0xE0` 起头(low 4 bits 含 layer + protection bit + bitrate index 第一位);我列出的 4 种是 MPEG-1 / MPEG-2 layer III 的高 8 bit,不覆盖 MPEG-2.5。若 Stable Audio Open / ACE-Step 实际输出 mp3 用 MPEG-2.5 编码,fence `test_generate_audio_mp3_mpeg_frame_sync_magic_match_accepts` 会 false-negative。**脆弱点**:这种 codec 边角是否需要 design D10 round-2 修订加全 MPEG sync 检测,还是接受「99% 覆盖率,1% 罕见 codec 落 follow-on」?

- **P14 — L2 evidence 客观判定中 duration 校验需要 audio metadata 解析**(tasks §11.4 + spec/examples-and-acceptance Live audio smoke L2 Scenario):「duration 接近 bundle 声明的 `duration_seconds`(±10%)」。**脆弱点**:F4 round-1 已锁定 `duration_seconds = None always`(ComfyUI 不暴露),那 L2 evidence 怎么验 duration?需要在 L2 evidence step 用 stdlib `wave` / `aifc` 或 mutagen 读 audio header parse duration — 但本 change scope 明确不引入 mutagen。Phase 1 mesh L2 没有这个问题(GLB 不含 duration 概念)。**实施时 §11.4 task 没办法执行**,要么放弃 duration 校验,要么 L2 step 引入 stdlib `wave`(只覆盖 wav)+ `aifc`(只覆盖 aifc)+ FLAC 用 raw bytes 解析 STREAMINFO block(几行 stdlib 代码)。Round-2 plan 修订:把 §11.4 (d) 改为「duration 校验跳过(audio metadata parser 在 follow-on change),只验 magic + size」?还是加一个轻量 FLAC 解析 helper?

- **P15 — Phase 1 mesh round-2 codex review 找过的 plan-stage 问题(对照学习)**:Phase 1 plan_cross_check.md 列出 4 个 finding(commit 顺序 / examples 提前 / live smoke ComfyUI 实机依赖 / probe 文件归属错)— 我**没**主动对照 Phase 1 plan-stage 错误清单逐项检查本 change plan 是否复刻同款错误。如 Phase 1 P-F4「`dry_run_pass.py` 文件归属错(原写 `run.py`)」— 本 change tasks §7.1 写法是否准确?需要 grep `_check_comfy_reachability` 在哪个文件确认。

## B. Cross-check Matrix

> Codex review verbatim 落 `review/codex_plan_review.md`(plugin_task_id=b4gbt5ero);verdict=needs-attention NO-SHIP;6 finding(1 critical + 3 high + 2 medium)。

| ID | Codex Finding(摘要) | Severity | Claude's choice(`## A` 引用) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| **F-Plan-1 — bundle JSON schema 用了不存在的嵌套结构** | tasks §8.1 模板用 `task_id` / `project_id` / `workflow.steps[]` 嵌套;真实 loader(`workflows/loader.py:34-36`)读 `raw["task"]` + `raw["workflow"]` + `raw["steps"]` 顶层三段;Phase 1 image / mesh bundle 都是这个结构 | critical | P8 我自我质疑「没实际 cat Phase 1 image / mesh bundle 看真实顶层结构」+ 列了「易踩 schema mismatch」 — 我看到了风险但没**实际查**。 | **accepted-codex** | tasks §8.1 重写 bundle JSON 顶层三段(`task` / `workflow`(无 `steps`)/ `steps`);micro_tasks 7.1 同步;specs/examples-and-acceptance Scenario `examples/comfy_local_smoke_audio.json declares text-to-audio single step` 同步真实结构;loader-fence 断言三段顶层结构 |
| **F-Plan-2 — L2 evidence non-blocking 违反 Phase 1 archive gate** | execution_plan.md:148(Critical Path §5)允许 L2 pending marker 后 archive;Phase 1 mesh execution_plan.md:162-191 显式「HARD BLOCKER + 禁止 post-archive defer L2 evidence + 无 ComfyUI host = S5 标 blocked」;Phase 1 `live_smoke_mesh_20260503_full.md:220` 是「full L2 PASS,可直接走 standard archive」 | high | P11 我自我质疑「没核对 Phase 1 archive timestamp vs L2 full pass timestamp」 — 我承认没查就放宽规则,这是直接违反 Phase 1 hard rule 的随意决策。 | **accepted-codex** | execution_plan.md Critical Path §5 反转:**L2 evidence HARD BLOCKER**(沿 Phase 1 模式),`/forgeue:change-finish` archive 前必须 full L2 PASS;若用户当前无 ComfyUI host,S5 标 blocked,在 `verification/verify_report.md` 显式记录 blocker reason,不允许 archive。`docs/acceptance/acceptance_report.md` Phase 2 audio 行只在 L2 full pass 后标通过。execution_plan.md "Risks" 段的 mitigation 也同步修(去掉「non-blocking;留 pending marker」语)。 |
| **F-Plan-3 — num_candidates>1 会静默只产 1 个 audio artifact** | micro_tasks 4.1c 伪代码 `_generate_via_comfy_worker` 仅一次 `worker.generate_audio(num_candidates=num)` 然后 return;真实 image / mesh worker 在 `comfy_worker.py:427` / `:689` 用 `for i in range(max(1, num_candidates)): ... params.setdefault("seed", call_seed) ... results.extend(self._run_once(...))` 显式 per-candidate loop | high | P3 + P5 我自我质疑了「executor 类属性 / step.config 字段读法」,但**没**自我质疑 num_candidates > 1 实际 candidate count 行为 — 我假定 worker.generate_audio 内部会 loop,但真实 image / mesh 是 worker 内部确实有 loop,我**没**在 micro_tasks 3.5 明确「`generate_audio` 内部含 per-candidate loop」。 | **accepted-codex** | micro_tasks 3.5(commit 3 ComfyAgentWorker.generate_audio 实装)显式加「`for i in range(max(1, num_candidates)): seed_for_call = (seed or 0) + i; params_for_call = dict(comfy_params); params_for_call.setdefault('seed', seed_for_call); ...` per-candidate loop」(沿 image / mesh 模式);design D10 步骤段加 per-candidate loop 描述;tasks §4.4 fence 加 `test_generate_audio_runs_subprocess_num_candidates_times_when_num_gt_one`(num=3 触发 3 次 _run_once_audio + 3 个 candidate);spec/provider-routing Step 5 描述同步「per-candidate loop」 |
| **F-Plan-4 — audio 输出读取缺 symlink / is_file 防护** | micro_tasks 3.5c-ii / 4.2 直接 `data = Path(abs_path).read_bytes()`;真实 image 路径 `comfy_worker.py:541-554` 在读 bytes 前 `src.is_file()` raise + `src.is_symlink()` raise,注释 "G11 R2 fix: reject symlinks ... to prevent a buggy / compromised agent CLI from redirecting reads to arbitrary host files";mesh 路径同(:805-814) | high | 我没自我质疑这一点 — Phase 1 G11 R2 fix 是 round 11 的 hardening,我**完全没注意**到这个 trust boundary 防护的存在。 | **accepted-codex** | micro_tasks 3.5c 加 `src = Path(abs_path); if not src.is_file(): raise WorkerUnsupportedResponse(...); if src.is_symlink(): raise WorkerUnsupportedResponse(...)` 在 `read_bytes` 之前(沿 image / mesh G11 R2 fix 模式);design D10 步骤段同步;spec/provider-routing Step 4 / 5 加防护描述;tasks §4.4 fence 加 `test_generate_audio_missing_path_raises_unsupported_response` + `test_generate_audio_symlink_path_raises_unsupported_response` 2 fence(沿 image / mesh 同款 fence) |
| **F-Plan-5 — L2 duration 校验与 no-parser 设计冲突** | tasks §11.4 (d) 要求 duration ±10% 校验,提到 mutagen / wave / aifc;但 design D10 已锁 `duration_seconds=None always`,artifact-contract spec 也锁 audio metadata 字段 None;wave / aifc 不能覆盖 FLAC / MP3 | medium | P14 我**显式**自我质疑了这个冲突(「§11.4 task 没办法执行」),但没决定走哪一边。 | **accepted-codex(选 A:L2 只验存在+大小+magic bytes+扩展名,duration 标 follow-on)** | tasks §11.4 (d) 删除(改为「duration 校验留 follow-on `audio-metadata-parser` change;本 change L2 evidence 不验 duration」);spec/examples-and-acceptance Scenario "Live audio smoke L2 evidence file is real audio bytes" 第 4 项删除;execution_plan.md Risks 表「L2 evidence 客观判定」行同步 |
| **F-Plan-6 — timeout 字段读写位置与真实 Step / RetryPolicy 不一致** | tasks §5.2 让 executor 读 `cfg.get('policy', {}).get('timeout_seconds')`(嵌套);真实 image / mesh executor 都读 `cfg.get('worker_timeout_s')`(`generate_image.py:83` / `generate_mesh.py:190`);`RetryPolicy` schema(`policies.py:25-30`)只有 `max_attempts / backoff / retry_on`,**无** `timeout_seconds` 字段;我 bundle 模板把 `timeout_seconds` 放进 `retry_policy` — Pydantic strict mode 会 raise unknown field | medium | P5 我自我质疑「需要 grep generate_mesh.py 实际读法验证」 — 我看到了风险但没查。 | **accepted-codex** | tasks §5.2 / micro_tasks 4.1d 改:`timeout_s = cfg.get("worker_timeout_s")`(沿 image / mesh 模式);bundle 模板(tasks §8.1 + execution_plan.md File Structure + spec/examples-and-acceptance Scenario)改:`step.config.worker_timeout_s = 300`(在 config 内,**不**放 retry_policy 顶层);`step.retry_policy = {"max_attempts": 2}`(只保留 RetryPolicy schema 接受的字段);design D9 retry/wrap 伪代码 `policy = ctx.step.retry_policy` 保持(retry_policy 本身正确,只是 timeout 不归它管);spec/provider-routing 相关 Scenario 同步 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。6 项 finding 全部 `accepted-codex`(F-Plan-1 critical + F-Plan-2/3/4 high + F-Plan-5/6 medium);无 `disputed-pending` / `disputed-permanent-drift` 项。

但 contract 回写工作量大(F-Plan-1 critical + F-Plan-2 high 直接阻断 S4-S5 进入 implementation):

- **execution_plan.md**:Critical Path §5 反转 L2 non-blocking(F-Plan-2);File Structure 表 bundle 字段名修(F-Plan-1 / F-Plan-6);Risks 表 mitigation 段对齐
- **micro_tasks.md**:3.5(audio bytes 读取加 is_file / is_symlink 防护;F-Plan-4)+ 3.5(generate_audio 加 per-candidate loop;F-Plan-3)+ 4.1c(timeout 读 `cfg.get("worker_timeout_s")`;F-Plan-6)+ 7.1(bundle 模板真实 schema 顶层三段;F-Plan-1)
- **tasks.md**:§4.2(audio bytes 读取加 is_file / is_symlink 防护 + per-candidate loop)+ §4.4(加 missing path / symlink fence + per-candidate fence,total +3 fence)+ §5.2 / §5.5(timeout 字段位置修 + 删 cfg.policy.timeout_seconds 用 worker_timeout_s)+ §8.1(bundle JSON 顶层三段重写)+ §11.4 (d) 删除 duration 校验
- **design.md**:D9 伪代码 retry_policy 注释加「timeout 不归 retry_policy 管,在 step.config.worker_timeout_s」(F-Plan-6);D10 步骤段加 per-candidate loop + is_file / is_symlink 防护(F-Plan-3 / F-Plan-4);Risks 表「L2 evidence 客观判定」行同步删 duration 校验(F-Plan-5);Migration Plan 段 L2 evidence non-blocking 反转
- **specs/provider-routing/spec.md**:audio Scenarios 中 worker contract Step 4 / 5 加 is_file / is_symlink 防护(F-Plan-4)+ per-candidate loop(F-Plan-3);"ComfyUI worker invokes the agent CLI via subprocess" Scenario 5(audio)中 retry_policy 字段相关描述同步;Step 5 「duration_seconds / sample_rate=None」论据加 metadata-parser follow-on 引用
- **specs/examples-and-acceptance/spec.md**:`examples/comfy_local_smoke_audio.json` Requirement 重写(顶层三段;F-Plan-1);`Live audio smoke L2 evidence file is real audio bytes` Scenario 第 4 项 duration 校验删除(F-Plan-5)
- **specs/probe-and-validation/spec.md**:audio fence 列表加 missing-path / symlink / per-candidate-loop 共 3 个(对照 image / mesh probe-and-validation 镜像)

## D. Independent Verification (file:line audit)

> 沿 ForgeUE memory `feedback_dont_punt_executable_tasks` 风格,**不**把 codex claim 当结论,逐条 file:line 实际查证。

| 验证项 | Codex 引用 | 实际查证(grep / Read 结果) | 验证结论 |
|---|---|---|---|
| **F-Plan-1 V1** loader 真实 schema | `src/framework/workflows/loader.py:31-36` | Read line 32-36:`raw = json.loads(...)`;`expand_model_refs(raw, ...)`;`task = Task.model_validate(raw["task"])`;`workflow = Workflow.model_validate(raw["workflow"])`;`steps = [Step.model_validate(s) for s in raw["steps"]]`。**顶层三段并列**;workflow 不嵌 steps。 | TRUE — codex 引用准确 |
| **F-Plan-1 V2** Phase 1 image bundle 真实结构 | `examples/comfy_local_smoke.json:2-27` | Read:line 2-17 `task` 顶层 + line 18-26 `workflow` 顶层(`workflow_id` / `name` / `version` / `entry_step_id` / `step_ids`,**无** `steps` 嵌套)+ line 28+ `steps` 顶层 array | TRUE |
| **F-Plan-1 V3** Phase 1 step 真实字段 | `examples/comfy_local_smoke.json:28-50` | Read line 28-50:`step_id` / `type:"generate"` / `name` / `risk_level:"medium"` / `capability_ref:"image.generation"` / `provider_policy.{capability_required, models_ref}` / `config.{num_candidates, seed, worker_timeout_s, spec.{comfy_workflow, comfy_params, comfy_lifecycle}}`。**无** `retry_policy` 顶层(我加了);**worker_timeout_s 在 config 内**(不在 retry_policy);**无嵌套 policy 字典** | TRUE — 同时验证 F-Plan-1 critical + F-Plan-6 medium |
| **F-Plan-2 V1** Phase 1 archive HARD BLOCKER 原文 | `archive/.../execution/execution_plan.md:162` + `:179-191` | Read:line 162 `Task 1.2 / 1.3 / 1.5 + Task 5(具体 manifest + params)+ Task 7(L2 evidence)是 **HARD BLOCKER** — 无 ComfyUI host 操作者不可推进`;line 190 `**禁止 post-archive defer L2 evidence**`;line 191 `无 ComfyUI host 时,**S5 标 blocked**,...,不允许 archive` | TRUE — Phase 1 显式锁定 |
| **F-Plan-2 V2** Phase 1 实际 archive timestamp | `archive/.../notes/live_smoke_mesh_20260503_full.md:220` | Read:`**Archive 决策**:full L2 PASS,可直接走 standard archive(不再需要 partial archive 备注)。` | TRUE — Phase 1 实际是 L2 full pass 后 archive,符合 plan |
| **F-Plan-3 V1** image worker per-candidate loop | `comfy_worker.py:427` | Read line 426-437:`results: list[ImageCandidate] = []` + `for i in range(max(1, num_candidates))` + per-iteration `call_seed = (seed or 0) + i` + `params_for_call.setdefault("seed", call_seed)` + `results.extend(self._run_once(...))` | TRUE |
| **F-Plan-3 V2** mesh worker per-candidate loop | `comfy_worker.py:689` | Read line 687-699:同上模式,`results: list[MeshCandidate] = []` + `for i in range(max(1, num_candidates))` + `_run_once_mesh` | TRUE |
| **F-Plan-4 V1** image read symlink + is_file 防护 | `comfy_worker.py:541-557` | Read line 541-557:`for src_str in images: src = Path(src_str); if not src.is_file(): raise WorkerUnsupportedResponse(...); if src.is_symlink(): raise WorkerUnsupportedResponse(...); ... shutil.copy2(src, dst); data = dst.read_bytes()`。注释 "G11 R2 fix: reject symlinks (and Windows junctions) to prevent a buggy / compromised agent CLI from redirecting reads to arbitrary host files (e.g. /etc/secrets via ../symlink)" | TRUE — codex 引用准确 |
| **F-Plan-4 V2** mesh read 同等防护 | `comfy_worker.py:805-814` | Phase 1 archive grep 已 confirm mesh 路径同模式:`outputs.glb path is a symlink, refusing to follow` | TRUE |
| **F-Plan-5 V1** tasks §11.4 (d) duration 校验 | `tasks.md:349` | Read:`(d) duration ≈ \`comfy_params.duration_seconds\`(±10%)— 用 \`mutagen\` 或 \`wave\`/\`aifc\` 标准库读 header,不用 ffprobe`。与 design D5 / D10 + artifact-contract spec(`duration_seconds=None always`)冲突 | TRUE |
| **F-Plan-6 V1** image executor timeout 读法 | `generate_image.py:83` | grep:`timeout_s = cfg.get("worker_timeout_s")` — 直接从 `cfg`(= `step.config or {}`)读 `worker_timeout_s` 字段,**不**走 nested `policy.timeout_seconds` | TRUE |
| **F-Plan-6 V2** mesh executor timeout 读法 | `generate_mesh.py:190` | grep:`timeout_s = cfg.get("worker_timeout_s")` — 同上 | TRUE |
| **F-Plan-6 V3** RetryPolicy schema 字段 | `src/framework/core/policies.py:25-30` | Read:`class RetryPolicy(BaseModel): max_attempts: int = 2; backoff: Literal["fixed", "exponential"] = "fixed"; retry_on: list[str] = Field(...)`。**无** `timeout_seconds` 字段;我把 `timeout_seconds` 放进 retry_policy 是 schema mismatch,Pydantic strict mode 会 raise | TRUE |

**所有 6 finding 全部独立验证 TRUE**。无 `disputed-permanent-drift`。Verdict NO-SHIP 是合理的:F-Plan-1(critical bundle 无法 load)+ F-Plan-2(违反 archive gate)+ F-Plan-3(num_candidates broken)+ F-Plan-4(trust boundary missing)联合作用 = 实施期间会立即出 KeyError、无 candidate 多产、安全漏洞、L2 evidence 缺失即 archive。

## 后续动作(post-cross-check)

1. **F-Plan-1/2/3/4/5/6 writeback**:统一一次性回写 6 finding(scope:execution_plan.md / micro_tasks.md / tasks.md / design.md / 4 spec deltas);沿 round-1 design writeback 模式,落 commit(`feat(openspec): comfy-agent-cli-audio-adoption plan-stage round-1 writeback - 6 findings accepted-codex`)+ backfill `writeback_commit` hash。
2. **写完跑** `forgeue_change_state.py --writeback-check` 确认 exit 0 + 0 DRIFT。
3. **可选 round-2 plan review**:重新跑 codex /codex:adversarial-review 确认 round-1 修订收敛(plan-stage round-2);若 codex 全 low / no finding,直接进 S4 implementation。
4. **进 S4** 跑 Superpowers executing-plans + TDD;按 commit 1-13 链落代码。
