---
change_id: comfy-agent-cli-audio-adoption
stage: S6
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
codex_plugin_available: true
triggered_by: "/forgeue:change-review (G11 stage hook /codex:adversarial-review)"
created_at: 2026-05-03T15:30:00+00:00
plugin_command: "/codex:adversarial-review --background <focus>"
plugin_task_id: b86swn4sj
---

# Codex Adversarial Review (G11) — verbatim output

`/codex:adversarial-review --background <full focus text>` 执行结果(plugin task
`b86swn4sj`,2026-05-03 23:25 完成)。Verdict **needs-attention** + 3 findings
(2 high + 1 medium)。

## Verbatim codex output

```text
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship: finish gate is accepting a known failed L2 audio path, and the new audio worker
still trusts arbitrary subprocess output paths. Archive would overstate production readiness.

Findings:
- [high] Finish gate does not enforce the change's L2 hard blocker (tools/forgeue_finish_gate.py:871-887)
  `build_report()` only aggregates generic evidence/frontmatter/task/openspec checks, so it can
  report zero blockers even when this change's own tasks mark L2 audio evidence as `DEFERRED
  post-archive` after the real ComfyUI run failed on `SaveAudioMP3` missing `quality`. Inference
  from the reviewed files: this lets the change archive without ever proving that
  `examples/comfy_local_smoke_audio.json` can produce and persist a real FLAC/MP3/WAV artifact,
  directly contradicting the hard-blocker contract recorded in the change artifacts.
  Recommendation: Make finish gate enforce declared L2 hard blockers for this change, or
  formally revise the contract/acceptance status. Do not archive until a live smoke evidence
  file records an actual audio artifact with existence, size, and magic-byte checks.

- [high] outputs.audio can read files outside the ComfyUI output boundary (src/framework/providers/workers/comfy_worker.py:1017-1040)
  `_run_once_audio()` converts each stdout path to `Path`, checks only `is_file()` and
  `is_symlink()`, then reads the bytes. A buggy or compromised local CLI can return any
  accessible non-symlink `.flac`, `.mp3`, or `.wav` path outside the ComfyUI run/output tree;
  the magic-byte table only proves it is audio-like, not that it was produced by this run.
  The symmetry argument with image/mesh repeats an existing trust-boundary gap instead of
  reducing it.
  Recommendation: Resolve each output path and require it to be under a configured or
  CLI-reported ComfyUI output/run root before `read_bytes()`. Add regression tests for absolute
  outside paths and traversal-style paths across audio, then harden image/mesh in the same
  follow-up or same patch.

- [medium] Per-candidate seed offset is bypassed when comfy_params already contains seed (src/framework/providers/workers/comfy_worker.py:908-917)
  The loop computes `call_seed = base + i`, but then uses
  `params_for_call.setdefault("seed", call_seed)`. The canonical bundle duplicates `seed`
  inside `comfy_params`, so if `num_candidates` is raised above 1 every subprocess receives
  the same seed while metadata reports incrementing seeds. That can produce duplicate
  candidates and misleading provenance; the current test only asserts call count and
  candidate count, not the actual `--params` JSON.
  Recommendation: Define one seed source of truth. If top-level `seed` drives candidate
  variation, overwrite `params_for_call["seed"] = call_seed`; otherwise document that
  `comfy_params.seed` wins and stop claiming per-candidate seed increments. Add a test that
  inspects subprocess `--params` for seeds 100, 101, 102 when `comfy_params` already contains
  `seed`.

Next steps:
- Block archive until L2 evidence is either passed or the contract is explicitly downgraded.
- Add path containment before shipping the audio worker path.
- Patch or clarify seed ownership and add a subprocess-params regression test.
```

## Findings table

| Finding | File:line | Severity | Resolution preview |
| --- | --- | --- | --- |
| G11-F1 Finish gate 不阻断 L2 hard blocker | tools/forgeue_finish_gate.py:871-887 | high | **L2 actual PASS**(用户授权改 ComfyUI workflow JSON 一行,重跑 smoke 拿真实 FLAC 1.17 MB);`live_smoke_audio_20260503_full.md` 落地 |
| G11-F2 outputs.audio path containment gap | comfy_worker.py:1017-1040 | high | **disputed-permanent-drift / accepted-claude**;design.md `## Reasoning Notes` G11-F2 段记录 codex 反驳全文 + Claude 反驳全文;follow-on `comfy-agent-cli-path-containment-hardening` 三 capability 同步加 |
| G11-F3 Per-candidate seed setdefault 被 comfy_params.seed 吞 | comfy_worker.py:908-917 | medium | **accepted-codex / fixed in this change**;`comfy_worker.py:912 setdefault → 直接覆盖`;新增 fence `test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`;image/mesh 同 bug 走 follow-on `comfy-worker-seed-setdefault-bug-fix` |

## Resolution preview (full Resolution in `cross_check_g11.md`)

| Finding | Resolution | Rationale |
| --- | --- | --- |
| G11-F1 | accepted-codex / **L2 actual PASS** | 用户授权改 ComfyUI workflow JSON `SaveAudioMP3 → SaveAudio` 一行,重跑 L2 smoke 真实 FLAC 1.17 MB 落地。Codex 推荐 "Do not archive until a live smoke evidence file records an actual audio artifact" 已满足 |
| G11-F2 | disputed-permanent-drift | symmetry argument 维持(单独 audio 加 containment 会创造 image/mesh false sense of security + scope 越界)+ codex 反驳完整记录 |
| G11-F3 | accepted-codex / fixed | seed setdefault → 直接覆盖,新加 fence 跑 PASS;image / mesh 同 bug 走 follow-on |

## References

- Cross-check + independent verification:`cross_check_g11.md`
- Verbatim raw output:`C:/Users/mzq/AppData/Local/Temp/claude/.../tasks/b86swn4sj.output`
- L2 evidence(F1 satisfied):`notes/live_smoke_audio_20260503_full.md`
- F2 design.md writeback:`design.md ## Reasoning Notes — G11-F2 round-8`
- F3 fix commit:`src/framework/providers/workers/comfy_worker.py:912`(待 commit)
- F3 fence:`tests/unit/test_comfy_subprocess_audio.py::test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`
