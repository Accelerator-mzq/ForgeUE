"""视频 metadata 解析器 fences。

通过 ffprobe 解析视频的 duration / frame_count / width / height / fps，
再回写到 `VideoCandidate` 顶层字段。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch


def test_parse_video_metadata_extracts_all_fields_from_ffprobe_json(tmp_path):
    """ffprobe JSON 中的 stream + format 字段应被解析成 5-tuple metadata。"""
    from framework.providers.workers.video_metadata import parse_video_metadata

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake mp4 bytes")

    ffprobe_json = {
        "streams": [
            {
                "width": 832,
                "height": 480,
                "avg_frame_rate": "24/1",
                "nb_frames": "81",
            }
        ],
        "format": {"duration": "3.375"},
    }
    completed = subprocess.CompletedProcess(
        args=["ffprobe"],
        returncode=0,
        stdout=json.dumps(ffprobe_json),
        stderr="",
    )

    with patch("framework.providers.workers.video_metadata.subprocess.run", return_value=completed) as run_mock:
        duration_seconds, frame_count, width, height, fps = parse_video_metadata(video)

    assert duration_seconds == 3.375
    assert frame_count == 81
    assert width == 832
    assert height == 480
    assert fps == 24.0
    assert run_mock.call_count == 1


def test_parse_video_metadata_missing_ffprobe_returns_none(tmp_path):
    """ffprobe 不可用时，解析器应安静回退到全 None。"""
    from framework.providers.workers.video_metadata import parse_video_metadata

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake mp4 bytes")

    with patch("framework.providers.workers.video_metadata.subprocess.run", side_effect=FileNotFoundError):
        duration_seconds, frame_count, width, height, fps = parse_video_metadata(video)

    assert duration_seconds is None
    assert frame_count is None
    assert width is None
    assert height is None
    assert fps is None
