---
change_id: comfy-agent-cli-audio-adoption
stage: S6
evidence_type: superpowers_review
contract_refs:
  - design.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: "/forgeue:change-review"
codex_plugin_available: true
created_at: 2026-05-03T15:20:00+00:00
---

# Superpowers Code Review (Finalize) — comfy-agent-cli-audio-adoption

> Sourced from Claude implementation notes during S4-S5 apply stage; consolidated as
> finalize evidence per `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.4.

## Scope reviewed

13-commit chain from `feat(audio): introduce AudioWorker ABC` through
`docs(notes): record L2 audio smoke deferred`(commit range covering ~55 files):

1. `feat(audio)` — AudioWorker ABC + AudioCandidate + 异常树 + FakeAudioWorker
2. `feat(registry)` — config/models.yaml + tests/fixtures/test_models.yaml audio_local alias
3. `feat(comfy)` — ComfyAgentWorker 4-dict audio capability + generate_audio + magic bytes
4. `feat(executor)` — GenerateAudioExecutor + ExecutorRegistry registration
5. `feat(failure-mode)` — audio_worker_timeout / audio_worker_unsupported FailureMode + classify priority
6. `feat(dry-run)` — DryRunPass._check_comfy_reachability gate set 扩 audio_local
7. `feat(examples)` — examples/comfy_local_smoke_audio.json bundle
8. `feat(probes)` — probes/provider/probe_comfy_audio.py opt-in
9-12. `docs(srs+lld+hld)` / `docs(test_spec+acceptance)` / `docs(changelog+claude)` 三组 doc sync
13. `docs(notes)` — L2 evidence DEFERRED post-archive(ComfyUI workflow JSON 上游 bug)

## Self-review highlights

### Cohesion
- 4-dict capability dispatch 表(`_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` /
  `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP`)沿 Phase 1 mesh
  扩展形态;新增 `_AUDIO_FORMAT_WHITELIST = {"flac","mp3","wav"}` class const
  避免函数级硬编码。
- F2 三-except 块(`ComfyWorkerTimeout → AudioWorkerTimeout` retry honor `_should_retry` /
  `ComfyWorkerUnsupportedResponse → AudioWorkerUnsupportedResponse` immediate raise /
  `ComfyWorkerError → AudioWorkerError` immediate raise)精确镜像 `generate_mesh.py`
  pattern,wrapping 用 `from exc` 保留 traceback chain。

### Test coverage
- `test_audio_worker.py` 6 fence(必填字段 / format Literal whitelist / duration_seconds default None /
  sample_rate default None / 异常 inheritance / FakeAudioWorker.generate_audio 返 list[AudioCandidate])
- `test_comfy_subprocess_audio.py` 19 fence(capability gate / outputs.audio missing /
  扩展名 whitelist / magic bytes mismatch / symlink 拒 / per-candidate seed 偏移 / 5 metadata 键)
- `test_generate_audio_comfy.py` 14 fence((StepType.generate, audio.t2a) lookup /
  _should_use_comfy_worker_path / F2 三-except / ArtifactType / file_suffix / metadata 三键 /
  worker_metadata 嵌套 / RetryPolicy.retry_on honor)
- 总计 +49 fence(目标 +30~35 估算偏低,实测可接受 — NFR-MAINT-003 不硬编码合规)

### Frontmatter compliance
- 20 formal evidence files:7 review(1 codex_design + 1 codex_plan + 6 codex_plan_round2-7)+
  8 cross-check(1 design + 7 plan rounds)+ 5 verification + notes
- 12-key audit frontmatter全 present;`disputed_open` 全 0;`drift_decision` + `writeback_commit`
  在 `aligned_with_contract: false` 时填全(round-5 commit `6118671`,各 round-2/3/4 同链)

### Risks identified + addressed
- F-Plan-R7-A:audio metadata single-source(三键 source-of-truth 在 `Artifact.metadata` 顶层,
  **不**在 `worker_metadata` 嵌套内重复)— spec.md + executor + tests aligned
- F-Plan-R7-B:`_should_retry(policy, wrapped)` honors `RetryPolicy.retry_on`(非全转 retry)
- F-Plan-R7-C:path containment defense **未加**(disputed-permanent-drift,symmetry argument
  with image/mesh executors;design.md Reasoning Notes anchor 锁论证)
- F6:Stable Audio Open 1.0 Stability AI Community License($1M revenue threshold)→ CLAUDE.md
  写入 license note + 用户与上游对齐;ForgeUE 不分发权重

### L2 evidence DEFERRED post-archive
- 框架路径完整 verify(routing → ExecutorRegistry → generate_audio → subprocess → wrap →
  FailureModeMap → Decision.abort_or_fallback;run `audio_smoke_224008` 凭证)
- Blocker:ComfyUI 0.9.2 user-authored workflow JSON `SaveAudioMP3` 缺 `quality`
  required input(out of scope per CLAUDE.md);沿 Phase 1 mesh L2 partial precedent;
  reproduction 步骤 + 1-line workflow fix(`SaveAudioMP3 → SaveAudio`)记 notes file

## Verdict

**APPROVE for archive**(L2 evidence post-archive 不阻断,Phase 1 precedent;Level 0 PASS
1294 tests;framework adoption verified;upstream blocker 不可在 ForgeUE 仓库 scope 内修复)。

## References

- `verification/verify_report.md` — Level 0 1294 passed
- `verification/doc_sync_report.md` — 0 drifts,REQUIRED 全 touched
- `notes/live_smoke_audio_blocked_20260503.md` — L2 deferred reasoning
- 8 codex review rounds 全 writeback `disputed_open: 0`(plan_cross_check_round1-7 + design_cross_check)
