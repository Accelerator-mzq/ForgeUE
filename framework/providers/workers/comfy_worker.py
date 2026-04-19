"""ComfyUI headless worker (§F3-1, §H).

Architecture: ComfyUI runs as an external HTTP server; this module speaks
JSON-over-HTTP to `/prompt` and polls `/history/<prompt_id>` for results.

Two implementations:
- HTTPComfyWorker : real adapter, imports `requests` lazily so tests/CI can
  import the framework without the dependency.
- FakeComfyWorker : deterministic scripted adapter used by tests and the
  offline P3 demo. Programs a queue of `list[ImageCandidate]` responses.

Candidates are returned as raw PNG bytes so the generate(image) executor can
hand them off to the File payload backend (§D.2 — images go to file, not inline).
"""
from __future__ import annotations

import hashlib
import io
import struct
import time
import zlib
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any


class WorkerError(RuntimeError):
    """Generic worker failure (bad request, upstream error)."""


class WorkerTimeout(WorkerError):
    """Worker exceeded wall-clock budget."""


@dataclass
class ImageCandidate:
    """One image result from a ComfyWorker call."""

    data: bytes                          # raw image bytes (PNG by default)
    width: int
    height: int
    seed: int
    mime_type: str = "image/png"
    format: str = "png"
    metadata: dict[str, Any] = field(default_factory=dict)


class ComfyWorker(ABC):
    """Adapter surface used by the generate(image) executor."""

    name: str = "comfy"

    @abstractmethod
    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        """Produce *num_candidates* images for *spec*. Must raise WorkerTimeout on timeout."""


# ----------------------------------------------------------------------------
# Fake worker — deterministic, offline, scriptable.
# ----------------------------------------------------------------------------


@dataclass
class _Script:
    """One scripted response for one `generate()` call."""

    candidates: list[ImageCandidate] | None = None
    raise_error: BaseException | None = None


class FakeComfyWorker(ComfyWorker):
    """Deterministic fake worker. Prefer explicit programming; falls back to
    synthesised stub PNGs derived from the spec + seed when unprogrammed.
    """

    name = "fake_comfy"

    def __init__(self) -> None:
        self._scripts: deque[_Script] = deque()
        self.calls: list[dict[str, Any]] = []

    # -- programming --

    def program(self, candidates: list[ImageCandidate]) -> None:
        self._scripts.append(_Script(candidates=list(candidates)))

    def program_error(self, exc: BaseException) -> None:
        self._scripts.append(_Script(raise_error=exc))

    # -- surface --

    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:
        self.calls.append({
            "spec": dict(spec),
            "num_candidates": num_candidates,
            "seed": seed,
            "timeout_s": timeout_s,
        })
        if self._scripts:
            script = self._scripts.popleft()
            if script.raise_error is not None:
                raise script.raise_error
            assert script.candidates is not None
            return list(script.candidates)
        return [
            _synth_candidate(spec=spec, index=i, seed=seed)
            for i in range(num_candidates)
        ]


def _synth_candidate(*, spec: dict[str, Any], index: int, seed: int | None) -> ImageCandidate:
    width = int(spec.get("width", 64))
    height = int(spec.get("height", 64))
    effective_seed = (seed or 0) + index
    # Derive a deterministic colour from (prompt_summary, seed, index).
    digest = hashlib.sha1(
        f"{spec.get('prompt_summary', '')}|{effective_seed}".encode("utf-8")
    ).digest()
    r, g, b = digest[0], digest[1], digest[2]
    data = _make_solid_png(width=width, height=height, rgb=(r, g, b))
    return ImageCandidate(
        data=data, width=width, height=height, seed=effective_seed,
        metadata={
            "prompt_summary": spec.get("prompt_summary"),
            "style_tags": list(spec.get("style_tags") or []),
            "synthetic": True,
            "rgb": [r, g, b],
            "index": index,
        },
    )


def _make_solid_png(*, width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Produce a minimal valid PNG of a solid colour. ~50 bytes for 1x1."""
    r, g, b = rgb
    raw = bytearray()
    row = bytes([0]) + bytes([r, g, b] * width)   # filter byte = 0, then RGB pixels
    for _ in range(height):
        raw += row
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        length = struct.pack(">I", len(payload))
        crc = struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        return length + tag + payload + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)   # 8-bit RGB
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    return bytes(png)


# ----------------------------------------------------------------------------
# HTTP worker — real ComfyUI /prompt integration (lazy-import requests).
# ----------------------------------------------------------------------------


class HTTPComfyWorker(ComfyWorker):
    """Minimal ComfyUI HTTP client. Requires a running ComfyUI server.

    Submits a workflow graph (caller-supplied via *spec['workflow_graph']*), polls
    `/history/<prompt_id>` until it resolves, then fetches each image from
    `/view?filename=...`. Most production setups will wrap this with a tighter
    contract, but this baseline covers the P3 demo path.
    """

    name = "http_comfy"

    def __init__(
        self,
        *,
        base_url: str,
        default_timeout_s: float = 120.0,
        poll_interval_s: float = 1.0,
        client_id: str = "forgeue",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_timeout_s = default_timeout_s
        self._poll_interval_s = poll_interval_s
        self._client_id = client_id

    def _import_requests(self):
        try:
            import requests  # type: ignore
        except ImportError as exc:   # pragma: no cover - import guard
            raise WorkerError(
                "`requests` is not installed. `pip install requests` to use HTTPComfyWorker."
            ) from exc
        return requests

    def generate(
        self,
        *,
        spec: dict[str, Any],
        num_candidates: int,
        seed: int | None = None,
        timeout_s: float | None = None,
    ) -> list[ImageCandidate]:  # pragma: no cover - real network
        requests = self._import_requests()
        graph = spec.get("workflow_graph")
        if graph is None:
            raise WorkerError("HTTPComfyWorker needs spec['workflow_graph'] (ComfyUI JSON)")

        submit_body = {"prompt": graph, "client_id": self._client_id}
        if seed is not None:
            submit_body.setdefault("extra_data", {})["seed"] = seed

        budget = timeout_s or self._default_timeout_s
        start = time.monotonic()
        try:
            resp = requests.post(
                f"{self._base_url}/prompt", json=submit_body, timeout=min(30.0, budget),
            )
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise WorkerTimeout(str(exc)) from exc
            raise WorkerError(str(exc)) from exc
        if resp.status_code != 200:
            raise WorkerError(f"ComfyUI /prompt {resp.status_code}: {resp.text[:200]}")
        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            raise WorkerError("ComfyUI /prompt did not return prompt_id")

        while True:
            if time.monotonic() - start > budget:
                raise WorkerTimeout(f"ComfyUI prompt_id={prompt_id} exceeded {budget}s")
            hist = requests.get(f"{self._base_url}/history/{prompt_id}", timeout=10.0)
            if hist.status_code == 200:
                data = hist.json().get(prompt_id)
                if data and data.get("outputs"):
                    return self._collect_outputs(requests, data["outputs"], spec=spec, seed=seed)
            time.sleep(self._poll_interval_s)

    def _collect_outputs(
        self, requests, outputs: dict, *, spec: dict, seed: int | None,
    ) -> list[ImageCandidate]:  # pragma: no cover - real network
        results: list[ImageCandidate] = []
        width = int(spec.get("width", 0))
        height = int(spec.get("height", 0))
        for node_id, node_out in outputs.items():
            for image_meta in node_out.get("images") or []:
                fname = image_meta.get("filename")
                if not fname:
                    continue
                r = requests.get(
                    f"{self._base_url}/view",
                    params={"filename": fname, "type": image_meta.get("type", "output"),
                            "subfolder": image_meta.get("subfolder", "")},
                    timeout=30.0,
                )
                if r.status_code != 200:
                    raise WorkerError(f"ComfyUI /view {r.status_code} for {fname}")
                results.append(ImageCandidate(
                    data=r.content, width=width, height=height, seed=seed or 0,
                    metadata={"node_id": node_id, "filename": fname, "source": "http_comfy"},
                ))
        if not results:
            raise WorkerError("ComfyUI returned no images")
        return results
