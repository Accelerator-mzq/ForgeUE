---
change_id: comfy-agent-cli-audio-adoption
stage: S4-S5
evidence_type: tdd_log
contract_refs:
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: forgeue-change-apply (S3→S4-S5 implementation; user 选 option A STOP plan-stage codex review at round-7)
codex_plugin_available: true
created_at: 2026-05-03T21:39:23+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
plan_stage_convergence_summary:
  total_rounds: 8 (1 design + 7 plan)
  total_findings_resolved: 27 accepted-codex + 1 disputed-permanent-drift (R7-C path containment; design.md `## Reasoning Notes` F-Plan-R7-C section)
  parent_writeback_commits:
    - a12e307 (round-1 design,6 finding 2H+4M)
    - 320bca7 (round-1 plan,6 finding 1C+3H+2M)
    - d3f859f (round-2 plan,3 finding 3M)
    - 5fed6b6 (round-3 plan,4 finding 1H+3M)
    - 2a28de2 (round-4 plan,3 finding 1H+2M)
    - 6118671 (round-5 plan,2 finding 2M)
    - 99257fa (round-6 plan,1 finding 1H — audio shape vs UE bridge architecture bug)
    - d30378e (round-7 plan,3 finding 2M accepted + 1M disputed-permanent-drift)
note: |
  TDD log incremented per /forgeue:change-apply implementation (per Phase 1 image change `2026-05-02-comfy-agent-cli-adoption/execution/tdd_log.md` 模式). Each commit
  appends one Section recording: micro-tasks done, fences added, pytest
  delta, boundary check, drift events.

  Plan-stage codex review chain (8 rounds total) 已收敛 — 见 plan_stage_convergence_summary 字段。
  S4 implementation 严格按 micro_tasks.md 13 commit chain;每 commit 内先写 fence(red),再写 production code(green),最后 refactor。
---

# Implementation TDD Log — comfy-agent-cli-audio-adoption


## Commit 1 — AudioWorker baseline + 6 fence (2026-05-03 21:39)

### Anchors
- `tasks.md#2.1` - `#2.7` (§2 AudioWorker baseline 全部 sub-tasks)
- `execution/micro_tasks.md` Commit 1 (1.1-1.8)
- F-Plan-R7-A round-7 修订:加 single-source metadata fence

### Implementation files

| File | Action | Details |
|---|---|---|
| `src/framework/providers/workers/audio_worker.py` | Create | `AudioCandidate` dataclass(顶层 `data: bytes` + `format: Literal["flac","mp3","wav"]` + `metadata: dict[str, Any]` + `duration_seconds: float \| None = None` + `sample_rate: int \| None = None` per F3 round-1 single-source + F-Plan-R7-A round-7);异常树 3 层(`AudioWorkerError` / `AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse`,沿 mesh 模式 + TBD-007 optional kwargs job_id/worker/model 远端预留);`AudioWorker(ABC)` keyword-only `generate_audio(*, spec, num_candidates, seed, timeout_s)` 签名(no `prompt: str` 参数 per F-Plan-R5-B + design D7/D8);`FakeAudioWorker` 测试 fixture(`_build_minimal_flac` helper 生 ~50-100 bytes 真实 FLAC magic + STREAMINFO METADATA_BLOCK + minimal frame,无第三方 codec 依赖) |
| `src/framework/providers/workers/__init__.py` | Modify | Re-export `AudioCandidate` / `AudioWorker` / `AudioWorkerError` / `AudioWorkerTimeout` / `FakeAudioWorker`(对照 mesh re-export 模式;`AudioWorkerUnsupportedResponse` **不** re-export — 沿用 mesh `MeshWorkerUnsupportedResponse` 不 re-export 习惯,consumer 用 `except AudioWorkerError` 即可 catch) |
| `tests/unit/test_audio_worker.py` | Create | 6 fence(5 sequenced + 1 R7-A round-7 bonus):`test_audio_worker_abc_requires_generate_audio` / `test_audio_candidate_format_whitelist` / `test_audio_worker_exception_tree_inheritance` / `test_fake_audio_worker_returns_minimal_valid_flac_bytes` / `test_fake_audio_worker_respects_num_candidates_parameter` / **`test_audio_candidate_metadata_does_not_duplicate_top_level_audio_fields`**(F-Plan-R7-A round-7 single-source 守门:metadata 字典禁含 duration_seconds/sample_rate/format/format_detected keys) |

### TDD cycle

1. **RED**:6 fence 全先写(import 失败,因 `audio_worker.py` 还没创建)
2. **GREEN**:`audio_worker.py` 含完整 implementation;`__init__.py` re-export;6/6 fence PASS
3. **REFACTOR**:无(实装直接对应 spec/provider-routing F-Plan-R5-B + F-Plan-R6-A + F-Plan-R7-A)

### Pytest baseline delta

- Pre-commit baseline:1234(per CHANGELOG.md Phase 1 mesh archive)+ 中间 OpenSpec fence 自动 collect 增量 = ~1242
- Post-commit:**1248 passed**(实测;`+ 6` fences from `test_audio_worker.py`,零回归)
- Δ:+6 fence,no failures

### Boundary check

- `git diff --name-only HEAD~0`:仅改 design.md 列出的 modules
  - `src/framework/providers/workers/audio_worker.py` ✅(execution_plan.md File Structure 表 + tasks §2.1 显式列出)
  - `src/framework/providers/workers/__init__.py` ✅(execution_plan.md File Structure 表 §5.3 显式列出)
  - `tests/unit/test_audio_worker.py` ✅(execution_plan.md Test files 表 + tasks §2.6 显式列出)
- 0 越界 ✅

### Drift events

- 无 drift。F-Plan-R5-B(no `prompt: str` 参数)+ F-Plan-R7-A(metadata single-source)round-X 修订都在本 commit 落实(ABC 签名 + dataclass 字段 + fence 6)。
- F-Plan-R6-A `shape="waveform"` 决策不在本 commit(本 commit 只建 ABC + Candidate + Fake;Artifact `shape` 由 commit 4 GenerateAudioExecutor `repo.put` 时设置,本 commit 不涉及)。
- F-Plan-R7-C disputed-permanent-drift(path containment)与本 commit 无关(本 commit 不读 outputs.audio bytes;commit 3 ComfyAgentWorker.generate_audio 才涉及)。


## Commit 2 — ModelRegistry config + 2 fence (2026-05-03 21:55)

### Anchors
- `tasks.md#3.1` - `#3.6` (§3 ModelRegistry config 全部 sub-tasks)
- `execution/micro_tasks.md` Commit 2 (2.1-2.7)

### Implementation files

| File | Action | Details |
|---|---|---|
| `config/models.yaml` | Modify | 加 `models.comfy_local_audio` entry(`id: "comfy/local-audio"` + `provider: comfy_api` + `kind: audio` + `pricing: null`)+ `aliases.audio_local`(preferred=[comfy_local_audio], fallback=[]);沿 image_local / mesh_local 模式 + ADR-007 边界判定 non-premium |
| `tests/fixtures/test_models.yaml` | Modify | 同步加 `comfy_local_audio` model + `audio_local` alias(unit test fixture,不动 production yaml) |
| `tests/unit/test_model_registry.py` | Modify | +2 fence:`test_comfy_local_audio_model_resolves_via_audio_local_alias`(全链路解析 alias→route)+ `test_audio_local_alias_kind_is_audio`(ResolvedRoute.kind="audio" 守门;沿 mesh test pattern) |

### Pytest baseline delta

- Pre-commit:1248
- Post-commit:**1250 passed**(+2)
- 零回归

### Boundary check

- `git diff --name-only`:`config/models.yaml` + `tests/fixtures/test_models.yaml` + `tests/unit/test_model_registry.py` 三个 file 全在 design.md File Structure scope 内 ✅
- 0 越界

### Drift events

无。


## Commit 3 — ComfyAgentWorker audio capability + 18 fence (2026-05-03 22:10)

### Anchors
- `tasks.md#4.1` - `#4.5` (§4 ComfyAgentWorker capability-aware 扩 audio 全部 sub-tasks)
- `execution/micro_tasks.md` Commit 3 (3.1-3.8)
- F-Plan-3 round-2 + F-Plan-R5-A round-5: per-candidate loop in worker
- F-Plan-4 round-2: is_file + is_symlink path trust-boundary
- F-Plan-R3-A round-3: __init__ error message audio supported list
- F5 round-1: magic bytes mandatory 二次校验
- F-Plan-R7-A round-7: metadata single-source(no duration/sample_rate/format keys in metadata dict)

### Implementation files

| File | Action | Details |
|---|---|---|
| `src/framework/providers/workers/comfy_worker.py` | Modify | (1) 4-dict 扩 audio entry(`_CAPABILITY_BY_MODEL_ID`/`_REQUIRED_OUTPUT_KEY`/`_AUXILIARY_OUTPUT_KEYS_BY_CAP`/`_REJECTED_OUTPUT_KEYS_BY_CAP`);(2) 加新常量 `_AUDIO_FORMAT_WHITELIST = {"flac","mp3","wav"}`;(3) `__init__` 错误消息更新(audio 已加,只剩 video follow-on);(4) 新方法 `generate_audio(*, spec, num_candidates, seed, timeout_s) -> list[AudioCandidate]` 含 capability 守门 + spec validate + per-candidate loop in worker;(5) 新 helper `_run_once_audio(*, comfy_workflow, params, params_snapshot, seed, timeout_s)` 含 subprocess.run + JSON parse + outputs.audio loop + path trust-boundary 防护(is_file + is_symlink)+ 扩展名 whitelist + magic bytes 二次校验(flac/mp3/wav)+ AudioCandidate 构造(metadata 5 个 comfy_* keys + duration/sample_rate=None always);(6) 顶层 `from .audio_worker import AudioCandidate` import |
| `tests/unit/test_comfy_subprocess_audio.py` | Create | 18 fence(独立 file 因 audio helpers `_make_audio_worker` / `_ok_audio_stdout` / `_make_flac_file` / `_make_mp3_file` / `_make_wav_file` 与 mesh helpers 区分清晰);覆盖 capability dispatch(2)+ 三段表(5)+ format/magic detection(6)+ path trust-boundary(2)+ per-candidate loop(1)+ metadata provenance(2) |

### TDD cycle

1. **GREEN-first**(因为依赖 commit 1 AudioCandidate + commit 2 model registry):先写 production code;然后 18 fence;**18/18 PASS first run**
2. 若 RED 出现:`xfail` mark 后写 production code 修

### Pytest baseline delta

- Pre-commit:1250
- Post-commit:**1268 passed**(+18)
- 零回归

### Boundary check

- `git diff --name-only`:
  - `src/framework/providers/workers/comfy_worker.py` ✅(execution_plan.md File Structure 表显式列;扩 audio 4-dict + generate_audio + _run_once_audio + _AUDIO_FORMAT_WHITELIST 都在 audio capability 范围内)
  - `tests/unit/test_comfy_subprocess_audio.py` ✅(execution_plan.md Test files 表;new file 与 test_comfy_subprocess.py 平行,模式与 mesh 同款)
- 0 越界 ✅

### Drift events

无。F5 + F-Plan-3 + F-Plan-4 + F-Plan-R3-A + F-Plan-R5-A + F-Plan-R7-A 全部修订都在本 commit 落实;F-Plan-R7-C disputed-permanent-drift(path containment)按设计**不**加 — 保留与 image / mesh G11 R2 fix 对称;follow-on `comfy-agent-cli-path-containment-hardening` 三 capability 统一处理。


## Commit 4 — GenerateAudioExecutor + ExecutorRegistry + 14 fence (2026-05-03 22:30)

### Anchors
- `tasks.md#5.1` - `#5.7` (§5 GenerateAudioExecutor + ExecutorRegistry 注册)
- `execution/micro_tasks.md` Commit 4 (4.1-4.7)
- F1 round-1 + F-Plan-R4-C round-4: capability_ref="audio.t2a" (NOT new step type)
- F2 round-1 + F-Plan-R7-B round-7: 三 except 块 + _should_retry honor RetryPolicy.retry_on
- F-Plan-R6-A round-6: Artifact shape="waveform" + UE bridge integration
- F-Plan-R7-A round-7: metadata single-source

### Implementation files

| File | Action | Details |
|---|---|---|
| `src/framework/runtime/executors/generate_audio.py` | Create | GenerateAudioExecutor 类(`step_type=StepType.generate, capability_ref="audio.t2a"`)+ `_should_use_comfy_worker_path` + `_generate_via_comfy_worker`(F2 三 except 块拆分 + F-Plan-R7-B `_should_retry` honor retry_on)+ execute() 含 `repo.put(artifact_type=ArtifactType(modality="audio", shape="waveform", display_name="audio_asset"), file_suffix=f".{cand.format}", metadata={...format/duration_seconds/sample_rate/worker_metadata})` 持久化(F-Plan-R6-A + F-Plan-R7-A)+ `_audio_mime_type` helper + `_should_retry` helper |
| `src/framework/runtime/executors/__init__.py` | Modify | 加 `from .generate_audio import GenerateAudioExecutor` import + `__all__` 加 `GenerateAudioExecutor` |
| `src/framework/run.py` | Modify | imports 加 `GenerateAudioExecutor`;`execs.register(GenerateAudioExecutor())` 在 `register(GenerateMeshExecutor(...))` 之后(F1 round-1:沿 image / mesh registration 模式;无 worker 注入因本 change scope 仅 ComfyUI 第一客户) |
| `tests/unit/test_generate_audio_comfy.py` | Create | 14 fence:executor dispatch(4)+ F2 三 except 块 + F-Plan-R7-B retry_on(4)+ 持久化 shape/metadata(2)+ ADR-007 边界(1)+ _should_retry helper(3) |

### TDD cycle

1. **GREEN-first**(依赖 commit 1 AudioCandidate + commit 2 model registry + commit 3 ComfyAgentWorker.generate_audio):写 production code → 运行 fence,2 处 contract 不一致触发 RED:
   - ExecutorResult 字段名:`artifact_ids` → 实际是 `artifacts: list[Artifact]`(只 artifacts + metrics 两字段)
   - test 用 walrus 操作符 `:=` 在函数签名里 — Python 不支持(SyntaxError)
2. **FIX**:删 `artifact_ids=` field、改 test 用 `[a.artifact_id for a in result.artifacts]`、删除 walrus 操作符
3. **GREEN**:14/14 fence PASS

### Pytest baseline delta

- Pre-commit:1268
- Post-commit:**1282 passed**(+14)
- 零回归

### Boundary check

- `git diff --name-only`:
  - `src/framework/runtime/executors/generate_audio.py` ✅(execution_plan.md File Structure 表 §5.1 显式列)
  - `src/framework/runtime/executors/__init__.py` ✅(execution_plan.md File Structure 表 §5.3 显式列)
  - `src/framework/run.py` ✅(execution_plan.md File Structure 表 §5.4 + F1 round-1 修订:NOT 改 loader.py)
  - `tests/unit/test_generate_audio_comfy.py` ✅(execution_plan.md Test files 表 §5.5 列)
- 0 越界

### Drift events

无。F1/F2/F-Plan-R4-C/F-Plan-R5-A/F-Plan-R6-A/F-Plan-R7-A/F-Plan-R7-B round-X 修订全部落实。F-Plan-R7-C disputed-permanent-drift(path containment)按设计**不**加(本 commit 不读 outputs.audio bytes,bytes-reading 在 commit 3 ComfyAgentWorker.generate_audio 内,沿 image/mesh symmetry)。

