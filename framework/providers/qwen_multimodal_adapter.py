"""Alibaba DashScope multimodal-generation adapter —— Qwen-Image / Qwen-Image-Edit.

Qwen-Image 不走 OpenAI `/v1/images/generations`，而是 DashScope 私有多模态端点：

    POST https://dashscope.aliyuncs.com/api/v1/services/aigc/
         multimodal-generation/generation
    {
      "model": "qwen-image-2.0-pro",
      "input": {
        "messages": [
          {"role":"user", "content":[
            {"text": "<prompt>"},
            {"image": "<url_or_base64_data_url>"}       # optional, for edit
          ]}
        ]
      },
      "parameters": {"n": 1, "size": "1024*1024", ...}
    }

响应:
    {"output":{"choices":[{"message":{"content":[{"image":"<url>"}]}}]}}

URL 短期（24h）有效，adapter 自己下载成 bytes 再返回给 caller —— 对外
看起来是同步 ImageResult 列表，跟其它 adapter 一致。
"""
from __future__ import annotations

import asyncio
import base64
import json
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
    ProviderResult,
    ProviderTimeout,
)


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

_DASHSCOPE_MULTIMODAL_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
    "multimodal-generation/generation"
)
_DASHSCOPE_MULTIMODAL_URL_INTL = (
    "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/"
    "multimodal-generation/generation"
)


class QwenMultimodalAdapter(ProviderAdapter):
    """Ali DashScope multimodal-generation for Qwen-Image / Qwen-Image-Edit.

    `supports(model)` matches `qwen/...` prefix. Text paths NotImplementedError
    —— Qwen text chat goes through LiteLLMAdapter with DashScope compatible-mode
    (different endpoint).
    """

    name = "qwen_multimodal"

    def __init__(self, *, intl: bool = False, default_timeout_s: float = 120.0) -> None:
        self._endpoint = _DASHSCOPE_MULTIMODAL_URL_INTL if intl else _DASHSCOPE_MULTIMODAL_URL
        self._default_timeout_s = default_timeout_s

    def supports(self, model: str) -> bool:
        return model.startswith("qwen/")

    async def acompletion(self, call: ProviderCall) -> ProviderResult:
        raise NotImplementedError(
            "QwenMultimodalAdapter only handles image / image_edit; "
            "use LiteLLMAdapter with DashScope compatible-mode for Qwen text chat"
        )

    async def astructured(
        self, call: ProviderCall, schema: type[BaseModel],
    ) -> BaseModel:
        raise NotImplementedError(
            "QwenMultimodalAdapter does not handle structured text; use LiteLLMAdapter"
        )

    async def aimage_generation(
        self, *, prompt: str, model: str, n: int = 1,
        size: str = "1024x1024", api_key: str | None = None,
        api_base: str | None = None, timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> list[ImageResult]:
        if not api_key:
            raise ProviderError("QwenMultimodalAdapter requires api_key")
        raw_model = model.split("/", 1)[1] if "/" in model else model

        dash_size = size.replace("x", "*") if "x" in size else size

        content: list[dict[str, Any]] = []
        if extra and extra.get("image"):
            content.append({"image": extra["image"]})
        content.append({"text": prompt})

        body = {
            "model": raw_model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": _build_parameters(n=n, size=dash_size, extra=extra),
        }
        resp = await _adashscope_post(
            self._endpoint, api_key=api_key, body=body,
            timeout_s=timeout_s or self._default_timeout_s,
        )
        return await _aextract_image_results(resp, model=model)

    async def aimage_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        extra = dict(extra or {})
        extra.setdefault(
            "image",
            f"data:image/png;base64,{base64.b64encode(source_image_bytes).decode('ascii')}",
        )
        return await self.aimage_generation(
            prompt=prompt, model=model, n=n, size=size,
            api_key=api_key, api_base=api_base,
            timeout_s=timeout_s, extra=extra,
        )


# ---- helpers ----------------------------------------------------------------

def _build_parameters(*, n: int, size: str, extra: dict | None) -> dict:
    params: dict[str, Any] = {"n": n, "size": size}
    if extra:
        # Well-known DashScope parameters
        for k in ("negative_prompt", "prompt_extend", "watermark", "seed"):
            if k in extra:
                params[k] = extra[k]
    return params


async def _adashscope_post(
    url: str, *, api_key: str, body: dict, timeout_s: float,
) -> dict:
    """Async POST to DashScope with transient retry."""

    async def _attempt() -> dict:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as c:
                r = await c.post(url, headers=headers, content=json.dumps(
                    body, separators=(",", ":"), ensure_ascii=False,
                ).encode("utf-8"))
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc)) from exc

        if r.status_code >= 400:
            err_body = r.text
            raise ProviderError(f"DashScope {r.status_code}: {err_body[:400]}")
        return r.json()

    return await with_transient_retry_async(
        _attempt,
        transient_check=lambda e: isinstance(e, ProviderTimeout) or (
            isinstance(e, ProviderError)
            and is_transient_network_message(str(e))
        ),
        max_attempts=2, backoff_s=2.0,
    )


async def _aextract_image_results(resp: dict, *, model: str) -> list[ImageResult]:
    output = resp.get("output") or {}
    choices = output.get("choices") or []
    if not choices:
        err = resp.get("message") or resp.get("code") or str(resp)[:300]
        raise ProviderError(f"DashScope multimodal returned no choices: {err}")

    # Collect URLs first, then download concurrently via asyncio.gather
    urls: list[str] = []
    for ch in choices:
        msg = ch.get("message") or {}
        content = msg.get("content") or []
        for block in content:
            url = block.get("image")
            if isinstance(url, str):
                urls.append(url)
    if not urls:
        raise ProviderError(
            f"DashScope multimodal response had choices but no image content: "
            f"{str(choices)[:300]}"
        )
    images = await asyncio.gather(*[_adownload(u) for u in urls])
    return [
        ImageResult(
            data=img, model=model, format="png", mime_type="image/png",
            raw={"source_url": u, "provider": "qwen_multimodal",
                 "usage": resp.get("usage"), "request_id": resp.get("request_id")},
        )
        for u, img in zip(urls, images)
    ]


async def _adownload(url: str, *, timeout_s: float = 60.0, on_progress=None) -> bytes:
    from framework.providers._download_async import chunked_download_async
    try:
        return await chunked_download_async(
            url, timeout_s=timeout_s, headers={"User-Agent": _UA},
            on_chunk=on_progress,
        )
    except Exception as exc:
        raise ProviderError(f"DashScope result download {url}: {exc}") from exc
