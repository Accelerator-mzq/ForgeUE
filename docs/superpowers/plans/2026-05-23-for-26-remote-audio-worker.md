# FOR-26 Remote Audio Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close FOR-26 by adding a generic HTTP remote audio worker for `audio.t2a`.

**Architecture:** Reuse the existing `AudioWorker` contract and inject a `RemoteHttpAudioWorker` from `framework.run` only when `FORGEUE_REMOTE_AUDIO_URL` is configured. Keep local ComfyUI audio routing unchanged.

**Tech Stack:** Python 3.12, pytest, httpx, ForgeUE `AudioWorker`, `GenerateAudioExecutor`, `ModelRegistry`.

---

### Task 1: RED tests for remote HTTP worker

**Files:**
- Create: `tests/unit/test_remote_audio_worker.py`
- Test: `tests/unit/test_remote_audio_worker.py`

- [ ] Write tests for base64 response, URL response, auth header, unsupported format, magic mismatch, and timeout.
- [ ] Run `python -m pytest tests/unit/test_remote_audio_worker.py -q`.
- [ ] Expected: fail because `framework.providers.workers.remote_audio_worker` does not exist.

### Task 2: GREEN remote worker implementation

**Files:**
- Create: `src/framework/providers/workers/remote_audio_worker.py`
- Modify: `src/framework/providers/workers/__init__.py`
- Test: `tests/unit/test_remote_audio_worker.py`

- [ ] Implement `RemoteHttpAudioWorker(AudioWorker)` with async HTTP POST via `httpx.AsyncClient`.
- [ ] Accept `bytes_base64` / `data_base64` / `audio_base64` or downloadable `url`.
- [ ] Validate `flac` / `mp3` / `wav` by magic bytes.
- [ ] Run `python -m pytest tests/unit/test_remote_audio_worker.py -q`.
- [ ] Expected: pass.

### Task 3: Wire runtime and registry

**Files:**
- Modify: `src/framework/run.py`
- Modify: `config/models.yaml`
- Modify: `tests/unit/test_model_registry.py`
- Create: `tests/unit/test_run_remote_audio.py`
- Create: `examples/remote_audio_smoke.json`
- Test: listed tests

- [ ] Add failing tests for `audio_remote` alias and `framework.run` env-based worker injection.
- [ ] Update `run.py` to create `RemoteHttpAudioWorker` when `FORGEUE_REMOTE_AUDIO_URL` exists.
- [ ] Add `remote_audio_http` model and `audio_remote` alias.
- [ ] Add dry-run-only example bundle.
- [ ] Run focused tests and integration smoke.

### Task 4: Documentation and backlog closeout

**Files:**
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`
- Modify: `CHANGELOG.md`

- [ ] Mark TBD-002 / LR-0127 as completed for generic HTTP remote audio worker.
- [ ] Keep provider-specific ElevenLabs / AudioCraft adapters as future optional work, not FOR-26 blockers.
- [ ] Add verification evidence links.

### Task 5: Verification

Run:

```bash
python -m pytest tests/unit/test_remote_audio_worker.py tests/unit/test_run_remote_audio.py tests/unit/test_model_registry.py tests/integration/test_example_bundles_smoke.py -q
python -m pytest tests/unit/test_audio_worker.py tests/unit/test_generate_audio_comfy.py tests/unit/test_comfy_subprocess_audio.py -q
```

Expected: all selected tests pass.

### Task 6: MiniMax music direct worker follow-on

**Files:**
- Create: `src/framework/providers/workers/minimax_music_worker.py`
- Create: `tests/unit/test_minimax_music_worker.py`
- Modify: `src/framework/run.py`
- Modify: `config/models.yaml`
- Modify: `tests/fixtures/test_models.yaml`
- Modify: `tests/unit/test_model_registry.py`
- Modify: `tests/unit/test_run_remote_audio.py`
- Create: `examples/minimax_music_smoke.json`

- [ ] Add failing tests for MiniMax native payload, URL download, hex response, provider error, timeout, `audio_minimax` alias, and `MINIMAX_KEY` injection.
- [ ] Implement `MiniMaxMusicWorker(AudioWorker)` using MiniMax `music_generation` payload fields.
- [ ] Keep `FORGEUE_REMOTE_AUDIO_URL` higher priority than `MINIMAX_KEY`.
- [ ] Add `minimax/music-2.6` virtual model and `audio_minimax` alias.
- [ ] Add dry-run-only MiniMax smoke bundle.
- [ ] Run focused tests and full verification.
