## ADDED Requirements

### Requirement: VideoWorker ABC, VideoCandidate dataclass, and VideoWorker exception tree establish video worker baseline

The system SHALL establish a video worker baseline at `src/framework/providers/workers/video_worker.py` that mirrors the structure of `audio_worker.py` (sibling to `AudioWorker` / `AudioCandidate`):

- `VideoCandidate` dataclass with required fields: `data: bytes` (video file bytes), `format: Literal["mp4"]` (lowercase, no leading dot;round-2 F2 修订 + round-3 PF3 sweep:mp4-only,webm follow-on `comfy-video-webm-adoption`), `metadata: dict[str, Any]` (provenance ONLY: exactly the 5 `comfy_*` keys `comfy_manifest`, `comfy_params_snapshot`, `comfy_capability="video"`, `comfy_original_filename`, `comfy_subprocess_run_metadata` — sweep-style sibling to audio's F-Plan-R7-A round-7 single-source decision: do NOT duplicate `duration_seconds` / `frame_count` / `width` / `height` / `fps` / `format` keys inside `metadata` to avoid double-source conflict with the top-level dataclass fields), `duration_seconds: float | None = None` (top-level), `frame_count: int | None = None` (top-level), `width: int | None = None` (top-level), `height: int | None = None` (top-level), `fps: float | None = None` (top-level); the `metadata` field is the source of `Artifact.metadata.worker_metadata` after `repo.put` per the audio Phase 2 `AudioCandidate.metadata["worker_metadata"]` modeling. **Round-3 PF4 修订**:Python `@dataclass` 不在 runtime 强制 `Literal` 类型,实际 mp4-only enforcement 在 worker 层 `_run_once_video` 扩展名检查 + BMFF strict header validation;dataclass 构造接受任意字符串(per `# type: ignore[arg-type]` 写法,沿 audio Phase 2 同款),fence 测 dataclass accept "mp4" + worker 层 reject "webm" / "mov"。

- `VideoWorker(ABC)` abstract base class with one `@abstractmethod`:

  ```python
  def generate_video(
      self,
      *,
      spec: dict,
      num_candidates: int,
      seed: int | None,
      timeout_s: float,
  ) -> list[VideoCandidate]: ...
  ```

  The signature SHALL NOT include a `prompt: str` parameter — bundle authors place prompt strings inside `spec["comfy_params"]` directly (per the design D7 decision); concrete implementations parse `spec` according to their own provider conventions

- Exception tree mirrors `audio_worker`:

  ```python
  class VideoWorkerError(RuntimeError): ...
  class VideoWorkerTimeout(VideoWorkerError): ...
  class VideoWorkerUnsupportedResponse(VideoWorkerError): ...
  ```

- A `FakeVideoWorker(VideoWorker)` test fixture SHALL be provided under `src/framework/providers/workers/video_worker.py` (or `tests/fakes/`) producing minimal valid mp4 bytes (~50-100 bytes, magic `b"ftyp"` at offset 4 + minimal box header `b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00..."` per ISO/IEC 14496-12 BMFF) without third-party codec dependencies, suitable for offline unit / integration tests

#### Scenario: VideoWorker ABC enforces generate_video signature

- **GIVEN** a hypothetical concrete subclass `class MyVideoWorker(VideoWorker):` that omits `generate_video` implementation
- **WHEN** `MyVideoWorker(...)` is instantiated
- **THEN** Python raises `TypeError: Can't instantiate abstract class MyVideoWorker with abstract method generate_video`; the ABC contract is enforced; `tests/unit/test_video_worker.py::test_video_worker_abc_requires_generate_video` fences this

#### Scenario: VideoCandidate.format dataclass accepts mp4; runtime enforcement is at worker layer (round-3 PF4 修订:audio Phase 2 同款 enforcement 模式)

- **GIVEN** an attempt to construct `VideoCandidate(data=b"...", format="mp4", metadata={}, ...)` (valid)以及 `VideoCandidate(data=b"...", format="webm", metadata={})` 或 `format="mov"`(沿 `# type: ignore[arg-type]` 写法,Python `@dataclass` 不在 runtime 强制 `Literal` 类型注解 — 沿 audio Phase 2 `tests/unit/test_audio_worker.py::test_audio_candidate_format_whitelist` 已显式记录的同款行为)
- **WHEN** the dataclass is instantiated
- **THEN** dataclass accepts both valid `"mp4"` AND non-Literal strings(如 `"webm"` / `"mov"`)WITHOUT raising — Python `@dataclass` 不 enforce Literal at runtime;实际 mp4-only 守门由 `ComfyAgentWorker._run_once_video` 在 `ext != "mp4"` 时 raise `WorkerUnsupportedResponse`(沿 audio `_run_once_audio` 同款分层 enforcement);`tests/unit/test_video_worker.py::test_video_candidate_format_mp4_accepted_dataclass_does_not_runtime_enforce_literal` fences 「mp4 accept + dataclass 不 reject webm/mov(at construction)」;runtime mp4-only invariant 守门 fence 在 `tests/unit/test_comfy_subprocess.py::test_generate_video_unsupported_extension_mov_raises_unsupported_response` + `::test_generate_video_webm_extension_rejected_pending_follow_on`(worker 层 enforcement)。webm support 需要 sweep `_KIND_MAP[("video","webm")] = "file_media_source"` extension + `domain_video.py` .webm path handling + corresponding tests,deferred to follow-on `comfy-video-webm-adoption`。The whitelist SHALL match the formats explicitly mapped in `manifest_builder._KIND_MAP` for the `"video"` modality (D1 single-mapping invariant)

#### Scenario: VideoWorkerTimeout inherits from VideoWorkerError

- **GIVEN** Python's standard `isinstance` check
- **WHEN** code catches `VideoWorkerError` to handle all video worker failures
- **THEN** `VideoWorkerTimeout` and `VideoWorkerUnsupportedResponse` are caught (parent `VideoWorkerError`); `tests/unit/test_video_worker.py::test_video_worker_exception_tree_inheritance` fences `issubclass(VideoWorkerTimeout, VideoWorkerError) is True` and the same for `VideoWorkerUnsupportedResponse`

### Requirement: comfy/local-video model and video_local alias register with ModelRegistry without extending ProviderDef schema

The system SHALL register a fourth virtual ComfyUI model in `config/models.yaml` (and the test fixture `tests/fixtures/test_models.yaml`) using only the existing `ProviderDef` / `ModelDef` / `Alias` schema established by `comfy-agent-cli-adoption`:

- `models.comfy_local_video` entry: `id: "comfy/local-video"` (REQUIRED, MUST match `_CAPABILITY_BY_MODEL_ID` key) + `provider: comfy_api` (reuses the existing `providers.comfy_api` entry; this change does NOT add a new provider) + `kind: video` + `pricing: null` (local GPU, no per-task cost; `pricing_autogen.status: manual` with `sourced_on` set to the change archive date and a comment documenting the local-GPU exemption per ADR-004)

- `aliases.video_local` entry: `preferred: ["comfy_local_video"]` + `fallback: []` (no fallback to remote video worker in this change scope; future remote video workers will be added by their own follow-on change `video-worker-remote-adoption` per the design D3 split)

- The `providers.comfy_api` entry SHALL NOT be modified by this change (already registered by `comfy-agent-cli-adoption`); the `ProviderDef` schema SHALL NOT be extended

#### Scenario: comfy/local-video model resolves via video_local alias

- **GIVEN** the post-change `config/models.yaml` and `tests/fixtures/test_models.yaml`
- **WHEN** `ModelRegistry.expand_alias("video_local")` is called
- **THEN** the resolved list contains exactly one route with `model="comfy/local-video"`, `provider="comfy_api"`, `kind="video"`, `pricing=None`; `tests/unit/test_model_registry.py::test_comfy_local_video_model_resolves_via_video_local_alias` fences this

#### Scenario: video_local alias kind is video

- **GIVEN** the post-change `config/models.yaml`
- **WHEN** `ModelRegistry` resolves the `video_local` alias
- **THEN** the resolved model entry's `kind` is `"video"` (not `"audio"` / `"mesh"` / `"image"`); `tests/unit/test_model_registry.py::test_video_local_alias_kind_is_video` fences this

## MODIFIED Requirements

### Requirement: ComfyAgentWorker dispatches by capability inferred from model id

The system SHALL infer ComfyAgentWorker `_capability` ∈ {`image`, `mesh`, `audio`, `video`} from the resolved `model_id` string at `__init__` time, using the class-level `_CAPABILITY_BY_MODEL_ID` table (round-2 F3 codex finding accepted-codex 2026-05-04: 由 ADDED「ComfyAgentWorker capability dispatch supports four capabilities」改为 MODIFIED 既有 Requirement,因为 Phase 1 + Phase 2 audio archive 后此 Requirement 主 spec 文件 `openspec/specs/provider-routing/spec.md:240` 仍声明 supported ids 三能力 `comfy/local` / `comfy/local-mesh` / `comfy/local-audio`,本 change 必须全文替换以避免 archive 后两条 Requirement 共存的契约漂移):

```python
_CAPABILITY_BY_MODEL_ID: dict[str, str] = {
    "comfy/local": "image",        # Phase 1 (comfy-agent-cli-adoption)
    "comfy/local-mesh": "mesh",    # Phase 1 mesh (comfy-agent-cli-mesh-audio-video-adoption)
    "comfy/local-audio": "audio",  # Phase 2 (comfy-agent-cli-audio-adoption)
    "comfy/local-video": "video",  # Phase 3 (comfy-agent-cli-video-adoption) — NEW
}
```

Bundle JSON SHALL NOT carry `outputs_kind` / `capability` fields; capability identity flows entirely through the resolved `model_id`. Unknown `model_id` SHALL raise `WorkerUnsupportedResponse` at `__init__` with a message naming the unknown id and listing all four supported ids (`"comfy/local", "comfy/local-mesh", "comfy/local-audio", "comfy/local-video"`); no subprocess SHALL be spawned.

The companion 4-dict tables governing output validation also SHALL extend to four entries (capability-keyed):

| dict | image | mesh | audio | video |
|---|---|---|---|---|
| `_REQUIRED_OUTPUT_KEY` | `"images"` | `"glb"` | `"audio"` | `"video"` |
| `_AUXILIARY_OUTPUT_KEYS_BY_CAP` | `set()` | `{"images"}` | `set()` | `set()` (VHS_VideoCombine emits only video file) |
| `_REJECTED_OUTPUT_KEYS_BY_CAP` | `{"glb", "audio", "video"}` | `{"audio", "video"}` | `{"images", "glb", "video"}` | `{"images", "glb", "audio"}` |

The class SHALL also declare `_VIDEO_FORMAT_WHITELIST: ClassVar[set[str]] = {"mp4"}` (round-2 F2 修订:webm deferred to follow-on `comfy-video-webm-adoption`) for use by `_run_once_video` extension-detection + magic-bytes / BMFF strict validation.

#### Scenario: ComfyAgentWorker constructed with comfy/local enters image capability mode (regression)

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`; resolved `ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None, kind="image", pricing=None)`
- **WHEN** the executor constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")`
- **THEN** `self._capability == "image"`; `_REQUIRED_OUTPUT_KEY[self._capability] == "images"`; downstream `_validate_outputs(outputs)` requires `outputs.images` non-empty and rejects `outputs.glb` / `outputs.audio` / `outputs.video` non-empty (image-mode behavior unchanged from Phase 1)

#### Scenario: ComfyAgentWorker constructed with comfy/local-mesh enters mesh capability mode (regression)

- **GIVEN** environment variables as above; resolved `ResolvedRoute(model="comfy/local-mesh", ..., kind="mesh", pricing=None)`
- **WHEN** the executor constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)`
- **THEN** `self._capability == "mesh"`; mesh-mode `_REQUIRED_OUTPUT_KEY` is `"glb"`, `_AUXILIARY_OUTPUT_KEYS_BY_CAP` is `{"images"}` (PNG preview tolerance), `_REJECTED_OUTPUT_KEYS_BY_CAP` is `{"audio", "video"}` (mesh-mode behavior unchanged from Phase 1 mesh)

#### Scenario: ComfyAgentWorker constructed with comfy/local-audio enters audio capability mode (regression)

- **GIVEN** environment variables as above; resolved `ResolvedRoute(model="comfy/local-audio", ..., kind="audio", pricing=None)`
- **WHEN** the executor constructs `ComfyAgentWorker(model_id="comfy/local-audio", ...)`
- **THEN** `self._capability == "audio"`; audio-mode `_REQUIRED_OUTPUT_KEY` is `"audio"`, `_AUXILIARY_OUTPUT_KEYS_BY_CAP` is empty, `_REJECTED_OUTPUT_KEYS_BY_CAP` is `{"images", "glb", "video"}` (audio-mode behavior unchanged from Phase 2)

#### Scenario: ComfyAgentWorker constructed with comfy/local-video enters video capability mode (NEW Phase 3)

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`; resolved `ResolvedRoute(model="comfy/local-video", api_key_env=None, api_base=None, kind="video", pricing=None)`; `ctx.run.run_id="run_video_smoke"`; `ctx.task.project_id="proj_video_smoke"`; `ctx.run_dir=Path("artifacts/2026-05-XX/run_video_smoke")`
- **WHEN** `GenerateVideoExecutor._generate_via_comfy_worker` constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-video", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")`
- **THEN** `self._capability == "video"`; `_REQUIRED_OUTPUT_KEY[self._capability] == "video"`; `_AUXILIARY_OUTPUT_KEYS_BY_CAP[self._capability] == set()`; `_REJECTED_OUTPUT_KEYS_BY_CAP[self._capability] == {"images", "glb", "audio"}`; no subprocess is spawned at construction time; `tests/unit/test_comfy_subprocess.py::test_capability_inferred_video_for_comfy_local_video` fences this

#### Scenario: unknown model_id raises with supported list including all four capabilities (Phase 3 sweep)

- **GIVEN** `ComfyAgentWorker(model_id="comfy/local-unknown", ...)`
- **WHEN** `__init__` runs `_CAPABILITY_BY_MODEL_ID.get(model_id)` and finds `None`
- **THEN** raises `WorkerUnsupportedResponse` with message naming the unknown id and listing **all four** supported ids: `"comfy/local"`, `"comfy/local-mesh"`, `"comfy/local-audio"`, `"comfy/local-video"`; no subprocess is spawned; `tests/unit/test_comfy_subprocess.py::test_unknown_model_id_raises_at_init_lists_video_in_supported` fences this

## ADDED Requirements

### Requirement: ComfyAgentWorker output validation enforces video three-tier rules

The system SHALL apply the existing capability-aware `_validate_outputs(outputs)` three-tier check to the new `video` capability, using the 4-dict tables enumerated in the MODIFIED Requirement above. The video row SHALL behave as follows:

- REQUIRED key: `outputs.video` non-empty string list → pass; missing key OR empty list → raise `WorkerUnsupportedResponse`
- AUXILIARY set: empty (`set()`) — VHS_VideoCombine emits only video file; no INFO log emission about auxiliaries (in contrast to mesh-mode which tolerates `outputs.images` as PNG preview and emits INFO log)
- REJECTED set: `{"images", "glb", "audio"}` — any of these keys with non-empty list → raise `WorkerUnsupportedResponse` with the offending key name

The pre-existing image / mesh / audio capability rows in the same 4-dict tables SHALL preserve their behavior (image rejects video; mesh rejects video; audio rejects video), since their `_REJECTED_OUTPUT_KEYS_BY_CAP` sets already include `"video"` per Phase 1 / Phase 2 spec definitions.

#### Scenario: video mode requires non-empty outputs.video

- **GIVEN** `ComfyAgentWorker._capability == "video"` and an `outputs` dict missing the `"video"` key OR with `outputs.video = []`
- **WHEN** `_validate_outputs(outputs)` runs
- **THEN** raises `WorkerUnsupportedResponse`; `tests/unit/test_comfy_subprocess.py::test_video_mode_raises_on_missing_outputs_video` + `::test_video_mode_raises_on_empty_outputs_video` fence this

#### Scenario: video mode rejects outputs.images / outputs.glb / outputs.audio

- **GIVEN** `ComfyAgentWorker._capability == "video"` and an `outputs` dict containing `outputs.images = ["..."]` (or `outputs.glb` or `outputs.audio`) non-empty
- **WHEN** `_validate_outputs(outputs)` runs
- **THEN** raises `WorkerUnsupportedResponse` naming the offending key; no auxiliary INFO log is emitted; `tests/unit/test_comfy_subprocess.py::test_video_mode_rejects_outputs_images` + `::test_video_mode_rejects_outputs_glb` + `::test_video_mode_rejects_outputs_audio` + `::test_video_mode_no_auxiliary_log_emission` fence this

#### Scenario: image / mesh / audio modes still reject outputs.video after change

- **GIVEN** `ComfyAgentWorker._capability == "image"` / `"mesh"` / `"audio"` and an `outputs` dict containing `"video": ["..."]` non-empty
- **WHEN** `_validate_outputs(outputs)` runs
- **THEN** raises `WorkerUnsupportedResponse` for each of the three pre-existing capability modes; `tests/unit/test_comfy_subprocess.py::test_image_mode_still_rejects_outputs_video_after_change` + `::test_mesh_mode_still_rejects_outputs_video_after_change` + `::test_audio_mode_still_rejects_outputs_video_after_change` fence the regression for each

### Requirement: ComfyAgentWorker.generate_video reads video bytes, validates magic bytes, and applies BMFF strict header check (round-2 F4 修订)

The system SHALL implement `ComfyAgentWorker.generate_video(spec, num_candidates, seed, timeout_s) -> list[VideoCandidate]` (NOT part of the `ComfyWorker` ABC; sibling method to `generate_mesh` / `generate_audio`). The implementation SHALL:

- Guard: `if self._capability != "video": raise WorkerUnsupportedResponse(f"generate_video called on _capability={self._capability!r}")`
- Parse spec: `comfy_workflow = spec["comfy_workflow"]`; `comfy_params = spec.get("comfy_params") or {}`; `per_call_timeout = float(timeout_s) if timeout_s else 600.0` (D3: 600s default vs audio 300s — Wan T2V 7-min generation vs audio Stable Audio ~30s)
- Per-candidate loop (sweep mirror of audio F-Plan-3 round-2 / image / mesh `for i in range(max(1, num_candidates))` at `comfy_worker.py:427` / `:689`): each iteration computes `call_seed = (seed or 0) + i`, copies `params_for_call = dict(comfy_params)`, sets `params_for_call["seed"] = call_seed` (direct overwrite, NOT `setdefault` — sweep mirror of audio Phase 2 G11-F3 `setdefault` bypass fix at `comfy_worker.py:912`), invokes `_run_once_video(comfy_workflow, params_for_call, params_snapshot=dict(params_for_call), call_seed, per_call_timeout)`, extends the results list
- `_run_once_video(...)` internal: invokes existing `_run_subprocess_and_validate(spec_for_call, timeout_s)` helper to obtain `outputs` dict (three-tier `_validate_outputs` already enforced for video); iterates `outputs.video` (absolute-path string list per ComfyUI agent CLI `runner.py::extract_outputs` source contract — same protocol as audio); for each path:
  - `src = Path(abs_path)`
  - **Path trust-boundary protection** (sweep mirror of audio F-Plan-4 round-2 + image / mesh G11 R2 fix at `comfy_worker.py:541-554`): `if not src.is_file(): raise WorkerUnsupportedResponse(...)` AND `if src.is_symlink(): raise WorkerUnsupportedResponse(...)`
  - `ext = src.suffix.lower()[1:]` (strip leading dot)
  - Whitelist check (round-2 F2 修订:mp4-only): `ext != "mp4" → raise WorkerUnsupportedResponse(f"unsupported video format {ext!r}, expected 'mp4' (webm follow-on; round-2 F2)")`
  - `data = src.read_bytes()` (D4: full bytes-read, sweep mirror of audio; large-file streaming deferred to follow-on `repo-put-streaming-payload`)
  - **BMFF strict header validation (D9 + round-2 F4 修订, mandatory)**:
    ```python
    # mp4: BMFF (ISO/IEC 14496-12) strict header check
    if len(data) < 16:
        raise WorkerUnsupportedResponse(
            f"mp4 too short: {len(data)} bytes (need >= 16 for minimal BMFF header)"
        )
    if data[4:8] != b"ftyp":
        raise WorkerUnsupportedResponse(
            f"mp4 BMFF header mismatch: offset 4-8 = {data[4:8]!r}, expected b'ftyp'"
        )
    box_size = int.from_bytes(data[0:4], "big")
    # round-3 PF2 修订:reject box_size == 1 (largesize follow-on `video-bmff-largesize-support`)
    if box_size == 1 or box_size < 8 or box_size > len(data):
        raise WorkerUnsupportedResponse(
            f"mp4 BMFF first box_size={box_size} out of range [8, {len(data)}] "
            f"(largesize box_size==1 deferred to follow-on `video-bmff-largesize-support`; round-3 PF2)"
        )
    major_brand = data[8:12]
    if major_brand == b"\x00\x00\x00\x00" or major_brand == b"    ":
        raise WorkerUnsupportedResponse(
            f"mp4 BMFF major_brand is empty / all-spaces: {major_brand!r}"
        )
    ```
  - Construct `VideoCandidate(data=data, format="mp4", metadata={"comfy_manifest": comfy_workflow, "comfy_params_snapshot": params_snapshot, "comfy_capability": "video", "comfy_original_filename": src.name, "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, frame_count=None, width=None, height=None, fps=None)` (D8: format hardcoded `"mp4"` post-F2 修订;5 metadata-None defaults — ComfyUI agent CLI does not expose video metadata; follow-on `video-metadata-parser` adds ffprobe / mutagen parsing)

#### Scenario: generate_video reads mp4 bytes and detects format

- **GIVEN** `ComfyAgentWorker._capability == "video"` and `_run_subprocess_and_validate` returning `outputs.video = ["<abs_path>/wan21_1.3b_5sec_00001.mp4"]`; the file at that path exists, is not a symlink, and contains valid mp4 bytes (magic `b"ftyp"` at offset 4)
- **WHEN** `generate_video(spec, num_candidates=1, seed=42, timeout_s=600)` runs
- **THEN** returns `[VideoCandidate(data=<mp4 bytes>, format="mp4", metadata={...}, duration_seconds=None, frame_count=None, ...)]`; `tests/unit/test_comfy_subprocess.py::test_generate_video_mp4_extension_detection_reads_bytes` fences this

#### Scenario: generate_video rejects unsupported extension (round-2 F2: webm also rejected as out-of-scope)

- **GIVEN** `outputs.video = ["<abs_path>/clip.mov"]` OR `outputs.video = ["<abs_path>/clip.webm"]`
- **WHEN** `generate_video(...)` runs
- **THEN** raises `WorkerUnsupportedResponse` with message naming the unsupported extension and explicitly mentioning that `'mp4'` is the only accepted format (webm deferred to follow-on `comfy-video-webm-adoption`); `tests/unit/test_comfy_subprocess.py::test_generate_video_unsupported_extension_mov_raises_unsupported_response` + `::test_generate_video_webm_extension_rejected_pending_follow_on` fence this

#### Scenario: generate_video BMFF too-short data raises (round-2 F4)

- **GIVEN** `outputs.video = ["<abs_path>/tiny.mp4"]` where the file content is fewer than 16 bytes (e.g. `b"\x00" * 8 + b"ftyp"` = 12 bytes — passes round-1 ftyp check but fails minimum BMFF header)
- **WHEN** `generate_video(...)` runs
- **THEN** raises `WorkerUnsupportedResponse` with message containing `"mp4 too short"` and the actual byte count; `tests/unit/test_comfy_subprocess.py::test_generate_video_bmff_too_short_raises_unsupported_response` fences this

#### Scenario: generate_video BMFF ftyp header mismatch raises

- **GIVEN** `outputs.video = ["<abs_path>/fake.mp4"]` where the file content does NOT have `b"ftyp"` at offset 4 (e.g. file starts with `b"\x00" * 16`)
- **WHEN** `generate_video(...)` runs
- **THEN** raises `WorkerUnsupportedResponse` with message containing `"mp4 BMFF header mismatch"` and the actual bytes at offset 4-8; `tests/unit/test_comfy_subprocess.py::test_generate_video_bmff_ftyp_mismatch_raises_unsupported_response` fences this

#### Scenario: generate_video BMFF box_size out of range raises (round-2 F4 + round-3 PF2 修订:largesize=1 同 reject)

- **GIVEN** `outputs.video = ["<abs_path>/corrupt.mp4"]` where the file has `b"ftyp"` at offset 4 but `data[0:4]` (box_size big-endian) is either:
  - `< 8` (e.g. 0 / 4 — too small for header)
  - `> len(data)` (e.g. 999999 in a 1KB file — exceeds payload)
  - **`== 1`** (round-3 PF2 修订:64-bit largesize box,本 change scope **rejected**;follow-on `video-bmff-largesize-support` 触发条件 = 真实 mp4 ≥ 4 GiB,Wan T2V 标准输出 5-15MB 不用 largesize)
- **WHEN** `generate_video(...)` runs
- **THEN** raises `WorkerUnsupportedResponse` with message containing `"mp4 BMFF first box_size=<N> out of range"` (and 提及 `largesize box_size==1 deferred to follow-on` for box_size==1 case); `tests/unit/test_comfy_subprocess.py::test_generate_video_bmff_box_size_too_small_raises` + `::test_generate_video_bmff_box_size_exceeds_len_raises` + `::test_generate_video_bmff_box_size_largesize_1_rejected_pending_follow_on` fence this (3 fences;round-3 PF2 修订:fence 名 `_largesize_1_accepted` → `_largesize_1_rejected_pending_follow_on`)

#### Scenario: generate_video BMFF major_brand empty raises (round-2 F4)

- **GIVEN** `outputs.video = ["<abs_path>/no_brand.mp4"]` where the file has valid `ftyp` + box_size but `data[8:12]` (major_brand) is `b"\x00\x00\x00\x00"` or `b"    "` (4 spaces)
- **WHEN** `generate_video(...)` runs
- **THEN** raises `WorkerUnsupportedResponse` with message containing `"mp4 BMFF major_brand is empty"` and the actual brand bytes; `tests/unit/test_comfy_subprocess.py::test_generate_video_bmff_major_brand_zero_raises` + `::test_generate_video_bmff_major_brand_spaces_raises` fence this (2 fences)

#### Scenario: generate_video accepts valid BMFF mp4 (Wan T2V baseline)

- **GIVEN** `outputs.video = ["<abs_path>/wan_valid.mp4"]` where the file is a valid Wan T2V output: len >= 16, `data[0:4]` = box_size in valid range, `data[4:8] == b"ftyp"`, `data[8:12] == b"isom"` (or `mp42` / `qt  ` / etc, any non-empty / non-zero major_brand)
- **WHEN** `generate_video(...)` runs
- **THEN** returns `[VideoCandidate(format="mp4", ...)]` successfully; `tests/unit/test_comfy_subprocess.py::test_generate_video_bmff_valid_mp4_accepts_with_isom_brand` + `::test_generate_video_bmff_valid_mp4_accepts_with_mp42_brand` fence this

#### Scenario: generate_video per-candidate seed override (regression of G11-F3 setdefault bypass)

- **GIVEN** `comfy_params = {"seed": 999}` (caller pre-set seed) and `seed=42`, `num_candidates=3`
- **WHEN** `generate_video(spec={"comfy_workflow": "...", "comfy_params": {"seed": 999, ...}}, num_candidates=3, seed=42, timeout_s=600)` runs the per-candidate loop
- **THEN** each iteration's `params_for_call["seed"]` is `42 + i` (NOT `999`) — direct overwrite per the sweep-mirror of audio Phase 2 G11-F3 fix; `subprocess.run` is invoked 3 times with seeds `42`, `43`, `44`; `tests/unit/test_comfy_subprocess.py::test_generate_video_per_candidate_seed_overrides_comfy_params_seed` fences this

#### Scenario: generate_video path trust-boundary rejects symlinks

- **GIVEN** `outputs.video = ["<abs_path>/symlink.mp4"]` where the path is a symlink (`Path.is_symlink() == True`)
- **WHEN** `generate_video(...)` runs
- **THEN** raises `WorkerUnsupportedResponse` with message naming the symlink path; NO `read_bytes()` is attempted; `tests/unit/test_comfy_subprocess.py::test_generate_video_symlink_path_raises_unsupported_response` fences this

#### Scenario: generate_video does not read FORGEUE_COMFY_INPUT_DIR (text-to-video has no source bytes)

- **GIVEN** `FORGEUE_COMFY_INPUT_DIR` env var is unset
- **WHEN** `generate_video(spec, num_candidates=1, seed=42, timeout_s=600)` runs
- **THEN** does NOT raise on missing env var (audio / video capabilities do not depend on it; only mesh capability requires it); `tests/unit/test_comfy_subprocess.py::test_generate_video_does_not_read_forgeue_comfy_input_dir_env_var` fences this

#### Scenario: generate_video does not mutate caller spec.comfy_params

- **GIVEN** `caller_spec = {"comfy_workflow": "...", "comfy_params": {"positive_prompt": "a cat", "seed": 42}}`; caller retains a reference to `caller_spec["comfy_params"]`
- **WHEN** `generate_video(spec=caller_spec, num_candidates=2, seed=10, timeout_s=600)` returns
- **THEN** `caller_spec["comfy_params"]` is byte-identical to its pre-call state (worker uses `dict(comfy_params)` snapshot per iteration); `tests/unit/test_comfy_subprocess.py::test_generate_video_does_not_mutate_caller_spec_comfy_params` fences this

### Requirement: GenerateVideoExecutor wraps ComfyWorker exceptions and honors RetryPolicy

The system SHALL implement `GenerateVideoExecutor` at `src/framework/runtime/executors/generate_video.py` (sibling to `GenerateAudioExecutor`):

- Class attributes: `step_type = StepType.generate` and `capability_ref = "video.t2v"` (mirror of `generate_audio.py:56-57` / `generate_mesh.py:66-67`)
- `_should_use_comfy_worker_path(self, ctx) -> bool`: returns `any(r.model == "comfy/local-video" for r in ctx.step.provider_policy.prepared_routes)` (note: `ctx.step.provider_policy` is at Step top level per `task.py:36`, NOT under `ctx.step.config`)
- `_generate_via_comfy_worker(self, ctx, spec, num, seed, timeout_s) -> list[VideoCandidate]`:
  - SHALL NOT call `_resolve_source_image(ctx)` (text-to-video has no source bytes; D7)
  - SHALL NOT read `FORGEUE_COMFY_INPUT_DIR` env var
  - Constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-video", run_id=..., project_id=..., artifacts_dir=ctx.run_dir, default_lifecycle="none")`
  - Reads retry policy: `policy = ctx.step.retry_policy or RetryPolicy()` (top-level field per `task.py:37`)
  - Reads timeout: `timeout_s = cfg.get("worker_timeout_s")` (NOT `policy.timeout_seconds` — `RetryPolicy` schema lacks that field; mirrors `generate_image.py:83` / `generate_mesh.py:190` / `generate_audio.py`)
  - Three `except` block split (sweep mirror of audio F2 / `generate_mesh.py:160-172`):
    - `ComfyWorkerTimeout` → wrap as `VideoWorkerTimeout(str(exc))` with `from exc`; honor `_should_retry(policy, wrapped)`; if `attempt + 1 >= attempts or not _should_retry(...)`: raise wrapped (NOT bare `raise`)
    - `ComfyWorkerUnsupportedResponse` → immediate `raise VideoWorkerUnsupportedResponse(str(exc)) from exc` (deterministic, no retry)
    - `ComfyWorkerError` → immediate `raise VideoWorkerError(str(exc)) from exc` (no retry)
- `execute(self, ctx) -> ExecutorResult`: parses `cfg = ctx.step.config or {}`, `spec = cfg.get("spec", {})`, `num = int(cfg.get("num_candidates", 1))`, `seed = cfg.get("seed")`, `timeout_s = cfg.get("worker_timeout_s")`; if `_should_use_comfy_worker_path(ctx)`: `candidates = _generate_via_comfy_worker(...)`; else: `raise VideoWorkerUnsupportedResponse("no video worker path resolved")`; iterates candidates calling `ctx.repository.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), metadata={"format": cand.format, "duration_seconds": cand.duration_seconds, "frame_count": cand.frame_count, "width": cand.width, "height": cand.height, "fps": cand.fps, "worker_metadata": dict(cand.metadata), ...})`

#### Scenario: GenerateVideoExecutor dispatches comfy/local-video to comfy worker branch

- **GIVEN** `ctx.step.provider_policy.prepared_routes = [Route(model="comfy/local-video", ...)]`; `ctx.step.config.spec = {"comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec", "comfy_params": {"positive_prompt": "a cat", ...}, "comfy_lifecycle": "none"}`
- **WHEN** `GenerateVideoExecutor.execute(ctx)` runs
- **THEN** `_should_use_comfy_worker_path(ctx)` returns `True`; `_generate_via_comfy_worker` is invoked; `_resolve_source_image(ctx)` is NOT invoked (text-to-video); `tests/unit/test_generate_video_comfy.py::test_executor_dispatches_comfy_local_video_to_comfy_worker_branch` + `::test_executor_no_source_image_resolution` fence this

#### Scenario: GenerateVideoExecutor wraps ComfyWorkerTimeout to VideoWorkerTimeout with from-exc

- **GIVEN** mocked `ComfyAgentWorker.generate_video` raises `ComfyWorkerTimeout("subprocess timed out after 600s")`; `policy.max_attempts == 1` (no retry); `policy.retry_on includes "timeout"`
- **WHEN** `_generate_via_comfy_worker` runs
- **THEN** raises `VideoWorkerTimeout("subprocess timed out after 600s")` chained via `from exc`; `tests/unit/test_generate_video_comfy.py::test_generate_via_comfy_worker_wraps_worker_timeout_to_video_worker_timeout_on_exhaustion` + `::test_generate_via_comfy_worker_preserves_original_exception_via_from_exc_chain` fence this

#### Scenario: GenerateVideoExecutor immediately wraps ComfyWorkerUnsupportedResponse without retry

- **GIVEN** mocked `ComfyAgentWorker.generate_video` raises `ComfyWorkerUnsupportedResponse("missing outputs.video")`; `policy.max_attempts == 3`
- **WHEN** `_generate_via_comfy_worker` runs
- **THEN** `worker.generate_video` is called exactly **once** (deterministic error short-circuits retry); raises `VideoWorkerUnsupportedResponse(...)` from cause; `tests/unit/test_generate_video_comfy.py::test_local_comfy_video_executor_unsupported_short_circuits_first_attempt` + `::test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_video_worker_unsupported_response_immediately` fence this

#### Scenario: GenerateVideoExecutor honors RetryPolicy.retry_on for timeout decisions

- **GIVEN** `RetryPolicy(max_attempts=3, retry_on=["provider_error"])` (does NOT include `"timeout"`); mocked `ComfyAgentWorker.generate_video` raises `ComfyWorkerTimeout(...)`
- **WHEN** `_generate_via_comfy_worker` runs
- **THEN** `worker.generate_video` is called exactly **once** (`_should_retry(policy, wrapped)` returns False because `retry_on` lacks `"timeout"`); raises `VideoWorkerTimeout(...)` from cause; `tests/unit/test_generate_video_comfy.py::test_local_comfy_video_executor_retry_on_excludes_timeout_short_circuits_first_attempt` fences this

#### Scenario: GenerateVideoExecutor retries on timeout when retry_on includes timeout

- **GIVEN** `RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error"])`; mocked `ComfyAgentWorker.generate_video` raises `ComfyWorkerTimeout(...)` on call 1, returns `[VideoCandidate(...)]` on call 2
- **WHEN** `_generate_via_comfy_worker` runs
- **THEN** `worker.generate_video` is called exactly **twice**; the second call's result is returned; no exception propagates; `tests/unit/test_generate_video_comfy.py::test_local_comfy_video_executor_calls_worker_generate_video_max_attempts_times_on_timeout` fences this

### Requirement: ADR-007 boundary applies to local ComfyUI video as non-premium

The system SHALL treat `comfy_local_video` (`pricing: null`, no `per_task_usd`) as **non-premium** under ADR-007 boundary, so `GenerateVideoExecutor._generate_via_comfy_worker` internal retry loop uses `(ctx.step.retry_policy or RetryPolicy()).max_attempts` (default 2) — bypassing the executor main-flow `attempts=1` premium enforcement. Future remote video workers (Runway / Pika / Sora; `pricing.per_task_usd > 0`) SHALL be premium → main-flow `attempts=1` strict.

#### Scenario: comfy/local-video pricing=None treated as non-premium

- **GIVEN** `route.model = "comfy/local-video"` resolved from `video_local` alias, with `pricing: null` in `config/models.yaml`
- **WHEN** `GenerateVideoExecutor.execute` evaluates premium status via existing `BudgetTracker.estimate_*_call_cost_usd` (or equivalent) check
- **THEN** the route is treated as non-premium; internal retry loop is allowed; `tests/unit/test_generate_video_comfy.py::test_local_comfy_video_pricing_none_treated_as_non_premium` fences this (mirror of mesh / audio boundary fences)

### Requirement: FailureModeMap routes VideoWorker exceptions to abort_or_fallback

The system SHALL extend `FailureModeMap` (`src/framework/runtime/failure_mode_map.py`) with two new modes for video worker failures:

- `FailureMode.video_worker_timeout` → `Decision.abort_or_fallback`
- `FailureMode.video_worker_unsupported` → `Decision.abort_or_fallback`

Both decisions mirror the audio_worker_* modes (Phase 2 + Phase 1 R4-F1 priority pattern). The `FailureModeMap.from_exception` classifier SHALL match wrapped video exceptions **before** generic worker exceptions and **before** audio / mesh worker exceptions (specific subclasses must precede generic parent classes per Phase 2 R4-F1 priority modeling):

```python
# Order:specific subclasses → generic parent
if isinstance(exc, VideoWorkerTimeout):
    return FailureMode.video_worker_timeout
if isinstance(exc, VideoWorkerUnsupportedResponse):
    return FailureMode.video_worker_unsupported
if isinstance(exc, VideoWorkerError):  # generic VideoWorker fallback
    return FailureMode.video_worker_unsupported
# Audio (Phase 2 已加)
if isinstance(exc, AudioWorkerTimeout): ...
# Mesh / Image / generic worker_* (existing)
```

#### Scenario: FailureModeMap routes wrapped VideoWorkerTimeout to abort_or_fallback

- **GIVEN** an exception `VideoWorkerTimeout("subprocess timed out after 600s")` (raised by `GenerateVideoExecutor._generate_via_comfy_worker` on retry exhaustion)
- **WHEN** `FailureModeMap.from_exception(exc)` is called
- **THEN** returns `FailureMode.video_worker_timeout`; the corresponding decision is `Decision.abort_or_fallback`; `tests/unit/test_failure_mode_map.py::test_failure_mode_map_routes_wrapped_video_worker_timeout_to_abort_or_fallback` fences this

#### Scenario: FailureModeMap routes wrapped VideoWorkerUnsupportedResponse to abort_or_fallback

- **GIVEN** an exception `VideoWorkerUnsupportedResponse("missing outputs.video")` (raised by `GenerateVideoExecutor._generate_via_comfy_worker` immediate-raise branch)
- **WHEN** `FailureModeMap.from_exception(exc)` is called
- **THEN** returns `FailureMode.video_worker_unsupported`; the corresponding decision is `Decision.abort_or_fallback`; `tests/unit/test_failure_mode_map.py::test_failure_mode_map_routes_wrapped_video_worker_unsupported_to_abort_or_fallback` fences this

#### Scenario: FailureModeMap video classification takes priority over generic Worker exception

- **GIVEN** an exception `VideoWorkerTimeout(...)` whose MRO includes `VideoWorkerError → RuntimeError`
- **WHEN** `FailureModeMap.from_exception(exc)` is called and the classifier walks isinstance checks in declared order
- **THEN** the classifier returns `FailureMode.video_worker_timeout` (specific subclass) — NOT `worker_timeout` (generic parent); `tests/unit/test_failure_mode_map.py::test_failure_mode_map_video_takes_priority_over_generic_worker_exception` fences the priority order
