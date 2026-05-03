---
change_id: comfy-agent-cli-audio-adoption
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_design_review.md
plugin_command: "/codex:adversarial-review --background \"design review for comfy-agent-cli-audio-adoption (S2 contract): TBD-002 lift + ComfyUI audio capability dispatch, AudioWorker ABC baseline, 4-dict capability table audio row, no source bytes path (text-to-audio), format whitelist {flac,mp3,wav}, audio.t2a step type registration\""
plugin_task_id: bktgw8l62
detected_env: claude-code
triggered_by: "/forgeue:change-plan (interactive Claude Code session, S2→S3 transition)"
codex_plugin_available: true
created_at: 2026-05-03T18:42:31+08:00
resolved_at: 2026-05-03T19:10:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (6 findings accepted-codex; pending writeback commits — see ## B Resolution column + post-cross-check action plan)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 cross-check 在调用 codex /codex:adversarial-review 之前冻结 `## A. Decision Summary` 段,
  以避免 Claude 看完 codex finding 后回填 ## A(协议自我保护)。
  ## B / C / D 在 codex review 落盘后由 Claude 续写。
  contract_refs 含 5 个 spec delta 文件以确保 codex 同时审 design + 全部 spec deltas。
---

# S2→S3 Design Cross-check: comfy-agent-cli-audio-adoption

## A. Claude's Decision Summary (frozen before codex run, 2026-05-03 18:42 +08:00)

> 本 change 起草时 Claude 的关键判断(冻结于此刻);Claude 不允许在看完 codex review 后回填本段。
> 列出每条决策的具体引用 file:line + 可被质疑的脆弱点(self-criticism),便于 codex / 后续 reviewer 直接对照。
> 沿 Phase 1 mesh(`comfy-agent-cli-mesh-audio-video-adoption`,2026-05-03 归档)的 D1-D10 框架,本 change 的偏离点列在 D7 / D8 / D10 / D-Audio-Baseline / D-TBD-Lift。

- **D1 — Capability dispatch via model id 沿用 Phase 1 协议**(design.md §Decisions D1):`_CAPABILITY_BY_MODEL_ID` 表扩第三 entry `"comfy/local-audio": "audio"`;bundle 不引入 `outputs_kind` 字段;unknown id `__init__` raise(沿 Phase 1 D1 规则)。**脆弱点**:Phase 1 D1 已锁,本 change 字典扩展是 forward-compatible,但若 ComfyUI 同一 manifest 既能产 image 又能产 audio(可能性低,但 Stable Audio 可能顺手输出 spectrogram PNG)— 我已在 D2 把 audio 的 `_AUXILIARY_OUTPUT_KEYS_BY_CAP["audio"] = set()` 锁紧(无容忍),mesh-mode 容忍 PNG preview 是 auxiliary,但 audio-mode 不容忍。这种 asymmetry 是否合理?是否应让 audio-mode 也容忍 `outputs.images` 作为 spectrogram preview?

- **D2 — 4-dict 三段表 audio row 落子**(design.md §Decisions D2):`_REQUIRED_OUTPUT_KEY["audio"] = "audio"`;`_AUXILIARY_OUTPUT_KEYS_BY_CAP["audio"] = set()`;`_REJECTED_OUTPUT_KEYS_BY_CAP["audio"] = {"images", "glb", "video"}`。**脆弱点 1**:OQ-1(design Open Questions §OQ-1):ComfyUI agent CLI 的实际 outputs key 是否真叫 `outputs.audio`?manifest `outputs.primary = "audio/flac"` 是 declaration,实际 ComfyUI agent CLI stdout key 名可能不同(如 `outputs.audio_files`)。tasks §1.5 推到 implementation 阶段实地探明;若不一致,4-dict 修订是 round-2 writeback 工作量。**脆弱点 2**:audio capability 完全无 auxiliary tolerance,与 mesh 容忍 `outputs.images` 不对称;若用户实际遇到 audio manifest 顺带产 PNG spectrogram(罕见但可能),会被 raise — 是否应预留 `auxiliary={"images"}` 允许 spectrogram preview?

- **D3 — Scope split:audio-only ComfyUI + audio worker baseline,远端 AudioCraft follow-on**(design.md §Decisions D3 + Goals/Non-Goals):本 change scope = AudioWorker ABC + AudioCandidate + GenerateAudioExecutor + audio.t2a step type + ComfyUI audio capability;远端 AudioCraft 独立 follow-on;ComfyUI video Phase 3 follow-on。**脆弱点 1**:用「ComfyUI 是 audio worker 第一真实客户」作为 lift TBD-002 的论据,但 TBD-002 原义是「待音频资产需求明确」— 当前用户只需 ComfyUI audio,AudioCraft 真实需求未到。这种「以第一客户立 ABC」的模式在 mesh 路径不存在(mesh ABC 已建于 Hunyuan3D 时代);audio 没有 free baseline 是真实差异,但 codex 可能 raise 「单一客户驱动 ABC 设计是 YAGNI 反向」— 我应该在 design / proposal 里更显式地论证 ABC 设计选择不会被 ComfyUI specifics 污染。**脆弱点 2**:change name `comfy-agent-cli-audio-adoption` 强调 ComfyUI 接入,但实际 scope 也包含 audio worker baseline(TBD-002 lift);名字与 scope 不完全对应,是否应改 `comfy-audio-and-audio-worker-baseline-adoption`?(沿 Phase 1 mesh 的 umbrella name 反惯例同模式;但 Phase 1 是 split scope 的反惯例,本 change 是 expanded scope 的反惯例)

- **D4 — ADR-007 边界沿用 `pricing.per_task_usd > 0`**(design.md §Decisions D4):本地 ComfyUI audio `pricing: null` → 非 premium → 内部 retry loop 用 `policy.max_attempts`;远端 audio worker(future)`per_task_usd > 0` → premium → strict no-silent-retry。**脆弱点**:Phase 1 round 4 R4-F1 提到 wrapped MeshWorkerTimeout 走 `mesh_worker_timeout` mode 的 `Decision.abort_or_fallback`(NOT retry_same_step),路由优先级要求 wrapped audio 异常**在** generic `WorkerTimeout` 之前匹配。tasks §6.2 显式说了「wrapped audio 异常必须**在** generic ComfyWorker / WorkerTimeout 之前匹配」,但 design 段没显式记录这个 priority order。是否应该在 design D4 加一段类似 Phase 1 R4-F1 的 priority 修订?

- **D5 — AudioCandidate.metadata provenance**(design.md §Decisions D5):AudioCandidate.metadata 5 keys + 3 optional keys(`duration_seconds` / `sample_rate` / `format_detected`);沿 Phase 1 mesh `MeshCandidate.metadata["worker_metadata"]` 模式,通过 `repo.put(metadata={"worker_metadata": dict(cand.metadata), ...})` 落 Artifact.metadata。**脆弱点**:`AudioCandidate.duration_seconds` / `sample_rate` 同时也是 SRS FR-STORE-004 audio metadata 字段,我设计时把它们放在 AudioCandidate 顶层(NOT metadata 子树)+ 同时又出现在 metadata 里(`metadata["duration_seconds"]` 是 best-effort 解析存的);双重存储路径混乱:executor 在 `repo.put` 时是该读顶层字段还是 metadata 子键?artifact-contract spec 写的是「`Artifact.metadata.duration_seconds`(top-level)」,但 AudioCandidate 顶层字段是否会冗余?

- **D6 — comfy_lifecycle: "none" only,沿用 Phase 1 D6**(design.md §Decisions D6):无新增 lifecycle 路径,沿 SRS TBD-010 follow-on。**脆弱点**:无(全沿用 Phase 1 锁定的限制)。

- **D7 — text-to-audio 路径,无 source bytes**(design.md §Decisions D7):audio executor SHALL NOT 调 `_resolve_source_image`,SHALL NOT 写 source bytes,SHALL NOT 读 `FORGEUE_COMFY_INPUT_DIR`。**脆弱点 1**:此决策与 Phase 1 mesh `_resolve_source_image` + `FORGEUE_COMFY_INPUT_DIR` 路径完全不同,实施时 GenerateAudioExecutor 的 `execute` 方法会有大段代码与 GenerateMeshExecutor 不同;是否应抽公共 `_dispatch_to_comfy_worker` helper?目前 design 让两个 executor 各自实现 `_generate_via_comfy_worker`,代码重复。**脆弱点 2**:audio 当前 scope=text-to-audio only(无 audio-to-audio 风格迁移);若未来 ComfyUI 暴露 audio-to-audio manifest,executor 接 source audio bytes 的协议未预留;但 spec 已显式 「out of scope」,follow-on 加。

- **D8 — Audio prompt 直接进 spec.comfy_params**(design.md §Decisions D8):bundle 作者写 manifest-aware 字段(`text` / `tags` / `lyrics` / `negative_prompt`);executor 不解构 / 不验证 / 不注入。与 mesh 的 `comfy_image_param_key` 模式相反。**脆弱点 1**:用户切换 manifest(ACE-Step ↔ Stable Audio)需要手工调整 `comfy_params` keys(`tags` vs `text`);bundle 作者错填 key 名时,error 来自 ComfyUI agent CLI 而非 ForgeUE 的 friendly check。是否应该在 GenerateAudioExecutor 加 manifest-aware key validation(对照 manifest schema 检查 prompt key 存在)?**脆弱点 2**:若 manifest 是 negative_prompt REQUIRED 但 bundle 没给,ComfyUI agent CLI 报 `Missing required param`,wrapped 为 `AudioWorkerUnsupportedResponse`;用户体验不好。design 假设 manifest schema 自身的 REQUIRED 标记由 `python -m comfyui_api params --workflow <name>` 暴露,但 ForgeUE 不二次校验。

- **D9 — AudioWorker ABC 签名 + internal retry loop**(design.md §Decisions D9):`generate_audio(spec, num, seed, timeout_s)` 签名,**no `prompt: str`** 参数(prompt 在 spec 里)。executor 内部 retry loop bounded by `policy.max_attempts`;wrapped exception with `__cause__`。**脆弱点 1**:ABC 签名不接 prompt 是为了与 ComfyAgentWorker(prompt 在 spec)对齐;但未来远端 AudioCraft worker 可能更习惯 `generate_audio(prompt: str, num, seed, timeout_s)` 签名(直接接 string)。ABC 现在的签名让远端 AudioCraft worker 必须从 spec 里挖 prompt,可能反向产生「spec 字段名不统一」(AudioCraft 期望 `spec["prompt"]`,ComfyUI 期望 `spec["comfy_params"]["text"]`)。**脆弱点 2**:retry loop 在 executor `_generate_via_comfy_worker` 内部实现,而不是 worker 自己实现 — 这与 Phase 1 mesh 模式一致,但 ABC 自身没说明 retry 由 caller 处理。是否应该在 ABC docstring 显式声明 retry policy 是 caller 责任?

- **D10 — AudioCandidate.format 检测从文件扩展名**(design.md §Decisions D10):格式 ∈ {flac, mp3, wav} whitelist;`Path(rel).suffix.lower()[1:]`;不在 whitelist raise。`repo.put(file_suffix=f".{cand.format}")` 与 mesh 单一 `.glb` 不同。**脆弱点 1**:格式检测不读 magic bytes(FLAC `fLaC` / MP3 `ID3` 或 `0xFF 0xFB` / WAV `RIFF`),只信任扩展名;若 ComfyUI 写出错误扩展名(如 `.flac` 内容是 mp3),ForgeUE 不会发现;UE `unreal.SoundFactory` 可能在 import 时 raise。Phase 1 mesh GLB 强制 magic bytes 二次校验(FR-WORKER-006);audio 不强制,是否过松?**脆弱点 2**:whitelist 只接受 3 种格式;若用户实际遇到 ogg / opus / m4a manifest(罕见),会被 raise;follow-on change 加 — 当前无 forward-compat hook(没有「expected_audio_formats: list[str]」可配置字段)。

- **D11 — Live smoke 选 Stable Audio Open**(design.md §Decisions D11):理由:模型权重小(~2GB)/ 节点解析最稳;ACE-Step custom node missing 风险高。**脆弱点**:Stable Audio Open 1.0 模型 license 是 Stability AI Community License(部分非商业限制),企业用户可能需要审查;design 未提及 license issue。是否应在 design Risks 里加一项?

- **D-Audio-Baseline — TBD-002 lift 走 ABC + 第一客户**(design.md §Goals + §D3):本 change 同步建 AudioWorker / AudioCandidate / GenerateAudioExecutor / audio.t2a step type;远端 AudioCraft 独立 follow-on(`audio-worker-audiocraft-adoption`)。**脆弱点 1**:Phase 1 mesh 复用既有 mesh ABC(Hunyuan3D 时代已建好),Phase 2 audio 没有这种 free baseline,本 change 比 Phase 1 多 ~2 个 commit(audio_worker.py 新建 + GenerateAudioExecutor 新建);估算 +34 fence(对照 Phase 1 +40)— 实际工作量是否被低估?implementation 期间可能踩 ABC 设计反复(尤其 OQ-1/2/3 的 ComfyUI subprocess 实际行为差异)。**脆弱点 2**:TBD-002 原义「Audio worker(AudioCraft 接入),待音频资产需求明确」— 用户当前没 AudioCraft 需求,本 change 用 ComfyUI 第一客户立 ABC,是否应该在 SRS §7.3 TBD-002 行写明「lift 后,AudioCraft 接入 = 走 ABC 第二客户」,避免后续 reviewer 看到 TBD-002 marked done 但远端 AudioCraft 协议没接而困惑?

- **D-TBD-Lift — TBD-002 状态变更**(proposal.md + design.md §3 「同步 lift TBD-002」):SRS §7.3 TBD-002 从「待音频资产需求明确」改为「audio worker baseline 已落地;远端 AudioCraft 协议落地待独立 follow-on change」。**脆弱点**:TBD lift 通常应有独立的 review 流程;本 change 把 lift 包含进 ComfyUI audio scope 里,codex 可能 raise「TBD lift 应单独走 ADR + change」。是否应该把 TBD-002 lift 拆成单独的 change(`audio-worker-baseline-tbd-002-lift`)?但拆分会让本 change 阻塞,且 ABC 设计与 ComfyUI 第一客户高度耦合,拆分价值有限。

- **D-Spec-MODIFIED-Coverage — 4 个 MODIFIED Requirements**(specs/provider-routing/spec.md):本 change MODIFIED 4 个 Phase 1 已落盘的 Requirements:
  - `ComfyAgentWorker dispatches by capability inferred from model id` — 加 audio entry + Scenario
  - `ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)` — 表扩 audio row + 5 个 audio Scenario
  - `ComfyUI worker invokes the agent CLI via subprocess` — capability 表扩 audio + Scenario
  - `Non-OpenAI protocols ship dedicated adapters` — pattern (c) 扩 GenerateAudioExecutor + Scenario
  
  **脆弱点 1**:OpenSpec MODIFIED 要求「include full updated content」— 我已包含完整 Requirement 文本(去掉「future」标记,加 audio 实际值);但 Phase 1 spec 主文件最后会被 archive 时 sync,本 change 里 MODIFIED 段是否会与 Phase 1 已 sync 进 specs/ 主文件的内容兼容?需要 codex 确认。**脆弱点 2**:`ComfyAgentWorker output validation is capability-aware` 表里 video 行还是「(future) TBD by `comfy-agent-cli-video-adoption`」未填实;若我 MODIFIED 时改写整张表只填 audio + 留 video future,Phase 3 video change 还需要再次 MODIFIED 同一 Requirement;是否每次都全文复制是 OpenSpec 反惯例?

- **D-Tasks-CommitOrder — 13 commit chain**(tasks.md §1-§13):commit 1=AudioWorker baseline → 2=ModelRegistry → 3=ComfyAgentWorker dispatch → 4=GenerateAudioExecutor → 5=FailureModeMap → 6=DryRunPass → 7=examples bundle → 8=probes → 9-12=docs sync → 13=L2 evidence。**脆弱点 1**:commit 1 (audio_worker.py) 在 commit 2-3 之前先落盘,但 commit 1 的 fence test 引用 `AudioWorker` ABC 时还没有 client;这种「ABC 先建,client 后建」的顺序在 git log 里看起来反直觉(应该有 client 才有 ABC)。是否应该把 commit 1 + 3 + 4 合并为一个 commit?但合并会让 commit diff 巨大(同时碰 worker / executor / loader),review 难。**脆弱点 2**:commit 7 examples bundle 在 commit 5 fence test 之前 — Phase 1 mesh 实践中 fence 在 examples 之前(因为 fence 守门 examples loader);本 change tasks order 与 Phase 1 不一致,可能让 commit 7 head 跑 baseline 失败(loader fence 还没加,bundle 解析行为未守门)。是否应交换 §7 ↔ §8?

- **D-DryRun-Probe-Extension — gate set 扩 audio**(tasks.md §7):`_check_comfy_reachability` gate set `{comfy/local, comfy/local-mesh, comfy/local-audio}`;`probe_sync` 不变(只测 `comfyui_api status`,与 capability 无关)。**脆弱点**:沿 Phase 1 模式,无独立脆弱点。

- **D-AUXILIARY-Asymmetry — audio 完全无 auxiliary tolerance**(design D2 + spec/provider-routing audio row):mesh 容忍 `outputs.images`(PNG preview 罕见);audio 不容忍任何 auxiliary。**脆弱点**:asymmetry 设计可能让 audio capability 在某些 future manifest 上变得脆弱;但 Phase 2 实际 manifest(ACE-Step / Stable Audio)都不出 auxiliary,本 change 选「严格 reject」可让 implementation 期间踩坑时 fail-fast 而非静默漏检。是否应该至少留一个 forward-compat hook(在 design 里说明 follow-on 加 spectrogram 路径会需要扩 auxiliary set)?

## B. Cross-check Matrix

> Codex review verbatim 落 `review/codex_design_review.md`(plugin_task_id=bktgw8l62);verdict=needs-attention NO-SHIP;6 finding(2 high + 4 medium)。

| ID | Codex Finding(摘要) | Severity | Claude's choice(`## A` 引用) | Resolution | 修复操作(待落盘 + commit) |
|---|---|---|---|---|---|
| **F1 — audio.t2a 运行时契约错误** | runtime-core spec 用 `step.kind`,但 `Step` 真实模型是 `type: StepType` + `capability_ref: str`(`src/framework/core/task.py:30-43`);loader 仅做 `Step.model_validate`(`workflows/loader.py:36`);ExecutorRegistry 按 `(step.type, step.capability_ref)` 查找(`runtime/executors/base.py:75`);现有 generate_image / generate_mesh 都用 `step_type = StepType.generate` + `capability_ref = "image.generation"` / `"mesh.generation"`(`generate_image.py:56-57`、`generate_mesh.py:66-67`)。我的 spec/runtime-core/spec.md "audio.t2a step type registered" + tasks §5.4 "loader.py 注册 audio.t2a step type" + bundle JSON `"kind": "audio.t2a"` 与现有 5 step type(`generate / review / select / validate / export`)枚举不兼容。 | high | D-Tasks-CommitOrder + D-Spec-MODIFIED-Coverage 我已自我质疑 commit 顺序与 OpenSpec 反惯例,但**没有**自我质疑「step.kind 不是真实运行时模型」— 这是我设计盲点,完全没注意到 `StepType` 枚举锁定 + `capability_ref: str` 才是路由 key。Phase 1 mesh executor `step_type = StepType.generate` 已是榜样。 | **accepted-codex** | (1) `specs/runtime-core/spec.md` 整段重写:`audio.t2a step type registered` Requirement → `audio.t2a capability_ref dispatched to GenerateAudioExecutor`,描述「`Step.type = StepType.generate`(沿用现有枚举,**不**新增 step type)+ `Step.capability_ref = "audio.t2a"` + `GenerateAudioExecutor.step_type = StepType.generate, capability_ref = "audio.t2a"` + 在 `framework.run` 注册 executor」;(2) `specs/examples-and-acceptance/spec.md` 「ComfyUI audio live smoke bundle」Requirement 修:bundle JSON 用 `"type": "generate"` + `"capability_ref": "audio.t2a"`,顶层 `provider_policy`/`depends_on`/`config`(NOT under config);(3) `tasks.md` §5.2(`step_kind = "audio.t2a"` → `step_type = StepType.generate, capability_ref = "audio.t2a"`)+ §5.3-§5.4(loader 注册改 `framework.run` 注册 ExecutorRegistry)+ §5.6 fence 名调(`test_audio_t2a_*step_kind_*` → `test_audio_t2a_capability_ref_*`)+ §8.1 examples bundle JSON 重写;(4) `proposal.md` Impact 段「workflow loader 注册第 N 个 step type」改为「executor registry 加 `(StepType.generate, "audio.t2a")` entry」;(5) `provider-routing/spec.md` audio Scenarios 中的 `step.kind="audio.t2a"` 全改 `step.type=StepType.generate` + `step.capability_ref="audio.t2a"` |
| **F2 — retry/wrap 伪代码 bare raise** | `design.md:262` 最后失败 `raise`(裸)重抛 `ComfyWorker*` 而非 `AudioWorker*` → FailureModeMap 看不到 audio_worker_* mode,abort_or_fallback 失效;`design.md:249-260` 单 except 块 retry 全部异常类型,deterministic unsupported 也 retry → GPU subprocess 重跑无意义,违 tasks fence `test_local_comfy_audio_executor_does_not_retry_on_worker_unsupported_response`。Phase 1 mesh `generate_mesh.py:160-172` 实装是正确分裂三 except 块:`_ComfyWorkerTimeout` → wrap + 条件 retry + `raise wrapped from exc`;`_ComfyWorkerUnsupportedResponse` → 不 retry + `raise MeshWorkerUnsupportedResponse(...) from exc`;`_ComfyWorkerError` → 不 retry + wrap。 | high | D9 我自我质疑 ABC docstring retry policy 责任,但**没有**自我质疑伪代码 bare `raise` + 单 except 全 retry 的语义错误。Phase 1 round 2 R2-F2 已经吃过同款苦头(retry budget critical fence)— 我直接复制粘贴了 round 1 模板没对照 round 2 修订。 | **accepted-codex** | (1) `design.md` D9 伪代码重写为三 except 块(对照 `generate_mesh.py:160-172`):`_ComfyWorkerTimeout` 走 retry + 最后 `raise AudioWorkerTimeout(...) from exc`;`_ComfyWorkerUnsupportedResponse` 立即 `raise AudioWorkerUnsupportedResponse(...) from exc`;`_ComfyWorkerError` 立即 `raise AudioWorkerError(...) from exc`;(2) `tasks.md` §5.2 实装伪代码同步重写;(3) 新增 fence `test_local_comfy_audio_executor_unsupported_short_circuits_first_attempt`(deterministic 不重试)+ 维持 `test_local_comfy_audio_executor_calls_worker_generate_audio_max_attempts_times_on_timeout`(只对 timeout 重试)|
| **F3 — AudioCandidate.duration_seconds 顶层 vs metadata 冲突** | `design.md:115-127` D5 `Rejected` 顶层字段(line 127:「duration / sample_rate 应该走 metadata 而非强制顶层」),但 D10(`design.md:357-361`)实际构造 `AudioCandidate(..., duration_seconds=parsed_or_None, sample_rate=parsed_or_None)` 用顶层字段;`provider-routing/spec.md:116` 同顶层;`artifact-contract/spec.md:41` Scenario 用 `cand.duration_seconds == 10.0`(顶层访问);`proposal.md` 写「duration_seconds、sample_rate」作为 dataclass 字段。D5 说「Rejected 顶层」,其它所有地方都用顶层 — 真实矛盾。 | medium | D5 我自我质疑「双重存储路径混乱」+「顶层字段 vs metadata 子树」,但**没有**做内部一致性 audit;我写完 D10 + 各 spec 之后**没有**回头校对 D5 立场是否还自洽。 | **accepted-codex** | (1) `design.md` D5 「Alternative 考虑 Rejected」段反转(顶层字段 ACCEPTED,理由:与 SRS FR-STORE-004 audio metadata 字段一致 + executor 持久化只读顶层避免 metadata 子树双重 source)+ 删 D5 optional keys 列表中的 `duration_seconds` / `sample_rate`(只保留 `format_detected` 作为 internal-only debug 字段;实测如果不需要也删);(2) `proposal.md §1` 描述对齐(顶层字段 + `| None = None`);(3) `tasks.md §2.2` AudioCandidate dataclass 已经写顶层字段(只是缺 `| None` 默认),加 `duration_seconds: float | None = None` + `sample_rate: int | None = None`;(4) artifact-contract Scenario 改:`worker_metadata` 仅 provenance(comfy_*),audio metadata 字段(`format` / `duration_seconds` / `sample_rate`)只从 candidate 顶层读 |
| **F4 — OQ-1/2/3 冻结成 REQUIRED spec** | `design.md:351-361` OQ-1/2/3 承认 ComfyUI agent CLI 真实 outputs 字段名 / batch 数量 / metadata 暴露形式都是未探明的外部协议;但 provider-routing spec(line 108-120 worker contract)+ 4-dict `_REQUIRED_OUTPUT_KEY["audio"] = "audio"`(`design.md:79-87` D2)已冻结。Phase 1 round 5 D10 实施期间发现 source bytes 必须写到 ComfyUI input/(round 1-4 假设错误)是同款先例。S2 不应把外部未验证协议当事实。 | medium | OQ-1/2/3 我**显式标记**为 implementation 阶段探明,且自我质疑「Phase 1 mesh 经验是 round 5 D10 实施期间发现 source bytes 必须写到 ComfyUI input/」;但**没有**接受这个教训反推「应该在 S2 跑 probe 而非 implementation 第二周」。codex 与我自我质疑同向。 | **accepted-codex** | (1) `tasks.md §1` 加 §1.5a「**S3 阻塞 probe**:跑真实 `python -m comfyui_api run --workflow Audio_Workflows/audio_stable_audio_example --params <minimal> --project test_audio_probe --lifecycle none --timeout 180`,记录 stdout JSON 完整结构(`outputs.audio` key 名 / list 长度 / `outputs.metadata.audio` 是否存在 / 各字段类型),写 `notes/audio_subprocess_probe_<date>.md`;若发现协议偏差(如 outputs key 不是 `audio`),先 round-2 design / spec / tasks 修订再进 §2」;(2) `design.md` OQ-1/2/3 标记从「resolve at G2 implementation 第二周」改为「**resolve at S2→S3 transition,本 cross-check round 后立即跑 probe**」;(3) 本 cross-check 同 commit 落 `notes/audio_subprocess_probe_<date>.md`(若 ComfyUI 现可用)或 `notes/audio_subprocess_probe_pending.md`(若 ComfyUI 不可用,留 explicit pending marker;不 advance S3 直到 probe 完成) |
| **F5 — 扩展名检测 vs artifact-contract「扩展名等同 payload」** | `provider-routing/spec.md:112-116` Step 3 仅 `Path(abs_path).suffix.lower()` 检测,Step 5 直接 `read_bytes()`;`artifact-contract/spec.md:17` 声称「`file_suffix=f".{cand.format}"` matches actual payload bytes」— 推论不成立(`.flac` 文件可能内容是 MP3 / HTML 错误页 / 截断)。Phase 1 mesh FR-WORKER-006 强制 GLB magic `b"glTF"` 二次校验;audio 没有强制等价物。`design.md:296` 「FLAC magic bytes 校验本 change scope=不强制」是错的让步。 | medium | D10 我**显式自我质疑**「不读 magic bytes,只信任扩展名;若 ComfyUI 写出错误扩展名,ForgeUE 不会发现」;但选择「whitelist 已防 weird 格式」作为 mitigation,这个 reasoning 不成立(whitelist 只挡 ext 不在三选一,挡不住扩展名错配 payload)。codex F5 与我自我质疑同向但更严厉。 | **accepted-codex** | (1) `design.md` D10 「FLAC magic bytes 校验」段反转:本 change scope=**强制**(沿 FR-WORKER-006 mesh 模式);加 magic bytes 表:`flac` → `b"fLaC"`;`mp3` → `b"ID3"` 或 MPEG frame sync `0xFF 0xFB` / `0xFF 0xFA`(任一 4-byte head);`wav` → `b"RIFF"` + offset 8 `b"WAVE"`(double-check);(2) `provider-routing/spec.md` Step 4 加「Magic bytes 二次校验:read_bytes() 后,前 4 字节 / 前 12 字节(WAV)对照 format-specific magic;不匹配 raise `WorkerUnsupportedResponse`(wrapped to `AudioWorkerUnsupportedResponse`)」;(3) `tasks.md §4.4` fence 加 `test_generate_audio_flac_magic_mismatch_raises_unsupported_response` × 3 format;(4) `artifact-contract/spec.md` Scenario「format aware file_suffix matches actual payload bytes」加 magic-verified 前提声明 |
| **F6 — Stable Audio Open license 风险未记** | `design.md:300-306` D11 选 Stable Audio Open 1.0 作为 L2 默认 manifest;Risks/Trade-offs(line 316+)无 license 项;Stability AI Community License 有 $1M annual revenue 商业门槛(sources cited:https://stability.ai/license / https://stability.ai/news-updates/stable-audio-open-research-paper)。UE 生产链项目可预见交付 / 企业使用风险。 | medium | D11 我自我质疑「Stable Audio Open license 是 Stability AI Community License(部分非商业限制),企业用户可能需要审查;design 未提及 license issue」+「是否应在 design Risks 里加一项?」— 我看到了 license 风险但**没有**落盘到 design Risks。 | **accepted-codex** | (1) `design.md` Risks 表加新行「Stable Audio Open 1.0 license 商业边界(Stability AI Community License + $1M revenue threshold)」;Mitigation:用户可替换 manifest(切 ACE-Step v1 或其它 license);CLAUDE.md ComfyUI section 加 license note;(2) `tasks.md §10.4` Documentation Sync Gate CLAUDE.md commit 加 license disclaimer 段;(3) `examples/comfy_local_smoke_audio.json` JSON 顶层加注释字段(若 OpenSpec loader 接受 `"_comment"` 等约定 key)或 README sibling note(若 JSON 不接受) |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。6 项 finding 全部 `accepted-codex`(F1 / F2 high + F3 / F4 / F5 / F6 medium);无 `disputed-pending` / `disputed-permanent-drift` 项。

但 contract 回写工作量大(F1 + F2 是 high,直接阻断 S3 进入 implementation):
- `design.md`:D5 反转 + D9 伪代码重写 + D10 magic bytes 反转 + D11 license note + Risks 表加 license 行 + OQ-1/2/3 timing 修(从「implementation 第二周」改「S2→S3 立即」)
- `proposal.md`:Impact 段「workflow loader step type」→「executor registry capability_ref」;§1 AudioCandidate 字段描述加 `| None`
- `tasks.md`:§1.5a 新增 ComfyUI subprocess probe(S3 阻塞);§2.2 dataclass 字段加 `| None = None`;§5.2 retry/wrap 伪代码重写(三 except 块)+ §5.3-§5.4 step type 注册改 executor registry + §5.6 fence 名调(step_kind → capability_ref);§8.1 examples bundle JSON 重写(`type: "generate"` + `capability_ref: "audio.t2a"` + 顶层 `provider_policy` / `depends_on`);§4.4 fence 加 magic bytes mismatch × 3;§10.4 CLAUDE.md license note
- `specs/runtime-core/spec.md`:整段重写(audio.t2a step kind → audio.t2a capability_ref;`Step.type=StepType.generate` + `capability_ref` 路由)
- `specs/examples-and-acceptance/spec.md`:Scenario `examples/comfy_local_smoke_audio.json declares text-to-audio single step with audio_local alias` 修(`kind` → `type` + `capability_ref`,顶层 `provider_policy`)
- `specs/provider-routing/spec.md`:audio Scenarios 中 `step.kind` 引用全改;Step 4 加 magic bytes 校验;`Non-OpenAI protocols ship dedicated adapters` MODIFIED Scenario 同步
- `specs/artifact-contract/spec.md`:Scenario「format-aware file_suffix matches actual payload bytes」加 magic-verified 前提

外加 F4 要求的 ComfyUI subprocess probe(S3 阻塞;若 ComfyUI 现可用,本轮跑;若不可用,留 pending marker)。

## D. Independent Verification (file:line audit)

> 沿 ForgeUE memory `feedback_dont_punt_executable_tasks` 风格,**不**把 codex claim 当结论,逐条 file:line 实际查证。

| 验证项 | Codex 引用 | 实际查证(grep / Read 结果) | 验证结论 |
|---|---|---|---|
| **F1-V1** Step 真实字段 | `src/framework/core/task.py:30-42` | Read line 30-43:`Step(BaseModel)` 含 `step_id: str` / `type: StepType` / `name: str` / `risk_level` / `capability_ref: str` / `provider_policy: ProviderPolicy \| None` / `retry_policy` / `transition_policy` / `input_bindings` / `output_schema` / `depends_on: list[str]` / `config: dict` / `metadata: dict`;**无** `kind` 字段。 | TRUE — codex 引用准确;Step 用 `type: StepType` + `capability_ref: str`,我的 spec 用 `step.kind` 不存在 |
| **F1-V2** loader 不做 step-kind 解析 | `src/framework/workflows/loader.py:31-36` | Grep `Step.model_validate` → line 36 `steps = [Step.model_validate(s) for s in raw["steps"]]`,无任何 step-kind 表 / step type 注册逻辑 | TRUE |
| **F1-V3** ExecutorRegistry 用 (step.type, capability_ref) | `src/framework/runtime/executors/base.py:63-75` | Grep:line 63 `class ExecutorRegistry`;line 65 `_exact: dict[tuple[StepType, str], StepExecutor]`;line 75 `key = (step.type, step.capability_ref)`;line 78-79 `if step.type in self._wildcard: return self._wildcard[step.type]`;line 81 错误消息 `f"No executor for step_type={step.type} capability_ref={step.capability_ref}"` | TRUE |
| **F1-V4** generate_image / generate_mesh executor 真实 step_type | `src/framework/runtime/executors/generate_image.py:54-57` + `generate_mesh.py:64-67` | Grep:`generate_image.py:56-57` `step_type = StepType.generate` + `capability_ref = "image.generation"`;`generate_mesh.py:66-67` `step_type = StepType.generate` + `capability_ref = "mesh.generation"`;`enums.py:21-28` `StepType` 枚举仅 5 个值(`generate / review / select / validate / export`),无 `audio_t2a` 候选 | TRUE — 强证据「不应新加 StepType,应复用 generate + 新 capability_ref `audio.t2a`」 |
| **F2-V1** design.md D9 伪代码 bare raise | `design.md:262` | Read line 246-264:line 262 `raise`(裸,不是 `raise wrapped` / `raise wrapped from exc`)— 在循环最后一次失败时**重抛原始 exc**(因为是 except 块内的 bare raise),而不是 wrapped。 | TRUE — codex 准确指出语义 bug |
| **F2-V2** mesh 实装是三 except 块分裂模式 | `src/framework/runtime/executors/generate_mesh.py:160-172` | Read line 160-172:三个独立 except(timeout / unsupported / generic),timeout 走 retry + `raise wrapped from exc`,unsupported / generic 立即 `raise XxxResponse(...) from exc` 不 retry。 | TRUE |
| **F3-V1** D5 Rejected 顶层 vs D10 用顶层冲突 | `design.md:115-127` + `design.md:351-361` | Read D5 line 127:「**Rejected**:dataclass 顶层字段已有 `format`(D10 必须),duration 和 sample_rate 是 best-effort 解析(若 ComfyUI 不暴露则 None),应该走 metadata 而非强制顶层」;但 D10 line 357-361 + provider-routing line 116 + artifact-contract line 41 全部用顶层字段构造 `AudioCandidate(..., duration_seconds=..., sample_rate=...)`;tasks §2.2 dataclass 字段也是顶层。 | TRUE — 真实矛盾 |
| **F4-V1** OQ 标记位置 | `design.md:351-361` | Read OQ-1/2/3 全部承认外部协议未定,resolve 标 implementation G2 第二周 | TRUE |
| **F4-V2** Phase 1 round 5 D10 类似先例 | `archive/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/design.md:385` | grep `D10`:Phase 1 round 5 D10 是 implementation Phase B Task 1.3 期间发现 ComfyUI LoadImage filename-only 约束,触发 round-5 source bytes 写到 input/ 修订 | TRUE — 强先例 |
| **F5-V1** provider-routing 仅扩展名检测 | `specs/provider-routing/spec.md:112-116` | Read line 112-116:Step 3 仅 `Path(abs_path).suffix.lower()` 检测扩展名,Step 5 `Path(abs_path).read_bytes()` 直接读;无 magic bytes 校验 step | TRUE |
| **F5-V2** Phase 1 mesh FR-WORKER-006 GLB magic | `docs/requirements/SRS.md` FR-WORKER-006 + `mesh_worker.py` magic check | grep FR-WORKER-006:存在;mesh `data[:4] == b"glTF"` 强制(SRS line 247-248)。audio 路径无等价 | TRUE — 主线 mesh / image 已强制,audio 未强制 |
| **F6-V1** design Risks 表无 license 行 | `design.md:316+` | Read Risks 表:8 行 mitigation,无 Stable Audio license 项 | TRUE |

**所有 6 finding 全部独立验证 TRUE**。无 `disputed-permanent-drift` 项;无需 ≥ 50 字 reason + reasoning_notes_anchor。

## 后续动作(post-cross-check)

1. **F4 探活**:本 cross-check 落盘后立即跑 ComfyUI subprocess probe(S3 阻塞 — 若 ComfyUI 现可用,本轮跑;若不可用,留 pending marker)。Probe 结果决定 4-dict + provider-routing 字段 / candidate 数量协议是否需 round-2 修订。
2. **F1 / F2 / F3 / F5 writeback**:design.md / proposal.md / tasks.md / 4 spec deltas 系统性回写(逐 commit),每 commit 落 `writeback_commit` hash 到 cross-check frontmatter 的 `## B Resolution` 列。
3. **F6 license note**:design.md Risks 表 + tasks §10.4 CLAUDE.md commit 加 license disclaimer。
4. **`forgeue_change_state.py --writeback-check`**:写完后跑,exit 0 才进 S3。
5. **Superpowers writing-plans**:exit 0 后输出 `execution/execution_plan.md` + `execution/micro_tasks.md`,引用更新后的 tasks.md 锚点。
