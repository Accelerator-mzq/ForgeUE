"""ffprobe-based video metadata parser.

从视频文件路径调用 ffprobe，提取 duration / frame_count / width / height / fps，
再交给 `VideoCandidate` 顶层字段使用。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def parse_video_metadata(path: str | Path) -> tuple[float | None, int | None, int | None, int | None, float | None]:
    """用 ffprobe 解析视频 5-tuple metadata。

    失败时静默返回全 None，调用方保留原有 fallback 语义。
    """
    video_path = Path(path)
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,nb_read_frames:format=duration",
                "-of",
                "json",
                str(video_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, OSError):
        return (None, None, None, None, None)

    if completed.returncode != 0:
        return (None, None, None, None, None)

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return (None, None, None, None, None)

    if not isinstance(payload, dict):
        return (None, None, None, None, None)

    stream = _first_stream(payload.get("streams"))
    format_info = payload.get("format") if isinstance(payload.get("format"), dict) else {}

    width = _as_int(stream.get("width")) if stream else None
    height = _as_int(stream.get("height")) if stream else None
    fps = _parse_fraction(
        _first_non_empty(
            _as_text(stream.get("avg_frame_rate")) if stream else None,
            _as_text(stream.get("r_frame_rate")) if stream else None,
        )
    )
    duration_seconds = _as_float(format_info.get("duration")) if format_info else None
    if duration_seconds is None and stream:
        duration_seconds = _as_float(stream.get("duration"))

    frame_count = None
    if stream:
        frame_count = _as_int(stream.get("nb_read_frames"))
        if frame_count is None:
            frame_count = _as_int(stream.get("nb_frames"))
        if frame_count is None and duration_seconds is not None and fps is not None:
            frame_count = int(round(duration_seconds * fps))

    return (duration_seconds, frame_count, width, height, fps)


def _first_stream(value: object) -> dict | None:
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    return first if isinstance(first, dict) else None


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_fraction(value: str | None) -> float | None:
    if not value or value == "N/A":
        return None
    if "/" not in value:
        return _as_float(value)
    numerator, denominator = value.split("/", 1)
    try:
        denom = float(denominator)
        if denom == 0:
            return None
        return float(numerator) / denom
    except (TypeError, ValueError):
        return None
