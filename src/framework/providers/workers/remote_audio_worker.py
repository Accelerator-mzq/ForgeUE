"""Remote HTTP audio worker(FOR-26).

这个 worker 是 `AudioWorker` 的通用远端实现:ForgeUE 只约定一个很薄的
HTTP JSON 契约,不绑定 ElevenLabs / AudioCraft / 私有服务的具体 API。
"""
from __future__ import annotations

import asyncio
import base64
from typing import Any, Literal, cast

import httpx

from framework.providers.workers.audio_metadata import parse_audio_metadata
from framework.providers.workers.audio_worker import (
    AudioCandidate,
    AudioWorker,
    AudioWorkerError,
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
)


_AUDIO_FORMATS = {"flac", "mp3", "wav"}
_BASE64_FIELDS = ("bytes_base64", "data_base64", "audio_base64")


class RemoteHttpAudioWorker(AudioWorker):
    """Generic HTTP adapter for remote text-to-audio services.

    请求体固定为 `model/prompt/num_candidates/seed/spec`。远端服务可以只读
    `spec`,也可以直接读顶层 prompt。响应支持 base64 payload 或可下载 URL。
    """

    name = "remote_audio_http"

    def __init__(
        self,
        *,
        endpoint_url: str,
        api_key: str | None = None,
        model: str | None = None,
        timeout_s: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not endpoint_url:
            raise ValueError("RemoteHttpAudioWorker endpoint_url is required")
        self._endpoint_url = endpoint_url
        self._api_key = api_key
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
        """同步兼容入口。

        主运行时走 `agenerate_audio`;这里保留给 ad-hoc 调用和 ABC 完整性。
        """
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
            "RemoteHttpAudioWorker.generate_audio called inside a running event loop; "
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
        body = {
            "model": self._model,
            "prompt": _extract_prompt(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "spec": dict(spec),
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self._transport,
                follow_redirects=True,
            ) as client:
                response = await client.post(
                    self._endpoint_url,
                    json=body,
                    headers=headers,
                )
                _raise_for_remote_status(response, worker=self)
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise AudioWorkerUnsupportedResponse(
                        "remote audio response is not JSON",
                        worker=self.name,
                        model=self._model,
                    ) from exc
                return await self._parse_response(payload, client=client, timeout_s=timeout)
        except httpx.TimeoutException as exc:
            raise AudioWorkerTimeout(
                str(exc) or "remote audio request timed out",
                worker=self.name,
                model=self._model,
            ) from exc
        except httpx.RequestError as exc:
            raise AudioWorkerError(
                str(exc) or "remote audio request failed",
                worker=self.name,
                model=self._model,
            ) from exc

    async def _parse_response(
        self,
        payload: Any,
        *,
        client: httpx.AsyncClient,
        timeout_s: float,
    ) -> list[AudioCandidate]:
        if not isinstance(payload, dict):
            raise AudioWorkerUnsupportedResponse(
                "remote audio response must be a JSON object",
                worker=self.name,
                model=self._model,
            )

        raw_items = payload.get("candidates")
        if raw_items is None:
            items = [payload]
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            raise AudioWorkerUnsupportedResponse(
                "remote audio response field 'candidates' must be a list",
                worker=self.name,
                model=self._model,
            )

        candidates: list[AudioCandidate] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise AudioWorkerUnsupportedResponse(
                    f"remote audio candidate {index} must be a JSON object",
                    worker=self.name,
                    model=self._model,
                )
            candidates.append(
                await self._candidate_from_item(
                    item,
                    parent=payload,
                    client=client,
                    timeout_s=timeout_s,
                    index=index,
                )
            )
        if not candidates:
            raise AudioWorkerUnsupportedResponse(
                "remote audio response returned no candidates",
                worker=self.name,
                model=self._model,
            )
        return candidates

    async def _candidate_from_item(
        self,
        item: dict[str, Any],
        *,
        parent: dict[str, Any],
        client: httpx.AsyncClient,
        timeout_s: float,
        index: int,
    ) -> AudioCandidate:
        fmt = _normalise_format(item.get("format"))
        data, source_url = await self._candidate_bytes(
            item, client=client, timeout_s=timeout_s,
        )
        if not _audio_magic_matches(fmt, data):
            raise AudioWorkerUnsupportedResponse(
                f"remote audio candidate {index} magic bytes mismatch "
                f"(format={fmt!r}, magic={data[:12].hex()})",
                worker=self.name,
                model=self._model,
            )

        parsed_duration, parsed_sample_rate = parse_audio_metadata(data, fmt)
        metadata = dict(item.get("metadata") if isinstance(item.get("metadata"), dict) else {})
        if self._model:
            metadata["remote_audio_model"] = self._model
        metadata["remote_audio_endpoint"] = self._endpoint_url
        if source_url:
            metadata["remote_audio_url"] = source_url
        job_id = item.get("job_id") or parent.get("job_id")
        if job_id is not None:
            metadata["remote_audio_job_id"] = str(job_id)

        return AudioCandidate(
            data=data,
            format=fmt,
            metadata=metadata,
            duration_seconds=_float_or_none(
                item.get("duration_seconds"), fallback=parsed_duration,
            ),
            sample_rate=_int_or_none(item.get("sample_rate"), fallback=parsed_sample_rate),
        )

    async def _candidate_bytes(
        self,
        item: dict[str, Any],
        *,
        client: httpx.AsyncClient,
        timeout_s: float,
    ) -> tuple[bytes, str | None]:
        for field in _BASE64_FIELDS:
            value = item.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                raise AudioWorkerUnsupportedResponse(
                    f"remote audio field {field!r} must be a base64 string",
                    worker=self.name,
                    model=self._model,
                )
            try:
                return base64.b64decode(value, validate=True), None
            except ValueError as exc:
                raise AudioWorkerUnsupportedResponse(
                    f"remote audio field {field!r} is not valid base64",
                    worker=self.name,
                    model=self._model,
                ) from exc

        url = item.get("url") or item.get("audio_url")
        if not isinstance(url, str) or not url:
            raise AudioWorkerUnsupportedResponse(
                "remote audio candidate needs bytes_base64/data_base64/audio_base64 or url",
                worker=self.name,
                model=self._model,
            )
        response = await client.get(url, timeout=timeout_s)
        _raise_for_remote_status(response, worker=self)
        return response.content, url


def _extract_prompt(spec: dict[str, Any]) -> str | None:
    """从常见字段提取 prompt;完整 spec 仍会原样透传。"""
    for key in ("prompt", "text", "input"):
        value = spec.get(key)
        if isinstance(value, str):
            return value
    return None


def _normalise_format(value: Any) -> Literal["flac", "mp3", "wav"]:
    fmt = str(value or "").lower().lstrip(".")
    if fmt not in _AUDIO_FORMATS:
        raise AudioWorkerUnsupportedResponse(
            f"unsupported audio format {fmt!r}; expected one of {sorted(_AUDIO_FORMATS)}"
        )
    return cast(Literal["flac", "mp3", "wav"], fmt)


def _audio_magic_matches(fmt: str, data: bytes) -> bool:
    """复用 ComfyUI audio 的最小 magic bytes 边界。"""
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


def _float_or_none(value: Any, *, fallback: float | None) -> float | None:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _int_or_none(value: Any, *, fallback: int | None) -> int | None:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _raise_for_remote_status(
    response: httpx.Response,
    *,
    worker: RemoteHttpAudioWorker,
) -> None:
    if response.status_code < 400:
        return
    msg = f"remote audio HTTP {response.status_code}"
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
