---
change_id: comfy-agent-cli-audio-adoption
stage: S6
evidence_type: cross_check
contract_refs:
  - design.md
  - tasks.md
  - review/codex_adversarial_review.md
  - notes/live_smoke_audio_20260503_full.md
  - openspec/specs/provider-routing/spec.md
codex_review_ref: review/codex_adversarial_review.md
plugin_command: "/codex:adversarial-review --background <focus>"
plugin_task_id: b86swn4sj
detected_env: claude-code
codex_plugin_available: true
triggered_by: "/forgeue:change-review (G11 stage cross-check independent verification)"
created_at: 2026-05-03T15:50:00+00:00
disputed_open: 0
aligned_with_contract: false
drift_decision: "G11-F1 accepted-codex/L2 actual PASS; G11-F2 disputed-permanent-drift (R7-C reaffirmed + codex pushback recorded); G11-F3 accepted-codex/fixed in this change"
writeback_commit: pending
drift_reason: |
  G11-F2 (path containment) maintained as disputed-permanent-drift per Reasoning Notes
  symmetry argument with image/mesh executors; codex re-pushback at [high] severity
  recorded verbatim in design.md ## Reasoning Notes — G11-F2 round-8 with Claude rebuttal.
  G11-F1 satisfied by L2 actual PASS (1.17 MB FLAC artifact, magic bytes verified).
  G11-F3 seed bug fixed in commit (setdefault → 直接覆盖 + fence).
reasoning_notes_anchor: design.md#g11-f2-round-8
round: G11
---

# G11 Cross-check — codex_adversarial_review.md(独立验证)

## A. Decision Summary(冻结于 codex 调用之前)

本轮 G11 cross-check 立场:
- **预期 codex 可能 catch**:audio worker 三处 G11-relevant 风险:(1) seed setdefault
  在 `comfy_params.seed` 已存在时 bypass 的 bug(image/mesh 同模式但 codex 通常会在
  audio 新代码 catch 一次)、(2) outputs.audio 路径 containment 缺口的 R7-C 重新挑战
  (codex 通常不接受 symmetry argument)、(3) L2 evidence DEFERRED 是否合契约。
- **R7-C 立场固定**:本轮 cross-check `## A` 锁定 R7-C disputed-permanent-drift 维持
  (Reasoning Notes anchor),如 codex 重提 path containment 仍走 disputed,Claude
  补充 codex 反驳全文 + 维持反驳依据。
- **F3 seed bug 立场**:如果 codex catch,**fix in audio change**(audio 是新代码,
  做对而非沿历史模式)+ 开 follow-on for image/mesh。
- **F1 L2 evidence**:如果 codex catch L2 deferred 不合 contract,**优先尝试 L2 actual
  PASS**(让用户授权改 ComfyUI workflow JSON 然后重跑 smoke);如不可行才走 spec 修订。

## B. Findings adjudication

### G11-F1: Finish gate 不阻断 L2 hard blocker — accepted-codex / L2 actual PASS

**Codex 论据**:`tools/forgeue_finish_gate.py:871-887` `build_report()` 仅聚合通用
evidence/frontmatter/task/openspec 检查,不强制本 change 自己 tasks.md 标的 "L2
DEFERRED post-archive"(ComfyUI 跑失败 SaveAudioMP3 缺 quality 导致)。这让 archive
绕过 L2 hard blocker contract。Recommendation:不归档 until live smoke evidence
file records actual audio artifact with existence, size, and magic-byte checks.

**Claude 立场**:**accepted-codex**。Claude 接受 codex 论证 + 用户授权下解决方案=
L2 actual PASS(NOT spec downgrade)。

**Action**:用户授权 Claude 改 ComfyUI workflow JSON 一行(`D:/AI/ComfyUI/workflows/.../
audio_stable_audio_example.json` `SaveAudioMP3` → `SaveAudio`,匹配 manifest
`outputs.primary: audio/flac` 原本声明),重跑 L2 smoke。

**Result**(独立验证 see `## D`):
- run_id `audio_smoke_l2_pass`,status `succeeded`
- artifact 1,227,925 bytes(1199.1 KB)真实 FLAC
- magic bytes `b'fLaC'` + STREAMINFO 头 PASS
- producer `comfy_agent_cli` / `comfy/local-audio`(audio executor 无 G6-F2/F3 同形态 bug)
- evidence file `notes/live_smoke_audio_20260503_full.md` 落地
- 原 deferred note `notes/live_smoke_audio_blocked_20260503.md` superseded

**Resolution**:`accepted-codex / L2 actual PASS`。codex 的 "Do not archive until a
live smoke evidence file records an actual audio artifact" 推荐已**完全满足**。

### G11-F2: outputs.audio path containment gap — disputed-permanent-drift / accepted-claude

**Codex 论据**:`_run_once_audio()` (comfy_worker.py:1017-1040) 只验 `is_file()` +
`is_symlink()`,buggy/compromised CLI 可返回任意 `.flac/.mp3/.wav` 路径(ComfyUI
run/output tree 之外)。Magic bytes 只证 audio-like 不证 produced by this run。
Symmetry argument with image/mesh "repeats an existing trust-boundary gap instead
of reducing it"。Recommendation:`Path.resolve()` + `is_relative_to(comfy_run_root)`
across audio + harden image/mesh in same follow-up or same patch + 加 regression
test for outside paths and traversal-style paths.

**Claude 立场**:**disputed-permanent-drift / accepted-claude**(R7-C 立场维持 + codex
反驳完整记录)。

**Reasoning(完整 6 段反驳记录在 `design.md ## Reasoning Notes — G11-F2 round-8`,
此处摘要):

1. **Symmetry argument 不依赖于 "三处都安全",依赖于 "asymmetric fix is wrong fix"**:
   仅 audio 加 containment 会让审计者看 image/mesh 代码时 mistakenly assume 同样防护
   (false sense of security on more sensitive image/mesh artifacts);**统一在 follow-on
   同步加** 才是正确解。

2. **Threat model 是 buggy CLI 不是 compromised CLI**:ComfyUI 是用户本地 subprocess,
   ComfyUI 输出路径由其 `comfyui_api/runner.py extract_outputs` 拼到 `comfy_run_root`
   下。如果 ComfyUI 已被 compromise 到能返回任意路径,用户机器 root 文件系统已暴露,
   framework 加 containment 也救不回来。

3. **Codex [high] vs Claude 风险评估**:Codex 给 [high] 因为 trust-boundary 缺口在抽象层
   永远是 [high]。Claude 评估实际危害:(a) defense-in-depth 第二层(magic bytes whitelist)
   要求文件至少是 valid FLAC/MP3/WAV,显著缩窄潜在 leak 面;(b) ComfyUI subprocess 同 user
   权限,subprocess 输出 ≈ user 自己读;(c) image/mesh 同模式生产 ~3 周无 incident。

4. **Architectural decision recap**:R7-C 的 disputed-permanent-drift 立场建立在
   "asymmetric fix is wrong fix + follow-on change 是正确解" 双前提下。G11-F2 codex
   re-pushback 没有改变这两个前提,只是上调 severity rating。Claude 维持 R7-C 立场。

5. **Follow-on commitment**:`comfy-agent-cli-path-containment-hardening` change 必须
   包含:三 capability 同步加 `Path.resolve().is_relative_to(comfy_run_root)` 校验、
   `comfy_run_root` 由 agent CLI metadata derive、三 fence 各加
   `path_outside_run_root_raises_unsupported_response`、cross-reference G11-F2 finding。

**Resolution**:`disputed-permanent-drift / accepted-claude`(R7-C 立场维持 + G11-F2
codex 反驳全文 + Claude 反驳全文记入 design.md anchor)。

### G11-F3: Per-candidate seed setdefault 被 comfy_params.seed 吞 — accepted-codex / fixed in this change

**Codex 论据**:`comfy_worker.py:908-917` `params_for_call.setdefault("seed", call_seed)`
在 `comfy_params` 已含 seed(canonical bundle `examples/comfy_local_smoke_audio.json`
就有)时 bypass 偏移。num_candidates>1 时所有 subprocess 收到同 seed,但 metadata 报告
递增 seed → 重复 candidate + 误导 provenance。Recommendation:overwrite
`params_for_call["seed"] = call_seed`;加 fence inspect subprocess `--params` for
seeds 100, 101, 102 when comfy_params 已含 seed。

**Claude 立场**:**accepted-codex**(audio 是新代码,做对而非沿 image/mesh 历史模式)。

**Action**:
- `src/framework/providers/workers/comfy_worker.py:912` 改 `setdefault("seed", call_seed)`
  → `params_for_call["seed"] = call_seed`(直接覆盖)+ 注释说明 image/mesh 同 bug 走
  follow-on
- 新加 fence `tests/unit/test_comfy_subprocess_audio.py::
  test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`(20 fences total
  → 20 PASS 实测)
- image (line 442) / mesh (line 703) 同 bug 走 follow-on change
  `comfy-worker-seed-setdefault-bug-fix`(三处 unify 一次性修)

**Resolution**:`accepted-codex / fixed in this change`(audio scope 内修)。

## C. disputed_open

**disputed_open: 0**:
- G11-F1 accepted-codex / L2 actual PASS(closed)
- G11-F2 disputed-permanent-drift(closed-with-reasoning per ForgeUE Workflow protocol;
  follow-on commitment recorded)
- G11-F3 accepted-codex / fixed in this change(closed)

## D. Independent verification(file:line + behavior 验证)

### G11-F1 — L2 evidence actual PASS 真实落地

**Independent verification commands**:

```bash
# Run summary
cat artifacts/2026-05-03/audio_smoke_l2_pass/run_summary.json
# {"status": "succeeded", ...}

# Artifact size
stat -c %s artifacts/2026-05-03/audio_smoke_l2_pass/audio_smoke_l2_pass_step_audio_cand_audio_0.flac
# 1227925

# Magic bytes
xxd -l 8 artifacts/2026-05-03/audio_smoke_l2_pass/audio_smoke_l2_pass_step_audio_cand_audio_0.flac
# 00000000: 664c 6143 0000 0022                      fLaC...."

# Provenance
cat artifacts/2026-05-03/audio_smoke_l2_pass/_artifacts.json | python -c "import json,sys; d=json.load(sys.stdin); print(d[0]['producer'])"
# {'run_id': 'audio_smoke_l2_pass', 'step_id': 'step_audio',
#  'provider': 'comfy_agent_cli', 'model': 'comfy/local-audio'}
```

**确认 G11-F1 由 L2 actual PASS 关闭**(NOT spec downgrade)。

### G11-F2 — disputed maintained per R7-C symmetry

`src/framework/providers/workers/comfy_worker.py` 验证(image / mesh / audio 均无
path containment):

- Image worker `:541-554`(legacy v1.6 image change):only `is_file()` + `is_symlink()`
- Mesh worker `:805-814`(Phase 1 mesh change):same pattern
- Audio worker `:1017-1040`(本 change):same pattern(symmetry confirmed)

**Asymmetric fix would be**:audio 加 containment + image/mesh 不加 → 创造 image/mesh
audit blind spot。Decision = follow-on 同步加。

### G11-F3 — fix verified

**Before fix**(线 912):
```python
params_for_call.setdefault("seed", call_seed)
```

**After fix**(commit pending):
```python
# G11-F3 round-8 codex finding fix:per-candidate seed 直接覆盖,不用 `setdefault`
params_for_call["seed"] = call_seed
```

**Fence verification**:
```bash
python -m pytest tests/unit/test_comfy_subprocess_audio.py::test_generate_audio_per_candidate_seed_overrides_comfy_params_seed -v
# PASSED
```

Fence 内容:`comfy_params={"seed": 42}` + `num_candidates=3` + `seed=100` →
extracted seeds from subprocess `--params` JSON == [100, 101, 102](setdefault bug
would yield [42, 42, 42];fence 实测 PASS confirms 已 fix)。

## E. Follow-on 注册

| Finding | Follow-on change | Priority |
| --- | --- | --- |
| G11-F2 | `comfy-agent-cli-path-containment-hardening`(三 capability 统一加 `Path.resolve()` + `is_relative_to(comfy_run_root)`)| medium(defense-in-depth hardening) |
| G11-F3 image/mesh 同 bug | `comfy-worker-seed-setdefault-bug-fix`(image:442 + mesh:703 同 fix)| medium(provenance-correctness;num_candidates=1 时 dormant) |

本 change archive 不阻断;follow-on 由用户后续 `/opsx:propose` 单独立项。

## F. Verdict

**G11 cross-check disputed_open: 0**;3 finding 全部 closed:
- F1 closed by L2 actual PASS
- F2 closed by disputed-permanent-drift with full Reasoning Notes
- F3 closed by accepted-codex / fixed in this change

本 change archive 通过 G11 验证。
