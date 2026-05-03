"""ComfyAgentWorker subprocess contract fences (OpenSpec change
comfy-agent-cli-adoption Task 7 — round 2 OQ-6 = F-B + round 3 H1-H5
fixes + plan codex Q1-Q3 sweep).

23 fences locking the full subprocess CLI contract per
`specs/probe-and-validation/spec.md` Requirement "ComfyUI subprocess
contract has dedicated regression fences". All fences mock at the
`subprocess.run` boundary (NOT HTTP — production ComfyAgentWorker uses
subprocess CLI per round 1 + 2 contract);  no `requests` / `httpx`
imports in this module.

Failure-mode mapping reference (specs/provider-routing/spec.md
Requirement "ComfyUI subprocess failure modes"):
- WorkerUnsupportedResponse: scripts_dir missing, module not found,
  exit 2 + Missing required param / value out of range / value_not_in_list,
  stdout non-JSON, missing outputs, env unset, project_id None,
  artifacts_dir None, non-none lifecycle, outputs.glb / outputs.audio
  non-empty
- WorkerTimeout: exit 2 + TimeoutError
- WorkerError: other exit 2 with unrecognised error string
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from framework.providers.workers.comfy_worker import (
    ComfyAgentWorker,
    WorkerError,
    WorkerTimeout,
    WorkerUnsupportedResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(tmp_path: Path) -> ComfyAgentWorker:
    """Construct a ComfyAgentWorker with valid REQUIRED args + a stub
    scripts_dir / artifacts_dir under tmp_path. Tests replace
    subprocess.run via patch to mock the actual CLI invocation."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    return ComfyAgentWorker(
        scripts_dir=scripts_dir,
        model_id="comfy/local",                  # P-F1 修订:capability dispatch 必填(image)
        run_id="run_test",
        project_id="proj_test",
        artifacts_dir=artifacts_dir,
    )


def _make_completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["mocked"], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def _ok_stdout(image_paths: list[str]) -> str:
    return json.dumps({
        "ok": True,
        "outputs": {"images": image_paths, "glb": [], "audio": []},
    })


def _make_png_file(path: Path) -> None:
    """Write a tiny valid-enough PNG so shutil.copy2 has something to copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal PNG signature + IHDR chunk (will not parse as image but is a real file)
    path.write_bytes(b"\x89PNG\r\n\x1a\nstub-bytes-for-fence")


# ---------------------------------------------------------------------------
# Constructor REQUIRED args (round 2 F4 + G3 fixes)
# ---------------------------------------------------------------------------


def test_project_id_none_raises_unsupported_response_at_init(tmp_path):
    """Round 2 F4 fix: project_id is REQUIRED; None or empty string
    raises WorkerUnsupportedResponse at __init__."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    with pytest.raises(WorkerUnsupportedResponse, match="project_id"):
        ComfyAgentWorker(
            scripts_dir=scripts_dir,
            model_id="comfy/local",                  # P-F1 修订
            run_id="run_x",
            project_id="",
            artifacts_dir=artifacts_dir,
        )


def test_artifacts_dir_none_raises_unsupported_response_at_init(tmp_path):
    """Round 2 G3 fix: artifacts_dir is REQUIRED; None raises at __init__."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    with pytest.raises(WorkerUnsupportedResponse, match="artifacts_dir"):
        ComfyAgentWorker(
            scripts_dir=scripts_dir,
            model_id="comfy/local",                  # P-F1 修订
            run_id="run_x",
            project_id="proj_x",
            artifacts_dir=None,  # type: ignore[arg-type]
        )


def test_lifecycle_other_than_none_raises_unsupported_response(tmp_path):
    """D6: only `default_lifecycle="none"` supported in this change scope.
    Any other value raises at __init__."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    with pytest.raises(WorkerUnsupportedResponse, match="default_lifecycle"):
        ComfyAgentWorker(
            scripts_dir=scripts_dir,
            model_id="comfy/local",                  # P-F1 修订
            run_id="run_x",
            project_id="proj_x",
            artifacts_dir=artifacts_dir,
            default_lifecycle="ensure_running",
        )


# ---------------------------------------------------------------------------
# probe_sync — dry-run preflight (round 3 P2 fix: SYNC, NOT asyncio)
# ---------------------------------------------------------------------------


def test_missing_scripts_dir_raises_unsupported_response(tmp_path):
    """probe_sync rejects non-existent scripts_dir."""
    bogus = tmp_path / "does_not_exist"
    with pytest.raises(WorkerUnsupportedResponse, match="scripts_dir not found"):
        ComfyAgentWorker.probe_sync(bogus, None, timeout_s=5.0)


def test_python_module_not_found_raises_unsupported_response(tmp_path):
    """probe_sync rejects scripts_dir without comfyui_api submodule."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    # Intentionally do NOT create comfyui_api submodule.
    with pytest.raises(WorkerUnsupportedResponse, match="module not found"):
        ComfyAgentWorker.probe_sync(scripts_dir, None, timeout_s=5.0)


def test_dry_run_30s_timeout(tmp_path):
    """probe_sync subprocess.TimeoutExpired → WorkerUnsupportedResponse
    with hint to start ComfyUI."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    with patch("subprocess.run") as run_mock:
        run_mock.side_effect = subprocess.TimeoutExpired(cmd=["mocked"], timeout=30.0)
        with pytest.raises(WorkerUnsupportedResponse, match="timed out"):
            ComfyAgentWorker.probe_sync(scripts_dir, None, timeout_s=30.0)


def test_probe_sync_nonzero_exit_raises(tmp_path):
    """probe_sync subprocess returncode != 0 → WorkerUnsupportedResponse."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed("", returncode=1, stderr="connection refused")
        with pytest.raises(WorkerUnsupportedResponse, match="exit 1"):
            ComfyAgentWorker.probe_sync(scripts_dir, None, timeout_s=5.0)


# ---------------------------------------------------------------------------
# generate() — failure mode mapping per spec D5 table
# ---------------------------------------------------------------------------


def test_exit2_missing_param_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(
            json.dumps({"ok": False, "error": "ValueError: Missing required param 'text'"}),
            returncode=2,
        )
        with pytest.raises(WorkerUnsupportedResponse, match="Missing required param"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_value_out_of_range_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(
            json.dumps({"ok": False, "error": "param 'width' value out of range [256, 2048]"}),
            returncode=2,
        )
        with pytest.raises(WorkerUnsupportedResponse, match="value out of range"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_value_not_in_list_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(
            json.dumps({"ok": False, "error": "ComfyUI rejected: value_not_in_list"}),
            returncode=2,
        )
        with pytest.raises(WorkerUnsupportedResponse, match="value_not_in_list"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_stdout_not_json_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed("<html>error page</html>", returncode=2)
        with pytest.raises(WorkerUnsupportedResponse, match="not valid JSON"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_stdout_missing_outputs_field_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(
            json.dumps({"ok": True, "duration_s": 10.0}),  # missing "outputs"
            returncode=0,
        )
        with pytest.raises(WorkerUnsupportedResponse, match="missing 'outputs'"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_timeout_maps_to_worker_timeout(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(
            json.dumps({"ok": False, "error": "TimeoutError: Prompt did not complete within 300s"}),
            returncode=2,
        )
        with pytest.raises(WorkerTimeout, match="TimeoutError"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_unrecognised_error_maps_to_worker_error(tmp_path):
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(
            json.dumps({"ok": False, "error": "RuntimeError: some unexpected condition"}),
            returncode=2,
        )
        with pytest.raises(WorkerError, match="ok=false") as exc_info:
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )
        # WorkerError but NOT WorkerUnsupportedResponse / WorkerTimeout subclasses
        assert not isinstance(exc_info.value, WorkerUnsupportedResponse)
        assert not isinstance(exc_info.value, WorkerTimeout)


# ---------------------------------------------------------------------------
# subprocess invocation — argv shape (round 2 OQ-3 + OQ-6 verify)
# ---------------------------------------------------------------------------


def test_subprocess_invocation_passes_workflow_params_lifecycle_timeout(tmp_path):
    """argv MUST contain --workflow / --params / --lifecycle / --timeout."""
    worker = _make_worker(tmp_path)
    png = tmp_path / "out.png"
    _make_png_file(png)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_stdout([str(png)]))
        worker.generate(
            spec={
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_params": {"text": "barrel", "seed": 42},
                "comfy_lifecycle": "none",
            },
            num_candidates=1,
            seed=42,
            timeout_s=120.0,
        )
    cmd = run_mock.call_args[0][0]
    assert "--workflow" in cmd
    assert "GameAssets/01b_singleview_sdxl" in cmd
    assert "--params" in cmd
    assert "--lifecycle" in cmd
    assert "none" in cmd
    assert "--timeout" in cmd
    assert "120" in cmd


def test_subprocess_invocation_passes_task_project_id_as_dash_dash_project(tmp_path):
    """OQ-3: --project value MUST equal task.project_id (worker constructor
    arg)."""
    worker = _make_worker(tmp_path)  # project_id="proj_test"
    png = tmp_path / "out.png"
    _make_png_file(png)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_stdout([str(png)]))
        worker.generate(
            spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
            num_candidates=1,
        )
    cmd = run_mock.call_args[0][0]
    project_idx = cmd.index("--project")
    assert cmd[project_idx + 1] == "proj_test"


# ---------------------------------------------------------------------------
# outputs handling — copy-to-tree + non-image rejection
# ---------------------------------------------------------------------------


def test_outputs_paths_are_copied_into_run_artifact_tree(tmp_path):
    """outputs.images paths are copy2'd into <artifacts_dir>/comfy/."""
    worker = _make_worker(tmp_path)
    src = tmp_path / "external" / "out.png"
    _make_png_file(src)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_stdout([str(src)]))
        candidates = worker.generate(
            spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
            num_candidates=1,
        )
    in_tree = worker.artifacts_dir / "comfy" / "out.png"
    assert in_tree.is_file()
    assert candidates[0].metadata["in_tree_path"] == str(in_tree)
    assert candidates[0].metadata["comfy_outputs_orig"] == str(src)


def test_outputs_glb_non_empty_raises_unsupported_response(tmp_path):
    """image-generation path must reject glb output (mesh deferred to TBD-009)."""
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [], "glb": ["/path/to/mesh.glb"], "audio": []},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match="glb"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/02_mini_textured_3d_hunyuan"},
                num_candidates=1,
            )


def test_outputs_audio_non_empty_raises_unsupported_response(tmp_path):
    """image-generation path must reject audio output (audio deferred to TBD-009)."""
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [], "glb": [], "audio": ["/path/to/track.mp3"]},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match="audio"):
            worker.generate(
                spec={"comfy_workflow": "Audio_Workflows/audio_ace_step_1"},
                num_candidates=1,
            )


def test_legacy_workflow_graph_field_rejected(tmp_path):
    """spec.workflow_graph (v1 inline) must raise — bundle migration守门."""
    worker = _make_worker(tmp_path)
    with pytest.raises(WorkerUnsupportedResponse, match="workflow_graph is deprecated"):
        worker.generate(
            spec={"workflow_graph": {"nodes": []}, "comfy_workflow": "X"},
            num_candidates=1,
        )


# ---------------------------------------------------------------------------
# Cancel best-effort under to_thread (D6 + round 2 narrative)
# ---------------------------------------------------------------------------


def test_cancel_under_to_thread_does_not_orphan_processes(tmp_path):
    """Lifecycle=none means subprocess naturally exits — no ComfyUI server
    child is spawned by the worker, so cancel propagation (which doesn't
    actually reach the worker due to asyncio.to_thread wrapping in the
    orchestrator) can not produce orphan processes. This fence is a
    narrative documentation of the contract: worker.generate() with
    lifecycle=none does not spawn extra child processes beyond the single
    `python -m comfyui_api` subprocess that itself runs to completion."""
    worker = _make_worker(tmp_path)
    png = tmp_path / "out.png"
    _make_png_file(png)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_stdout([str(png)]))
        worker.generate(
            spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
            num_candidates=1,
        )
    # Verify subprocess.run was called exactly once per candidate.
    # No persistent server process spawned; subprocess returns immediately.
    assert run_mock.call_count == 1
    # Default lifecycle "none" passed in argv — no auto-start ComfyUI server.
    cmd = run_mock.call_args[0][0]
    lifecycle_idx = cmd.index("--lifecycle")
    assert cmd[lifecycle_idx + 1] == "none"


# ---------------------------------------------------------------------------
# Executor + DryRunPass integration (round 2 G2 + G1 fixes)
# ---------------------------------------------------------------------------


def test_executor_dispatches_comfy_local_to_worker_not_router(tmp_path, monkeypatch):
    """GenerateImageExecutor._should_use_worker_path detects model='comfy/local'
    in prepared_routes — takes worker dispatch branch instead of router branch."""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.executors.generate_image import GenerateImageExecutor

    executor = GenerateImageExecutor()
    ctx = MagicMock()
    ctx.step.provider_policy.prepared_routes = [
        ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None,
                      kind="image", pricing=None),
    ]
    assert executor._should_use_worker_path(ctx) is True

    # Non-comfy route should NOT trigger worker path.
    ctx2 = MagicMock()
    ctx2.step.provider_policy.prepared_routes = [
        ResolvedRoute(model="qwen/qwen-image-2.0", api_key_env="QWEN", api_base=None,
                      kind="image", pricing=None),
    ]
    assert executor._should_use_worker_path(ctx2) is False


def test_comfy_agent_worker_reads_env_config(tmp_path, monkeypatch):
    """_generate_via_worker reads FORGEUE_COMFY_SCRIPTS_DIR / _PYTHON_EXE /
    _LIFECYCLE from env and constructs ComfyAgentWorker."""
    from framework.runtime.executors.generate_image import GenerateImageExecutor

    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "comfy_scripts"))
    monkeypatch.delenv("FORGEUE_COMFY_PYTHON_EXE", raising=False)
    monkeypatch.delenv("FORGEUE_COMFY_LIFECYCLE", raising=False)
    (tmp_path / "comfy_scripts" / "comfyui_api").mkdir(parents=True)
    (tmp_path / "run_dir").mkdir()

    png = tmp_path / "out.png"
    _make_png_file(png)

    executor = GenerateImageExecutor()
    ctx = MagicMock()
    ctx.run.run_id = "run_test"
    ctx.task.project_id = "proj_test"
    ctx.run_dir = tmp_path / "run_dir"

    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_stdout([str(png)]))
        candidates, chosen_model, pricing = executor._generate_via_worker(
            ctx=ctx, spec={"comfy_workflow": "X"}, num=1, seed=0, timeout_s=60.0,
        )
    assert chosen_model == "comfy/local"
    assert pricing is None
    assert len(candidates) == 1
    # subprocess argv should contain expected config from env + ctx
    cmd = run_mock.call_args[0][0]
    assert "comfyui_api" in " ".join(cmd)


def test_env_unset_raises_unsupported_response(tmp_path, monkeypatch):
    """_generate_via_worker without FORGEUE_COMFY_SCRIPTS_DIR raises
    WorkerUnsupportedResponse — env config required for comfy/local route."""
    from framework.runtime.executors.generate_image import GenerateImageExecutor

    monkeypatch.delenv("FORGEUE_COMFY_SCRIPTS_DIR", raising=False)
    executor = GenerateImageExecutor()
    ctx = MagicMock()
    ctx.run_dir = tmp_path
    ctx.run.run_id = "run_x"
    ctx.task.project_id = "proj_x"

    with pytest.raises(WorkerUnsupportedResponse, match="FORGEUE_COMFY_SCRIPTS_DIR"):
        executor._generate_via_worker(
            ctx=ctx, spec={"comfy_workflow": "X"}, num=1, seed=0, timeout_s=60.0,
        )


def test_dry_run_skips_probe_when_no_comfy_local_in_routes(tmp_path, monkeypatch):
    """DryRunPass._check_comfy_reachability: bundle without comfy/local
    route SHALL NOT spawn probe_sync subprocess — qwen/glm bundles
    unaffected on hosts without ComfyUI installed."""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        ResolvedRoute(model="qwen/qwen-image-2.0", api_key_env="QWEN",
                      api_base=None, kind="image", pricing=None),
    ]

    with patch("subprocess.run") as run_mock:
        dry_run._check_comfy_reachability(report, steps=[step])
        # No probe spawn — bundle has no comfy/local.
        run_mock.assert_not_called()


def test_dry_run_probe_runs_when_comfy_local_in_routes(tmp_path, monkeypatch):
    """DryRunPass._check_comfy_reachability: bundle with comfy/local
    route triggers sync probe_sync subprocess (round 3 P2 fix:
    sync, NOT asyncio.run nesting)."""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(scripts_dir))

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None,
                      kind="image", pricing=None),
    ]

    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed("ok", returncode=0)
        dry_run._check_comfy_reachability(report, steps=[step])
        # Probe spawned exactly once (the single status call).
        assert run_mock.call_count == 1
        cmd = run_mock.call_args[0][0]
        assert "comfyui_api" in " ".join(cmd)
        assert "status" in cmd
    assert report.checks.get("comfy.cli_reachable") is True


# ===========================================================================
# OpenSpec change comfy-agent-cli-mesh-audio-video-adoption Phase 1 mesh
# fences(per spec/probe-and-validation/spec.md + spec/provider-routing/spec.md
# + spec/artifact-contract/spec.md named tests 全集)
# ===========================================================================
import logging
import shutil

from framework.providers.workers.mesh_worker import MeshCandidate


def _make_mesh_worker(tmp_path: Path) -> ComfyAgentWorker:
    """Mesh-mode worker fixture(model_id='comfy/local-mesh' → _capability='mesh')。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "comfyui_api").mkdir(exist_ok=True)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    return ComfyAgentWorker(
        scripts_dir=scripts_dir,
        model_id="comfy/local-mesh",
        run_id="run_test_mesh",
        project_id="proj_test_mesh",
        artifacts_dir=artifacts_dir,
    )


def _ok_mesh_stdout(glb_paths: list[str], extra_outputs: dict | None = None) -> str:
    outputs = {"glb": glb_paths, "images": [], "audio": [], "video": []}
    if extra_outputs:
        outputs.update(extra_outputs)
    return json.dumps({"ok": True, "outputs": outputs})


def _make_glb_file(path: Path, *, extra_bytes: bytes = b"") -> None:
    """写一个最小合法 GLB(magic bytes b'glTF' + version + length + JSON chunk header
    占位)。fence 只需要 magic 通过校验,内容可不完整。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    # GLB header: "glTF"(4) + version u32(4) + total length u32(4) + ...
    path.write_bytes(b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 16 + extra_bytes)


# ---- Capability dispatch (D1) -------------------------------------------------


def test_capability_inferred_image_for_comfy_local(tmp_path):
    """D1: model_id='comfy/local' → _capability='image'(image-mode dispatch)。"""
    worker = _make_worker(tmp_path)  # _make_worker uses model_id='comfy/local'
    assert worker._capability == "image"
    assert worker.model_id == "comfy/local"


def test_capability_inferred_mesh_for_comfy_local_mesh(tmp_path):
    """D1: model_id='comfy/local-mesh' → _capability='mesh'(mesh-mode dispatch)。"""
    worker = _make_mesh_worker(tmp_path)
    assert worker._capability == "mesh"
    assert worker.model_id == "comfy/local-mesh"


def test_unknown_model_id_raises_at_init(tmp_path):
    """D1: 未知 model_id 在 __init__ raise(不静默 fallback)。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    with pytest.raises(WorkerUnsupportedResponse, match=r"unsupported model_id=.*comfy/local-bogus"):
        ComfyAgentWorker(
            scripts_dir=scripts_dir,
            model_id="comfy/local-bogus",
            run_id="run_x",
            project_id="proj_x",
            artifacts_dir=artifacts_dir,
        )


# ---- Capability guard on generate vs generate_mesh ----------------------------


def test_generate_image_raises_on_mesh_mode_worker(tmp_path):
    """generate (image ABC) 调用 mesh-mode worker → raise(应使用 generate_mesh)。"""
    worker = _make_mesh_worker(tmp_path)
    with pytest.raises(WorkerUnsupportedResponse, match="capability='mesh'"):
        worker.generate(spec={"comfy_workflow": "x", "comfy_params": {}}, num_candidates=1)


def test_generate_mesh_raises_on_image_mode_worker(tmp_path):
    """generate_mesh 调用 image-mode worker → raise。"""
    worker = _make_worker(tmp_path)  # image-mode
    with pytest.raises(WorkerUnsupportedResponse, match="capability='image'"):
        worker.generate_mesh(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            source_image_filename="fake.png",     # round 5 D10:filename only
            num_candidates=1,
        )


# ---- 三段表 _validate_outputs (D2 + B4 + R2-F4) ------------------------------


def test_mesh_mode_raises_on_missing_outputs_glb(tmp_path):
    """B4: mesh-mode REQUIRED outputs.glb empty → raise。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    with patch("subprocess.run") as run_mock:
        # outputs.glb empty
        run_mock.return_value = _make_completed(_ok_mesh_stdout([]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"outputs\.glb empty"):
            worker.generate_mesh(
                spec={"comfy_workflow": "Mesh/01", "comfy_params": {}},
                source_image_filename=fake_input.name,
                num_candidates=1,
            )


def test_mesh_mode_accepts_non_empty_outputs_images_as_auxiliary(tmp_path):
    """B4 critical:mesh-mode auxiliary outputs.images 容忍(不 raise),
    只产 MeshCandidate(不构造 ImageCandidate 副产物)。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout(
            [str(fake_glb)],
            extra_outputs={"images": [str(tmp_path / "preview.png")]},
        ))
        cands = worker.generate_mesh(
            spec={"comfy_workflow": "Mesh/02_with_preview", "comfy_params": {}},
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
        # 只 1 个 MeshCandidate;preview PNG 被忽略不构造任何 candidate
        assert len(cands) == 1
        assert isinstance(cands[0], MeshCandidate)
        assert cands[0].format == "glb"


def test_mesh_mode_emits_info_log_for_auxiliary_outputs_images_with_count_and_paths(tmp_path, caplog):
    """R2-F4 critical:mesh-mode auxiliary outputs.images SHALL emit INFO log
    via logger 'framework.providers.workers.comfy_worker',含 count / paths /
    capability 三字段。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    preview_paths = [str(tmp_path / "preview.png")]
    caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker")
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout(
            [str(fake_glb)], extra_outputs={"images": preview_paths},
        ))
        worker.generate_mesh(
            spec={"comfy_workflow": "Mesh/02", "comfy_params": {}},
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
    matched = [r for r in caplog.records
               if "auxiliary outputs.images" in r.message
               and "count=1" in r.message
               and "capability='mesh'" in r.message]
    assert matched, f"expected INFO log with count/paths/capability fields; got records: {[r.message for r in caplog.records]}"


def test_mesh_mode_raises_on_rejected_outputs_audio(tmp_path):
    """B4: mesh-mode REJECTED outputs.audio non-empty → raise。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout(
            [str(fake_glb)], extra_outputs={"audio": ["unexpected.wav"]},
        ))
        with pytest.raises(WorkerUnsupportedResponse, match=r"rejected non-empty outputs.*audio"):
            worker.generate_mesh(
                spec={"comfy_workflow": "Mesh/03", "comfy_params": {}},
                source_image_filename=fake_input.name,
                num_candidates=1,
            )


def test_mesh_mode_raises_on_rejected_outputs_video(tmp_path):
    """B4: mesh-mode REJECTED outputs.video non-empty → raise。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout(
            [str(fake_glb)], extra_outputs={"video": ["unexpected.mp4"]},
        ))
        with pytest.raises(WorkerUnsupportedResponse, match=r"rejected non-empty outputs.*video"):
            worker.generate_mesh(
                spec={"comfy_workflow": "Mesh/04", "comfy_params": {}},
                source_image_filename=fake_input.name,
                num_candidates=1,
            )


def test_image_mode_still_rejects_outputs_video(tmp_path):
    """image-mode regression(B4 修订三段表 image-mode REJECTED 集 = {glb, audio, video})。"""
    worker = _make_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": ["x.png"], "video": ["x.mp4"]},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match=r"rejected non-empty outputs.*video"):
            worker.generate(spec={
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_params": {},
            }, num_candidates=1)


# ---- Mesh artifact (data + metadata + GLB magic) (D5 + R2-F3) ----------------


def test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path(tmp_path):
    """D5: MeshCandidate.data == Path(outputs.glb[0]).read_bytes()(无 worker 内部 copy,
    bytes 直接进 candidate;ArtifactRepository.put 后续负责 in-tree copy)。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb, extra_bytes=b"some-payload-bytes")
    expected_bytes = fake_glb.read_bytes()
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout([str(fake_glb)]))
        cands = worker.generate_mesh(
            spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
    assert len(cands) == 1
    assert cands[0].data == expected_bytes
    assert cands[0].data.startswith(b"glTF")


def test_comfy_mesh_candidate_metadata_records_comfy_provenance(tmp_path):
    """D5: MeshCandidate.metadata 含 comfy_manifest / comfy_params_snapshot /
    comfy_capability / comfy_original_filename / comfy_source_image_path。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "src.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset_textured_00001.glb"
    _make_glb_file(fake_glb)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout([str(fake_glb)]))
        cands = worker.generate_mesh(
            spec={
                "comfy_workflow": "Mesh/02_mini_textured_3d_hunyuan",
                "comfy_params": {"texture_quality": "high"},
            },
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
    md = cands[0].metadata
    assert md["comfy_manifest"] == "Mesh/02_mini_textured_3d_hunyuan"
    assert md["comfy_capability"] == "mesh"
    assert md["comfy_original_filename"] == "asset_textured_00001.glb"
    # round 5 D10:metadata 字段 comfy_input_filename(filename only,不是绝对路径);
    # ComfyUI input dir 由 executor 知道,worker 不记 dir(executor 会另补)
    assert md["comfy_input_filename"] == fake_input.name
    # snapshot 含 user 显式 params + executor 注入的 input_image(round 5 D8 默认 key)+ seed
    snap = md["comfy_params_snapshot"]
    assert snap["texture_quality"] == "high"
    assert snap["input_image"] == fake_input.name


def test_comfy_mesh_candidate_metadata_snapshot_isolated_from_spec_mutation(tmp_path):
    """D5: post-call mutate caller spec.comfy_params 不影响已落 metadata snapshot
    (deep copy via dict(...) inside generate_mesh)。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "src.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    spec = {
        "comfy_workflow": "M/01",
        "comfy_params": {"steps": 20, "seed_init": 42},
    }
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout([str(fake_glb)]))
        cands = worker.generate_mesh(
            spec=spec, source_image_filename=fake_input.name, num_candidates=1,
        )
    # mutate caller spec.comfy_params
    spec["comfy_params"]["steps"] = 999
    spec["comfy_params"]["new_field"] = "polluted"
    snap = cands[0].metadata["comfy_params_snapshot"]
    assert snap["steps"] == 20  # snapshot 未污染
    assert "new_field" not in snap


def test_comfy_mesh_rejects_non_glb_magic_bytes(tmp_path):
    """GLB magic bytes 校验:b"glTF" prefix REQUIRED。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "fake.glb"
    fake_glb.parent.mkdir(parents=True, exist_ok=True)
    fake_glb.write_bytes(b"NOT_A_GLB" + b"\x00" * 16)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout([str(fake_glb)]))
        with pytest.raises(WorkerUnsupportedResponse, match="glTF binary magic"):
            worker.generate_mesh(
                spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_filename=fake_input.name,
                num_candidates=1,
            )


def test_comfy_mesh_rejects_symlink_outputs_glb_path(tmp_path):
    """安全检查:outputs.glb 路径是 symlink → raise(防止 compromised CLI 重定向)。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "input.png"
    fake_input.write_bytes(b"<png>")
    real_glb = tmp_path / "real.glb"
    _make_glb_file(real_glb)
    sym_glb = tmp_path / "link.glb"
    try:
        os.symlink(str(real_glb), str(sym_glb))
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlink unsupported on this OS / unprivileged user")
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout([str(sym_glb)]))
        with pytest.raises(WorkerUnsupportedResponse, match="symlink"):
            worker.generate_mesh(
                spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_filename=fake_input.name,
                num_candidates=1,
            )


# ---- Source image path injection (D7 + D8) ----------------------------------


def test_generate_mesh_injects_source_image_filename_into_comfy_params_under_default_input_image_key(tmp_path):
    """D8 round 5 修订:bundle 不声明 comfy_image_param_key 时,默认注入到 'input_image'
    (对齐 LoadImage 节点参数名;round 1-4 默认 'image_path' 是凭直觉错值)。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "src.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    captured_argv: list[list[str]] = []
    def _capture(*args, **kwargs):
        captured_argv.append(list(args[0]))
        return _make_completed(_ok_mesh_stdout([str(fake_glb)]))
    with patch("subprocess.run", side_effect=_capture):
        worker.generate_mesh(
            spec={"comfy_workflow": "M/01", "comfy_params": {"steps": 20}},
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
    assert len(captured_argv) == 1
    cmd = captured_argv[0]
    # --params 后的 JSON 含 input_image = filename(round 5 D10:filename only,不是绝对路径)
    params_idx = cmd.index("--params")
    params_dict = json.loads(cmd[params_idx + 1])
    assert params_dict["input_image"] == fake_input.name  # filename only
    assert params_dict["steps"] == 20


def test_generate_mesh_injects_under_custom_comfy_image_param_key_when_bundle_declares_it(tmp_path):
    """D8: bundle 显式声明 comfy_image_param_key='image' 时,注入到该 key
    (round 5 修订:用 'image' 测 override,因为新默认 'input_image' 与某些 fence 默认值重合)。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "src.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    captured_argv: list[list[str]] = []
    def _capture(*args, **kwargs):
        captured_argv.append(list(args[0]))
        return _make_completed(_ok_mesh_stdout([str(fake_glb)]))
    with patch("subprocess.run", side_effect=_capture):
        worker.generate_mesh(
            spec={
                "comfy_workflow": "M/01",
                "comfy_params": {"steps": 20},
                "comfy_image_param_key": "image",   # custom override
            },
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
    cmd = captured_argv[0]
    params_idx = cmd.index("--params")
    params_dict = json.loads(cmd[params_idx + 1])
    assert params_dict["image"] == fake_input.name  # custom key
    assert "input_image" not in params_dict  # 不污染默认 key(因 override)


def test_generate_mesh_does_not_mutate_caller_spec_comfy_params(tmp_path):
    """D8: worker 必须 deep-copy spec.comfy_params,不污染 caller dict。"""
    worker = _make_mesh_worker(tmp_path)
    fake_input = tmp_path / "src.png"
    fake_input.write_bytes(b"<png>")
    fake_glb = tmp_path / "asset.glb"
    _make_glb_file(fake_glb)
    caller_params = {"steps": 20, "guidance": 7.5}
    caller_params_id = id(caller_params)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_mesh_stdout([str(fake_glb)]))
        worker.generate_mesh(
            spec={"comfy_workflow": "M/01", "comfy_params": caller_params},
            source_image_filename=fake_input.name,
            num_candidates=1,
        )
    # caller dict 未被注入 image_path / seed
    assert "image_path" not in caller_params
    assert id(caller_params) == caller_params_id  # same object identity
    assert caller_params == {"steps": 20, "guidance": 7.5}  # unchanged content


# ---- dry-run gate extension (P-F4) -------------------------------------------


def test_dry_run_probe_runs_when_comfy_local_mesh_in_routes(tmp_path, monkeypatch):
    """P-F4: dry-run probe gate 扩为 set membership;comfy/local-mesh route 也触发 probe。"""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(scripts_dir))

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        ResolvedRoute(model="comfy/local-mesh", api_key_env=None, api_base=None,
                      kind="mesh", pricing=None),
    ]

    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed("ok", returncode=0)
        dry_run._check_comfy_reachability(report, steps=[step])
        # comfy/local-mesh 也触发 probe(P-F4 set 扩展)
        assert run_mock.call_count == 1
        cmd = run_mock.call_args[0][0]
        assert "comfyui_api" in " ".join(cmd)
        assert "status" in cmd
    assert report.checks.get("comfy.cli_reachable") is True


def test_dry_run_skips_probe_when_no_comfy_local_or_local_mesh_in_routes(tmp_path):
    """regression: 仅 qwen / glm / hunyuan 路径不触发 ComfyUI probe(性能 + 可用性)。"""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        ResolvedRoute(model="hunyuan/hy-3d-3.1", api_key_env="HUNYUAN_3D_KEY",
                      api_base=None, kind="mesh", pricing={"per_task_usd": 0.25}),
    ]

    with patch("subprocess.run") as run_mock:
        dry_run._check_comfy_reachability(report, steps=[step])
        assert run_mock.call_count == 0  # 完全跳过 probe


# ---- G11-F3 follow-on: per-candidate seed override (image + mesh) ------------
# OpenSpec change `comfy-worker-seed-setdefault-bug-fix`(2026-05-04):
# 镜像 audio fence
# `tests/unit/test_comfy_subprocess_audio.py::test_generate_audio_per_candidate_seed_overrides_comfy_params_seed`
# 模式;验证 image / mesh per-candidate seed 直接覆盖 `comfy_params.seed`。


def test_generate_image_per_candidate_seed_overrides_comfy_params_seed(tmp_path):
    """G11-F3 follow-on:`comfy_params` 已含 `seed: 42` 时,per-candidate seed 偏移
    仍生效(每个 candidate 拿 100 / 101 / 102 不是同 42)。fence 守门
    `setdefault → 直接覆盖` 修复(防 num_candidates>1 时 candidate 重复)。"""
    worker = _make_worker(tmp_path)
    fakes = [tmp_path / f"out_{i}.png" for i in range(3)]
    for f in fakes:
        _make_png_file(f)
    with patch("subprocess.run") as run_mock:
        run_mock.side_effect = [
            _make_completed(_ok_stdout([str(f)])) for f in fakes
        ]
        worker.generate(
            spec={"comfy_workflow": "x", "comfy_params": {"seed": 42}},  # caller 显式 seed
            num_candidates=3,
            seed=100,  # base seed
        )
    # 提取每个 subprocess.run 调用的 --params JSON 里的 seed 字段
    seeds_seen: list[int] = []
    for call in run_mock.call_args_list:
        argv = call.args[0]
        idx = argv.index("--params")
        params = json.loads(argv[idx + 1])
        seeds_seen.append(params["seed"])
    assert seeds_seen == [100, 101, 102], (
        f"Expected per-candidate seed override 100/101/102, got {seeds_seen}; "
        f"setdefault bug would return [42, 42, 42]"
    )


def test_generate_mesh_per_candidate_seed_overrides_comfy_params_seed(tmp_path):
    """G11-F3 follow-on (mesh):`comfy_params` 已含 `seed: 42` 时,per-candidate
    seed 偏移仍生效。Mirror image fence 模式;mesh path 走 image-to-mesh DAG,
    需要 source_image_filename 参数,但 seed 注入 logic 与 image / audio 一致。"""
    worker = _make_mesh_worker(tmp_path)
    fakes = [tmp_path / f"out_{i}.glb" for i in range(3)]
    for f in fakes:
        _make_glb_file(f)
    with patch("subprocess.run") as run_mock:
        run_mock.side_effect = [
            _make_completed(_ok_mesh_stdout([str(f)])) for f in fakes
        ]
        worker.generate_mesh(
            spec={"comfy_workflow": "x", "comfy_params": {"seed": 42}},  # caller 显式 seed
            source_image_filename="forgeue_test.png",
            num_candidates=3,
            seed=100,  # base seed
        )
    seeds_seen: list[int] = []
    for call in run_mock.call_args_list:
        argv = call.args[0]
        idx = argv.index("--params")
        params = json.loads(argv[idx + 1])
        seeds_seen.append(params["seed"])
    assert seeds_seen == [100, 101, 102], (
        f"Expected per-candidate mesh seed override 100/101/102, got {seeds_seen}; "
        f"setdefault bug would return [42, 42, 42]"
    )


# ---- G6-F2 follow-on: producer attribution for comfy/local image path -------
# OpenSpec change `comfy-executor-producer-attribution-fix`(2026-05-04):
# fence 守门 comfy/local 分支活跃时,Artifact.producer.provider == "comfy_agent_cli"
# (NOT self._worker.name 注入的 fallback worker 名)。


def test_executor_dispatches_comfy_local_records_provider_as_comfy_agent_cli(tmp_path, monkeypatch):
    """G6-F2 follow-on:comfy/local 路径活跃时,Artifact.producer.provider
    == "comfy_agent_cli",NOT injected worker name(framework.run 注入的
    FakeComfyWorker name 会污染 audit / comparison report)。"""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    from framework.artifact_store import ArtifactRepository, get_backend_registry
    from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
    from framework.core.policies import PreparedRoute, ProviderPolicy
    from framework.core.task import Run, Step, Task
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.executors.base import StepContext
    from framework.runtime.executors.generate_image import GenerateImageExecutor

    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)

    fake_png = tmp_path / "out.png"
    _make_png_file(fake_png)

    reg = get_backend_registry(artifact_root=str(tmp_path / "artifacts"))
    repo = ArtifactRepository(backend_registry=reg)
    policy = ProviderPolicy(
        capability_required="image.generation",
        prepared_routes=[PreparedRoute(
            model="comfy/local", api_key_env=None, api_base=None,
            kind="image", pricing=None,
        )],
    )
    step = Step(
        step_id="step_image", type=StepType.generate, name="img",
        risk_level=RiskLevel.medium, capability_ref="image.generation",
        config={
            "num_candidates": 1,
            "seed": 0,
            "worker_timeout_s": 60,
            "spec": {
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_params": {"prompt": "test"},
                "comfy_lifecycle": "none",
            },
        },
        provider_policy=policy,
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.basic_llm, title="img",
        input_payload={}, expected_output={}, project_id="proj_img",
    )
    run = Run(
        run_id="run_img", task_id="t", project_id="proj_img",
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="w", trace_id="tr",
    )
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[], run_dir=tmp_path / "run_dir",
    )
    (tmp_path / "run_dir").mkdir()

    # injected worker(FakeComfyWorker-like)— 其 name 不应 leak 到 producer
    injected_worker = MagicMock()
    injected_worker.name = "fake_comfy_injected"
    executor = GenerateImageExecutor(worker=injected_worker)

    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_stdout([str(fake_png)]))
        result = executor.execute(ctx)

    # 应有 1 image artifact + 1 bundle artifact
    image_arts = [a for a in result.artifacts if a.artifact_type.modality == "image"]
    bundle_arts = [a for a in result.artifacts if a.artifact_type.modality == "bundle"]
    assert len(image_arts) == 1, f"expected 1 image artifact, got {len(image_arts)}"
    assert len(bundle_arts) == 1, f"expected 1 bundle artifact, got {len(bundle_arts)}"
    # G6-F2 fix:image artifact provider == "comfy_agent_cli"
    assert image_arts[0].producer.provider == "comfy_agent_cli", (
        f"Expected provider='comfy_agent_cli' for comfy/local path, "
        f"got {image_arts[0].producer.provider!r}; pre-fix would yield 'fake_comfy_injected'"
    )
    # bundle producer 同样 attribution
    assert bundle_arts[0].producer.provider == "comfy_agent_cli", (
        f"Bundle producer should also be 'comfy_agent_cli', "
        f"got {bundle_arts[0].producer.provider!r}"
    )
    # metrics["worker"] 同样 comfy_agent_cli
    assert result.metrics["worker"] == "comfy_agent_cli", (
        f"metrics.worker should be 'comfy_agent_cli', got {result.metrics['worker']!r}"
    )
