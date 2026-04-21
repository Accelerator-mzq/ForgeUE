"""Tencent Hunyuan tokenhub adapter —— submit + poll + download 协议封装 (Plan C async).

腾讯混元图生 / 混元生 3D 的非 OpenAI 路径都走 `tokenhub.tencentmaas.com` 代理：
异步任务型 API,一次 submit 拿 job_id,轮询 query 直到 DONE,下载 URL 取 bytes。

抽象为 `TokenhubMixin` —— 图生 adapter 和 3D worker 共用 submit/poll/download。
Plan C 改为 async-first:底层走 `httpx.AsyncClient`,`time.sleep` 换 `asyncio.sleep`,
取消语义(`CancelledError`)从 poll 循环直接传播。
"""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
from pydantic import BaseModel

from framework.observability.event_bus import (
    ProgressEvent,
    current_run_step,
    publish as publish_event,
)
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


def _extract_progress_pct(resp: dict) -> float | None:
    """Best-effort dig for a progress percentage in a tokenhub /query response.
    Tokenhub field naming varies across models — try a few common keys."""
    for k in ("progress", "percent", "progress_percent", "percentage"):
        v = resp.get(k)
        if isinstance(v, (int, float)) and 0 <= v <= 100:
            return float(v)
    return None


def _dispatch_progress(cb, status: str, elapsed: float, raw_resp: dict) -> None:
    """Invoke a progress callback, tolerating both 2- and 3-arg signatures."""
    try:
        cb(status, elapsed, raw_resp)
    except TypeError:
        try:
            cb(status, elapsed)
        except Exception:
            pass
    except Exception:
        pass


class TokenhubMixin:
    """Shared async submit/poll/download helpers for tokenhub.tencentmaas.com."""

    _default_poll_interval_s: float = 3.0
    _default_timeout_s: float = 300.0
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    async def _th_post(self, url: str, *, key: str, body: dict, timeout_s: float) -> dict:
        """Async POST with Bearer auth and transient retry."""

        async def _attempt() -> dict:
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": self._UA,
            }
            payload = json.dumps(
                body, separators=(",", ":"), ensure_ascii=False,
            ).encode("utf-8")
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as c:
                    r = await c.post(url, headers=headers, content=payload)
            except httpx.TimeoutException as exc:
                raise ProviderTimeout(str(exc)) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(str(exc)) from exc

            if r.status_code >= 400:
                err_body = r.text
                raise ProviderError(
                    f"tokenhub {url} {r.status_code}: {err_body[:300]}"
                )
            return r.json()

        return await with_transient_retry_async(
            _attempt,
            transient_check=lambda e: isinstance(e, ProviderTimeout) or (
                isinstance(e, ProviderError)
                and is_transient_network_message(str(e))
            ),
            max_attempts=2, backoff_s=2.0,
        )

    async def _th_download(self, url: str, *, timeout_s: float = 60.0,
                            on_progress=None) -> bytes:
        """Async chunked download with HTTP Range resume."""
        from framework.providers._download_async import chunked_download_async
        try:
            return await chunked_download_async(
                url, timeout_s=timeout_s,
                headers={"User-Agent": self._UA},
                on_chunk=on_progress,
            )
        except Exception as exc:
            raise ProviderError(f"tokenhub download {url}: {exc}") from exc

    async def _th_submit(self, *, submit_url: str, key: str, model: str,
                          payload_extra: dict, timeout_s: float) -> str:
        body = {"model": model, **payload_extra}
        resp = await self._th_post(submit_url, key=key, body=body, timeout_s=timeout_s)
        status = str(resp.get("status", "")).lower()
        if status in ("failed", "fail", "error"):
            err = resp.get("error") or {}
            raise ProviderError(
                f"tokenhub submit failed: {err.get('message') or err or resp}"
            )
        job_id = resp.get("id") or resp.get("job_id")
        if not job_id:
            raise ProviderError(f"tokenhub submit returned no id: {resp}")
        return str(job_id)

    async def _th_poll(self, *, query_url: str, key: str, model: str, job_id: str,
                        budget_s: float, poll_interval_s: float | None = None,
                        on_progress=None) -> dict:
        """Async poll /query until terminal status.

        `await asyncio.sleep(interval)` between iterations — `CancelledError`
        propagates immediately so external timeouts / user-cancellation can
        abort the poll without waiting for *budget_s* to elapse.

        Progress callback signature is adaptive: 3-arg callers receive
        `(status, elapsed_s, raw_resp)`; legacy 2-arg callers still work.
        """
        interval = poll_interval_s or self._default_poll_interval_s
        loop = asyncio.get_running_loop()
        start = loop.time()
        while True:
            elapsed = loop.time() - start
            if elapsed > budget_s:
                raise ProviderTimeout(
                    f"tokenhub job {job_id} exceeded {budget_s}s (last poll at {elapsed:.1f}s)"
                )
            resp = await self._th_post(
                query_url, key=key,
                body={"model": model, "id": job_id}, timeout_s=20.0,
            )
            status = str(resp.get("status", "")).lower()
            if on_progress is not None:
                _dispatch_progress(on_progress, status, elapsed, resp)
            # Mirror to ambient EventBus if set (WebSocket subscribers)
            progress_pct = _extract_progress_pct(resp)
            rid, sid = current_run_step()
            publish_event(ProgressEvent(
                run_id=rid, step_id=sid, phase="tokenhub_poll",
                elapsed_s=elapsed, progress_pct=progress_pct,
                raw={"job_id": job_id, "status": status, "model": model},
            ))
            if status in ("done", "success", "finished", "completed"):
                return resp
            if status in ("failed", "fail", "error", "cancelled"):
                raise ProviderError(
                    f"tokenhub job {job_id} {status}: "
                    f"{resp.get('error') or resp.get('message') or resp}"
                )
            await asyncio.sleep(interval)

    @staticmethod
    def _extract_result_url(resp: dict, *, prefer_keys: tuple[str, ...] = (
        "url", "image_url", "result_url", "model_url", "pbr_model",
        "output_url", "file_url", "asset_url",
    )) -> str:
        """Find the downloadable result URL inside a tokenhub /query DONE response."""
        def _walk(node, prefer: list[str], other: list[str]) -> None:
            if isinstance(node, str):
                if node.startswith("http"):
                    other.append(node)
                return
            if isinstance(node, list):
                for item in node:
                    _walk(item, prefer, other)
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    if isinstance(v, str) and v.startswith("http"):
                        (prefer if k in prefer_keys else other).append(v)
                    else:
                        _walk(v, prefer, other)

        prefer_hits: list[str] = []
        other_hits: list[str] = []
        _walk(resp, prefer_hits, other_hits)
        if prefer_hits:
            return prefer_hits[0]
        if other_hits:
            return other_hits[0]
        raise ProviderError(
            f"tokenhub response has no recognizable result URL: "
            f"keys={list(resp)} sample={str(resp)[:400]}"
        )


# ----------------------------------------------------------------------------
# Image adapter
# ----------------------------------------------------------------------------


class HunyuanImageAdapter(TokenhubMixin, ProviderAdapter):
    """Hunyuan image gen / edit via tokenhub.tencentmaas.com (Bearer auth)."""

    name = "hunyuan_tokenhub"

    def supports(self, model: str) -> bool:
        return model.startswith("hunyuan/")

    async def acompletion(self, call: ProviderCall) -> ProviderResult:
        raise NotImplementedError(
            "HunyuanImageAdapter does not handle text completion; "
            "use LiteLLMAdapter with api_base=api.hunyuan.cloud.tencent.com"
        )

    async def astructured(
        self, call: ProviderCall, schema: type[BaseModel],
    ) -> BaseModel:
        raise NotImplementedError(
            "HunyuanImageAdapter does not handle structured text; "
            "use LiteLLMAdapter"
        )

    async def aimage_generation(
        self, *, prompt: str, model: str, n: int = 1,
        size: str = "1024x1024", api_key: str | None = None,
        api_base: str | None = None, timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> list[ImageResult]:
        if not api_key:
            raise ProviderError("HunyuanImageAdapter requires api_key (bearer token)")
        if not api_base:
            raise ProviderError("HunyuanImageAdapter requires api_base (tokenhub URL)")
        if n < 1:
            raise ProviderError(
                f"HunyuanImageAdapter: n must be >= 1 (got {n})"
            )
        raw_model = model.split("/", 1)[1] if "/" in model else model
        budget = timeout_s or self._default_timeout_s
        # tokenhub /submit only accepts a single prompt per call — pop
        # progress callbacks once up-front, then fan out N submit/poll/
        # download chains below. Each sibling shares the same callbacks
        # so UI layers see progress from every candidate.
        extra_clean: dict[str, Any] = dict(extra or {})
        on_poll_progress = extra_clean.pop("_forge_progress_cb", None)
        on_download_progress = extra_clean.pop("_forge_download_cb", None)
        submit_url = f"{api_base.rstrip('/')}/submit"
        query_url = f"{api_base.rstrip('/')}/query"

        async def _one(index: int) -> ImageResult:
            payload_extra: dict[str, Any] = {"prompt": prompt, **extra_clean}
            job_id = await self._th_submit(
                submit_url=submit_url, key=api_key, model=raw_model,
                payload_extra=payload_extra, timeout_s=min(30.0, budget),
            )
            done_resp = await self._th_poll(
                query_url=query_url, key=api_key, model=raw_model,
                job_id=job_id, budget_s=budget,
                on_progress=on_poll_progress,
            )
            result_url = self._extract_result_url(done_resp)
            img_bytes = await self._th_download(
                result_url, on_progress=on_download_progress,
            )
            return ImageResult(
                data=img_bytes, model=model,
                format="png", mime_type="image/png",
                raw={"job_id": job_id, "source_url": result_url,
                     "provider": "hunyuan_tokenhub",
                     "size_requested": size, "n_requested": n,
                     "candidate_index": index},
            )

        if n == 1:
            return [await _one(0)]
        # Fan out N parallel submit/poll/download chains. Overall latency
        # ≈ slowest candidate (not n × one_candidate). Matches the
        # HunyuanMeshWorker.agenerate shape for consistency.
        return list(await asyncio.gather(*[_one(i) for i in range(n)]))

    async def aimage_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        """Edit mode —— push source image in as b64 data URL under `image` key."""
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
