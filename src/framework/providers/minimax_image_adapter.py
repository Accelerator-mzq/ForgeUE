"""MiniMax `image_generation` 图片适配器。

只做最薄的一层协议适配:
- Bearer 认证
- `/v1/image_generation` POST
- `data.image_base64` 解码
- 结果统一成 `ImageResult`

MiniMax 官方文档只明确了 `image-01`、`prompt`、`aspect_ratio`、
`subject_reference` 与 `response_format=base64`，这里不擅自扩展协议。
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
from math import gcd
from typing import Any

import httpx
from pydantic import BaseModel

from framework.providers._retry_async import (
    is_transient_network_message,
    with_transient_retry_async,
)
from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderError,
    ProviderTimeout,
    ProviderUnsupportedResponse,
)


_UA = "ForgeUE/1.0 (+minimax_image_adapter)"
_DEFAULT_ENDPOINT = "https://api.minimaxi.com/v1/image_generation"


class MiniMaxImageAdapter(ProviderAdapter):
    """MiniMax 图片生成直连适配器。"""

    name = "minimax_image"

    def __init__(self, *, default_timeout_s: float = 120.0) -> None:
        self._default_timeout_s = default_timeout_s

    def supports(self, model: str) -> bool:
        return model.startswith("minimax/")

    async def acompletion(self, call: ProviderCall) -> Any:  # pragma: no cover - 图片专用适配器
        raise NotImplementedError(
            "MiniMaxImageAdapter does not handle text completion"
        )

    async def astructured(
        self, call: ProviderCall, schema: type[BaseModel],
    ) -> BaseModel:  # pragma: no cover - 图片专用适配器
        raise NotImplementedError(
            "MiniMaxImageAdapter does not handle structured text"
        )

    async def aimage_generation(
        self, *, prompt: str, model: str, n: int = 1,
        size: str = "1024x1024", api_key: str | None = None,
        api_base: str | None = None, timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> list[ImageResult]:
        if not api_key:
            raise ProviderError("MiniMaxImageAdapter requires api_key")
        if n < 1:
            raise ProviderError(f"MiniMaxImageAdapter: n must be >= 1 (got {n})")

        endpoint = (api_base or _DEFAULT_ENDPOINT).rstrip("/")
        raw_model = model.split("/", 1)[1] if "/" in model else model
        aspect_ratio = _aspect_ratio_for_size(
            str((extra or {}).get("aspect_ratio") or size),
        )
        response_format = str((extra or {}).get("response_format") or "base64")
        subject_reference = (extra or {}).get("subject_reference")
        budget = timeout_s or self._default_timeout_s

        async def _one(index: int) -> ImageResult:
            body: dict[str, Any] = {
                "model": raw_model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "response_format": response_format,
            }
            if subject_reference is not None:
                body["subject_reference"] = subject_reference
            resp = await _post_json(
                endpoint, api_key=api_key, body=body, timeout_s=budget,
            )
            return _extract_first_image_result(
                resp, model=model, candidate_index=index,
                aspect_ratio=aspect_ratio, response_format=response_format,
            )

        if n == 1:
            return [await _one(0)]
        return list(await asyncio.gather(*[_one(i) for i in range(n)]))

    async def aimage_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        """MiniMax 官方只明确了 reference-image 生成，这里不冒充通用编辑。"""
        raise NotImplementedError(
            "MiniMaxImageAdapter does not implement image_edit; "
            "use aimage_generation with subject_reference"
        )


def _aspect_ratio_for_size(size: str) -> str:
    """把 `1024x576` 这类尺寸收敛成 MiniMax 需要的 `16:9`。"""
    if ":" in size:
        return size
    if "*" in size:
        sep = "*"
    elif "x" in size:
        sep = "x"
    else:
        return "1:1"
    left, right = size.split(sep, 1)
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return "1:1"
    if width <= 0 or height <= 0:
        return "1:1"
    g = gcd(width, height)
    return f"{width // g}:{height // g}"


async def _post_json(
    url: str, *, api_key: str, body: dict, timeout_s: float,
) -> dict:
    """MiniMax 原生 POST。"""

    async def _attempt() -> dict:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as c:
                r = await c.post(
                    url,
                    headers=headers,
                    content=json.dumps(
                        body,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8"),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc)) from exc

        if r.status_code >= 400:
            raise ProviderError(
                f"MiniMax image_generation HTTP {r.status_code}: {r.text[:400]}"
            )
        try:
            payload = r.json()
        except ValueError as exc:
            raise ProviderUnsupportedResponse(
                f"MiniMax image_generation returned 200 but body is not JSON: "
                f"{r.text[:200]!r}"
            ) from exc

        base_resp = payload.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        if status_code not in (None, 0, "0"):
            raise ProviderError(
                f"MiniMax image_generation failed: "
                f"{base_resp.get('status_msg') or base_resp.get('message') or payload}"
            )
        return payload

    return await with_transient_retry_async(
        _attempt,
        transient_check=lambda e: not isinstance(
            e, ProviderUnsupportedResponse,
        ) and (
            isinstance(e, ProviderTimeout) or (
                isinstance(e, ProviderError)
                and is_transient_network_message(str(e))
            )
        ),
        max_attempts=2,
        backoff_s=2.0,
    )


def _extract_first_image_result(
    payload: dict, *, model: str, candidate_index: int,
    aspect_ratio: str, response_format: str,
) -> ImageResult:
    data = payload.get("data") or {}
    image_field = data.get("image_base64")
    if image_field is None:
        raise ProviderUnsupportedResponse(
            "MiniMax image_generation response missing data.image_base64"
        )

    if isinstance(image_field, str):
        encoded_items = [image_field]
    elif isinstance(image_field, list):
        encoded_items = [item for item in image_field if isinstance(item, str)]
    else:
        encoded_items = []
    if not encoded_items:
        raise ProviderUnsupportedResponse(
            "MiniMax image_generation response has no decodable image_base64"
        )

    try:
        data_bytes = base64.b64decode(encoded_items[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProviderUnsupportedResponse(
            "MiniMax image_generation image_base64 is not valid base64"
        ) from exc

    mime_type, fmt = _detect_image_format(data_bytes)
    raw = {
        "provider": "minimax_image",
        "minimax_model": payload.get("data", {}).get("model") or model.split("/", 1)[-1],
        "candidate_index": candidate_index,
        "aspect_ratio": aspect_ratio,
        "response_format": response_format,
        "returned_image_count": len(encoded_items),
    }
    for key in ("trace_id", "request_id"):
        if payload.get(key) is not None:
            raw[key] = payload[key]
    return ImageResult(
        data=data_bytes,
        model=model,
        format=fmt,
        mime_type=mime_type,
        raw=raw,
    )


def _detect_image_format(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpeg"
    return "image/jpeg", "jpeg"
