---
change_id: comfy-agent-cli-video-adoption
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
  - specs/ue-export-bridge/spec.md
codex_review_ref: review/codex_plan_review.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan adversarial review for OpenSpec change comfy-agent-cli-video-adoption: review execution_plan.md (16 commits chain) + micro_tasks.md (~80 TDD micro tasks). Sweep-mirror of audio Phase 2 + new UE bridge video 资产链路 + round-2 codex F1-F4 全 accepted-codex writeback (commit 55dc4d4 含全部 round-2 修订). Focus areas: (a) commit 1-16 顺序 head-baseline 风险 (commit 1 = ArtifactType modality Literal 扩 video 1-line + 1 fence; commit 2 = VideoWorker baseline 新文件 + 5 fence; commit 4 = ComfyAgentWorker capability dispatch 16 fence; commit 8c = round-2 F1 export gate sweep 同 commit 改三处 5 fence); (b) BMFF strict 校验 9 fence 命名一致性 (D9 + round-2 F4); (c) F1 sweep 三处必须同 commit (export.py:215 + policies.py:96 + permission_policy.py:18) 否则 is_op_allowed 与 PermissionPolicy 字段 / _OP_ALLOW_ATTR 映射不一致破坏 video import 默认 allow tier; (d) D8 VideoCandidate 顶层字段 single-source 在 5 个 metadata 字段(duration_seconds / frame_count / width / height / fps) None-默认 是否被 fence 覆盖到 _generate_video_metadata_best_effort_when_comfy_does_not_emit; (e) D12 Content/Movies/ vs Content/Generated/ 路径分流是否在 domain_video.py 实装时被 P4 stub fence 验证 (test_p4_domain_video_copies_mp4_to_content_movies_subdir + test_p4_domain_video_creates_file_media_source_uasset_in_content_generated_subdir); (f) D14 FailureModeMap priority 顺序 (video before audio before mesh before generic) 在 commit 6 实装时是否被 fence 覆盖 test_failure_mode_map_video_takes_priority_over_generic_worker_exception. Plan cross-check Claude 立场已冻结于 review/plan_cross_check.md ## A.\""
plugin_task_id: pending
detected_env: claude-code
triggered_by: "/forgeue:change-apply (S3→S4-S5 transition; Superpowers executing-plans + TDD pending)"
codex_plugin_available: true
created_at: 2026-05-04T12:15:00+08:00
resolved_at: 2026-05-04T13:40:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks+proposal+runner.py (4 findings 全 accepted-codex; commit 1185377 含全部 round-3 PF1-PF4 修订;PF1 路径 (a) 用户 2026-05-04 拍板 → ComfyUI runner.py user-authored extension 已实施;PF2/PF3/PF4 同步 sweep)
writeback_commit: 1185377
drift_reason: "round-3 codex plan review 4 findings PF1-PF4 全 accepted-codex,commit 1185377 含全部修订(PF1 ComfyUI runner.py user-authored extension 用户授权 + PF2 BMFF largesize reject + PF3 spec sweep + PF4 dataclass enforcement layer)"
reasoning_notes_anchor: "design.md `## Reasoning Notes — round-3 codex plan review (2026-05-04)`"
note: |
  本 plan_cross_check 在调 codex /codex:adversarial-review plan hook 之前冻结 `## A` 段,
  以避免 Claude 看完 codex finding 后回填 ## A(协议自我保护)。
  ## B / C / D 在 codex review 落盘后由 Claude 续写。
  contract_refs 含 execution_plan.md + micro_tasks.md(本 stage 主审对象)+ design/specs/tasks
  (锚点真源)。Round-2 codex design review 已收敛(commit 55dc4d4);本 plan review 主审
  「plan-vs-contract 一致性」+「commit 顺序 / fence 写法 / 越界风险」。
---

# S3→S4-S5 Plan Cross-check: comfy-agent-cli-video-adoption

## A. Claude's Decision Summary (frozen before codex plan review, 2026-05-04 12:15 +08:00)

> 本 stage 起草 execution_plan.md + micro_tasks.md 时 Claude 的关键判断;冻结于 codex plan review 调用之前。
> 列出每条 plan 决策的脆弱点(self-criticism),便于 codex 直接对照源码 + design.md 找漏洞。
> 沿 audio Phase 2 plan_cross_check P1-P10 模式;本 change 多了 UE bridge video 资产链路 + round-2 F1 export gate sweep 两个新风险面。

### P1 — Commit 1 ArtifactType modality Literal 扩 video 顺序合理性

execution_plan.md commit chain commit 1 = `core/artifact.py:35 modality: Literal[..., "video", ...]` + 1 fence。head 跑 baseline = 1294 不变,新加 1 fence pass。

**脆弱点 1**:Pydantic Literal 扩展是简单的字段 schema 改动,但全项目 grep `modality=` 可能有几十处使用点(executors / repo / review / manifest_builder),若有 closed-set switch / `if modality == ...:` 链漏掉 video 分支,fence 不会 catch(因 commit 1 只测 ArtifactType 自身 Pydantic accept)。我**没**实际 grep `modality=` 全项目验证 closed-set 假设;若存在 `match modality: case "image": ...; case "audio": ...; case "mesh": ...; case _: raise UnsupportedModality(...)` 这种 exhaustive 模式,commit 1 后续 commits 会踩到。

**脆弱点 2**:commit 1 head 跑 `pytest tests/unit/test_artifact.py -v` 全绿要求既有 image / audio / mesh modality fence 不退化,但若既有 fence 用 `pytest.mark.parametrize` 列举所有 modality 枚举值并依赖列表完整性(如 `for m in get_args(ArtifactType.model_fields["modality"].annotation): ...`),扩 video 后 parametrize 长度变化,既有 fence 不退化但 count 增加 — 这是 OK 不算 regression。

### P2 — Commit 2 VideoWorker baseline 新文件 import 链

micro_tasks 2.1-2.7 创建 `video_worker.py` + 5 fence;commit 2 head pytest baseline 不变 + 5 fence pass。

**脆弱点 1**:`__init__.py` 暴露 `from .video_worker import VideoCandidate, VideoWorker, ...` 我**没**在 micro_tasks 显式列出修改 `src/framework/providers/workers/__init__.py`;Phase 1 mesh + Phase 2 audio 已经 import 暴露 mesh / audio worker 符号,video 必须 sweep 加。若 commit 2 内部 fence import `from framework.providers.workers.video_worker import VideoCandidate` 直接走完整路径,**不**走 `__init__` re-export,fence 可能绿但下游 commit 5 / 8 等 import `from framework.providers.workers import VideoCandidate` 会失败。

**脆弱点 2**:`FakeVideoWorker._build_minimal_mp4` 构造 minimal valid BMFF mp4 bytes(round-2 F4 收紧后必须含 `b"ftyp"` at offset 4 + box_size in [8, len] + major_brand non-empty)— 我**没**写实际 byte sequence,implementer 可能写出未通过 BMFF strict 5-tuple 校验的 minimal bytes(commit 4 _run_once_video 强校验 reject)。需要 micro_tasks 2.5 加入具体 byte sequence reference,如:
```python
b"\x00\x00\x00\x20" +  # box_size = 32
b"ftyp" +              # box_type
b"isom" +              # major_brand
b"\x00\x00\x02\x00" +  # minor_version
b"isom" + b"iso2" + b"mp41" + b"mp42"  # compatible_brands list
```

### P3 — Commit 4 ComfyAgentWorker 加 video 4-dict 与现有 image+mesh+audio fence 兼容性

micro_tasks 4.1-4.6 编辑 comfy_worker.py 加 video entry。

**脆弱点 1**:`__init__` 守门 line 367 错误消息当前是 `f"expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)} (video is the only remaining follow-on; see SRS TBD-009)"` — 加 video 后,`sorted(...)` 自动 list 4 个 ids,但**括号注释「video is the only remaining follow-on」过期**(video 已加),需要更新为「all 3 phases of TBD-009 closed」或删掉括号注释。我**没**在 micro_tasks 显式列出「更新 `__init__` 守门错误消息括号注释」micro task;commit 4 head fence `test_unknown_model_id_raises_at_init_lists_video_in_supported` 可能因消息字面过期而需要修。

**脆弱点 2**:`_VIDEO_FORMAT_WHITELIST = {"mp4"}` 单元素 set 在 round-2 F2 后是 fixed contract;但若 implementer 实施时为「将来 webm follow-on 时少改一处」加 `{"mp4", "webm"}` 然后用 `if ext != "mp4": raise` 单独路径,会与 spec/probe-and-validation `test_video_candidate_format_whitelist_mp4_only` Pydantic Literal["mp4"] fence 不一致(后者要求 webm Pydantic 直接 reject,前者运行时才 reject)。需要确认 implementer 严格按 micro_tasks 4.1 list 写 `{"mp4"}` 单元素。

### P4 — Commit 5 GenerateVideoExecutor 实装与 audio Phase 2 路径对齐

micro_tasks 5.1-5.8 沿 audio F1-F2 + R7-B retry policy honor + R6-A `shape="mp4"` UE bridge dispatch。

**脆弱点 1**:`GenerateVideoExecutor.__init__` 实际签名(类比 audio `GenerateAudioExecutor.__init__`)— 是否需要构造时注入 fallback worker?audio `GenerateAudioExecutor` 是无 fallback worker(纯本地 ComfyUI),video 应该也是无 fallback;但若我假设的 `GenerateVideoExecutor()` 简单构造与 audio 实际签名不一致(audio 可能传 `default_worker=None` 显式参数),implementer 实施时会需要 grep 确认 audio 实际签名后才能写 video 同款。

**脆弱点 2**:`ExecutorRegistry.register(executor)` 实际签名(`base.py:69 if executor.capability_ref is None: ... else self._exact[(executor.step_type, executor.capability_ref)] = executor`)读类属性。GenerateVideoExecutor 实例化时 `step_type` + `capability_ref` 类属性必须存在;若 implementer 写成 instance 属性(`def __init__(self): self.step_type = ...`)而非类属性,registry 注册路径会变(读 class attr fail → 走 instance attr → 但 type hint 可能不一致)。需要严格按 audio Phase 2 模式写类属性,**不**是 instance 属性。

### P5 — Commit 6 FailureModeMap priority(round-2 D14 + 沿 audio R4-F1)

micro_tasks 6.2 「video isinstance check **在 audio / mesh / generic 之前**」。

**脆弱点 1**:实际 `failure_mode_map.py from_exception` 当前 priority 顺序(post-audio Phase 2 archive)我**没** grep 验证 — audio 是否真的在 mesh 之前?若 audio 在 mesh 之后 / generic 之前,video 加在 audio 之前 + audio + mesh + generic 顺序合理。但若 audio 实际在 generic 之前但 mesh 之后(因 mesh 是 Phase 1 先建),video 加在 audio 之前可能与 mesh 之后 priority 不一致(video / mesh 谁先谁后无 isinstance 冲突,不影响行为,但 fence `test_failure_mode_map_video_takes_priority_over_generic_worker_exception` 命名暗示 video 必须**在 generic 之前**,不必**在 mesh / audio 之前**)。是否需要 priority 严格定义?

**脆弱点 2**:`FailureMode.video_worker_timeout` 与 `FailureMode.video_worker_unsupported` enum 值需要在 `FailureMode` enum 中加;若 `FailureMode` 用 IntEnum / StrEnum 自动赋值,加 video 不影响 audio / mesh 已有值;若用显式整数 / 字符串,需要 sweep 整个 enum。我**没**确认 `FailureMode` enum 实际类型。

### P6 — Commit 7 manifest_builder._KIND_MAP + import_plan_builder 改动范围

micro_tasks 7.1-7.6 编辑 manifest_builder + import_plan_builder + 5+1 fence。

**脆弱点 1**:`_KIND_MAP` 当前是 module-level dict literal,加 `("video", "mp4"): "file_media_source"` 是简单 dict insertion;但 `_PREFIX_BY_KIND` 加 `MS_` 必须确认 sorted asset_kind 顺序在 docstring 表里也更新(顶部 docstring 的 modality.shape → asset_kind 表 + prefix 表)— 我已在 micro_tasks 7.1 列出「顶部 docstring 更新」但具体改哪几行未指定。

**脆弱点 2**:`import_plan_builder.py` 的 `file_media_source` asset_kind → `import_file_media_source` operation kind 映射 — 我**没** grep `import_plan_builder.py` 看实际映射逻辑(是 dict literal、`elif` 链、还是 dispatch 函数?)。若是 `elif kind == "texture": op_kind = "import_texture"` 链,需要 sweep 加 video 分支;若是 dict literal `_ASSET_KIND_TO_OP_KIND = {"texture": "import_texture", ...}`,加一行即可。

### P7 — Commit 8 domain_video.py + run_import dispatch + Content/Movies/ 路径分流(D12)

micro_tasks 8.1-8.7 创建 domain_video.py 调 `unreal.FileMediaSourceFactory` + `_OP_HANDLERS` 加 dispatch。

**脆弱点 1**:`unreal.FileMediaSourceFactory` 真实 API 我**没**在 P4 真机 hands-on 验证(design OQ-3 显式列出此风险)。Implementer 实施 commit 8 时可能发现 API 不符 design D1 预期(如需 `unreal.MediaSource` base class + `unreal.MediaPlayerFactory`),触发 round-2 design 修订(沿 a2_mesh round 5 D10 modify 模式)。**STOP** + 回写 design.md D1 + Risks。

**脆弱点 2**:`unreal.FileMediaSource.file_path` editor property 设置方式 — `set_editor_property("file_path", "Movies/<run_id>/<MS_<base>>.mp4")` 是 UE Python API 标准但**相对路径基准**(相对 `Content/` 还是 absolute)我**没**确认。若 UE 实际期望 absolute / 不同基准,domain_video 实装会需要计算路径,fence `test_p4_domain_video_creates_file_media_source_uasset_in_content_generated_subdir` 可能验不到 file_path 字段实际值。

**脆弱点 3**:`Content/Movies/` 目录是否在 UE packaging settings 默认接受 standalone movie file — design OQ-4 显式 deferred 到 P4 真机验证;P4 fence 用 stub `unreal` 模块跑,无法验证 packaging 真实行为(只能验 dispatch + Evidence record + 文件 copy 路径)。L2 + a2_video commandlet round-trip 才能真实验证 packaging。

### P8 — Commit 8c round-2 F1 export gate sweep 三处必须同 commit

micro_tasks 8c.1-8c.8 编辑 export.py + policies.py + permission_policy.py + 5 fence。

**脆弱点 1(critical)**:三处必须同 commit 改 — 若 implementer 拆分到三个独立 commit,中间 commit head 会出现「PermissionPolicy 字段已加但 _OP_ALLOW_ATTR 未加」或反之,`is_op_allowed(PermissionPolicy(), op)` 路径可能 raise `AttributeError`。execution_plan / micro_tasks 都明确「必须同 commit」但没在 commit 8c 内部加 sub-task `8c.0 STOP if attempting to split across commits`。

**脆弱点 2**:`policies.py:96` 加字段位置是否破坏既有 `PermissionPolicy.model_validate({...})` 调用 — Pydantic 默认值字段加在末尾应该 forward-compatible(既有调用不传新字段使用默认 True)。但若 `policies.py` 用 `frozen=True` 或 `model_config = ConfigDict(extra="forbid")` 严格 schema,加新字段后既有 `PermissionPolicy(allow_import_texture=True, allow_import_audio=True, allow_import_static_mesh=True)` 调用仍 OK(只是没传新字段使用默认值);但若 既有测试 `assert policy.model_dump() == {"allow_import_texture": True, ...}` 字面 dict 比较,新字段会破坏这种 fence。我**没** grep `tests/` 找 `PermissionPolicy.model_dump()` literal dict 比较 fence。

**脆弱点 3**:`tests/integration/test_p4_ue_manifest_only.py::test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence` 端到端 fence 需要构造一个 video Artifact 跑完整 ExportExecutor.execute → manifest_builder → import_plan_builder → permission mask → EvidenceWriter.append 链路。stub `unreal` 模块当前可能不支持 FileMediaSourceFactory `import_assets` 调用 — 若 stub 未扩,P4 fence head 红灯。需要 micro_tasks 8.4 同时扩 stub `unreal` 模块。

### P9 — Commit 10 examples bundle JSON schema 真实性

micro_tasks 10.1 复制 tasks §9b.1 完整 JSON。

**脆弱点 1**:`Vedio/Wan2.1-T2V-1.3B_native_5sec` 字符串(D5 上游拼写)— bundle JSON 内的字符串如果 IDE 自动 lint / typo-check 可能被改成 `Video/`(误改风险)。需要 commit 10 添加 inline 注释提醒 + commit 12-15 docs sync 反复强调。

**脆弱点 2**:`worker_timeout_s: 600`(D3)— 是否真的够 Wan T2V 7-min 生成 + ComfyUI 启动 / 模型加载?L2 evidence 跑时若超时可能需要调到 900-1200。tasks §11.3 写「若 worker_timeout_s=600 不够(冷启动超时),调到 900-1200 重跑」,但 examples bundle 默认 600 可能让首次跑用户被超时坑。是否应该 default 提高到 900?Claude 立场:600 是 Wan 1.3B 5sec 标称 420s + 30% 余量,合理;ComfyUI 冷启动应该用户端预先暖启(L2 evidence note 已显式提示)。

### P10 — Commit 16 L2 + a2_video P4 真机验收 commandlet 自动化

micro_tasks 16.1-16.11 沿 a2_mesh 2026-04-23 commandlet 模式。

**脆弱点 1**:`UnrealEditor-Cmd.exe -ExecutePythonScript=ue_scripts/run_import.py -nullrhi -nosplash -unattended` 命令行参数 — `-nullrhi` 防止 UE 启动渲染上下文,FileMediaSource import 是 file copy + asset metadata 注册不需要 GPU 渲染,理论上 OK;但若 UE FileMediaSource import 实际需要解码 mp4 验证(invoke ffmpeg / Bink 等编解码插件),`-nullrhi` 可能阻断。需要 implementer 在 16.8 实际跑时若 import 失败 round-2 修订(去掉 `-nullrhi` 或加 `-AllowCommandletRendering`)。

**脆弱点 2**:`Content/Movies/<run_id>/MS_<base>.mp4` 实际落点验证 — UE 5.x packaging settings 默认 `Movies/` 是 standalone movie file 路径,但用户 UE project 自定义 packaging settings 可能不接受。需要 evidence note 显式记录 packaging 行为 + 若 fail follow-on 加 `bundle.config.video_target_subdir` override 字段。

### P11 — Round-2 F1+F4 修订对 commit chain 影响

round-2 修订加了 commit 8c (F1) + BMFF strict 9 fence (F4),整体 commit 数从原 15 → 16,fence 总数从 +50 → +58。

**脆弱点**:tasks.md §13.1 Finish Gate 实测 baseline `1294 → 预计 ~1352`(+58 fence),但实测 baseline 可能因 ComfyUI / UE 真机环境变化而上下浮动 ±5;fence 总数硬数字应以 implementer 实测为准,**不**硬编码。execution_plan + micro_tasks 都说「不硬编码」但 finish gate 验证脚本是否容许 ±5 偏差?若 finish gate 期望精确数字,会误报 regression。

### P12 — Plan-vs-contract 一致性 sweep

execution_plan 16 commits 是否完整覆盖 tasks.md §1-§13 所有 sub-task?

**脆弱点 1**:tasks.md §1 准备工作(§1.1-§1.7)+ §12 Codex review hooks(§12.1-§12.2)+ §13 Finish gate(§13.1-§13.4)在 execution_plan 没有对应 commit(因为这些是 stage gate 而非 implementation commit)。若 implementer 走 micro_tasks 顺序跳过 §1.5 OQ-1+OQ-2 静态阅读 + §1.5b 实测补全,commit 4 (ComfyAgentWorker) 实施时可能踩 OQ-1 假设错(`outputs.video` 字段名不是 `"video"`)— 整个 commit 4 fence 得重写。需要 micro_tasks 在 commit 4 之前加 prep step「先做 §1.5 / §1.5b OQ probe」。

**脆弱点 2**:execution_plan「modified files」清单 vs 实际 commit chain 改动范围一致性 — 我列了 17 个文件改动,implementer 实施时可能漏改 1-2 个(如 `tests/fixtures/test_models.yaml` 容易忘改,只改 `config/models.yaml`)。boundary check 会 catch,但 catch 时已经在实施末尾,需要 rebase / 补 commit。

### Round-2 F1+F4 修订总结

- **D12b 新增**:Export gate 三处 sweep — 这是 execution_plan / micro_tasks commit 8c 全新加;commit chain 从 15 → 16
- **D9 BMFF strict 校验**:9 fence 替换原 4 fence(magic bytes 4-byte + webm 接受);commit 4 fence 总数从 ~14 → ~16
- **D8 mp4-only**:format Literal 收紧 + 删除所有 webm 实施细节(spec / fence / bundle)
- **D-Followon-Registry 扩 webm 项**:`comfy-video-webm-adoption` 新加(F2 副作用)
- **plan 与 contract sweep 后一致**:commit 8c 同 commit 改三处的 critical invariant 已写入 micro_tasks 8c.7 verification step

---

## B. Codex Findings × Claude Resolution

Codex verdict: `needs-attention`;4 个 finding(1 high + 3 medium)。**全 accepted-codex writeback**,无 disputed。**PF1 是 critical blocker** — 需要用户决策修复路径才能继续 implementation。

| # | codex finding | severity | location | Claude resolution | writeback target |
|---|---|---|---|---|---|
| PF1 | `outputs.video` 被当成已确认事实,但 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` 实际只返回 {images, audio, glb, raw};commit 4 加 `_REQUIRED_OUTPUT_KEY["video"] = "video"` 后真实 Wan 7-min 跑会被 `_validate_outputs` 判 missing,executor + UE import 全断;mock fence 漏检 live 断点 | high | `tasks.md:29-30` + `D:/AI/ComfyUI/scripts/comfyui_api/runner.py:209-249` | **accepted-codex** (待用户决策修复路径) | **STOP implementation pending user direction**;两条候选路径:(a) **扩 runner.py 加 video 收集**(沿 Phase 1 round 5 D10 mini-LoadImage 模式;user-authored ComfyUI 共享目录 修改;CLAUDE.md "ComfyUI 共享目录新增 ForgeUE 依赖" 段必须更新);(b) **ForgeUE-side fallback** — `_run_once_video` 走 `outputs.raw` 遍历 node_outputs 寻找 video 文件路径(脆弱:依赖 VHS_VideoCombine 节点输出 shape;未来 ComfyUI 升级 VHS 节点可能挂)。Claude 推荐路径 (a)(沿 Phase 1 D10 precedent + 与 audio / mesh / image 收集协议一致);路径 (b) 如选则需要在 D7 加新 fallback 决策段 + 新 fence `test_generate_video_extracts_path_from_outputs_raw_when_video_key_missing` |
| PF2 | BMFF `box_size == 1` 64-bit largesize 解析错 — 当前 spec 用 `data[8:12]` 当 major_brand,但 ISO BMFF 规定 size=1 时 bytes 8-15 是 largesize,major_brand 应从 byte 16 起;16-byte 伪 header 能通过"strict"校验直到 UE FileMediaSource import 才失败 | medium | `design.md:273-306` + `specs/provider-routing/spec.md:185-200` (BMFF strict 段) | **accepted-codex** (走简化路径:本 change 拒绝 `box_size == 1`) | design.md D9 + spec/provider-routing BMFF strict 段更新:`box_size != 1 and (box_size < 8 or box_size > len(data))` → `box_size < 8 or box_size > len(data)`(去掉 `box_size != 1` 例外,直接拒绝 largesize);删除 fence `test_generate_video_bmff_box_size_largesize_1_accepted` + 加 fence `test_generate_video_bmff_box_size_largesize_1_rejected_pending_follow_on`;design.md `## Reasoning Notes — round-3 codex plan review` 加 Resolution + 登记 follow-on `video-bmff-largesize-support`(触发条件:用户实际遇到 largesize mp4 输出,Wan T2V 标准输出不用 largesize 罕见)|
| PF3 | round-2 mp4-only writeback 未完成 — `specs/provider-routing/spec.md:7` 顶层 Requirement 仍声明 `Literal["mp4", "webm"]`,proposal.md 仍有 `{mp4, webm}` whitelist + webm magic bytes 文案;archive 后留下自相矛盾合同(顶层 Requirement vs Scenario) | medium | `specs/provider-routing/spec.md:7` + `proposal.md` (webm 残留行) | **accepted-codex** | sweep `specs/provider-routing/spec.md` 把所有 webm 残留改 mp4-only:line 7 `Literal["mp4", "webm"]` → `Literal["mp4"]`;line 88 `_VIDEO_FORMAT_WHITELIST = {"mp4", "webm"}` (round-1 残留) → `{"mp4"}`;line 128 `ext not in {"mp4", "webm"}` → `ext != "mp4"`;line 131-134 magic_ok 双分支(mp4 + webm)→ 单 mp4 BMFF strict;sweep proposal.md 同款 |
| PF4 | TDD 计划假设 dataclass 会校验 Literal,但 Python `@dataclass` 不在 runtime 强制 Literal 类型;commit 2 fence `test_video_candidate_format_whitelist_mp4_only` 期望 `format="webm"` 触发 dataclass `Literal["mp4"]` 校验失败,但 dataclass 不会报;audio Phase 2 已显式选 worker 层 enforcement 模式 | medium | `tasks.md:56-104` + `tests/unit/test_audio_worker.py:39-53`(audio 同款行为) | **accepted-codex** (走 (b) 沿 audio Phase 2 模式) | tasks.md §3.6 fence 名 + 内容更新:删 `test_video_candidate_format_whitelist_mp4_only`(原期望 dataclass 拒绝 webm)+ 改为 `test_video_candidate_format_mp4_accepted_dataclass_does_not_runtime_enforce_literal`(沿 audio 同款 fence 写法);spec/probe-and-validation 同款 fence 名更新;真正的 mp4-only 守门保留在 `_run_once_video` 扩展名层 (`ext != "mp4" → raise`);design.md D8 + D9 加注释「Python dataclass 不强制 Literal,enforcement 在 worker 层」|

## C. Disputed-open count

`disputed_open: 0`

4 个 finding 全 accepted-codex writeback;无 disputed-permanent-drift,无 disputed-pending。但 **PF1 是 critical implementation blocker** — Claude **STOP** implementation pending user direction on fix path (a) vs (b)。

## D. 独立验证(Claude 自审 codex claim,沿 ForgeUE memory `feedback_verify_external_reviews`)

不把 codex claim 当结论;每条 finding 独立 grep / Read 验证 file:line 真实存在。

### PF1 独立验证 — ✅ 100% real (CRITICAL)

**Claim**:`D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` 当前实现只收集并返回 `{images, audio, glb, raw}`,无 `video` key。

**Claude 实读验证**(`Read` + `Grep` tool):

`D:/AI/ComfyUI/scripts/comfyui_api/runner.py:186-249` 实读 `extract_outputs` 函数:

```python
def extract_outputs(history_entry: dict, root: Path | None = None) -> dict:
    """...
    Returns
    -------
    dict with keys:
        ``images`` — list of absolute path strings for PNG/image outputs.
        ``audio``  — list of absolute path strings for audio outputs.
        ``glb``    — list of absolute path strings for .glb mesh outputs.
        ``raw``    — the full ``outputs`` dict for advanced use.
    """
    out_root = ...
    images = []
    audio = []
    glb = []

    for _node_id, node_out in outputs.items():
        # --- images --- (line 214-224)
        for img in node_out.get("images", []):
            ...
        # --- audio --- (line 226-236)
        for aud in node_out.get("audio", []):
            ...
        # --- glb --- (line 238-247)
        for item in node_out.get("result", []):
            if not item.endswith(".glb"):
                continue
            ...

    return {"images": images, "audio": audio, "glb": glb, "raw": outputs}
```

✅ Confirmed — **没有 `video` key 收集逻辑**;返回 dict 只有 4 keys;VHS_VideoCombine 节点输出会落在 `raw` 里(完整 outputs dict),但 `_validate_outputs(outputs)` 在 ForgeUE 端走 `outputs.video` 路径查 — 必拿到 KeyError / AttributeError → `WorkerUnsupportedResponse(missing outputs.video)`。

**Claude resolution 自查**:critical blocker。Claude **STOP** implementation;不加任何 video-output-related 代码直到用户决策修复路径。两条路径都需要新增 design 段:
- (a) 扩 runner.py:CLAUDE.md "ComfyUI 共享目录新增 ForgeUE 依赖" 段加新行;design.md 加新决策段「D-Runner-Extension」;tasks §1.x 加 sub-task「实施前先扩 runner.py + verify shape via probe」
- (b) ForgeUE workaround:design D7 加 fallback 段「若 outputs.video 缺,worker 走 outputs.raw 遍历 node_outputs 寻找 video 扩展名路径」;新 fence `test_generate_video_extracts_path_from_outputs_raw_when_video_key_missing`;脆弱性 → tasks §1.5b implementation 阶段必须探明 VHS_VideoCombine 节点输出 shape

### PF2 独立验证 — ✅ 100% real

**Claim**:BMFF `box_size == 1` 表示 64-bit largesize,bytes 8-15 是 largesize 字段,major_brand 应从 byte 16 起;current spec 错用 `data[8:12]` 作 major_brand。

**Claude 实读验证**:

`design.md:273-306` 实读 D9 BMFF strict 校验段:

```python
box_size = int.from_bytes(data[0:4], "big")
if box_size != 1 and (box_size < 8 or box_size > len(data)):
    raise WorkerUnsupportedResponse(
        f"mp4 BMFF first box_size={box_size} out of range [8, {len(data)}]"
    )
major_brand = data[8:12]
```

✅ Confirmed — `box_size != 1 and ...` 显式跳过 box_size==1 的 range check;然后 `major_brand = data[8:12]` 当 box_size==1 时实际指向 largesize 字段而非 major_brand。

ISO/IEC 14496-12 BMFF spec(industry knowledge):
- box header: `[size:4][type:4]`
- if size == 1: `[size:4=1][type:4][largesize:8]` → body starts at offset 16
- if size == 0: extends to end of file
- ftyp box body: `[major_brand:4][minor_version:4][compatible_brands[]]`

So when box_size==1, major_brand should be at `data[16:20]`, not `data[8:12]`. Codex 100% correct on BMFF spec interpretation.

**Claude resolution 自查**:走简化路径 — 本 change 不支持 largesize(`box_size == 1` 直接 reject + follow-on `video-bmff-largesize-support`)。Wan T2V 标准输出 mp4 不用 largesize(单个 video file < 4GB 远小于 32-bit size 边界 4GiB),所以拒绝 largesize 在 baseline 不影响真实 use case。修复:`box_size != 1 and (box_size < 8 or box_size > len(data))` 改为 `box_size == 1 or box_size < 8 or box_size > len(data)` → reject 三种情况(largesize / 太小 / 超长)。Fence `test_generate_video_bmff_box_size_largesize_1_accepted` 改为 `..._rejected_pending_follow_on`。

### PF3 独立验证 — ✅ 100% real

**Claim**:`provider-routing/spec.md:7` 顶层 Requirement 仍声明 `Literal["mp4", "webm"]`;round-2 F2 mp4-only writeback 未完成。

**Claude 实读验证**:

`specs/provider-routing/spec.md` 实读:
- Line 7:`format: Literal["mp4", "webm"]` ✅ 残留 webm
- Line 88:`_VIDEO_FORMAT_WHITELIST: ClassVar[set[str]] = {"mp4", "webm"}` ❌ 已在 line 99/101 改成 `{"mp4"}`,但**两处都存在** — 我的 round-2 writeback 漏掉了 line 88(只改了下半段 spec body)

我的 grep 发现 line 7 和 line 88 都有 webm 残留,这是我 round-2 writeback 的真实漏洞 — 我只改了 ## ADDED 段的 generate_video method spec,没改 ## ADDED 第一个 Requirement「VideoWorker ABC, VideoCandidate dataclass...」的 VideoCandidate 字段段(line 7)。

**Claude resolution 自查**:sweep `specs/provider-routing/spec.md` line 7 的 VideoCandidate Literal + line 88 的 _VIDEO_FORMAT_WHITELIST 残留 + proposal.md 同款。这是 round-2 真实 writeback 漏洞,codex catch 是真的;接受 PF3 100% accepted-codex。

### PF4 独立验证 — ✅ 100% real

**Claim**:Python `@dataclass` 不在 runtime 校验 Literal 类型注解;commit 2 fence `test_video_candidate_format_whitelist_mp4_only` 期望 `format="webm"` 触发 dataclass `Literal["mp4"]` 校验失败,但 dataclass 不会报。

**Claude 实读验证**:

`tests/unit/test_audio_worker.py:39-53` 实读 audio 同款 fence:

```python
def test_audio_candidate_format_whitelist() -> None:
    """`AudioCandidate.format` SHALL be one of {"flac", "mp3", "wav"}.

    Note:dataclass with `Literal` annotation 不在 runtime 强制校验(Python 不检查
    Literal 类型),实际守门由 ComfyAgentWorker.generate_audio 在 read_bytes 后
    raise WorkerUnsupportedResponse 完成 ...
    本 fence 验证 dataclass 接受 3 个 valid format 字符串构造成功 — runtime 守门
    在 `ComfyAgentWorker.generate_audio` 层。
    """
    for fmt in ("flac", "mp3", "wav"):
        cand = AudioCandidate(data=b"fake bytes", format=fmt)  # type: ignore[arg-type]
        assert cand.format == fmt
        ...
```

✅ Confirmed — audio Phase 2 已显式记录「dataclass 不强制 Literal」,fence 只测 valid formats accepted。Python `@dataclass` 与 Pydantic 不同:
- Pydantic `BaseModel`:Literal 在 `model_validate` 时强制校验
- `@dataclass`:Literal 只是 type hint,runtime 不校验

我的 video micro_tasks 2.6 写「`format="webm"` / `format="mov"` 触发 dataclass `Literal["mp4"]` 校验失败」是错的。

**Claude resolution 自查**:走 (b) 沿 audio Phase 2 模式 — 删除 dataclass 构造拒绝 fence,改测 dataclass accept mp4 + worker 层 _run_once_video 扩展名拒绝 webm。codex 提示「若沿 audio 模式,删除 dataclass 构造拒绝要求,只在 _run_once_video 扩展名/BMFF 边界拒绝」是正确路径。tasks.md §3.6 fence 名 + 内容更新:删 `test_video_candidate_format_whitelist_mp4_only`,加 `test_video_candidate_format_mp4_accepted_dataclass_does_not_runtime_enforce_literal`(沿 audio 同款 fence 写法 + 注释说明「runtime enforcement 在 worker 层」)。

### 总结

✅ 4/4 finding 全 100% real,无 codex hallucination。
✅ Resolution 全 accepted-codex,无 disputed。
✅ disputed_open: 0。
🛑 PF1 是 critical implementation blocker — Claude **STOP** implementation pending 用户决策修复路径(扩 runner.py vs ForgeUE-side workaround)。
✅ PF2 / PF3 / PF4 待 writeback round (Claude 可单独完成,无需用户决策 — 但与 PF1 一起 batch writeback 更高效)。

