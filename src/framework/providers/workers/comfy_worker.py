"""ComfyUI agent CLI worker (v2 since OpenSpec change comfy-agent-cli-adoption).

Architecture: ComfyUI runs as an external GPU process owned by the user
(see provider-routing/spec.md Invariants — `lifecycle="none"` only in
this change scope per D6). This module invokes the new agent CLI
(`python -m comfyui_api`) as a synchronous subprocess and parses the
stdout JSON envelope. Worker config (scripts_dir / python_exe /
default_lifecycle) reads from environment variables `FORGEUE_COMFY_*`,
not from `ProviderDef` fields (round 2 OQ-6 = F-B decision; ProviderDef
schema NOT extended — F-A registered as SRS TBD-011 follow-on).

v1 HTTPComfyWorker (raw HTTP `/prompt` + `/history` + `/view`) lived
here until commit 292420a; see git history for the v1 implementation.

Three exposed classes:
- ComfyWorker     : ABC adapter surface used by GenerateImageExecutor
- FakeComfyWorker : deterministic scripted/synth adapter for offline tests
- ComfyAgentWorker: real adapter invoking python -m comfyui_api as subprocess

Production flow:
  GenerateImageExecutor._should_use_worker_path detects model=='comfy/local'
  → constructs ComfyAgentWorker(scripts_dir=env, run_id, project_id,
    artifacts_dir=ctx.run_dir, ...)
  → calls worker.generate(spec={comfy_workflow, comfy_params, comfy_lifecycle},
    num_candidates, seed, timeout_s)
  → subprocess.run([sys.executable, "-m", "comfyui_api", "run",
    "--workflow", X, "--params", json.dumps(P), "--project", project_id,
    "--lifecycle", "none", "--timeout", str(timeout_s)], cwd=scripts_dir,
    timeout=timeout_s + buffer)
  → parse stdout JSON, copy outputs.images into artifacts_dir/comfy/,
    construct list[ImageCandidate]

Cancel semantics: subprocess.run is blocking; CancelledError does not
reach generate() because GenerateImageExecutor.execute is wrapped by
asyncio.to_thread in orchestrator.py:474 (round 2 G2 + round 3 H1+H2
documentation drift acknowledged in design.md D6 — best-effort under
to_thread; lifecycle=none means subprocess naturally exits and no
ComfyUI server child is spawned, so no orphan process risk).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class WorkerError(RuntimeError):
    """Generic worker failure (bad request, upstream error)."""


class WorkerTimeout(WorkerError):
    """Worker exceeded wall-clock budget."""


class WorkerUnsupportedResponse(WorkerError):
    """Worker observed a deterministically bad response shape that it
    cannot consume — e.g. agent CLI exit 2 with `Missing required
    param`, stdout not valid JSON, outputs.images empty, non-empty
    outputs.glb / outputs.audio in image-generation path.

    Distinct from generic `WorkerError` so FailureModeMap routes this
    to `unsupported_response` → `Decision.abort_or_fallback` rather
    than `worker_error` → `fallback_model` → same-step retry.
    Preserves the FR-RUNTIME-012 invariant (round 2 spec)."""


@dataclass
class ImageCandidate:
    """One image result from a ComfyWorker call."""

    data: bytes                          # raw image bytes (PNG by default)
    width: int
    height: int
    seed: int
    mime_type: str = "image/png"
    format: str = "png"
    metadata: dict[str, Any] = field(default_factory=dict)


class ComfyWorker(ABC):
    """Adapter surface used by the generate(image) executor."""

    name: str = "comfy"

    @abstractmethod
    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """Produce *num_candidates* images for *spec*. Must raise WorkerTimeout on timeout."""


# ----------------------------------------------------------------------------
# Fake worker — deterministic, offline, scriptable.
# ----------------------------------------------------------------------------


@dataclass
class _Script:
    """One scripted response for one `generate()` call."""

    candidates: list[ImageCandidate] | None = None
    raise_error: BaseException | None = None


class FakeComfyWorker(ComfyWorker):
    """Deterministic fake worker. Prefer explicit programming; falls back to
    synthesised stub PNGs derived from the spec + seed when unprogrammed.

    v2 schema gate (OpenSpec change comfy-agent-cli-adoption Task 6):
    if `spec` contains the new ComfyUI bundle fields (`comfy_workflow`),
    enforce schema constraints (`comfy_workflow` is str, `comfy_params`
    is dict, `comfy_lifecycle` defaults to "none" — must be "none" if
    present). Specs without `comfy_workflow` are accepted as-is for
    backward compatibility with pre-change tests (v1 inline-workflow_graph
    path; legacy `prompt_summary` / `style_tags` synth path).
    """

    name = "fake_comfy"

    def __init__(self) -> None:
        self._scripts: deque[_Script] = deque()
        self.calls: list[dict[str, Any]] = []

    # -- programming --

    def program(self, candidates: list[ImageCandidate]) -> None:
        self._scripts.append(_Script(candidates=list(candidates)))

    def program_error(self, exc: BaseException) -> None:
        self._scripts.append(_Script(raise_error=exc))

    # -- surface --

    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        # v2 schema gate (OpenSpec change Task 6): only enforced if spec
        # uses the new `comfy_workflow` field; legacy `prompt_summary`
        # specs pass through unchanged for back-compat.
        if "comfy_workflow" in spec:
            if not isinstance(spec["comfy_workflow"], str) or not spec["comfy_workflow"]:
                raise WorkerUnsupportedResponse(
                    "FakeComfyWorker.generate: spec.comfy_workflow must be a "
                    "non-empty string"
                )
            if "comfy_params" in spec and not isinstance(spec["comfy_params"], dict):
                raise WorkerUnsupportedResponse(
                    "FakeComfyWorker.generate: spec.comfy_params must be a dict"
                )
            lifecycle = spec.get("comfy_lifecycle", "none")
            if lifecycle != "none":
                raise WorkerUnsupportedResponse(
                    f"FakeComfyWorker.generate: spec.comfy_lifecycle must be 'none' "
                    f"(got {lifecycle!r}); see TBD-010 for executor-async-rewrite."
                )
        self.calls.append({
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
        })
        if self._scripts:
            script = self._scripts.popleft()
            if script.raise_error is not None:
                raise script.raise_error
            assert script.candidates is not None
            return list(script.candidates)
        return [
            _synth_candidate(spec=spec, index=i, seed=seed)
            for i in range(num_candidates)
        ]


def _synth_candidate(*, spec: dict[str, Any], index: int, seed: int | None) -> ImageCandidate:
    width = int(spec.get("width", 64))
    height = int(spec.get("height", 64))
    effective_seed = (seed or 0) + index
    # Derive a deterministic colour from (prompt_summary, seed, index).
    digest = hashlib.sha1(
        f"{spec.get('prompt_summary', '')}|{effective_seed}".encode("utf-8")
    ).digest()
    r, g, b = digest[0], digest[1], digest[2]
    data = _make_solid_png(width=width, height=height, rgb=(r, g, b))
    return ImageCandidate(
        data=data, width=width, height=height, seed=effective_seed,
        metadata={
            "prompt_summary": spec.get("prompt_summary"),
            "style_tags": list(spec.get("style_tags") or []),
            "synthetic": True,
            "rgb": [r, g, b],
            "index": index,
        },
    )


def _make_solid_png(*, width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Produce a minimal valid PNG of a solid colour. ~50 bytes for 1x1."""
    r, g, b = rgb
    raw = bytearray()
    row = bytes([0]) + bytes([r, g, b] * width)   # filter byte = 0, then RGB pixels
    for _ in range(height):
        raw += row
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        length = struct.pack(">I", len(payload))
        crc = struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        return length + tag + payload + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)   # 8-bit RGB
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    return bytes(png)


# ----------------------------------------------------------------------------
# Real worker — invoke `python -m comfyui_api` as subprocess.
# ----------------------------------------------------------------------------


# Failure-mode discriminators (round 2 spec D5 + round 3 P2 sync probe).
_UNSUPPORTED_ERROR_MARKERS = (
    "Missing required param",
    "value out of range",
    "value_not_in_list",
)


class ComfyAgentWorker(ComfyWorker):
    """Subprocess adapter for ComfyUI agent CLI (`python -m comfyui_api`).

    Constructor is keyword-only with REQUIRED args first per Python rules
    (round 3 H3 fix — round 2 contract sketch had required positional
    after default which is SyntaxError). REQUIRED `run_id` / `project_id`
    / `artifacts_dir` raise `WorkerUnsupportedResponse` if missing or
    invalid (round 2 F4 + G3 fixes).

    Worker config (scripts_dir / python_exe / default_lifecycle) is
    sourced from the executor's env-var read (round 2 OQ-6 = F-B
    decision; ProviderDef schema NOT extended).

    `default_lifecycle` is asserted to be "none" — the only value
    supported in this change scope (D6; cancel best-effort under
    orchestrator's to_thread wrapping; ensure_running / ensure_release /
    self_managed_session deferred to TBD-010 executor-async-rewrite).

    `generate()` is sync (blocks via `subprocess.run` with timeout) —
    matches `ComfyWorker` ABC. CancelledError does not reach generate
    because GenerateImageExecutor.execute is wrapped by asyncio.to_thread
    in orchestrator.py — sync executors in to_thread cannot be
    interrupted (orchestrator.py:286-296). Lifecycle=none means
    subprocess naturally exits and no ComfyUI server child is spawned,
    so cancel best-effort acceptable per design.md D6.

    `probe_sync()` classmethod is the dry-run preflight variant (called
    from DryRunPass.run which is itself sync inside the arun event loop;
    round 3 plan codex P2 fix — must NOT use asyncio.run).
    """

    name = "comfy_agent_cli"

    def __init__(
        self,
        *,                                       # H3: keyword-only
        scripts_dir: Path,                       # REQUIRED
        run_id: str,                             # REQUIRED (F4 fix)
        project_id: str,                         # REQUIRED (F4 fix)
        artifacts_dir: Path,                     # REQUIRED (G3 fix; ctx.run_dir)
        python_exe: Path | None = None,          # OPTIONAL (= sys.executable)
        default_lifecycle: str = "none",         # OPTIONAL (only "none" supported in this change)
    ) -> None:
        # F4 fix: REQUIRED project_id None/empty raise.
        if not project_id:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: project_id is REQUIRED; "
                "executor must pass ctx.task.project_id (round 2 OQ-3)"
            )
        if not run_id:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: run_id is REQUIRED; "
                "executor must pass ctx.run.run_id"
            )
        # G3 fix: REQUIRED artifacts_dir None or non-directory raise.
        if artifacts_dir is None:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: artifacts_dir is REQUIRED; "
                "executor must pass ctx.run_dir (round 2 OQ-7 = G-A; "
                "Path('.') default is test-mock convenience only)"
            )
        artifacts_dir = Path(artifacts_dir)
        if not artifacts_dir.is_dir():
            # Auto-create — this is a normal first-run condition for the
            # production path where Orchestrator computes run_dir but
            # the directory may not yet exist. ImageCandidate copy
            # target needs a real directory.
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        # D6: lifecycle scope is locked to "none" in this change (TBD-010 will lift).
        if default_lifecycle != "none":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker only supports default_lifecycle='none' "
                f"in this change scope (got {default_lifecycle!r}); "
                f"see SRS TBD-010 for the future executor-async-rewrite change."
            )
        self.scripts_dir = Path(scripts_dir)
        self.python_exe = Path(python_exe) if python_exe else Path(sys.executable)
        self.default_lifecycle = default_lifecycle
        self.run_id = run_id
        self.project_id = project_id
        self.artifacts_dir = artifacts_dir

    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """Sync invocation; calls subprocess once per candidate (each with
        seed += i). Per-call timeout is `timeout_s` (default 300s if not
        given). Total wall-clock = num_candidates × per-call (no internal
        parallelism — keeps cancel/timeout semantics simple)."""
        # Reject legacy v1 spec shape (round 2 spec).
        if "workflow_graph" in spec:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.generate: spec.workflow_graph is deprecated "
                "since OpenSpec change comfy-agent-cli-adoption; use "
                "spec.comfy_workflow + spec.comfy_params instead"
            )
        comfy_workflow = spec.get("comfy_workflow")
        if not isinstance(comfy_workflow, str) or not comfy_workflow:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.generate: spec.comfy_workflow REQUIRED, "
                "must be non-empty string (manifest name like "
                "'GameAssets/01b_singleview_sdxl')"
            )
        comfy_params = spec.get("comfy_params", {})
        if not isinstance(comfy_params, dict):
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.generate: spec.comfy_params must be a dict"
            )
        lifecycle = spec.get("comfy_lifecycle", "none")
        if lifecycle != "none":
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.generate: spec.comfy_lifecycle must be "
                f"'none' in this change scope (got {lifecycle!r}); "
                f"see SRS TBD-010 for executor-async-rewrite"
            )
        per_call_timeout = float(timeout_s) if timeout_s else 300.0
        results: list[ImageCandidate] = []
        for i in range(max(1, num_candidates)):
            call_seed = (seed or 0) + i
            params_for_call = dict(comfy_params)
            # Inject seed if not already in params
            params_for_call.setdefault("seed", call_seed)
            results.extend(self._run_once(
                comfy_workflow=comfy_workflow,
                params=params_for_call,
                seed=call_seed,
                timeout_s=per_call_timeout,
            ))
        return results

    def _run_once(
        self,
        *,
        comfy_workflow: str,
        params: dict[str, Any],
        seed: int,
        timeout_s: float,
    ) -> list[ImageCandidate]:
        """One subprocess.run call → 1+ ImageCandidate (depends on
        comfy_params batch_size)."""
        cmd = [
            str(self.python_exe), "-m", "comfyui_api", "run",
            "--workflow", comfy_workflow,
            "--params", json.dumps(params, ensure_ascii=False),
            "--project", self.project_id,
            "--lifecycle", "none",
            "--timeout", str(int(timeout_s)),
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.scripts_dir),
                timeout=timeout_s + 30.0,        # outer wrap > inner CLI timeout
                capture_output=True,
                text=True,
                # G11 R1 fix: explicit UTF-8 + errors="replace" — Windows
                # default locale (cp936/cp1252 etc.) can't decode UTF-8
                # JSON containing non-ASCII filenames / errors / workflows;
                # raised UnicodeDecodeError would not match WorkerError
                # branches and would crash the live run unstructured.
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkerTimeout(
                f"ComfyAgentWorker subprocess wall-clock exceeded "
                f"{timeout_s + 30.0}s (CLI internal timeout was {timeout_s}s)"
            ) from exc
        except FileNotFoundError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: failed to spawn subprocess "
                f"(python_exe={self.python_exe!r}, scripts_dir={self.scripts_dir!r}): "
                f"{exc}; verify FORGEUE_COMFY_SCRIPTS_DIR env var"
            ) from exc

        # Parse stdout JSON; map failures per spec D5 table.
        stdout = (result.stdout or "").strip()
        if not stdout:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: empty stdout (exit code {result.returncode}; "
                f"stderr first 500 chars: {(result.stderr or '')[:500]!r})"
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout is not valid JSON "
                f"(exit code {result.returncode}; first 500 chars: {stdout[:500]!r})"
            ) from exc

        if not isinstance(data, dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout JSON is not a dict (got {type(data).__name__})"
            )
        if not data.get("ok"):
            error_msg = str(data.get("error", ""))
            if "TimeoutError" in error_msg:
                raise WorkerTimeout(
                    f"ComfyAgentWorker: ComfyUI reported TimeoutError: {error_msg}"
                )
            for marker in _UNSUPPORTED_ERROR_MARKERS:
                if marker in error_msg:
                    raise WorkerUnsupportedResponse(
                        f"ComfyAgentWorker: deterministic param error: {error_msg}"
                    )
            raise WorkerError(
                f"ComfyAgentWorker: comfyui_api returned ok=false "
                f"(exit {result.returncode}, error: {error_msg})"
            )

        if "outputs" not in data or not isinstance(data["outputs"], dict):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: stdout JSON missing 'outputs' field or "
                f"not a dict (got {data.get('outputs')!r})"
            )
        outputs = data["outputs"]
        # Reject non-image outputs (round 2 spec — image-generation path
        # must not silently drop mesh / audio bytes).
        if outputs.get("glb"):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: outputs.glb non-empty in image-generation path "
                f"(got {outputs['glb']!r}); workflow {comfy_workflow!r} appears "
                f"to be a mesh manifest — see SRS TBD-009 for ComfyUI mesh follow-on"
            )
        if outputs.get("audio"):
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: outputs.audio non-empty in image-generation path "
                f"(got {outputs['audio']!r}); workflow {comfy_workflow!r} appears "
                f"to be an audio manifest — see SRS TBD-009 for ComfyUI audio follow-on"
            )
        images = outputs.get("images") or []
        if not images:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker: outputs.images empty for workflow "
                f"{comfy_workflow!r}; deterministic empty response cannot be "
                f"recovered by same-step retry"
            )

        # Copy each output PNG into <artifacts_dir>/comfy/ for in-tree
        # placement (round 2 G3 + artifact-contract spec).
        comfy_subdir = self.artifacts_dir / "comfy"
        comfy_subdir.mkdir(parents=True, exist_ok=True)
        candidates: list[ImageCandidate] = []
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        for src_str in images:
            src = Path(src_str)
            if not src.is_file():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images path does not exist: {src}"
                )
            # G11 R2 fix: reject symlinks (and Windows junctions) to prevent
            # a buggy / compromised agent CLI from redirecting reads to
            # arbitrary host files (e.g. /etc/secrets via ../symlink).
            if src.is_symlink():
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images path is a symlink, "
                    f"refusing to follow: {src}"
                )
            dst = comfy_subdir / src.name
            shutil.copy2(src, dst)
            data = dst.read_bytes()
            # G11 R2 fix: validate PNG magic bytes (8-byte signature
            # 89 50 4E 47 0D 0A 1A 0A). image-generation path must reject
            # non-PNG bytes — a workflow producing JPG/WEBP/etc. should be
            # treated as deterministic mismatch (caller declared image
            # capability with implicit PNG expectation per ImageCandidate
            # mime_type default). Future change can broaden the magic
            # allowlist to JPEG/WEBP if needed.
            if data[:8] != b"\x89PNG\r\n\x1a\n":
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker: outputs.images file {src.name!r} is "
                    f"not a valid PNG (first 8 bytes {data[:8]!r}); "
                    f"image-generation path requires PNG magic bytes"
                )
            candidates.append(ImageCandidate(
                data=data,
                width=width,
                height=height,
                seed=seed,
                metadata={
                    "comfy_workflow": comfy_workflow,
                    "filename": src.name,
                    "in_tree_path": str(dst),
                    "source": "comfy_agent_cli",
                    "comfy_project_id": self.project_id,
                    "comfy_outputs_orig": str(src),
                },
            ))
        return candidates

    @classmethod
    def probe_sync(
        cls,
        scripts_dir: Path,
        python_exe: Path | None,
        timeout_s: float = 30.0,
    ) -> None:
        """SYNCHRONOUS dry-run probe (round 3 plan codex P2 fix — uses
        `subprocess.run` not `asyncio.create_subprocess_exec` because
        DryRunPass.run is sync called from inside arun's event loop;
        nesting asyncio.run would raise RuntimeError).

        Validates: scripts_dir exists + comfyui_api submodule exists +
        `python -m comfyui_api status` exits 0 within timeout_s.
        Raises `WorkerUnsupportedResponse` with hint to start ComfyUI
        + check `FORGEUE_COMFY_SCRIPTS_DIR` on any failure.
        """
        scripts_dir = Path(scripts_dir)
        py = Path(python_exe) if python_exe else Path(sys.executable)
        if not scripts_dir.exists():
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI scripts_dir not found at {scripts_dir!r}; "
                f"set FORGEUE_COMFY_SCRIPTS_DIR or verify path"
            )
        if not (scripts_dir / "comfyui_api").is_dir():
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI module not found at "
                f"{scripts_dir / 'comfyui_api'!r}; install comfyui_api package "
                f"under scripts_dir"
            )
        try:
            result = subprocess.run(
                [str(py), "-m", "comfyui_api", "status"],
                cwd=str(scripts_dir),
                timeout=timeout_s,
                capture_output=True,
                text=True,
                # G11 R1 fix: same UTF-8 + errors="replace" rationale as
                # ComfyAgentWorker._run_once subprocess.run.
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI status probe timed out ({timeout_s}s); "
                f"start ComfyUI via `python -m factory_v3 serve` then retry (note: `comfyui_api` CLI does NOT have a `serve` subcommand; use sister CLI `factory_v3 serve` from same scripts/ dir)"
            ) from exc
        except FileNotFoundError as exc:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.probe_sync: failed to spawn subprocess "
                f"(python_exe={py!r}): {exc}"
            ) from exc
        if result.returncode != 0:
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI status returned exit {result.returncode}; "
                f"start ComfyUI via `python -m factory_v3 serve` then retry (note: `comfyui_api` CLI does NOT have a `serve` subcommand; use sister CLI `factory_v3 serve` from same scripts/ dir) "
                f"(stderr first 500 chars: {(result.stderr or '')[:500]!r})"
            )
