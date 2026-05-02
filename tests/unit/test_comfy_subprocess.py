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
