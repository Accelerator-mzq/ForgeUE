"""ComfyAgentWorker video capability fences (OpenSpec change comfy-agent-cli-video-adoption Phase 3).

Per spec/probe-and-validation/spec.md "ComfyUI video capability dispatch has dedicated
regression fences" + per round-2 F2 / F4 + round-3 PF1 / PF2 / PF3 / PF4 修订。

Separate file from test_comfy_subprocess.py (沿 audio Phase 2 test_comfy_subprocess_audio.py
模式),保持 video fence 模块化。

Fence categories(approximately 17 fences):
- Capability dispatch(2):capability_inferred_video + unknown id supported list(全 4 capability)
- 三段表 video row(5):missing/empty outputs.video + reject images/glb/audio + no auxiliary log
- generate_video path:format detection + extension whitelist(2):mp4 OK + mov/webm reject (PF3)
- BMFF strict 5-tuple(round-2 F4 + round-3 PF2,7 fences):too_short / ftyp_mismatch /
  box_size_too_small / box_size_exceeds_len / box_size_largesize_1_rejected /
  major_brand_zero / major_brand_spaces + 2 happy paths (isom + mp42)
- Path trust-boundary(2):missing path + symlink
- Per-candidate loop(1):num=3 → 3 subprocess + per-candidate seed override(沿 audio G11-F3)
- Metadata provenance(2):5 keys + snapshot independence
- env independence(1):does NOT read FORGEUE_COMFY_INPUT_DIR(text-to-video 沿 audio D7)
- Cross-capability regression(3):image/mesh/audio modes still reject outputs.video after Phase 3
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from framework.providers.workers.comfy_worker import (
    ComfyAgentWorker,
    WorkerUnsupportedResponse,
)
from framework.providers.workers.video_worker import VideoCandidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_video_worker(tmp_path: Path) -> ComfyAgentWorker:
    """Video-mode worker fixture (model_id='comfy/local-video' → _capability='video').

    Path containment heuristic uses `scripts_dir.parent` = `tmp_path`,
    所以 fake outputs in tmp_path 通过 containment 校验
    (沿 audio path-containment-hardening 模式)。
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "comfyui_api").mkdir(exist_ok=True)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    return ComfyAgentWorker(
        scripts_dir=scripts_dir,
        model_id="comfy/local-video",
        run_id="run_test_video",
        project_id="proj_test_video",
        artifacts_dir=artifacts_dir,
    )


def _make_completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["mocked"], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def _ok_video_stdout(video_paths: list[str], extra_outputs: dict | None = None) -> str:
    """Standard runner.py extract_outputs output dict shape (round-3 PF1
    D-Runner-Extension:user-authored runner.py 加 video collection block 后,
    返回 dict 含 video key)。
    """
    outputs = {"images": [], "audio": [], "glb": [], "video": video_paths}
    if extra_outputs:
        outputs.update(extra_outputs)
    return json.dumps({"ok": True, "outputs": outputs})


def _make_minimal_mp4(path: Path, *, major_brand: bytes = b"isom") -> None:
    """Minimal valid BMFF mp4 file passing round-2 F4 + round-3 PF2 strict 5-tuple.

    Layout (32 bytes):
    - offset 0-3:  box_size = 32 (0x00000020)
    - offset 4-7:  type = "ftyp"
    - offset 8-11: major_brand
    - offset 12-15: minor_version = 0x00000200
    - offset 16-31: compatible_brands = "isom" + "iso2" + "mp41" + "mp42"
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        b"\x00\x00\x00\x20"  # box_size = 32
        + b"ftyp"             # type
        + major_brand         # major_brand
        + b"\x00\x00\x02\x00" # minor_version
        + b"isom" + b"iso2" + b"mp41" + b"mp42"  # compatible_brands
    )
    assert len(data) == 32
    path.write_bytes(data)


# ---------------------------------------------------------------------------
# Capability dispatch(2 fences)
# ---------------------------------------------------------------------------


def test_capability_inferred_video_for_comfy_local_video(tmp_path):
    """D6: model_id='comfy/local-video' → _capability='video'."""
    worker = _make_video_worker(tmp_path)
    assert worker._capability == "video"
    assert worker.model_id == "comfy/local-video"


def test_unknown_model_id_raises_at_init_lists_video_in_supported(tmp_path):
    """Round-3 D6 修订:错误消息 supported list 含全 4 capability(image / mesh /
    audio / video — TBD-009 全 phase closed)。
    """
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
    assert "comfy/local-video" in msg, f"supported list 应含 comfy/local-video; got: {msg}"
    assert "comfy/local-audio" in msg
    assert "comfy/local-mesh" in msg
    assert "comfy/local" in msg


# ---------------------------------------------------------------------------
# 三段表 video row(D6;5 fences)
# ---------------------------------------------------------------------------


def test_video_mode_raises_on_missing_outputs_video(tmp_path):
    """video capability REQUIRED `outputs.video` non-empty;missing key → raise。"""
    worker = _make_video_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [], "audio": [], "glb": []},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match=r"video"):
            worker.generate_video(
                spec={"comfy_workflow": "Vedio/test", "comfy_params": {"positive_prompt": "x"}},
                num_candidates=1,
            )


def test_video_mode_raises_on_empty_outputs_video(tmp_path):
    """video capability REQUIRED `outputs.video` non-empty;empty list → raise。"""
    worker = _make_video_worker(tmp_path)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"video"):
            worker.generate_video(
                spec={"comfy_workflow": "Vedio/test", "comfy_params": {"positive_prompt": "x"}},
                num_candidates=1,
            )


def test_video_mode_rejects_outputs_images(tmp_path):
    """video capability REJECT outputs.images non-empty(无 auxiliary tolerance,沿 audio D6)。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout(
            [str(fake_video)], extra_outputs={"images": ["thumbnail.png"]},
        ))
        with pytest.raises(WorkerUnsupportedResponse, match=r"images"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_video_mode_rejects_outputs_glb(tmp_path):
    """video capability REJECT outputs.glb non-empty。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout(
            [str(fake_video)], extra_outputs={"glb": ["unexpected.glb"]},
        ))
        with pytest.raises(WorkerUnsupportedResponse, match=r"glb"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_video_mode_rejects_outputs_audio(tmp_path):
    """video capability REJECT outputs.audio non-empty。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout(
            [str(fake_video)], extra_outputs={"audio": ["unexpected.flac"]},
        ))
        with pytest.raises(WorkerUnsupportedResponse, match=r"audio"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---------------------------------------------------------------------------
# Cross-capability regression(3 fences;sweep image / mesh / audio modes 仍拒绝 outputs.video)
# ---------------------------------------------------------------------------


def test_image_mode_still_rejects_outputs_video_after_phase3(tmp_path):
    """Regression:Phase 3 加 video capability 后,image-mode 仍 reject outputs.video non-empty。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    worker = ComfyAgentWorker(
        scripts_dir=scripts_dir, model_id="comfy/local",
        run_id="x", project_id="x", artifacts_dir=artifacts_dir,
    )
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": ["preview.png"], "audio": [], "glb": [], "video": [str(fake_video)]},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match=r"video"):
            worker.generate(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_mesh_mode_still_rejects_outputs_video_after_phase3(tmp_path):
    """Regression:mesh-mode 仍 reject outputs.video non-empty。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    worker = ComfyAgentWorker(
        scripts_dir=scripts_dir, model_id="comfy/local-mesh",
        run_id="x", project_id="x", artifacts_dir=artifacts_dir,
    )
    fake_glb = tmp_path / "x.glb"
    fake_glb.write_bytes(b"glTF" + b"\x00" * 16)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    fake_image = tmp_path / "image.png"
    fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [str(fake_image)], "audio": [], "glb": [str(fake_glb)], "video": [str(fake_video)]},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match=r"video"):
            worker.generate_mesh(
                spec={"comfy_workflow": "x", "comfy_params": {}, "comfy_image_param_key": "input_image"},
                source_image_filename="forgeue_test.png",
                num_candidates=1,
            )


def test_audio_mode_still_rejects_outputs_video_after_phase3(tmp_path):
    """Regression:audio-mode 仍 reject outputs.video non-empty。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "comfyui_api").mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    worker = ComfyAgentWorker(
        scripts_dir=scripts_dir, model_id="comfy/local-audio",
        run_id="x", project_id="x", artifacts_dir=artifacts_dir,
    )
    fake_audio = tmp_path / "audio.flac"
    fake_audio.write_bytes(b"fLaC" + b"\x80\x00\x00\x22" + b"\x00" * 100)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(json.dumps({
            "ok": True,
            "outputs": {"images": [], "audio": [str(fake_audio)], "glb": [], "video": [str(fake_video)]},
        }))
        with pytest.raises(WorkerUnsupportedResponse, match=r"video"):
            worker.generate_audio(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---------------------------------------------------------------------------
# Format whitelist mp4-only(round-2 F2 + round-3 PF3 sweep;2 fences)
# ---------------------------------------------------------------------------


def test_generate_video_mp4_extension_detection_reads_bytes(tmp_path):
    """mp4 extension OK,通过 BMFF strict 5-tuple → VideoCandidate。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "wan_test.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={"comfy_workflow": "Vedio/test", "comfy_params": {"positive_prompt": "x"}},
            num_candidates=1,
        )
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.format == "mp4"
    assert cand.data == fake_video.read_bytes()


def test_generate_video_unsupported_extension_mov_raises_unsupported_response(tmp_path):
    """mov / 其它扩展名 reject(round-2 F2 mp4-only)。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "clip.mov"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"mov"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_webm_extension_rejected_pending_follow_on(tmp_path):
    """round-2 F2 + round-3 PF3 sweep:webm reject + 错误消息提及 follow-on。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "clip.webm"
    _make_minimal_mp4(fake_video)  # webm 扩展名但用 BMFF bytes — 实际 webm payload 也无所谓,扩展名层先 reject
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"webm.*follow-on") as exc_info:
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )
        assert "comfy-video-webm-adoption" in str(exc_info.value)


# ---------------------------------------------------------------------------
# BMFF strict 5-tuple(round-2 F4 + round-3 PF2;9 fences:7 reject + 2 accept)
# ---------------------------------------------------------------------------


def test_generate_video_bmff_too_short_raises_unsupported_response(tmp_path):
    """File < 16 bytes → BMFF too short reject(round-2 F4)。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "tiny.mp4"
    fake_video.parent.mkdir(parents=True, exist_ok=True)
    fake_video.write_bytes(b"\x00" * 8 + b"ftyp")  # 12 bytes,过短
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"too short"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_bmff_ftyp_mismatch_raises_unsupported_response(tmp_path):
    """offset 4-8 != b"ftyp" → BMFF header mismatch reject。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "noftyp.mp4"
    fake_video.parent.mkdir(parents=True, exist_ok=True)
    fake_video.write_bytes(b"\x00" * 32)  # 32 bytes,但 offset 4 不是 ftyp
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"BMFF header mismatch"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_bmff_box_size_too_small_raises(tmp_path):
    """box_size < 8(e.g. 0)→ out of range reject。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "smallbox.mp4"
    fake_video.parent.mkdir(parents=True, exist_ok=True)
    # box_size = 0,ftyp at offset 4,major_brand isom
    fake_video.write_bytes(b"\x00\x00\x00\x00" + b"ftyp" + b"isom" + b"\x00" * 20)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"out of range"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_bmff_box_size_exceeds_len_raises(tmp_path):
    """box_size > len(data) → out of range reject。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "bigbox.mp4"
    fake_video.parent.mkdir(parents=True, exist_ok=True)
    # box_size = 999999,文件只有 32 bytes
    fake_video.write_bytes(b"\x00\x0F\x42\x3F" + b"ftyp" + b"isom" + b"\x00" * 20)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"out of range"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_bmff_box_size_largesize_1_rejected_pending_follow_on(tmp_path):
    """round-3 PF2:box_size == 1 (64-bit largesize) 本 change scope reject +
    错误消息提及 follow-on `video-bmff-largesize-support`。
    """
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "largesize.mp4"
    fake_video.parent.mkdir(parents=True, exist_ok=True)
    # box_size = 1,ftyp at offset 4,16+ bytes(满足 len >= 16 但 box_size==1 reject)
    fake_video.write_bytes(b"\x00\x00\x00\x01" + b"ftyp" + b"\x00\x00\x00\x00\x00\x00\x00\x40" + b"isom" + b"\x00" * 12)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"largesize") as exc_info:
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )
        assert "video-bmff-largesize-support" in str(exc_info.value)


def test_generate_video_bmff_major_brand_zero_raises(tmp_path):
    """major_brand at offset 8-12 全 0 → empty brand reject。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "zerobrand.mp4"
    _make_minimal_mp4(fake_video, major_brand=b"\x00\x00\x00\x00")
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"major_brand is empty"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_bmff_major_brand_spaces_raises(tmp_path):
    """major_brand at offset 8-12 全 space → empty brand reject。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "spacebrand.mp4"
    _make_minimal_mp4(fake_video, major_brand=b"    ")
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"major_brand is empty"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_bmff_valid_mp4_accepts_with_isom_brand(tmp_path):
    """Happy path:major_brand == "isom"(ISO Base Media File Format)→ accept。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "isom.mp4"
    _make_minimal_mp4(fake_video, major_brand=b"isom")
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(candidates) == 1
    assert candidates[0].format == "mp4"


def test_generate_video_bmff_valid_mp4_accepts_with_mp42_brand(tmp_path):
    """Happy path:major_brand == "mp42" → accept(常见 ffmpeg muxing brand)。"""
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "mp42.mp4"
    _make_minimal_mp4(fake_video, major_brand=b"mp42")
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(candidates) == 1
    assert candidates[0].format == "mp4"


# ---------------------------------------------------------------------------
# Path trust-boundary(2 fences)
# ---------------------------------------------------------------------------


def test_generate_video_missing_path_raises_unsupported_response(tmp_path):
    """outputs.video 路径不存在 → reject(沿 audio G11 R2 fix)。"""
    worker = _make_video_worker(tmp_path)
    nonexistent = tmp_path / "ghost.mp4"  # 不创建文件
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(nonexistent)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"path does not exist"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


def test_generate_video_symlink_path_raises_unsupported_response(tmp_path):
    """outputs.video 路径是 symlink → reject(防 symlink redirect attack;沿 audio G11 R2 fix)。"""
    if os.name == "nt":
        pytest.skip("symlink 在 Windows 需要 admin 权限,跳过(POSIX 全覆盖)")
    worker = _make_video_worker(tmp_path)
    target = tmp_path / "real.mp4"
    _make_minimal_mp4(target)
    link = tmp_path / "link.mp4"
    link.symlink_to(target)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(link)]))
        with pytest.raises(WorkerUnsupportedResponse, match=r"symlink"):
            worker.generate_video(
                spec={"comfy_workflow": "x", "comfy_params": {}},
                num_candidates=1,
            )


# ---------------------------------------------------------------------------
# Per-candidate loop + seed override(沿 audio F-Plan-3 + G11-F3;1 fence)
# ---------------------------------------------------------------------------


def test_generate_video_runs_subprocess_num_candidates_times_with_per_candidate_seed_override(tmp_path):
    """num_candidates=3 → 3 次 subprocess.run + per-candidate seed = (caller_seed or 0) + i,
    直接覆盖 caller comfy_params.seed(沿 audio G11-F3 fix 同款,**不**用 setdefault)。
    """
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={
                "comfy_workflow": "x",
                "comfy_params": {"positive_prompt": "test", "seed": 999},  # caller 预填 seed=999
            },
            num_candidates=3,
            seed=42,
        )
    assert run_mock.call_count == 3, f"应调 3 次 subprocess.run,实际 {run_mock.call_count}"
    assert len(candidates) == 3
    # 验证每次调用 seed 是 42 + i(NOT 999 — caller's pre-filled seed 被覆盖)
    seen_seeds = []
    for call in run_mock.call_args_list:
        cmd = call.args[0]
        # cmd 含 --params <json>;parse JSON 取 seed
        params_idx = cmd.index("--params")
        params = json.loads(cmd[params_idx + 1])
        seen_seeds.append(params["seed"])
    assert seen_seeds == [42, 43, 44], f"per-candidate seed 应是 [42,43,44],实际 {seen_seeds}"


# ---------------------------------------------------------------------------
# Metadata provenance(2 fences)
# ---------------------------------------------------------------------------


def test_generate_video_metadata_records_5_comfy_provenance_keys(tmp_path):
    """D8 + round-3 PF1:VideoCandidate.metadata 含 5 个 comfy_* provenance keys
    (comfy_manifest / comfy_params_snapshot / comfy_capability="video" /
    comfy_original_filename / comfy_subprocess_run_metadata)。
    """
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "wan21_5sec_00001.mp4"
    _make_minimal_mp4(fake_video)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={
                "comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec",
                "comfy_params": {"positive_prompt": "uplifting space scene", "seed": 5042},
            },
            num_candidates=1,
            seed=5042,
        )
    cand = candidates[0]
    assert set(cand.metadata.keys()) == {
        "comfy_manifest",
        "comfy_params_snapshot",
        "comfy_capability",
        "comfy_original_filename",
        "comfy_subprocess_run_metadata",
    }
    assert cand.metadata["comfy_manifest"] == "Vedio/Wan2.1-T2V-1.3B_native_5sec"
    assert cand.metadata["comfy_capability"] == "video"
    assert cand.metadata["comfy_original_filename"] == "wan21_5sec_00001.mp4"
    # D8 single-source:5 个 video metadata 顶层字段全 None
    assert cand.duration_seconds is None
    assert cand.frame_count is None
    assert cand.width is None
    assert cand.height is None
    assert cand.fps is None


def test_generate_video_metadata_snapshot_is_independent_copy(tmp_path):
    """D8:metadata.comfy_params_snapshot 是 dict() 副本;mutating caller spec
    不影响 snapshot(沿 audio Phase 2 同款 isolation)。
    """
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    caller_params = {"positive_prompt": "original", "seed": 100}
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={"comfy_workflow": "x", "comfy_params": caller_params},
            num_candidates=1,
            seed=100,
        )
    snapshot = candidates[0].metadata["comfy_params_snapshot"]
    # 修改 caller dict
    caller_params["positive_prompt"] = "MUTATED"
    caller_params["new_key"] = "added"
    # snapshot 不受影响
    assert snapshot["positive_prompt"] == "original"
    assert "new_key" not in snapshot


# ---------------------------------------------------------------------------
# env independence(1 fence;沿 audio D7)
# ---------------------------------------------------------------------------


def test_generate_video_does_not_read_forgeue_comfy_input_dir_env_var(tmp_path, monkeypatch):
    """video 是 text-to-video(D7),无 source bytes input;不读
    `FORGEUE_COMFY_INPUT_DIR` env var(沿 audio D7 同款 — 该 env var 是 mesh-specific)。
    """
    worker = _make_video_worker(tmp_path)
    fake_video = tmp_path / "video.mp4"
    _make_minimal_mp4(fake_video)
    # 显式 unset env var (确保 video path 不读 it)
    monkeypatch.delenv("FORGEUE_COMFY_INPUT_DIR", raising=False)
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed(_ok_video_stdout([str(fake_video)]))
        candidates = worker.generate_video(
            spec={"comfy_workflow": "x", "comfy_params": {}},
            num_candidates=1,
        )
    assert len(candidates) == 1
    assert candidates[0].format == "mp4"


# ---------------------------------------------------------------------------
# DryRunPass gate(commit 9):comfy/local-video 触发 reachability probe
# ---------------------------------------------------------------------------


def test_dry_run_probes_comfy_when_comfy_local_video_in_routes(tmp_path, monkeypatch):
    """commit 9:DryRunPass `_check_comfy_reachability` gate set 扩 `comfy/local-video`
    (沿 P-F4 + audio commit 6 同款 set membership 模式)— bundle 含 video_local
    alias 时触发 ComfyUI subprocess probe。
    """
    from unittest.mock import MagicMock

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
        ResolvedRoute(model="comfy/local-video", api_key_env=None, api_base=None,
                      kind="video", pricing=None),
    ]

    with patch("subprocess.run") as run_mock:
        run_mock.return_value = _make_completed("ok", returncode=0)
        dry_run._check_comfy_reachability(report, steps=[step])
        # comfy/local-video 触发 probe(commit 9 gate 扩)
        assert run_mock.call_count == 1
        cmd = run_mock.call_args[0][0]
        assert "comfyui_api" in " ".join(cmd)
        assert "status" in cmd
    assert report.checks.get("comfy.cli_reachable") is True
