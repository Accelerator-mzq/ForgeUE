"""MiniMax Music 2.6 audio worker(FOR-26 follow-on).

这个 worker 是 MiniMax `music_generation` 原生 API 的薄适配层:
ForgeUE 仍使用 `AudioWorker` / `AudioCandidate` 契约,这里只负责把
`step.config.spec` 转成 MiniMax 请求体,并把 URL/hex 音频转成 bytes。
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from framework.providers.workers.audio_metadata import parse_audio_metadata
from framework.providers.workers.audio_worker import (
    AudioCandidate,
    AudioWorker,
    AudioWorkerError,
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
)


DEFAULT_MINIMAX_MUSIC_ENDPOINT = "https://api.minimaxi.com/v1/music_generation"
DEFAULT_MINIMAX_MUSIC_MODEL = "music-2.6"
_AUDIO_FORMATS = {"flac", "mp3", "wav"}
_DEFAULT_AUDIO_SETTING = {
    "sample_rate": 44100,
    "bitrate": 256000,
    "format": "mp3",
}
_PASSTHROUGH_KEYS = (
    "lyrics",
    "lyrics_optimizer",
    "is_instrumental",
    "audio_url",
    "audio_base64",
    "cover_feature_id",
)


class MiniMaxMusicWorker(AudioWorker):
    """MiniMax music_generation adapter.

    默认使用本地 `docs/api_des/MiniMax-Audio.md` 中的中国区 endpoint。
    如账号属于国际站,可用 `FORGEUE_MINIMAX_MUSIC_URL` 覆盖。
    """

    name = "minimax_music"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint_url: str = DEFAULT_MINIMAX_MUSIC_ENDPOINT,
        model: str = DEFAULT_MINIMAX_MUSIC_MODEL,
        timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("MiniMaxMusicWorker api_key is required")
        self._api_key = api_key
        self._endpoint_url = endpoint_url
        self._model = model
        self._timeout_s = timeout_s
        # 测试用 MockTransport 注入口;生产默认 None。
        self._transport = transport

    def generate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
        """同步兼容入口;主运行时走 agenerate_audio。"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.agenerate_audio(
                    spec=spec,
                    num_candidates=num_candidates,
                    seed=seed,
                    timeout_s=timeout_s,
                )
            )
        raise AudioWorkerError(
            "MiniMaxMusicWorker.generate_audio called inside a running event loop; "
            "use agenerate_audio instead",
            worker=self.name,
            model=self._model,
        )

    async def agenerate_audio(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int = 1,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[AudioCandidate]:
        timeout = timeout_s if timeout_s is not None else self._timeout_s
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        count = max(1, num_candidates)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self._transport,
                follow_redirects=True,
            ) as client:
                candidates: list[AudioCandidate] = []
                for index in range(count):
                    body = _build_payload(spec=spec, model=self._model)
                    response = await client.post(
                        self._endpoint_url,
                        headers=headers,
                        json=body,
                    )
                    _raise_for_minimax_http_status(response, worker=self)
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise AudioWorkerUnsupportedResponse(
                            "MiniMax music_generation response is not JSON",
                            worker=self.name,
                            model=self._model,
                        ) from exc
                    candidates.append(
                        await self._candidate_from_payload(
                            payload,
                            request_body=body,
                            client=client,
                            timeout_s=timeout,
                            index=index,
                            seed=seed,
                        )
                    )
                return candidates
        except httpx.TimeoutException as exc:
            raise AudioWorkerTimeout(
                str(exc) or "MiniMax music_generation request timed out",
                worker=self.name,
                model=self._model,
            ) from exc
        except httpx.RequestError as exc:
            raise AudioWorkerError(
                str(exc) or "MiniMax music_generation request failed",
                worker=self.name,
                model=self._model,
            ) from exc

    async def _candidate_from_payload(
        self,
        payload: Any,
        *,
        request_body: dict[str, Any],
        client: httpx.AsyncClient,
        timeout_s: float,
        index: int,
        seed: int | None,
    ) -> AudioCandidate:
        if not isinstance(payload, dict):
            raise AudioWorkerUnsupportedResponse(
                "MiniMax music_generation response must be a JSON object",
                worker=self.name,
                model=self._model,
            )
        _raise_for_minimax_base_resp(payload, worker=self)

        data_obj = payload.get("data")
        if not isinstance(data_obj, dict):
            raise AudioWorkerUnsupportedResponse(
                "MiniMax music_generation response missing data object",
                worker=self.name,
                model=self._model,
            )
        status = data_obj.get("status")
        if status not in (None, 2, "2"):
            raise AudioWorkerUnsupportedResponse(
                f"MiniMax music_generation returned unfinished status {status!r}",
                worker=self.name,
                model=self._model,
            )

        fmt = _normalise_format(
            (request_body.get("audio_setting") or {}).get("format"),
        )
        audio_value = _extract_audio_value(data_obj)
        data, source_url = await _audio_bytes_from_value(
            audio_value,
            output_format=str(request_body.get("output_format") or "url"),
            client=client,
            timeout_s=timeout_s,
            worker=self,
        )
        if not _audio_magic_matches(fmt, data):
            raise AudioWorkerUnsupportedResponse(
                f"MiniMax music_generation magic bytes mismatch "
                f"(format={fmt!r}, magic={data[:12].hex()})",
                worker=self.name,
                model=self._model,
            )

        parsed_duration, parsed_sample_rate = parse_audio_metadata(data, fmt)
        extra_info = payload.get("extra_info") if isinstance(payload.get("extra_info"), dict) else {}
        metadata: dict[str, Any] = {
            "provider": "minimax",
            "minimax_model": str(request_body.get("model") or self._model),
            "minimax_endpoint": self._endpoint_url,
            "minimax_output_format": str(request_body.get("output_format") or "url"),
            "minimax_candidate_index": index,
        }
        if seed is not None:
            metadata["minimax_seed"] = seed
        trace_id = payload.get("trace_id")
        if trace_id is not None:
            metadata["minimax_trace_id"] = str(trace_id)
        if source_url:
            # MiniMax URL 常带临时签名 query;下载要用完整 URL,metadata 只留无 query 版本。
            metadata["minimax_source_url"] = _strip_url_query(source_url)
        for key in ("music_size", "music_bitrate"):
            if key in extra_info:
                metadata[f"minimax_{key}"] = extra_info[key]

        return AudioCandidate(
            data=data,
            format=fmt,
            metadata=metadata,
            duration_seconds=_duration_from_extra(
                extra_info.get("music_duration"),
                fallback=parsed_duration,
            ),
            sample_rate=_int_or_none(
                extra_info.get("music_sample_rate"),
                fallback=parsed_sample_rate,
            ),
        )


def _build_payload(*, spec: dict[str, Any], model: str) -> dict[str, Any]:
    """把 ForgeUE spec 转成 MiniMax music_generation 原生请求体。"""
    prompt = _extract_prompt(spec)
    if not prompt:
        raise AudioWorkerUnsupportedResponse(
            "MiniMax music_generation needs spec.prompt/spec.text/spec.input",
        )

    raw_audio_setting = spec.get("audio_setting")
    audio_setting = dict(_DEFAULT_AUDIO_SETTING)
    if isinstance(raw_audio_setting, dict):
        audio_setting.update(raw_audio_setting)
    audio_setting["format"] = _normalise_format(audio_setting.get("format"))

    payload: dict[str, Any] = {
        "model": str(spec.get("model") or model),
        "prompt": prompt,
        "audio_setting": audio_setting,
        "output_format": str(spec.get("output_format") or "url"),
    }
    for key in _PASSTHROUGH_KEYS:
        if key in spec:
            payload[key] = spec[key]
    return payload


def _extract_prompt(spec: dict[str, Any]) -> str | None:
    for key in ("prompt", "text", "input"):
        value = spec.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_audio_value(data_obj: dict[str, Any]) -> str:
    for key in ("audio", "audio_url", "url"):
        value = data_obj.get(key)
        if isinstance(value, str) and value:
            return value
    raise AudioWorkerUnsupportedResponse(
        "MiniMax music_generation response missing data.audio/data.audio_url",
    )


async def _audio_bytes_from_value(
    value: str,
    *,
    output_format: str,
    client: httpx.AsyncClient,
    timeout_s: float,
    worker: MiniMaxMusicWorker,
) -> tuple[bytes, str | None]:
    if value.startswith(("http://", "https://")):
        response = await client.get(value, timeout=timeout_s)
        _raise_for_minimax_http_status(response, worker=worker)
        return response.content, value
    if output_format == "url":
        raise AudioWorkerUnsupportedResponse(
            "MiniMax music_generation expected URL output but response data.audio was not URL",
            worker=worker.name,
            model=worker._model,
        )
    try:
        return bytes.fromhex(value), None
    except ValueError as exc:
        raise AudioWorkerUnsupportedResponse(
            "MiniMax music_generation data.audio is not valid hex audio",
            worker=worker.name,
            model=worker._model,
        ) from exc


def _normalise_format(value: Any) -> Literal["flac", "mp3", "wav"]:
    fmt = str(value or "").lower().lstrip(".")
    if fmt not in _AUDIO_FORMATS:
        raise AudioWorkerUnsupportedResponse(
            f"unsupported MiniMax audio format {fmt!r}; expected one of {sorted(_AUDIO_FORMATS)}",
        )
    return cast(Literal["flac", "mp3", "wav"], fmt)


def _audio_magic_matches(fmt: str, data: bytes) -> bool:
    """复用音频 worker 的最小 magic bytes 边界。"""
    if fmt == "flac":
        return data[:4] == b"fLaC"
    if fmt == "mp3":
        return data[:3] == b"ID3" or data[:2] in (
            b"\xff\xfb",
            b"\xff\xfa",
            b"\xff\xf3",
            b"\xff\xf2",
        )
    if fmt == "wav":
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    return False


def _duration_from_extra(value: Any, *, fallback: float | None) -> float | None:
    if value is None:
        return fallback
    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return fallback


def _strip_url_query(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _int_or_none(value: Any, *, fallback: int | None) -> int | None:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _raise_for_minimax_base_resp(
    payload: dict[str, Any],
    *,
    worker: MiniMaxMusicWorker,
) -> None:
    base_resp = payload.get("base_resp")
    if not isinstance(base_resp, dict):
        return
    status_code = base_resp.get("status_code")
    if status_code in (None, 0, "0"):
        return
    status_msg = str(base_resp.get("status_msg") or status_code)
    raise AudioWorkerUnsupportedResponse(
        f"MiniMax music_generation failed: {status_msg}",
        worker=worker.name,
        model=worker._model,
    )


def _raise_for_minimax_http_status(
    response: httpx.Response,
    *,
    worker: MiniMaxMusicWorker,
) -> None:
    if response.status_code < 400:
        return
    msg = f"MiniMax music_generation HTTP {response.status_code}"
    if 400 <= response.status_code < 500:
        raise AudioWorkerUnsupportedResponse(
            msg,
            worker=worker.name,
            model=worker._model,
        )
    raise AudioWorkerError(
        msg,
        worker=worker.name,
        model=worker._model,
    )
