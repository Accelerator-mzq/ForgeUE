"""MiniMax music worker 离线契约测试。"""
from __future__ import annotations

import json

import httpx
import pytest

from framework.providers.workers.audio_worker import (
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
)
from framework.providers.workers.minimax_music_worker import MiniMaxMusicWorker


def _mp3_bytes() -> bytes:
    return b"ID3" + b"\x00" * 64


@pytest.mark.asyncio
async def test_minimax_music_worker_posts_native_payload_and_downloads_url():
    """MiniMax worker 应发送 MiniMax 原生 payload,并把返回 URL 下载成 AudioCandidate。"""
    calls: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, str(req.url)))
        if req.method == "POST":
            body = json.loads(req.content.decode("utf-8"))
            assert str(req.url) == "https://api.minimaxi.com/v1/music_generation"
            assert req.headers["authorization"] == "Bearer sk-minimax"
            assert body == {
                "model": "music-2.6",
                "prompt": "cinematic fantasy tavern loop",
                "lyrics": "[Verse]\nForge the blade tonight",
                "audio_setting": {
                    "sample_rate": 44100,
                    "bitrate": 256000,
                    "format": "mp3",
                },
                "output_format": "url",
                "is_instrumental": False,
            }
            return httpx.Response(
                200,
                json={
                    "data": {
                        "audio": "https://filecdn.minimax.chat/public/out.mp3?Expires=1&Signature=secret",
                        "status": 2,
                    },
                    "trace_id": "trace-1",
                    "extra_info": {
                        "music_duration": 25364,
                        "music_sample_rate": 44100,
                        "music_bitrate": 256000,
                    },
                    "base_resp": {"status_code": 0, "status_msg": ""},
                },
            )
        if req.method == "GET":
            assert str(req.url) == "https://filecdn.minimax.chat/public/out.mp3?Expires=1&Signature=secret"
            return httpx.Response(200, content=_mp3_bytes())
        return httpx.Response(404)

    worker = MiniMaxMusicWorker(
        api_key="sk-minimax",
        model="music-2.6",
        transport=httpx.MockTransport(handler),
    )

    cands = await worker.agenerate_audio(
        spec={
            "prompt": "cinematic fantasy tavern loop",
            "lyrics": "[Verse]\nForge the blade tonight",
            "is_instrumental": False,
        },
        num_candidates=1,
        seed=123,
        timeout_s=7.0,
    )

    assert calls == [
        ("POST", "https://api.minimaxi.com/v1/music_generation"),
        ("GET", "https://filecdn.minimax.chat/public/out.mp3?Expires=1&Signature=secret"),
    ]
    assert len(cands) == 1
    assert cands[0].format == "mp3"
    assert cands[0].data.startswith(b"ID3")
    assert cands[0].duration_seconds == pytest.approx(25.364)
    assert cands[0].sample_rate == 44100
    assert cands[0].metadata["provider"] == "minimax"
    assert cands[0].metadata["minimax_trace_id"] == "trace-1"
    assert cands[0].metadata["minimax_source_url"] == "https://filecdn.minimax.chat/public/out.mp3"


@pytest.mark.asyncio
async def test_minimax_music_worker_accepts_hex_audio_response():
    """MiniMax output_format=hex 时,data.audio 应按 hex bytes 解析。"""

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        assert body["output_format"] == "hex"
        return httpx.Response(
            200,
            json={
                "data": {"audio": _mp3_bytes().hex(), "status": 2},
                "base_resp": {"status_code": 0, "status_msg": ""},
            },
        )

    worker = MiniMaxMusicWorker(
        api_key="sk-minimax",
        transport=httpx.MockTransport(handler),
    )

    cands = await worker.agenerate_audio(
        spec={"prompt": "short victory sting", "output_format": "hex"},
    )

    assert cands[0].format == "mp3"
    assert cands[0].data.startswith(b"ID3")
    assert "minimax_source_url" not in cands[0].metadata


@pytest.mark.asyncio
async def test_minimax_music_worker_rejects_provider_error_response():
    """MiniMax base_resp 非 0 时应 fail-fast,不要把错误 JSON 当音频。"""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 1008, "status_msg": "invalid lyrics"},
            },
        )

    worker = MiniMaxMusicWorker(
        api_key="sk-minimax",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AudioWorkerUnsupportedResponse, match="invalid lyrics"):
        await worker.agenerate_audio(spec={"prompt": "x"})


@pytest.mark.asyncio
async def test_minimax_music_worker_maps_timeout_to_audio_timeout():
    """网络 timeout 应归类为 AudioWorkerTimeout。"""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("minimax timed out", request=req)

    worker = MiniMaxMusicWorker(
        api_key="sk-minimax",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AudioWorkerTimeout, match="minimax timed out"):
        await worker.agenerate_audio(spec={"prompt": "x"}, timeout_s=0.01)
