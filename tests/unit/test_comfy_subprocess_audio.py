"""ComfyAgentWorker audio capability fences (OpenSpec change comfy-agent-cli-audio-adoption Phase 2).

Per spec/probe-and-validation/spec.md "ComfyUI audio capability dispatch has dedicated
regression fences" + per F-Plan-3 / F-Plan-4 / F-Plan-R6-A / F-Plan-R7-A round-X 修订。

Separate file from test_comfy_subprocess.py to keep audio fences modular(per Phase 1
mesh fences in test_comfy_subprocess.py — mesh is grouped in same file because mesh
helpers `_make_mesh_worker` / `_ok_mesh_stdout` / `_make_glb_file` are in same module;
audio uses similar but distinct helpers, isolated here for readability)。

Fence categories(approximately 16 fences):
- Capability dispatch(2):capability_inferred_audio + unknown id supported list
- 三段表 audio row(5):missing/empty outputs.audio + reject images/glb/video
- generate_audio path:format detection + magic bytes(5):flac/mp3-id3/mp3-mpeg/wav + ogg + mismatch
- Path trust-boundary(2):missing path + symlink
- Per-candidate loop(1):num=3 → 3 subprocess
- Metadata provenance(2):5 keys + snapshot independence
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from framework.providers.workers.audio_worker import AudioCandidate
from framework.providers.workers.comfy_worker import (
    ComfyAgentWorker,
    WorkerUnsupportedResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio_worker(tmp_path: Path) -> ComfyAgentWorker:
    """Audio-mode worker fixture (model_id='comfy/local-audio' → _capability='audio').

    Path containment heuristic uses `scripts_dir.parent` = `tmp_path`,
    so fake outputs in tmp_path pass the containment check
    (`comfy-agent-cli-path-containment-hardening` 2026-05-04).
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "comfyui_api").mkdir(exist_ok=True)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    return ComfyAgentWorker(
        scripts_dir=scripts_dir,
        model_id="comfy/local-audio",
        run_id="run_test_audio",
        project_id="proj_test_audio",
        artifacts_dir=artifacts_dir,
    )



class _AsyncFakeProcess:
    """模拟 asyncio.subprocess.Process,供 patch asyncio.create_subprocess_exec 使用。
    TBD-010 Task 3 async-subprocess 改造后,所有 comfy worker 路径经 asyncio.create_subprocess_exec。
    """

    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
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
    """_make_completed 的 async 版本,返回 _AsyncFakeProcess 实例。"""
    return _AsyncFakeProcess(stdout=stdout, returncode=returncode, stderr=stderr)


def _detach_ok_stdout(prompt_id: str = "fake-prompt-1") -> str:
    """detach submit 段的成功响应(上游 AGENT_API.md §1.8 实测 shape)。"""
    return json.dumps({
        "ok": True, "prompt_id": prompt_id, "detached": True, "timeout_hint_s": 300,
    })


def _patch_create_subprocess_exec(fake_proc: "_AsyncFakeProcess | None" = None, *, side_effect=None):
    """返回 asyncio.create_subprocess_exec 的 patch context manager。

    用法:
        with _patch_create_subprocess_exec(_make_async_completed(stdout)) as mock:
            worker.generate_audio(...)
            cmd = list(mock.call_args)  # create_subprocess_exec 的位置参数 tuple

    side_effect: callable(*a, **kw) → _AsyncFakeProcess 或 iter 返回 _AsyncFakeProcess。
    """
    import asyncio as _aio

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
            # detach-wait 协议 dispatch:submit 段返回 canned ok+prompt_id,
            # cancel 段返回 canned ok;fake_proc 语义 = wait 段响应
            # (既有测试的失败注入 stdout 因此落在 wait 段,分类共享
            # _raise_comfy_failure,语义不变)
            if "--detach" in a:
                return _AsyncFakeProcess(_detach_ok_stdout())
            if "cancel" in a:
                return _AsyncFakeProcess(json.dumps({"ok": True, "interrupted": True}))
            return fake_proc

    class _Ctx:
        """create_subprocess_exec patch context manager。call_args / call_count / call_args_list 支持。"""
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



def _ok_audio_stdout(audio_paths: list[str], extra_outputs: dict | None = None) -> str:
    outputs = {"audio": audio_paths, "images": [], "glb": [], "video": []}
    if extra_outputs:
        outputs.update(extra_outputs)
    return json.dumps({"ok": True, "outputs": outputs})


def _make_flac_file(path: Path, *, payload: bytes = b"\x00" * 32) -> None:
    """Minimal valid FLAC file: magic `fLaC` + STREAMINFO header + body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fLaC" + b"\x80\x00\x00\x22" + b"\x00" * 34 + payload)


def _make_mp3_file(path: Path, *, with_id3: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if with_id3:
        path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    else:
        path.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)


def _make_wav_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"\x00" * 100)


# ---- Capability dispatch ------------------------------------------------------


def test_capability_inferred_audio_for_comfy_local_audio(tmp_path):
    """F1 round-1: model_id='comfy/local-audio' → _capability='audio'."""
    worker = _make_audio_worker(tmp_path)
    assert worker._capability == "audio"
    assert worker.model_id == "comfy/local-audio"


def test_unknown_model_id_raises_at_init_lists_audio_in_supported(tmp_path):
    """F-Plan-R3-A round-3 + F-Plan-R4-C round-4: 错误消息 supported list 含 audio。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    with pytest.raises(WorkerUnsupportedResponse) as exc_info:
        ComfyAgentWorker(
            scripts_dir=scripts_dir,
            model_id="comfy/local-bogus",
            run_id="x",
            project_id="x",
            artifacts_dir=artifacts_dir,
        )
    msg = str(exc_info.value)
    assert "comfy/local-audio" in msg, f"supported list should include comfy/local-audio; got: {msg}"
    assert "comfy/local-mesh" in msg
    assert "comfy/local" in msg


# ---- 三段表 audio row(D2)----------------------------------------------------


def test_audio_mode_raises_on_missing_outputs_audio(tmp_path):
    """audio capability REQUIRED `outputs.audio` non-empty;missing key → raise。"""
    worker = _make_audio_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
json.dumps({
            "ok": True,
            "outputs": {"images": [], "glb": [], "video": []},
        })
    )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"audio"):
            worker.generate_audio(
                spec={"comfy_workflow": "Audio_Workflows/test", "comfy_params": {"text": "x"}},
                num_candidates=1,
            )


def test_audio_mode_raises_on_empty_outputs_audio(tmp_path):
    """audio capability REQUIRED `outputs.audio` non-empty;empty list → raise。"""
    worker = _make_audio_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"audio"):
            worker.generate_audio(
                spec={"comfy_workflow": "Audio_Workflows/test", "comfy_params": {"text": "x"}},
                num_candidates=1,
            )


def test_audio_mode_rejects_outputs_images(tmp_path):
    """audio capability REJECT outputs.images non-empty(无 auxiliary tolerance)。"""
    worker = _make_audio_worker(tmp_path)
    fake_audio = tmp_path / "audio.flac"
    _make_flac_file(fake_audio)
    with _patch_create_subprocess_exec(_make_async_completed(
_ok_audio_stdout(
            [str(fake_audio)], extra_outputs={"images": ["spectrogram.png"]},
        )
    )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"images"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_audio_mode_rejects_outputs_glb(tmp_path):
    """audio capability REJECT outputs.glb non-empty。"""
    worker = _make_audio_worker(tmp_path)
    fake_audio = tmp_path / "audio.flac"
    _make_flac_file(fake_audio)
    with _patch_create_subprocess_exec(_make_async_completed(
_ok_audio_stdout(
            [str(fake_audio)], extra_outputs={"glb": ["unexpected.glb"]},
        )
    )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"glb"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_audio_mode_rejects_outputs_video(tmp_path):
    """audio capability REJECT outputs.video non-empty。"""
    worker = _make_audio_worker(tmp_path)
    fake_audio = tmp_path / "audio.flac"
    _make_flac_file(fake_audio)
    with _patch_create_subprocess_exec(_make_async_completed(
_ok_audio_stdout(
            [str(fake_audio)], extra_outputs={"video": ["unexpected.mp4"]},
        )
    )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"video"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---- generate_audio path:format detection + magic bytes(D10 + F5)------------


def test_generate_audio_flac_extension_detection_records_source_path_without_full_read(tmp_path):
    """flac 扩展名 + `fLaC` magic 接受 → AudioCandidate(format="flac", source_path=...)。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.flac"
    _make_flac_file(fake, payload=b"hello")
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock, \
            patch.object(Path, "read_bytes", side_effect=AssertionError("Comfy audio worker must not full-read output")):
        cands = worker.generate_audio(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(cands) == 1
    assert isinstance(cands[0], AudioCandidate)
    assert cands[0].format == "flac"
    assert cands[0].source_path == str(fake)
    assert cands[0].data[:4] == b"fLaC"


def test_generate_audio_mp3_id3_magic_match_accepts(tmp_path):
    """mp3 扩展名 + `ID3` tag magic 接受。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.mp3"
    _make_mp3_file(fake, with_id3=True)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        cands = worker.generate_audio(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(cands) == 1
    assert cands[0].format == "mp3"


def test_generate_audio_mp3_mpeg_frame_sync_magic_match_accepts(tmp_path):
    """mp3 扩展名 + MPEG frame sync 0xFF 0xFB magic 接受。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.mp3"
    _make_mp3_file(fake, with_id3=False)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        cands = worker.generate_audio(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(cands) == 1
    assert cands[0].format == "mp3"


def test_generate_audio_wav_riff_wave_magic_match_accepts(tmp_path):
    """wav 扩展名 + `RIFF`+`WAVE` magic 接受。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.wav"
    _make_wav_file(fake)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        cands = worker.generate_audio(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(cands) == 1
    assert cands[0].format == "wav"


def test_generate_audio_unsupported_extension_ogg_raises_unsupported_response(tmp_path):
    """D10:扩展名 whitelist {flac, mp3, wav};.ogg 不在 → raise WorkerUnsupportedResponse。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.ogg"
    fake.write_bytes(b"OggS\x00" + b"\x00" * 100)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"ogg|unsupported audio format"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_audio_flac_magic_bytes_mismatch_raises_unsupported_response(tmp_path):
    """F5 round-1 mandatory:.flac 扩展名 + 错 magic bytes → raise。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.flac"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_bytes(b"<html>not flac</html>" + b"\x00" * 50)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"format mismatch|magic"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---- Path trust-boundary(F-Plan-4 round-2)---------------------------------


def test_generate_audio_missing_path_raises_unsupported_response(tmp_path):
    """F-Plan-4 round-2:outputs.audio 路径不存在 → raise。"""
    worker = _make_audio_worker(tmp_path)
    with _patch_create_subprocess_exec(_make_async_completed(
_ok_audio_stdout(
            [str(tmp_path / "does_not_exist.flac")],
        )
    )) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"does not exist"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_audio_symlink_path_raises_unsupported_response(tmp_path):
    """F-Plan-4 round-2:outputs.audio 路径是 symlink → raise(防 buggy CLI)。"""
    worker = _make_audio_worker(tmp_path)
    real = tmp_path / "real.flac"
    _make_flac_file(real)
    sym = tmp_path / "link.flac"
    try:
        sym.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not supported on this platform")
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(sym)]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match=r"symlink"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---- Per-candidate loop in worker(F-Plan-3 + F-Plan-R5-A round-5)----------


def test_generate_audio_runs_subprocess_num_candidates_times_when_num_gt_one(tmp_path):
    """F-Plan-3 round-2 + F-Plan-R5-A round-5:per-candidate loop in worker;
    num_candidates=3 → 3 次 subprocess.run + 3 个 candidate(seed 递增)。"""
    worker = _make_audio_worker(tmp_path)
    fakes = [tmp_path / f"out_{i}.flac" for i in range(3)]
    for f in fakes:
        _make_flac_file(f, payload=f.name.encode())
    _fake_procs_audio = [_make_async_completed(_ok_audio_stdout([str(f)])) for f in fakes]
    _fake_iter_audio = iter(_fake_procs_audio)
    def _audio_num_factory(*a, **kw):
        # R4: detach-wait 协议 dispatch
        if "--detach" in a:
            return _make_async_completed(_detach_ok_stdout())
        if "cancel" in a:
            return _make_async_completed('{"ok":true}')
        return next(_fake_iter_audio)
    with _patch_create_subprocess_exec(side_effect=_audio_num_factory) as run_mock:
        cands = worker.generate_audio(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=3,
            seed=100,
        )
    # R2: 每个 candidate submit+wait = 2 次,3 candidates = 6 次
    assert run_mock.call_count == 6, f"Expected 6 subprocess invocations (3x submit+wait), got {run_mock.call_count}"
    assert len(cands) == 3


def test_generate_audio_per_candidate_seed_overrides_comfy_params_seed(tmp_path):
    """G11-F3 round-8 codex finding fix:`comfy_params` 已含 `seed: 42` 时,
    per-candidate seed 偏移仍生效(每个 candidate 拿 100 / 101 / 102 不是同 42)。
    fence 守门 `setdefault → 直接覆盖` 修复(防 num_candidates>1 时 candidate 重复)。"""
    worker = _make_audio_worker(tmp_path)
    fakes = [tmp_path / f"out_{i}.flac" for i in range(3)]
    for f in fakes:
        _make_flac_file(f, payload=f.name.encode())
    _fake_procs_seed = [_make_async_completed(_ok_audio_stdout([str(f)])) for f in fakes]
    _fake_iter_seed = iter(_fake_procs_seed)
    def _audio_seed_factory(*a, **kw):
        # R4: detach-wait 协议 dispatch
        if "--detach" in a:
            return _make_async_completed(_detach_ok_stdout())
        if "cancel" in a:
            return _make_async_completed('{"ok":true}')
        return next(_fake_iter_seed)
    with _patch_create_subprocess_exec(side_effect=_audio_seed_factory) as run_mock:
        worker.generate_audio(
            spec={"comfy_workflow": "x", "comfy_params": {"seed": 42}},  # caller 显式 seed
            num_candidates=3,
            seed=100,  # base seed
        )
    # R2: 从 submit cmd(含 --params)里提取 seed
    seeds_seen: list[int] = []
    for call in run_mock.call_args_list:
        argv = list(call)
        if "--params" not in argv:
            continue  # wait cmd 没有 --params,跳过
        idx = argv.index("--params")
        params = json.loads(argv[idx + 1])
        seeds_seen.append(params["seed"])
    assert seeds_seen == [100, 101, 102], (
        f"Expected per-candidate seed override 100/101/102, got {seeds_seen}; "
        f"setdefault bug would return [42, 42, 42]"
    )


# ---- AudioCandidate.metadata(F-Plan-R7-A round-7 single-source + provenance)


def test_generate_audio_metadata_records_comfy_provenance(tmp_path):
    """F-Plan-R7-A round-7:metadata 仅 5 个 comfy_* provenance keys。
    duration_seconds / sample_rate 顶层 None always(F4 round-1)。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.flac"
    _make_flac_file(fake)
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        cands = worker.generate_audio(
            spec={
                "comfy_workflow": "Audio_Workflows/audio_stable_audio_example",
                "comfy_params": {"text": "uplifting", "seed": 42},
            },
            num_candidates=1,
            seed=42,
        )
    assert len(cands) == 1
    cand = cands[0]
    assert cand.metadata["comfy_manifest"] == "Audio_Workflows/audio_stable_audio_example"
    assert cand.metadata["comfy_capability"] == "audio"
    assert cand.metadata["comfy_original_filename"] == "out.flac"
    assert isinstance(cand.metadata["comfy_params_snapshot"], dict)
    assert isinstance(cand.metadata["comfy_subprocess_run_metadata"], dict)
    forbidden = {"duration_seconds", "sample_rate", "format", "format_detected"}
    leaked = forbidden & cand.metadata.keys()
    assert not leaked, f"AudioCandidate.metadata leaked top-level audio fields: {leaked}"
    assert cand.duration_seconds is None
    assert cand.sample_rate is None


def test_generate_audio_metadata_snapshot_is_independent_copy(tmp_path):
    """metadata['comfy_params_snapshot'] is a `dict(...)` copy:caller mutate
    `spec['comfy_params']` 之后 snapshot 不变。"""
    worker = _make_audio_worker(tmp_path)
    fake = tmp_path / "out.flac"
    _make_flac_file(fake)
    spec = {
        "comfy_workflow": "x",
        "comfy_params": {"text": "before", "seed": 1},
    }
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(fake)]))) as run_mock:
        cands = worker.generate_audio(spec=spec, num_candidates=1, seed=1)
    spec["comfy_params"]["text"] = "AFTER"
    spec["comfy_params"]["new_key"] = "leaked"
    snapshot = cands[0].metadata["comfy_params_snapshot"]
    assert snapshot["text"] == "before", "snapshot must isolate from caller mutation"
    assert "new_key" not in snapshot


# ---- DryRunPass(commit 6:gate set 扩 audio)----------------------------------


@pytest.mark.asyncio
async def test_dry_run_probe_runs_when_comfy_local_audio_in_routes(tmp_path, monkeypatch):
    """audio 的 Comfy subprocess provider metadata route 会触发 aprobe。
    Step 6: async _check_comfy_reachability + aprobe 转换。"""
    from unittest.mock import MagicMock
    from framework.core.policies import PreparedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(scripts_dir))

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        PreparedRoute(
            model="comfy/local-audio",
            kind="audio",
            provider_name="comfy_api",
            provider_kind="subprocess",
            provider_config={
                "adapter": "comfy_agent_cli",
                "scripts_dir": str(scripts_dir),
                "python_exe": None,
                "default_lifecycle": "none",
                "input_dir": None,
                "output_root": str(tmp_path),
            },
        ),
    ]

    with _patch_create_subprocess_exec(_make_async_completed("ok", returncode=0)) as run_mock:
        await dry_run._check_comfy_reachability(report, steps=[step])
        # audio route 通过 provider metadata 命中 ComfyAgentWorker aprobe。
        assert run_mock.call_count == 1
        call_args = run_mock.call_args
        assert "comfyui_api" in call_args


# ---- G11-F2 follow-on: path containment for outputs.audio --------------------

def test_audio_outputs_path_outside_comfy_output_root_raises_unsupported_response(tmp_path):
    """G11-F2 follow-on:audio worker outputs.audio path 在 comfy_output_root 之外
    → raise WorkerUnsupportedResponse(`comfy-agent-cli-path-containment-hardening`
    2026-05-04 兑现 R7-C disputed-permanent-drift 之 follow-on commitment)。"""
    worker = _make_audio_worker(tmp_path)
    bad_dir = Path(tmp_path).parent / "bad_outside_root_audio"
    bad_dir.mkdir(exist_ok=True)
    bad_flac = bad_dir / "leak.flac"
    _make_flac_file(bad_flac)
    assert not bad_flac.resolve().is_relative_to(worker.comfy_output_root), (
        f"Test setup error: bad_flac {bad_flac.resolve()} unexpectedly under "
        f"comfy_output_root {worker.comfy_output_root}"
    )
    with _patch_create_subprocess_exec(_make_async_completed(_ok_audio_stdout([str(bad_flac)]))) as run_mock:
        with pytest.raises(WorkerUnsupportedResponse, match="outside comfy_output_root"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---------------------------------------------------------------------------
# detach-wait change Task 3: audio prompt_id metadata fence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audio_prompt_id_recorded_in_candidate_metadata(tmp_path):
    """audio metadata fence:comfy_prompt_id 透传(audio capability,detach-wait change Task 3)。"""
    fake = tmp_path / "out.flac"
    _make_flac_file(fake)
    worker = _make_audio_worker(tmp_path)
    with _patch_create_subprocess_exec(
        _make_async_completed(_ok_audio_stdout([str(fake)]))
    ):
        cands = await worker.agenerate_audio(
            spec={"comfy_workflow": "Audio_Workflows/x", "comfy_params": {}},
            num_candidates=1,
        )
    assert cands[0].metadata["comfy_prompt_id"] == "fake-prompt-1"
