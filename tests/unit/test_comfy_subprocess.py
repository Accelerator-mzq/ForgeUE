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
    subprocess.run via patch to mock the actual CLI invocation.

    OpenSpec change `comfy-agent-cli-path-containment-hardening`(2026-05-04):
    `comfy_output_root` heuristic falls back to `scripts_dir.parent`
    (= `tmp_path`)so fake outputs written directly to tmp_path/out_*.png
    pass the containment check `_assert_path_within_comfy_output_root`.
    """
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


class _AsyncFakeProcess:
    """模拟 asyncio.subprocess.Process,用于替代 subprocess.CompletedProcess。
    TBD-010 Task 3:现有测试将 _make_completed 返回值换成 _AsyncFakeProcess 实例。
    _AsyncFakeProcess.to_async_mock() 返回供 patch asyncio.create_subprocess_exec 使用的工厂函数。
    """

    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        # 保存为 bytes,模拟 asyncio.create_subprocess_exec stdout pipe 输出
        self._stdout_bytes = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
        self._stderr_bytes = stderr.encode("utf-8") if isinstance(stderr, str) else stderr
        self.returncode = returncode

    async def communicate(self):
        return (self._stdout_bytes, self._stderr_bytes)

    async def wait(self):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass


def _make_async_completed(stdout: str, returncode: int = 0, stderr: str = "") -> _AsyncFakeProcess:
    """_make_completed 的 async 版本,返回 _AsyncFakeProcess 实例。
    与 _make_completed 同接口,方便逐步替换。"""
    return _AsyncFakeProcess(stdout=stdout, returncode=returncode, stderr=stderr)


def _patch_create_subprocess_exec(fake_proc: "_AsyncFakeProcess | None" = None, *, side_effect=None):
    """返回 asyncio.create_subprocess_exec 的 patch context manager。

    用法:
        with _patch_create_subprocess_exec(_make_async_completed(stdout)) as mock:
            worker.generate(...)
            cmd = mock.call_args[0]  # 注意: create_subprocess_exec 接收 *args

    side_effect: callable(*a, **kw) -> _AsyncFakeProcess 列表迭代(类似 subprocess.run mock side_effect)。
    """
    import asyncio as _aio
    from contextlib import contextmanager

    calls = []

    if side_effect is not None:
        _effects = list(side_effect) if not callable(side_effect) else None
        _effect_fn = side_effect if callable(side_effect) else None
        _effect_iter = iter(_effects) if _effects else None

        async def _factory(*a, **kw):
            calls.append(a)
            if _effect_fn:
                return _effect_fn(*a, **kw)
            return next(_effect_iter)
    else:
        async def _factory(*a, **kw):
            calls.append(a)
            return fake_proc

    class _Ctx:
        """patch 的上下文管理器。支持 call_args_list / call_count / call_args。"""
        def __init__(self):
            self._orig = None
            self.call_args_list = calls

        @property
        def call_args(self):
            return self.call_args_list[-1] if self.call_args_list else None

        @property
        def call_count(self):
            return len(self.call_args_list)

        def __enter__(self):
            self._orig = _aio.create_subprocess_exec
            _aio.create_subprocess_exec = _factory  # type: ignore[assignment]
            return self

        def __exit__(self, *_):
            _aio.create_subprocess_exec = self._orig  # type: ignore[assignment]

    return _Ctx()


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
# probe / aprobe — dry-run preflight (Step 6: aprobe async 主面 + probe_sync sync shim)
# ---------------------------------------------------------------------------


def test_missing_scripts_dir_raises_unsupported_response(tmp_path):
    """probe_sync(sync shim)拒绝不存在的 scripts_dir — 文件系统守门,无 subprocess。"""
    bogus = tmp_path / "does_not_exist"
    with pytest.raises(WorkerUnsupportedResponse, match="scripts_dir not found"):
        ComfyAgentWorker.probe_sync(bogus, None, timeout_s=5.0)


def test_python_module_not_found_raises_unsupported_response(tmp_path):
    """probe_sync(sync shim)拒绝没有 comfyui_api 子模块的 scripts_dir。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    # 故意不创建 comfyui_api 子模块
    with pytest.raises(WorkerUnsupportedResponse, match="module not found"):
        ComfyAgentWorker.probe_sync(scripts_dir, None, timeout_s=5.0)


@pytest.mark.asyncio
async def test_aprobe_missing_scripts_dir_raises_unsupported_response(tmp_path):
    """aprobe(async 主面)拒绝不存在的 scripts_dir — 文件系统守门,无 subprocess。"""
    bogus = tmp_path / "does_not_exist"
    with pytest.raises(WorkerUnsupportedResponse, match="scripts_dir not found"):
        await ComfyAgentWorker.aprobe(bogus, None, timeout_s=5.0)


@pytest.mark.asyncio
async def test_aprobe_module_not_found_raises_unsupported_response(tmp_path):
    """aprobe(async 主面)拒绝没有 comfyui_api 子模块的 scripts_dir。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    # 故意不创建 comfyui_api 子模块
    with pytest.raises(WorkerUnsupportedResponse, match="module not found"):
        await ComfyAgentWorker.aprobe(scripts_dir, None, timeout_s=5.0)


@pytest.mark.asyncio
async def test_dry_run_30s_timeout(tmp_path):
    """aprobe asyncio.TimeoutError → WorkerUnsupportedResponse,含 hint to start ComfyUI。
    Step 6:probe_sync(sync shim)→ aprobe(async 主面),patch asyncio.create_subprocess_exec。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()

    import asyncio as _aio

    class _TimeoutFakeProcess:
        """模拟 communicate() 永久挂起的 fake process,触发 asyncio.wait_for 超时。"""
        returncode = None

        async def communicate(self):
            # 永远挂起,让 asyncio.wait_for 抛出 TimeoutError
            await _aio.sleep(9999)
            return (b"", b"")

        def terminate(self):
            # aprobe 的 finally cleanup 会调用 terminate;模拟进程被终止
            self.returncode = -15

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    async def _timeout_factory(*a, **kw):
        return _TimeoutFakeProcess()

    orig = _aio.create_subprocess_exec
    _aio.create_subprocess_exec = _timeout_factory  # type: ignore[assignment]
    try:
        with pytest.raises(WorkerUnsupportedResponse, match="timed out"):
            # timeout_s=0.01 让 wait_for 迅速触发 TimeoutError
            await ComfyAgentWorker.aprobe(scripts_dir, None, timeout_s=0.01)
    finally:
        _aio.create_subprocess_exec = orig  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_aprobe_nonzero_exit_raises(tmp_path):
    """aprobe subprocess returncode != 0 → WorkerUnsupportedResponse。
    Step 6:patch asyncio.create_subprocess_exec 返回 returncode=1 的 fake process。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    with _patch_create_subprocess_exec(_make_async_completed("", returncode=1, stderr="connection refused")):
        with pytest.raises(WorkerUnsupportedResponse, match="exit 1"):
            await ComfyAgentWorker.aprobe(scripts_dir, None, timeout_s=5.0)


# ---------------------------------------------------------------------------
# generate() — failure mode mapping per spec D5 table
# ---------------------------------------------------------------------------


def test_exit2_missing_param_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
            json.dumps({"ok": False, "error": "ValueError: Missing required param 'text'"}),
            returncode=2,
        )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="Missing required param"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_value_out_of_range_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
            json.dumps({"ok": False, "error": "param 'width' value out of range [256, 2048]"}),
            returncode=2,
        )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="value out of range"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_value_not_in_list_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
            json.dumps({"ok": False, "error": "ComfyUI rejected: value_not_in_list"}),
            returncode=2,
        )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="value_not_in_list"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_stdout_not_json_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed("<html>error page</html>", returncode=2)) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="not valid JSON"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_stdout_missing_outputs_field_maps_to_unsupported(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
            json.dumps({"ok": True, "duration_s": 10.0}),  # missing "outputs"
            returncode=0,
        )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="missing 'outputs'"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_timeout_maps_to_worker_timeout(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
            json.dumps({"ok": False, "error": "TimeoutError: Prompt did not complete within 300s"}),
            returncode=2,
        )) as run_mock:
        with pytest.raises(WorkerTimeout, match="TimeoutError"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
            )


def test_exit2_unrecognised_error_maps_to_worker_error(tmp_path):
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
            json.dumps({"ok": False, "error": "RuntimeError: some unexpected condition"}),
            returncode=2,
        )) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(png)]))) as run_mock:
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
    cmd = list(run_mock.call_args)
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(png)]))) as run_mock:
        worker.generate(
            spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
            num_candidates=1,
        )
    cmd = list(run_mock.call_args)
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(src)]))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [], "glb": ["/path/to/mesh.glb"], "audio": []},
        }))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="glb"):
            worker.generate(
                spec={"comfy_workflow": "GameAssets/02_mini_textured_3d_hunyuan"},
                num_candidates=1,
            )


def test_outputs_audio_non_empty_raises_unsupported_response(tmp_path):
    """image-generation path must reject audio output (audio deferred to TBD-009)."""
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [], "glb": [], "audio": ["/path/to/track.mp3"]},
        }))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(png)]))) as run_mock:
        worker.generate(
            spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
            num_candidates=1,
        )
    # Verify create_subprocess_exec was called exactly once per candidate.
    # No persistent server process spawned; subprocess returns immediately.
    assert run_mock.call_count == 1
    # Default lifecycle "none" passed in argv — no auto-start ComfyUI server.
    cmd = list(run_mock.call_args)
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

    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(png)]))) as run_mock:
        candidates, chosen_model, pricing = executor._generate_via_worker(
            ctx=ctx, spec={"comfy_workflow": "X"}, num=1, seed=0, timeout_s=60.0,
        )
    assert chosen_model == "comfy/local"
    assert pricing is None
    assert len(candidates) == 1
    # subprocess argv should contain expected config from env + ctx
    cmd = list(run_mock.call_args)
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


@pytest.mark.asyncio
async def test_dry_run_skips_probe_when_no_comfy_local_in_routes(tmp_path, monkeypatch):
    """DryRunPass._check_comfy_reachability(async): 无 comfy/local route 的 bundle
    不触发 aprobe subprocess — qwen/glm bundle 在无 ComfyUI 主机上不受影响。
    Step 6: async _check_comfy_reachability 转换。"""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        ResolvedRoute(model="qwen/qwen-image-2.0", api_key_env="QWEN",
                      api_base=None, kind="image", pricing=None),
    ]

    with _patch_create_subprocess_exec(_make_async_completed("ok", returncode=0)) as run_mock:
        await dry_run._check_comfy_reachability(report, steps=[step])
        # 无 comfy/local route — 完全跳过 probe
        assert run_mock.call_count == 0


@pytest.mark.asyncio
async def test_dry_run_probe_runs_when_comfy_local_in_routes(tmp_path, monkeypatch):
    """DryRunPass._check_comfy_reachability(async): comfy/local route 触发 aprobe subprocess。
    Step 6: async _check_comfy_reachability + aprobe 转换(原 sync probe_sync 路径已 async 化)。"""
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

    with _patch_create_subprocess_exec(_make_async_completed("ok", returncode=0)) as run_mock:
        await dry_run._check_comfy_reachability(report, steps=[step])
        # aprobe 恰好触发一次(status 子命令)
        assert run_mock.call_count == 1
        # call_args 是 create_subprocess_exec 的 positional args 元组: (py, "-m", "comfyui_api", "status")
        call_args = run_mock.call_args
        assert "comfyui_api" in call_args
        assert "status" in call_args
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
    """Mesh-mode worker fixture(model_id='comfy/local-mesh' → _capability='mesh')。

    Path containment heuristic uses `scripts_dir.parent` = `tmp_path`,
    so fake outputs in tmp_path pass the containment check.
    """
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([]))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout(
            [str(fake_glb)],
            extra_outputs={"images": [str(tmp_path / "preview.png")]},
        ))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout(
            [str(fake_glb)], extra_outputs={"images": preview_paths},
        ))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout(
            [str(fake_glb)], extra_outputs={"audio": ["unexpected.wav"]},
        ))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout(
            [str(fake_glb)], extra_outputs={"video": ["unexpected.mp4"]},
        ))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"rejected non-empty outputs.*video"):
            worker.generate_mesh(
                spec={"comfy_workflow": "Mesh/04", "comfy_params": {}},
                source_image_filename=fake_input.name,
                num_candidates=1,
            )


def test_image_mode_still_rejects_outputs_video(tmp_path):
    """image-mode regression(B4 修订三段表 image-mode REJECTED 集 = {glb, audio, video})。"""
    worker = _make_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(json.dumps({
            "ok": True,
            "outputs": {"images": ["x.png"], "video": ["x.mp4"]},
        }))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(fake_glb)]))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(fake_glb)]))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(fake_glb)]))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(fake_glb)]))) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(sym_glb)]))) as run_mock:
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
    def _capture_factory1(*args, **kwargs):
        # create_subprocess_exec 以位置参数方式传入各 argv 项
        captured_argv.append(list(args))
        return _make_async_completed(_ok_mesh_stdout([str(fake_glb)]))
    with _patch_create_subprocess_exec(side_effect=_capture_factory1) as run_mock:
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
    def _capture_factory2(*args, **kwargs):
        captured_argv.append(list(args))
        return _make_async_completed(_ok_mesh_stdout([str(fake_glb)]))
    with _patch_create_subprocess_exec(side_effect=_capture_factory2) as run_mock:
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
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(fake_glb)]))) as run_mock:
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


@pytest.mark.asyncio
async def test_dry_run_probe_runs_when_comfy_local_mesh_in_routes(tmp_path, monkeypatch):
    """P-F4: dry-run probe gate 扩为 set membership;comfy/local-mesh route 也触发 aprobe。
    Step 6: async _check_comfy_reachability 转换。"""
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

    with _patch_create_subprocess_exec(_make_async_completed("ok", returncode=0)) as run_mock:
        await dry_run._check_comfy_reachability(report, steps=[step])
        # comfy/local-mesh 也触发 aprobe(P-F4 set 扩展 + Step 6 async 化)
        assert run_mock.call_count == 1
        call_args = run_mock.call_args
        assert "comfyui_api" in call_args
        assert "status" in call_args
    assert report.checks.get("comfy.cli_reachable") is True


@pytest.mark.asyncio
async def test_dry_run_skips_probe_when_no_comfy_local_or_local_mesh_in_routes(tmp_path):
    """regression: 仅 qwen / glm / hunyuan 路径不触发 ComfyUI aprobe(性能 + 可用性)。
    Step 6: async _check_comfy_reachability 转换。"""
    from framework.providers.model_registry import ResolvedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        ResolvedRoute(model="hunyuan/hy-3d-3.1", api_key_env="HUNYUAN_3D_KEY",
                      api_base=None, kind="mesh", pricing={"per_task_usd": 0.25}),
    ]

    with _patch_create_subprocess_exec(_make_async_completed("ok", returncode=0)) as run_mock:
        await dry_run._check_comfy_reachability(report, steps=[step])
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
    _fake_procs_image = [_make_async_completed(_ok_stdout([str(f)])) for f in fakes]
    _fake_iter_image = iter(_fake_procs_image)
    with _patch_create_subprocess_exec(side_effect=lambda *a, **kw: next(_fake_iter_image)) as run_mock:
        worker.generate(
            spec={"comfy_workflow": "x", "comfy_params": {"seed": 42}},  # caller 显式 seed
            num_candidates=3,
            seed=100,  # base seed
        )
    # 提取每个 create_subprocess_exec 调用的 --params JSON 里的 seed 字段
    seeds_seen: list[int] = []
    for call in run_mock.call_args_list:
        # call 是 tuple-of-args(create_subprocess_exec 的位置参数)
        argv = list(call)
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
    _fake_procs_mesh = [_make_async_completed(_ok_mesh_stdout([str(f)])) for f in fakes]
    _fake_iter_mesh = iter(_fake_procs_mesh)
    with _patch_create_subprocess_exec(side_effect=lambda *a, **kw: next(_fake_iter_mesh)) as run_mock:
        worker.generate_mesh(
            spec={"comfy_workflow": "x", "comfy_params": {"seed": 42}},  # caller 显式 seed
            source_image_filename="forgeue_test.png",
            num_candidates=3,
            seed=100,  # base seed
        )
    seeds_seen: list[int] = []
    for call in run_mock.call_args_list:
        # call 是 tuple-of-args(create_subprocess_exec 的位置参数)
        argv = list(call)
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

    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(fake_png)]))) as run_mock:
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


# ---- G11-F2 follow-on: path containment for outputs.images / .glb / .audio --
# OpenSpec change `comfy-agent-cli-path-containment-hardening`(2026-05-04):
# fence 守门 ComfyUI subprocess 返回 `comfy_output_root` 之外的路径时,
# `_run_once*` raise WorkerUnsupportedResponse(NOT 静默读 bytes)。


def test_image_outputs_path_outside_comfy_output_root_raises_unsupported_response(tmp_path):
    """G11-F2 follow-on:image worker outputs.images path 在 comfy_output_root 之外
    (即 scripts_dir.parent 之外)→ raise WorkerUnsupportedResponse。"""
    worker = _make_worker(tmp_path)
    # 创建一个 BAD path 在 worker.comfy_output_root 之外(系统 temp 一级以上)
    bad_dir = Path(tmp_path).parent / "bad_outside_root"
    bad_dir.mkdir(exist_ok=True)
    bad_png = bad_dir / "leak.png"
    _make_png_file(bad_png)
    # confirm bad_png 真的 outside output_root
    assert not bad_png.resolve().is_relative_to(worker.comfy_output_root), (
        f"Test setup error: bad_png {bad_png.resolve()} is unexpectedly under "
        f"comfy_output_root {worker.comfy_output_root}"
    )
    with _patch_create_subprocess_exec(_make_async_completed(_ok_stdout([str(bad_png)]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="outside comfy_output_root"):
            worker.generate(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_mesh_outputs_path_outside_comfy_output_root_raises_unsupported_response(tmp_path):
    """G11-F2 follow-on:mesh worker outputs.glb path 在 comfy_output_root 之外
    → raise WorkerUnsupportedResponse。"""
    worker = _make_mesh_worker(tmp_path)
    bad_dir = Path(tmp_path).parent / "bad_outside_root_mesh"
    bad_dir.mkdir(exist_ok=True)
    bad_glb = bad_dir / "leak.glb"
    _make_glb_file(bad_glb)
    assert not bad_glb.resolve().is_relative_to(worker.comfy_output_root)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_mesh_stdout([str(bad_glb)]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="outside comfy_output_root"):
            worker.generate_mesh(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                source_image_filename="forgeue_test.png",
                num_candidates=1,
            )


# ===========================================================================
# Task 3: ComfyAgentWorker async-subprocess + comfy-submission 串行锁
# (executor-async-rewrite change, TBD-010)
#
# 这四个 fence 守门:
#   1. agenerate* 主面使用 asyncio.create_subprocess_exec(非 subprocess.run)
#   2. 同一 event loop 内并发 agenerate 被串行化(最多 1 个 subprocess 同时运行)
#   3. 跨 asyncio.run 边界不产生 cross-loop RuntimeError
#   4. sync generate* shim 仍可用(probe 脚本 / 旧调用路径兼容)
# ===========================================================================
import asyncio as _asyncio


def _make_fake_agent_worker(tmp_path: Path) -> "ComfyAgentWorker":
    """构造 image-mode ComfyAgentWorker,用于 async subprocess 测试。
    与 _make_worker 相同,单独命名以便 async 测试组引用清晰。"""
    return _make_worker(tmp_path)


async def test_comfy_agenerate_uses_create_subprocess_exec(monkeypatch, tmp_path):
    """agenerate 主面必须使用 asyncio.create_subprocess_exec(非 subprocess.run)。
    monkeypatch asyncio.create_subprocess_exec 返回 fake Process,
    验证 agenerate 调用路径经过 async 接口而非 subprocess.run。"""
    import asyncio
    import json as _json

    # --- 准备 fake output PNG 文件(在 worker 的 comfy_output_root 内)---
    # _make_fake_agent_worker 使用 scripts_dir = tmp_path/"scripts",
    # comfy_output_root = scripts_dir.parent = tmp_path,所以 fake_png 需要在 tmp_path 下。
    fake_png = tmp_path / "comfy_out.png"
    _make_png_file(fake_png)

    # --- 构造 worker ---
    worker = _make_fake_agent_worker(tmp_path)

    # --- 创建 fake asyncio.Process:communicate() 返回合法 JSON bytes ---
    fake_stdout_bytes = _json.dumps({
        "ok": True,
        "outputs": {"images": [str(fake_png)], "glb": [], "audio": [], "video": []},
    }).encode("utf-8")

    spawned = {"via": None}

    class FakeProcess:
        """模拟 asyncio.subprocess.Process。"""
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            return (fake_stdout_bytes, b"")

        async def wait(self):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    async def _fake_create(*a, **kw):
        spawned["via"] = "create_subprocess_exec"
        return FakeProcess()

    monkeypatch.setattr(_asyncio, "create_subprocess_exec", _fake_create)

    # --- 调用 agenerate ---
    result = await worker.agenerate(
        spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
        num_candidates=1,
        seed=1,
        timeout_s=30,
    )
    assert spawned["via"] == "create_subprocess_exec", (
        "agenerate 应通过 asyncio.create_subprocess_exec 启动子进程,"
        f"但实际 via={spawned['via']!r}"
    )
    assert isinstance(result, list)


async def test_comfy_submit_lock_serializes_concurrent_agenerate(tmp_path):
    """同一 event loop 内两个并发 agenerate 应被串行化:最大并发数为 1。
    通过 monkeypatch asyncio.create_subprocess_exec 注入计数器来验证。"""
    import asyncio
    import json as _json

    inflight = {"now": 0, "max": 0}

    fake_png = tmp_path / "out_lock.png"
    _make_png_file(fake_png)
    fake_stdout = _json.dumps({
        "ok": True,
        "outputs": {"images": [str(fake_png)], "glb": [], "audio": [], "video": []},
    }).encode("utf-8")

    class SlowFakeProcess:
        """模拟耗时 0.15s 的 subprocess,用于放大并发窗口。"""
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            # 模拟 subprocess 运行耗时,让并发窗口可观测
            await asyncio.sleep(0.15)
            return (fake_stdout, b"")

        async def wait(self):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    original_create = asyncio.create_subprocess_exec

    async def _counting_create(*a, **kw):
        inflight["now"] += 1
        inflight["max"] = max(inflight["max"], inflight["now"])
        proc = SlowFakeProcess()
        # 等 communicate 完成后才减计数(模拟 submit→poll 段的持有期)
        original_proc = proc

        class WrappedProc:
            def __init__(self):
                self.returncode = 0

            async def communicate(self):
                try:
                    return await original_proc.communicate()
                finally:
                    inflight["now"] -= 1

            async def wait(self):
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

        return WrappedProc()

    # 两个使用同一 scripts_dir / artifacts_dir 的 worker
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "comfyui_api").mkdir(exist_ok=True)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    w1 = ComfyAgentWorker(
        scripts_dir=scripts_dir, model_id="comfy/local",
        run_id="run_lock_1", project_id="proj_lock",
        artifacts_dir=artifacts_dir,
    )
    w2 = ComfyAgentWorker(
        scripts_dir=scripts_dir, model_id="comfy/local",
        run_id="run_lock_2", project_id="proj_lock",
        artifacts_dir=artifacts_dir,
    )

    # monkeypatch asyncio.create_subprocess_exec(模块级替换)
    import framework.providers.workers.comfy_worker as _cw_mod
    original = _asyncio.create_subprocess_exec
    _asyncio.create_subprocess_exec = _counting_create  # type: ignore[assignment]
    try:
        await _asyncio.gather(
            w1.agenerate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1, seed=1, timeout_s=30,
            ),
            w2.agenerate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1, seed=2, timeout_s=30,
            ),
        )
    finally:
        _asyncio.create_subprocess_exec = original  # type: ignore[assignment]

    assert inflight["max"] == 1, (
        f"串行锁应保证同一 loop 内最多 1 个 comfy subprocess 同时运行,"
        f"但观察到最大并发数 max={inflight['max']}"
    )


def test_comfy_submit_lock_safe_across_asyncio_run_loops(tmp_path):
    """跨 loop 安全:连续两个 asyncio.run 各自内部并发两个 agenerate,
    不产生 cross-loop RuntimeError(模块级单一 asyncio.Lock 会炸,per-loop 则 OK)。"""
    import asyncio
    import json as _json

    fake_png = tmp_path / "out_xloop.png"
    _make_png_file(fake_png)
    fake_stdout = _json.dumps({
        "ok": True,
        "outputs": {"images": [str(fake_png)], "glb": [], "audio": [], "video": []},
    }).encode("utf-8")

    inflight_results: list[int] = []

    async def _two_concurrent() -> int:
        """在一个新 event loop 内并发两个 agenerate,返回观察到的最大并发数。"""
        inflight = {"now": 0, "max": 0}

        class SlowFakeProcess:
            def __init__(self):
                self.returncode = 0

            async def communicate(self):
                await asyncio.sleep(0.1)
                return (fake_stdout, b"")

            async def wait(self):
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

        original_create = asyncio.create_subprocess_exec

        async def _counting_create(*a, **kw):
            inflight["now"] += 1
            inflight["max"] = max(inflight["max"], inflight["now"])
            proc = SlowFakeProcess()

            class WrappedProc:
                def __init__(self):
                    self.returncode = 0

                async def communicate(self):
                    try:
                        return await proc.communicate()
                    finally:
                        inflight["now"] -= 1

                async def wait(self):
                    return 0

                def terminate(self):
                    pass

                def kill(self):
                    pass

            return WrappedProc()

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        (scripts_dir / "comfyui_api").mkdir(exist_ok=True)
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        w1 = ComfyAgentWorker(
            scripts_dir=scripts_dir, model_id="comfy/local",
            run_id="run_xloop_1", project_id="proj_xloop",
            artifacts_dir=artifacts_dir,
        )
        w2 = ComfyAgentWorker(
            scripts_dir=scripts_dir, model_id="comfy/local",
            run_id="run_xloop_2", project_id="proj_xloop",
            artifacts_dir=artifacts_dir,
        )

        _asyncio.create_subprocess_exec = _counting_create  # type: ignore[assignment]
        try:
            await _asyncio.gather(
                w1.agenerate(
                    spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                    num_candidates=1, seed=10, timeout_s=30,
                ),
                w2.agenerate(
                    spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                    num_candidates=1, seed=20, timeout_s=30,
                ),
            )
        finally:
            _asyncio.create_subprocess_exec = original_create  # type: ignore[assignment]
        return inflight["max"]

    # loop A
    result_a = asyncio.run(_two_concurrent())
    assert result_a == 1, f"loop A: 最大并发应为 1,实际 {result_a}"
    # loop B — 跨 loop 边界:per-loop 锁不产生 cross-loop RuntimeError
    result_b = asyncio.run(_two_concurrent())
    assert result_b == 1, f"loop B: 最大并发应为 1,实际 {result_b}"


def test_comfy_generate_sync_shim_still_works(tmp_path):
    """sync generate() shim 在 agenerate 主面引入后仍可正常使用
    (probe 脚本 / 旧调用路径兼容)。
    generate() 委托 asyncio.run(agenerate(...)),agenerate 内部使用 asyncio.create_subprocess_exec。
    monkeypatch asyncio.create_subprocess_exec 返回 fake Process 验证 sync shim 正常工作。"""
    import asyncio
    import json as _json

    # fake output PNG 放在 comfy_output_root 内(= scripts_dir.parent = tmp_path)
    fake_png = tmp_path / "out_shim.png"
    _make_png_file(fake_png)

    worker = _make_fake_agent_worker(tmp_path)

    fake_stdout_bytes = _json.dumps({
        "ok": True,
        "outputs": {"images": [str(fake_png)], "glb": [], "audio": [], "video": []},
    }).encode("utf-8")

    class FakeProcess:
        """模拟 asyncio.subprocess.Process。"""
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            return (fake_stdout_bytes, b"")

        async def wait(self):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    original_create = asyncio.create_subprocess_exec

    async def _wrap_coro(val):
        return val

    asyncio.create_subprocess_exec = lambda *a, **kw: _wrap_coro(FakeProcess())  # type: ignore[assignment]

    try:
        result = worker.generate(
            spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
            num_candidates=1,
            seed=1,
            timeout_s=30,
        )
    finally:
        asyncio.create_subprocess_exec = original_create  # type: ignore[assignment]

    assert isinstance(result, list), (
        f"generate() sync shim 应返回 list[ImageCandidate],实际返回 {type(result)}"
    )


# ---------------------------------------------------------------------------
# Task 4: cancel 时 server-side /interrupt 单测
# ---------------------------------------------------------------------------


def _make_slow_fake_worker(tmp_path: Path) -> "ComfyAgentWorker":
    """构造 image-mode ComfyAgentWorker,用于 cancel 路径测试。
    与 _make_fake_agent_worker 相同但独立命名,便于 Task 4 测试组引用。"""
    return _make_worker(tmp_path)


@pytest.mark.asyncio
async def test_comfy_cancel_aborts_server_side_prompt(monkeypatch, tmp_path):
    """Task 4 RED fence:cancel 时 _abort_comfy_prompt 必须被调用一次,
    且 CLI 子进程(proc)被 terminate 后 returncode 不为 None。

    monkeypatch _abort_comfy_prompt 为 spy coroutine,
    agenerate 的 communicate 永久挂起以模拟 GPU job 运行中。
    cancel agenerate task → finally 块需先调 _abort_comfy_prompt 再 terminate。
    """
    import asyncio as _aio

    # --- spy:记录 _abort_comfy_prompt 被调用次数 ---
    aborted = {"n": 0}

    async def _spy_abort(self):
        aborted["n"] += 1

    monkeypatch.setattr(ComfyAgentWorker, "_abort_comfy_prompt", _spy_abort)

    # --- 慢 fake process:communicate 永久挂起,terminate 后设置 returncode ---
    class _SlowProcess:
        """模拟正在运行 GPU job 的 subprocess:communicate 永久挂起。
        terminate 被调用时将 returncode 设为 -15(SIGTERM)。"""

        def __init__(self):
            self.returncode = None

        async def communicate(self):
            # 永久挂起,模拟 ComfyUI 正在生成
            await _aio.sleep(9999)
            return (b"", b"")

        def terminate(self):
            # terminate 后 returncode 设为 -15
            self.returncode = -15

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    # 保存 proc 引用供 cancel 后检查
    last_proc_holder = {"proc": None}

    async def _slow_create(*a, **kw):
        p = _SlowProcess()
        last_proc_holder["proc"] = p
        return p

    import asyncio as asyncio_mod
    original_create = asyncio_mod.create_subprocess_exec
    asyncio_mod.create_subprocess_exec = _slow_create  # type: ignore[assignment]

    worker = _make_slow_fake_worker(tmp_path)

    try:
        # 启动 agenerate task(image-mode;timeout_s=600 避免内部超时先触发)
        task = _aio.create_task(
            worker.agenerate(
                spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
                num_candidates=1,
                seed=1,
                timeout_s=600,
            )
        )
        # 等待 communicate 进入挂起状态
        await _aio.sleep(0.2)
        # cancel task
        task.cancel()
        with pytest.raises(_aio.CancelledError):
            await task
        # 给 finally 块一点时间完成
        await _aio.sleep(0.1)
        # 断言:_abort_comfy_prompt 被调用恰好 1 次
        assert aborted["n"] == 1, (
            f"_abort_comfy_prompt 应被调用 1 次,实际 {aborted['n']} 次"
        )
        # 断言:proc 被 terminate 后 returncode 不为 None
        proc = last_proc_holder["proc"]
        assert proc is not None, "proc 应在 agenerate 内被创建并由 _last_proc 保存"
        assert proc.returncode is not None, (
            f"proc.returncode 应在 terminate 后非 None,实际 {proc.returncode!r}"
        )
    finally:
        asyncio_mod.create_subprocess_exec = original_create  # type: ignore[assignment]
