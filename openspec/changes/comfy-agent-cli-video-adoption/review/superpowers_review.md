---
change_id: comfy-agent-cli-video-adoption
stage: S6
evidence_type: superpowers_review
contract_refs: [proposal.md, design.md, tasks.md, specs/provider-routing/spec.md, specs/runtime-core/spec.md, specs/artifact-contract/spec.md, specs/ue-export-bridge/spec.md, specs/probe-and-validation/spec.md, specs/examples-and-acceptance/spec.md]
aligned_with_contract: true
detected_env: claude-code
triggered_by: "/forgeue:change-review (Superpowers requesting-code-review finalize)"
codex_plugin_available: true
---

# Superpowers Review — Finalize (2026-05-04)

## Scope

OpenSpec change comfy-agent-cli-video-adoption(TBD-009 Phase 3)16 commits 全 diff vs base 5ea85ae。涵盖:framework 实施(`src/framework/providers/workers/video_worker.py` + `comfy_worker.py` 扩展 + `runtime/executors/generate_video.py` + `manifest_builder.py` + `policies.py` + `core/ue.py` + `runtime/failure_mode_map.py`)、UE 桥接(`ue_scripts/domain_video.py` + `ue_scripts/run_import.py` _OP_HANDLERS 扩展)、48+ fence 增量、6 spec deltas、design.md 15 决策(D1-D15 + 5 D-extension)、L2 + a2_video P4 commandlet 实测 evidence。

## 评审分类

### A. 设计契约一致性

- ✅ 15 决策 D1-D15 全有 design.md Reasoning 段记录(round-1/2/3/7);7 轮 codex review 全收敛 (disputed_open=0);writeback 真实(commit 1185377 round-3 PF1-PF4 + commit 1dfa5db round-7 R1+R2)
- ✅ 6 spec deltas 全 ADDED 模式(provider-routing 12th model id `comfy/local-video` + video_local alias;runtime-core video.t2v capability;artifact-contract modality "video" Literal;ue-export-bridge file_media_source asset map + MS_ prefix;probe-and-validation BMFF strict;examples-and-acceptance bundle)
- ✅ MODIFIED Requirement 检查:provider-routing 沿用 ADDED(避免二次 MODIFIED 历史 Phase 1/2 已 MODIFIED 的 Requirement,符合 OpenSpec 惯例)— 已在 design D-extension R-MODIFIED-2 显式登记

### B. 实施完整性

- ✅ ComfyAgentWorker 4-dict capability dispatch(image / mesh / audio / video)— `generate_video` 走专属方法,与 audio/mesh 路径对称
- ✅ FailureModeMap D14 priority(video before audio before mesh before generic)— commit 6 实装 + fence `test_failure_mode_map_video_takes_priority_over_generic_worker_exception` cover
- ✅ Round-2 F1 4-处 export gate sweep(`export.py:215` _is_importable + `policies.py:96` PermissionPolicy + `permission_policy.py:18` _OP_ALLOW_ATTR + `core/ue.py` UEImportOperation.kind Literal)— 4 commits 同步 sweep 防 video import 默认 deny 漏洞
- ✅ BMFF strict 5-tuple 校验(`comfy_worker.py:1382-1410`)— len ≥ 16 + ftyp at offset 4 + box_size in [8,len] reject box_size==1 + major_brand non-empty/non-zero/non-spaces;round-3 PF2 写入 reject largesize follow-on `video-bmff-largesize-support`

### C. Live Smoke Evidence

- ✅ L2 video_smoke_l2_20260504_v3 实测:status: succeeded;589564 bytes mp4;hash ff0e213aad...;BMFF strict 5-tuple 全通过(box_size=32,ftyp@4,major_brand=b"isom",len=589564);ArtifactType.modality="video"+shape="mp4"+mime_type="video/mp4";producer.provider="comfy_agent_cli"+model="comfy/local-video"
- ✅ a2_video_20260504_v2 P4 真机 commandlet:UE 5.7 UnrealEditor-Cmd.exe + nullrhi + nosplash + unattended;evidence 三 op 全 success;`MS_a2_video_20260504_v2_step_video_cand_video_0.uasset`(1702 bytes)落 Content/Generated/Video/;`MS_..._cand_video_0.mp4`(338512 bytes)落 Content/Movies/;FileMediaSource.file_path="Movies/a2_video_20260504_v2/MS_..._cand_video_0.mp4" 相对 Content/(D12 packaging path 分流实测验证)

### D. Round-7 Contract Gap Writeback(implementation 期暴露)

- **R1 D1 implementation gap**(P4 commandlet 实测):UE 5.7 FileMediaSource asset 类无 `loop` / `play_on_open` editor property — domain_video.py:99-102 移除 + 加 UE API 边界注释;import_options 在 manifest 保留给 follow-on(LevelSequence / MediaPlayer 配置层)消费;design.md `## Reasoning Notes — round-7 P4 commandlet writeback (2026-05-04)` R1 段登记;evidence aligned_with_contract: false + drift_decision: written-back-to-domain_video.py
- **R2 D-Runner-Extension SHARED_DIR 扩展**(L2 实测):Wan T2V manifest(`Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + `..._native.json`)漏 5 个 VHS_VideoCombine widget default patch(frame_rate=24.0 / loop_count=0 / format="video/h264-mp4" / pingpong=false / save_output=true);两份 manifest 已补;design.md round-7 R2 + CLAUDE.md ComfyUI 接入段 D-Runner-Extension 已显式登记 manifest 路径

### E. 非阻塞 follow-on(已登记,不进 SRS §7.3)

- `comfy-video-webm-adoption`(round-2 F2 webm follow-on,触发 = 用户实际 webm use case)
- `video-bmff-largesize-support`(round-3 PF2 largesize follow-on,触发 = 真实 mp4 ≥ 4GiB)
- `video-metadata-parser`(D8 single-source 5 个 metadata 字段 None 默认,follow-on parser stdlib 解析 mvhd box / track header)
- `video-worker-remote-adoption`(D-Runner-Extension scope 外,远端 video provider 接入)
- `comfy-video-image-sequence-adoption`(D1 alternative 路径,LevelSequence + image sequence,本 change scope 外)
- `comfy-video-level-sequence-adoption`(round-7 R1 alternative 路径,与 LevelSequence + MediaPlayer 配置层 follow-on 同源)

## 评审结论

**APPROVE for archive**:

- 16 commits 全 atomicity 合理(commit 1 = ArtifactType modality 1-line + 1 fence;commit 2 = VideoWorker baseline;commit 4 = ComfyAgentWorker dispatch;commit 7-8 = framework + UE-script 拆分;commit 10-15 = bundle / docs / fence / writeback / round-7 收尾;commit 16 = L2 + P4 evidence + R1 R2 writeback)
- 7 轮 codex review 全收敛(disputed_open=0)
- pytest -q 实测 1414 passed(+120 fence over baseline 1294)
- L0 verify_report PASS;doc_sync_report 9/9 REQUIRED touched
- L2 framework.run 真实 ComfyUI subprocess 跑通(15min Wan 2.1 1.3B);a2_video P4 真机 UE 5.7 commandlet 三 op evidence 全 success
- D12 packaging path 分流实测验证(.uasset → Content/Generated/Video/, .mp4 → Content/Movies/)

**Documentation sync gate**:9 [REQUIRED] 全 touched;OPTIONAL README 评估为不需要;round-7 增量(R1 + R2)在 design.md round-7 段 + CLAUDE.md ComfyUI 接入段 D-Runner-Extension 显式登记。

**Archive readiness**:可走 `openspec archive comfy-agent-cli-video-adoption --target main`;sync-specs 阶段会自动 merge 6 spec deltas 到 `openspec/specs/`。
