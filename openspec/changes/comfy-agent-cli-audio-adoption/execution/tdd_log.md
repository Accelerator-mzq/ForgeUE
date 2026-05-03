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

