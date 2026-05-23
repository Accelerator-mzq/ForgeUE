"""FOR-26 remote HTTP audio worker 离线契约测试。"""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from framework.providers.workers.audio_worker import (
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
)
from framework.providers.workers.remote_audio_worker import RemoteHttpAudioWorker


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _flac_bytes() -> bytes:
    return b"fLaC" + b"\x00" * 64


def _wav_bytes() -> bytes:
    return b"RIFF\x24\x00\x00\x00WAVE" + b"\x00" * 48


@pytest.mark.asyncio
async def test_remote_http_audio_worker_posts_spec_and_decodes_base64_candidate():
    """远端 worker 应发送通用 JSON,并把 base64 音频转成 AudioCandidate。"""
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        body = json.loads(req.content.decode("utf-8"))
        assert req.method == "POST"
        assert str(req.url) == "https://audio.example.test/generate"
        assert req.headers["authorization"] == "Bearer sk-test"
        assert body == {
            "model": "music-test",
            "prompt": "calm orchestral loop",
            "num_candidates": 2,
            "seed": 123,
            "spec": {"prompt": "calm orchestral loop", "style": "cinematic"},
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "format": "flac",
                        "bytes_base64": _b64(_flac_bytes()),
                        "duration_seconds": 1.5,
                        "sample_rate": 44100,
                        "metadata": {"provider": "mock-audio"},
                    }
                ]
            },
        )

    worker = RemoteHttpAudioWorker(
        endpoint_url="https://audio.example.test/generate",
        api_key="sk-test",
        model="music-test",
        transport=httpx.MockTransport(handler),
    )

    cands = await worker.agenerate_audio(
        spec={"prompt": "calm orchestral loop", "style": "cinematic"},
        num_candidates=2,
        seed=123,
        timeout_s=9.0,
    )

    assert len(seen) == 1
    assert len(cands) == 1
    assert cands[0].format == "flac"
    assert cands[0].data.startswith(b"fLaC")
    assert cands[0].duration_seconds == 1.5
    assert cands[0].sample_rate == 44100
    assert cands[0].metadata["provider"] == "mock-audio"
    assert cands[0].metadata["remote_audio_model"] == "music-test"


@pytest.mark.asyncio
async def test_remote_http_audio_worker_downloads_url_candidate_without_api_key():
    """远端响应也可以只给 url;未配置 key 时不发送 Authorization。"""
    calls: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, str(req.url)))
        assert "authorization" not in req.headers
        if req.method == "POST":
            return httpx.Response(
                200,
                json={"format": "wav", "url": "https://cdn.example.test/out.wav"},
            )
        if req.method == "GET" and str(req.url) == "https://cdn.example.test/out.wav":
            return httpx.Response(200, content=_wav_bytes())
        return httpx.Response(404, json={"error": "unexpected"})

    worker = RemoteHttpAudioWorker(
        endpoint_url="https://audio.example.test/generate",
        transport=httpx.MockTransport(handler),
    )

    cands = await worker.agenerate_audio(
        spec={"text": "short UI success sting"},
        num_candidates=1,
        seed=None,
        timeout_s=5.0,
    )

    assert calls == [
        ("POST", "https://audio.example.test/generate"),
        ("GET", "https://cdn.example.test/out.wav"),
    ]
    assert cands[0].format == "wav"
    assert cands[0].data.startswith(b"RIFF")
    assert cands[0].metadata["remote_audio_url"] == "https://cdn.example.test/out.wav"


@pytest.mark.asyncio
async def test_remote_http_audio_worker_rejects_unsupported_format():
    """格式白名单只允许 flac/mp3/wav,避免 UE import 侧收到未知音频。"""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"format": "aac", "bytes_base64": _b64(b"ADTS")},
        )

    worker = RemoteHttpAudioWorker(
        endpoint_url="https://audio.example.test/generate",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AudioWorkerUnsupportedResponse, match="unsupported audio format"):
        await worker.agenerate_audio(spec={"prompt": "x"})


@pytest.mark.asyncio
async def test_remote_http_audio_worker_rejects_magic_mismatch():
    """声明格式和真实 bytes 不一致时 fail-fast。"""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"format": "mp3", "bytes_base64": _b64(b"not an mp3")},
        )

    worker = RemoteHttpAudioWorker(
        endpoint_url="https://audio.example.test/generate",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AudioWorkerUnsupportedResponse, match="magic bytes"):
        await worker.agenerate_audio(spec={"prompt": "x"})


@pytest.mark.asyncio
async def test_remote_http_audio_worker_maps_http_timeout_to_audio_timeout():
    """HTTP timeout 应归类为 AudioWorkerTimeout,让 FailureModeMap 保持 audio-specific。"""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("remote audio timed out", request=req)

    worker = RemoteHttpAudioWorker(
        endpoint_url="https://audio.example.test/generate",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AudioWorkerTimeout, match="remote audio timed out"):
        await worker.agenerate_audio(spec={"prompt": "x"}, timeout_s=0.01)
