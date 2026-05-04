---
change_id: comfy-agent-cli-video-adoption
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md
  - execution/execution_plan.md
  - design.md
  - review/codex_design_review.md
  - review/design_cross_check.md
detected_env: claude-code
triggered_by: /forgeue:change-plan (Superpowers writing-plans skill methodology, micro task expansion of execution_plan.md)
codex_plugin_available: true
created_at: 2026-05-04T11:58:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 micro_tasks.md 是 execution_plan.md 的 step-level expansion,以 TDD 节奏组织。
  每个 task 引用 tasks.md#X.Y 锚点;每个 commit 由 N 个 micro task 组成,落 working
  tree 后跑 `pytest -q` 验证。禁止越界:若 implementation 需要新文件 / 新函数 / 新 fence
  而 micro_tasks 未列,STOP 并回写到 tasks.md(4 类 DRIFT taxonomy)。
---

# Micro Tasks — comfy-agent-cli-video-adoption

> **TDD 节奏**:每 commit 内先写 fence(red),再写 production code(green),最后 refactor。fence 名严格沿用 `tasks.md` / `specs/probe-and-validation/spec.md` 列出的 testable assertions。
>
> **执行策略**:用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` skill;每 commit 跑 `pytest -q` 验证不退化(post-change baseline ≈ 1294 + 累计 fence)。

## Commit 1 — ArtifactType modality Literal 扩 video(`tasks.md` §2)

> 单文件改动,1-line + 1 fence;commit head 跑 baseline = 1294 不变,新加 1 fence pass。

- [ ] 1.1 编辑 [`src/framework/core/artifact.py:35`](src/framework/core/artifact.py#L35) `ArtifactType.modality` Literal 加一项 `"video"` — 锚点 tasks §2.1
- [ ] 1.2 编辑 [`src/framework/core/policies.py:39-40`](src/framework/core/policies.py#L39-L40) `kind` 注释加 `video` — 锚点 tasks §2.2
- [ ] 1.3 加 fence `tests/unit/test_artifact.py::test_artifact_type_modality_literal_accepts_video`(post-change Pydantic accepts `modality="video"`;assert `ArtifactType.internal == "video.mp4"`)— 锚点 tasks §2.3
- [ ] 1.4 跑 `python -m pytest tests/unit/test_artifact.py -v`(全绿,既有 image/audio/mesh modality fence 不退化)— 锚点 tasks §2.4
- [ ] 1.5 commit:`feat(artifact): extend ArtifactType modality Literal to include "video" (Phase 3 D2)`

## Commit 2 — VideoWorker baseline(`tasks.md` §3)

> 新建 `video_worker.py` 含 ABC + Candidate + 异常树 + FakeVideoWorker;test_video_worker.py 5 fence(round-2 F2:format Literal mp4-only)。**No client 依赖**(commit 2 head 跑 baseline = 1294+1 不变,新加 5 fence pass)。

- [ ] 2.1 创建 [`src/framework/providers/workers/video_worker.py`](src/framework/providers/workers/video_worker.py) 骨架 — 锚点 tasks §3.1
- [ ] 2.2 实现 `VideoCandidate` dataclass(round-2 F2:format Literal mp4-only)— 锚点 tasks §3.2:
  ```python
  @dataclass
  class VideoCandidate:
      data: bytes
      format: Literal["mp4"]
      metadata: dict[str, Any] = field(default_factory=dict)
      duration_seconds: float | None = None
      frame_count: int | None = None
      width: int | None = None
      height: int | None = None
      fps: float | None = None
  ```
- [ ] 2.3 实现异常树 — 锚点 tasks §3.3
- [ ] 2.4 实现 `VideoWorker(ABC)` ABC — 锚点 tasks §3.4
- [ ] 2.5 实现 `FakeVideoWorker` 测试 fixture(minimal mp4 bytes 含 `b"ftyp"` at offset 4)— 锚点 tasks §3.5
- [ ] 2.6 加 5 fence to `tests/unit/test_video_worker.py`(round-2 F2:`test_video_candidate_format_whitelist_mp4_only`)— 锚点 tasks §3.6
- [ ] 2.7 跑 `python -m pytest tests/unit/test_video_worker.py -v`(全绿)
- [ ] 2.8 commit:`feat(video): introduce VideoWorker ABC + VideoCandidate dataclass + exception tree (TBD-009 Phase 3 baseline)`

## Commit 3 — ModelRegistry config 扩展(`tasks.md` §4)

- [ ] 3.1 编辑 `config/models.yaml` 加 `models.comfy_local_video` entry + `aliases.video_local` entry — 锚点 tasks §4.1 + §4.2
- [ ] 3.2 编辑 `tests/fixtures/test_models.yaml` 同步 — 锚点 tasks §4.4
- [ ] 3.3 加 2 fence to `tests/unit/test_model_registry.py`(`test_comfy_local_video_model_resolves_via_video_local_alias` + `test_video_local_alias_kind_is_video`)— 锚点 tasks §4.5
- [ ] 3.4 跑 `python -m pytest tests/unit/test_model_registry.py -v`(全绿)
- [ ] 3.5 commit:`feat(registry): add comfy/local-video virtual model + video_local alias`

## Commit 4 — ComfyAgentWorker capability-aware 扩 video(`tasks.md` §5)

> **关键 invariant**:D6 4-dict 扩 video + D9+F4 BMFF strict 校验 + D7 无 source bytes + per-candidate seed override(audio G11-F3 sweep mirror)。~16 fence。

- [ ] 4.1 编辑 [`src/framework/providers/workers/comfy_worker.py`](src/framework/providers/workers/comfy_worker.py) 扩 4-dict + `_VIDEO_FORMAT_WHITELIST = {"mp4"}` — 锚点 tasks §5.1
- [ ] 4.2 实现 `generate_video(spec, num_candidates, seed, timeout_s) -> list[VideoCandidate]` per-candidate loop + `_run_once_video` 含 path trust-boundary + 扩展名 whitelist mp4-only + **BMFF strict 4-tuple 校验**(round-2 F4)+ VideoCandidate 构造 — 锚点 tasks §5.2
- [ ] 4.3 verify `__init__` 守门 error message 列出 `comfy/local-video` — 锚点 tasks §5.3
- [ ] 4.4 加 ~16 fence to `tests/unit/test_comfy_subprocess.py`(per `specs/probe-and-validation/spec.md` "ComfyUI video capability dispatch has dedicated regression fences" Requirement 列表;capability dispatch 2 + 三段表 video 行 5+3 regression + BMFF strict 9 fence + per-candidate loop 2 + path trust-boundary 2 + generate_video 实装 7 + single-source 1 + webm rejection 1)— 锚点 tasks §5.4

  关键 fence(由 spec/probe-and-validation 命名锁定):
  - capability dispatch:`test_capability_inferred_video_for_comfy_local_video` + `test_unknown_model_id_raises_at_init_lists_video_in_supported`
  - 三段表 video:`test_video_mode_raises_on_missing_outputs_video` + `..._empty_outputs_video` + `..._rejects_outputs_images` + `..._rejects_outputs_glb` + `..._rejects_outputs_audio` + `test_video_mode_no_auxiliary_log_emission`
  - regression:`test_image_mode_still_rejects_outputs_video_after_change` + `..._mesh_mode_..._after_change` + `..._audio_mode_..._after_change`
  - BMFF strict(round-2 F4):`test_generate_video_bmff_too_short_raises_unsupported_response` + `..._ftyp_mismatch_raises` + `..._box_size_too_small_raises` + `..._box_size_exceeds_len_raises` + `..._box_size_largesize_1_accepted` + `..._major_brand_zero_raises` + `..._major_brand_spaces_raises` + `..._valid_mp4_accepts_with_isom_brand` + `..._valid_mp4_accepts_with_mp42_brand`
  - per-candidate loop + seed override:`test_generate_video_runs_subprocess_num_candidates_times_when_num_gt_one` + `test_generate_video_per_candidate_seed_overrides_comfy_params_seed`
  - path trust-boundary:`test_generate_video_missing_path_raises_unsupported_response` + `..._symlink_path_raises_unsupported_response`
  - generate_video 实装:`test_generate_video_mp4_extension_detection_reads_bytes` + `..._unsupported_extension_mov_raises_unsupported_response` + `..._webm_extension_rejected_pending_follow_on`(round-2 F2)+ `..._metadata_records_comfy_provenance` + `..._metadata_snapshot_is_independent_copy` + `..._metadata_best_effort_when_comfy_does_not_emit` + `..._does_not_mutate_caller_spec_comfy_params` + `..._does_not_read_forgeue_comfy_input_dir_env_var`
  - single-source:`test_video_candidate_metadata_does_not_duplicate_top_level_video_fields`

- [ ] 4.5 跑 `python -m pytest tests/unit/test_comfy_subprocess.py -v`(全绿,既有 image/mesh/audio mode fence 不退化)
- [ ] 4.6 commit:`feat(comfy): extend ComfyAgentWorker with video capability dispatch + generate_video method`

## Commit 5 — GenerateVideoExecutor + ExecutorRegistry 注册(`tasks.md` §6)

> 沿 audio Phase 2 F1-F2 + R7-B retry policy honor + R6-A `shape="mp4"` UE bridge dispatch。~14 fence。

- [ ] 5.1 创建 [`src/framework/runtime/executors/generate_video.py`](src/framework/runtime/executors/generate_video.py) 骨架(类比 generate_audio.py)— 锚点 tasks §6.1
- [ ] 5.2 实现 `GenerateVideoExecutor` 类(class attributes + `_should_use_comfy_worker_path` + `_generate_via_comfy_worker` 三 except 块 + `execute` 含 `repo.put` with `shape="mp4"` 唯一映射)— 锚点 tasks §6.2
- [ ] 5.3 编辑 [`src/framework/runtime/executors/__init__.py`](src/framework/runtime/executors/__init__.py) 加 import — 锚点 tasks §6.3
- [ ] 5.4 编辑 [`src/framework/run.py`](src/framework/run.py) `ExecutorRegistry` setup 段加 `registry.register(GenerateVideoExecutor(...))` — 锚点 tasks §6.4
- [ ] 5.5 加 ~14 fence to `tests/unit/test_generate_video_comfy.py`(executor dispatch 3 + retry budget 4 含 F2 三 except 块 + retry_on honor + 异常 wrap 4 + 持久化 3 + ADR-007 1 + UE bridge integration 2 + FailureModeMap 2)— 锚点 tasks §6.5
- [ ] 5.6 加 2 fence to `tests/unit/test_workflow_loader.py`(`test_video_t2v_capability_ref_dispatches_to_generate_video_executor` + `test_video_t2v_step_rejects_hardcoded_model_id_without_alias`)— 锚点 tasks §6.6
- [ ] 5.7 跑 `python -m pytest tests/unit/test_generate_video_comfy.py tests/unit/test_workflow_loader.py -v`(全绿)
- [ ] 5.8 commit:`feat(executor): introduce GenerateVideoExecutor + video.t2v capability_ref registration in ExecutorRegistry`

## Commit 6 — FailureModeMap video_worker_* mode(`tasks.md` §7)

> D14 priority:VideoWorkerTimeout 必须**先于** AudioWorkerTimeout / generic 匹配。+6 fence。

- [ ] 6.1 编辑 [`src/framework/runtime/failure_mode_map.py`](src/framework/runtime/failure_mode_map.py) 加 `video_worker_timeout` + `video_worker_unsupported` mode 默认 abort_or_fallback — 锚点 tasks §7.1
- [ ] 6.2 在 `from_exception` 加 video isinstance check **在 audio / mesh / generic 之前** — 锚点 tasks §7.2
- [ ] 6.3 加 6 fence to `tests/unit/test_failure_mode_map.py`(per spec/probe-and-validation 命名)— 锚点 tasks §7.3
- [ ] 6.4 跑 `python -m pytest tests/unit/test_failure_mode_map.py -v`(全绿)
- [ ] 6.5 commit:`feat(failure-mode): map VideoWorkerTimeout / VideoWorkerUnsupportedResponse to abort_or_fallback`

## Commit 7 — UE bridge framework-side(`tasks.md` §8a)

> D1 + D12:`_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + `_default_import_options` 加 video + `metadata_overrides` 白名单 + import_plan_builder + permission tier。~5-7 fence。

- [ ] 7.1 编辑 [`src/framework/ue_bridge/manifest_builder.py`](src/framework/ue_bridge/manifest_builder.py) `_KIND_MAP` 加 `("video", "mp4"): "file_media_source"` + `_PREFIX_BY_KIND["file_media_source"] = "MS_"` + `_default_import_options` 新分支 + `metadata_overrides` 白名单加 video keys + 顶部 docstring 更新 — 锚点 tasks §8a.1-8a.5
- [ ] 7.2 编辑 [`src/framework/ue_bridge/import_plan_builder.py`](src/framework/ue_bridge/import_plan_builder.py) 加 file_media_source asset_kind → import_file_media_source operation kind 映射 — 锚点 tasks §8a.6
- [ ] 7.3 加 ~5 fence to `tests/unit/test_manifest_builder.py`(`test_kind_map_video_mp4_routes_to_file_media_source` + `test_prefix_by_kind_file_media_source_is_MS_underscore` + `test_default_import_options_for_file_media_source_kind_returns_video_keys` + `test_metadata_overrides_whitelist_includes_video_keys` + `test_video_artifact_with_mp4_shape_produces_ms_prefixed_ue_name`)— 锚点 tasks §8a.8
- [ ] 7.4 加 1-2 fence to `tests/unit/test_ue_bridge.py`(`test_import_plan_builder_maps_file_media_source_to_import_file_media_source_op`)— 锚点 tasks §8a.9
- [ ] 7.5 跑 `python -m pytest tests/unit/test_manifest_builder.py tests/unit/test_ue_bridge.py -v`(全绿)
- [ ] 7.6 commit:`feat(ue-bridge): map (video, mp4) to file_media_source asset_kind with MS_ prefix in manifest_builder`

## Commit 8 — UE-script-side domain_video.py + run_import dispatch(`tasks.md` §8b)

> D12 关键:`Content/Movies/<run_id>/<MS_<base>>.mp4` 路径分流 + `Content/Generated/<run_id>/<MS_<base>>.uasset`;NFR-PORT-003 `domain_video` 不 import framework。

- [ ] 8.1 创建 [`ue_scripts/domain_video.py`](ue_scripts/domain_video.py) 含 `import_video_entry(entry, project_root)` — 锚点 tasks §8b.1
- [ ] 8.2 实装 D12 路径分流(mp4 → Content/Movies/, .uasset → Content/Generated/)+ `unreal.FileMediaSourceFactory` + `AssetImportTask` + file_path editor property — 锚点 tasks §8b.2
- [ ] 8.3 编辑 [`ue_scripts/run_import.py`](ue_scripts/run_import.py) `_OP_HANDLERS` 加 `"import_file_media_source": domain_video.import_video_entry` + import 段 — 锚点 tasks §8b.3 + §8b.4
- [ ] 8.4 加 3 fence to `tests/integration/test_p4_ue_manifest_only.py`(per spec/probe-and-validation P4 真机 stub fence 列表)— 锚点 tasks §8b.5
- [ ] 8.5 加 1 fence to `tests/unit/test_ue_scripts_no_framework_import.py`(`test_domain_video_does_not_import_framework`)— 锚点 tasks §8b.6
- [ ] 8.6 跑 `python -m pytest tests/integration/test_p4_ue_manifest_only.py tests/unit/test_ue_scripts_no_framework_import.py -v`(全绿)
- [ ] 8.7 commit:`feat(ue-scripts): add domain_video.import_video_entry with Content/Movies/ packaging path split`

## Commit 8c — Export gate sweep(`tasks.md` §8c,**round-2 F1 NEW**)

> **关键 round-2 F1 修订**:三处必须同 commit 改 — `_is_importable` whitelist + `PermissionPolicy.allow_import_file_media_source` + `_OP_ALLOW_ATTR["import_file_media_source"]`。否则 video Artifact 在 `ExportExecutor` 阶段被静默过滤,P4 真机看不到 .uasset。+5 fence(2 unit + 1 unit + 2 integration P4)。

- [ ] 8c.1 编辑 [`src/framework/runtime/executors/export.py:215`](src/framework/runtime/executors/export.py#L215) `_is_importable` modality whitelist 加 `"video"` — 锚点 tasks §8c.1
- [ ] 8c.2 编辑 [`src/framework/core/policies.py:96`](src/framework/core/policies.py#L96) `PermissionPolicy` 加 `allow_import_file_media_source: bool = True` — 锚点 tasks §8c.2
- [ ] 8c.3 编辑 [`src/framework/ue_bridge/permission_policy.py:18`](src/framework/ue_bridge/permission_policy.py#L18) `_OP_ALLOW_ATTR` dict 加 `"import_file_media_source": "allow_import_file_media_source"` entry — 锚点 tasks §8c.3
- [ ] 8c.4 创建 [`tests/unit/test_export_is_importable.py`](tests/unit/test_export_is_importable.py) 加 1 fence:`test_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension` — 锚点 tasks §8c.4
- [ ] 8c.5 加 2 fence to `tests/unit/test_permission_policy.py`(`test_permission_policy_default_allows_import_file_media_source` + `test_is_op_allowed_grants_import_file_media_source_under_default_policy`)— 锚点 tasks §8c.5
- [ ] 8c.6 加 2 integration fence to `tests/integration/test_p4_ue_manifest_only.py`(`test_p4_export_executor_passes_video_artifact_through_is_importable_to_manifest_builder` + `test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence`)— 锚点 tasks §8c.6
- [ ] 8c.7 跑 `python -m pytest tests/unit/test_export_is_importable.py tests/unit/test_permission_policy.py tests/integration/test_p4_ue_manifest_only.py -v`(全绿;特别验证 F1 sweep 修复效果)
- [ ] 8c.8 commit:`feat(export): sweep video modality through ExportExecutor _is_importable + PermissionPolicy.allow_import_file_media_source + permission_policy._OP_ALLOW_ATTR (round-2 F1 fix)`

## Commit 9 — DryRunPass extension(`tasks.md` §9a)

- [ ] 9.1 编辑 [`src/framework/runtime/dry_run_pass.py`](src/framework/runtime/dry_run_pass.py) `_check_comfy_reachability` gate 扩 `comfy/local-video` — 锚点 tasks §9a.1
- [ ] 9.2 加 1 fence to `tests/unit/test_dry_run_pass.py`(`test_dry_run_probes_comfy_when_comfy_local_video_in_routes`)— 锚点 tasks §9a.3
- [ ] 9.3 跑 `python -m pytest tests/unit/test_dry_run_pass.py -v`(全绿)
- [ ] 9.4 commit:`feat(dry-run): extend ComfyUI reachability probe gate to include comfy/local-video`

## Commit 10 — examples/comfy_local_smoke_video.json bundle(`tasks.md` §9b)

> D3 + D5 关键:`comfy_workflow: "Vedio/Wan2.1-T2V-1.3B_native_5sec"`(D5 上游拼写)+ `worker_timeout_s: 600`(D3:Wan T2V 7-min)。

- [ ] 10.1 创建 [`examples/comfy_local_smoke_video.json`](examples/comfy_local_smoke_video.json)(完整 JSON per tasks §9b.1)— 锚点 tasks §9b.1
- [ ] 10.2 加 1 fence to `tests/integration/test_example_bundles_smoke.py`(`test_comfy_local_smoke_video_loads_with_video_local_alias_and_no_workflow_graph`)— 锚点 tasks §9b.2
- [ ] 10.3 跑 `python -m pytest tests/integration/test_example_bundles_smoke.py -v`(全绿)
- [ ] 10.4 commit:`feat(examples): add comfy_local_smoke_video.json bundle (text-to-video single step, Wan 2.1 1.3B 5sec)`

## Commit 11 — probe_comfy_video.py(`tasks.md` §9c)

- [ ] 11.1 创建 [`probes/provider/probe_comfy_video.py`](probes/provider/probe_comfy_video.py)(沿 audio probe 模板)— 锚点 tasks §9c.1
- [ ] 11.2 实装 opt-in `FORGEUE_PROBE_COMFY_VIDEO=1` + 模块顶层零副作用 + BMFF strict 校验(round-2 F4)+ ASCII `[OK]` / `[FAIL]` / `[SKIP]` 标记 — 锚点 tasks §9c.2
- [ ] 11.3 加 1 fence to `tests/unit/test_probe_framework.py`(`test_probe_comfy_video_default_skip_without_optin`)— 锚点 tasks §9c.3
- [ ] 11.4 跑 `python -m pytest tests/unit/test_probe_framework.py -v`(全绿)
- [ ] 11.5 commit:`feat(probes): add probe_comfy_video.py opt-in video smoke (FORGEUE_PROBE_COMFY_VIDEO=1)`

## Commit 12-15 — Documentation Sync Gate(`tasks.md` §10)

详见 [tasks.md](../tasks.md) §10.1-§10.4 4 commit splits(SRS+LLD / HLD+test_spec / acceptance+CHANGELOG / CLAUDE+AGENTS)。每 commit 跑 `/forgeue:change-doc-sync` 静态扫描确认 [REQUIRED] 全 sync。

## Commit 16 — L2 evidence + a2_video UE 真机 P4(`tasks.md` §11)

> D15 关键:commandlet 自动化(沿 a2_mesh 2026-04-23 模式),Bash 直接驱动 `UnrealEditor-Cmd.exe -ExecutePythonScript=...`。L2 evidence + a2_video evidence 落 `notes/live_smoke_video_<date>.md`。**用户必须在 §11.1 准备步骤预先暖启 ComfyUI**(Wan 1.3B ~3GB HuggingFace 拉首次慢)。

- [ ] 16.1 用户准备:Wan 1.3B 模型权重已缓存 — 锚点 tasks §11.1
- [ ] 16.2 终端 1 启 ComfyUI — 锚点 tasks §11.2
- [ ] 16.3 跑 framework smoke `--task examples/comfy_local_smoke_video.json --live-llm --run-id video_smoke_l2_<date>`(预期总耗时 9-10 分钟)— 锚点 tasks §11.3
- [ ] 16.4 验证 L2 evidence:文件存在 + 大小 > 1MB + BMFF strict 4-tuple(round-2 F4)+ producer attribution + 5 metadata None — 锚点 tasks §11.4
- [ ] 16.5 evidence 文件 `notes/live_smoke_video_<date>.md` 落 framework section — 锚点 tasks §11.5
- [ ] 16.6 用户准备 UE 5.x + PythonScriptPlugin enabled — 锚点 tasks §11b.1
- [ ] 16.7 设 `FORGEUE_RUN_FOLDER` env — 锚点 tasks §11b.2
- [ ] 16.8 跑 commandlet `UnrealEditor-Cmd.exe -ExecutePythonScript=ue_scripts/run_import.py -nullrhi -nosplash -unattended` — 锚点 tasks §11b.3
- [ ] 16.9 验证 UE-side a2_video evidence:`Content/Movies/<run_id>/<MS_<base>>.mp4` + `Content/Generated/<run_id>/<MS_<base>>.uasset` + `evidence.json` 含 `import_file_media_source` `status="success"` — 锚点 tasks §11b.4
- [ ] 16.10 evidence 文件 `notes/live_smoke_video_<date>.md` 续写 a2_video section — 锚点 tasks §11b.5
- [ ] 16.11 commit:`docs(openspec): L2 + a2_video P4 actual PASS evidence + commandlet automation`

## Cross-cutting verification(每 commit 跑)

- `python -m pytest <touched_fence_files> -v`(全绿)
- post-commit-chain `python -m pytest -q` 实测,基线 1294 → 预计 ~1352(round-2 F1+F4 修订:+58 fence)
- post-§8c verify F1 sweep:`python -m pytest tests/unit/test_export_is_importable.py tests/unit/test_permission_policy.py tests/integration/test_p4_ue_manifest_only.py -v`(F1 sweep verification 必跑)
- post-§5 verify D9+F4 BMFF strict:`python -m pytest tests/unit/test_comfy_subprocess.py -v -k bmff`(BMFF 9 fence 必绿)

## DRIFT 处理协议(STOP + 回写)

若 implementer 在实施过程中发现 contract gap / 越界需求,MUST STOP 并按 4 类 DRIFT 处理:

- **Type 1 evidence_introduces_decision_not_in_contract**:发现需要新决策(如 D-* 标签)而 design.md 未列 → 回写到 design.md `## Decisions` 段
- **Type 2 evidence_references_missing_anchor**:micro_task 引用 `tasks.md#X.Y` 但 tasks.md 没有该 anchor → 回写到 tasks.md 加 sub-task
- **Type 3 evidence_contradicts_contract**:实施细节与 spec 文字矛盾 → 回写到 spec/<capability>/spec.md MODIFIED Requirement
- **Type 4 evidence_exposes_contract_gap**:实施暴露 design / spec 没考虑的真实场景(如 `ExportExecutor._is_importable` round-1 漏掉的 export gate sweep)→ 回写到 design.md(新决策段)+ tasks.md(新 task)+ spec(新 ADDED Requirement);本 round-2 F1 即此类示范
