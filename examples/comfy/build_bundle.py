"""Build examples/comfy_local_smoke.json from tavern_door.api.json.

ComfyUI workflow_graph (API format) cannot be referenced by file from a
TaskBundle — `_resolve_spec` only reads inline dicts. This helper inlines
the workflow into a minimal single-step bundle so `framework.run --comfy-url`
can drive it.

Usage:
    python examples/comfy/build_bundle.py

Re-run after editing tavern_door.api.json to regenerate the bundle.
Override defaults via env vars:
    FORGEUE_COMFY_WIDTH=512 FORGEUE_COMFY_HEIGHT=512 \
        FORGEUE_COMFY_PROMPT="custom artifact metadata prompt" \
        FORGEUE_COMFY_BATCH_SIZE=3 \
        python examples/comfy/build_bundle.py

`FORGEUE_COMFY_BATCH_SIZE > 1` patches every EmptyLatentImage node's
batch_size in the inlined workflow_graph and aligns the bundle's
num_candidates so framework artifact bookkeeping matches what ComfyUI
will actually produce in one /prompt call.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / "examples" / "comfy" / "tavern_door.api.json"
BUNDLE_PATH = REPO_ROOT / "examples" / "comfy_local_smoke.json"

# Defaults match the current tavern_door.api.json (SD 1.5, 512x512, cat prompt).
# Override per-run via env if you swap workflows.
DEFAULT_WIDTH = int(os.environ.get("FORGEUE_COMFY_WIDTH", "512"))
DEFAULT_HEIGHT = int(os.environ.get("FORGEUE_COMFY_HEIGHT", "512"))
DEFAULT_PROMPT = os.environ.get(
    "FORGEUE_COMFY_PROMPT",
    "ComfyUI local smoke (real prompt lives in workflow_graph CLIPTextEncode node)",
)
DEFAULT_BATCH_SIZE = max(1, int(os.environ.get("FORGEUE_COMFY_BATCH_SIZE", "1")))
SEED_OVERRIDE = os.environ.get("FORGEUE_COMFY_SEED")  # None or numeric str


def _patch_batch_size(workflow_graph: dict, batch_size: int) -> int:
    """Set every EmptyLatentImage node's batch_size. Returns nodes patched."""
    if batch_size <= 1:
        return 0
    n = 0
    for node in workflow_graph.values():
        if isinstance(node, dict) and node.get("class_type") == "EmptyLatentImage":
            node.setdefault("inputs", {})["batch_size"] = batch_size
            n += 1
    return n


def _patch_seed(workflow_graph: dict, seed: int) -> int:
    """Set every KSampler-style node's seed. Returns nodes patched."""
    n = 0
    for node in workflow_graph.values():
        if isinstance(node, dict) and node.get("class_type", "").startswith("KSampler"):
            node.setdefault("inputs", {})["seed"] = seed
            n += 1
    return n


def main() -> int:
    if not WORKFLOW_PATH.exists():
        print(f"[FAIL] workflow not found: {WORKFLOW_PATH}")
        return 1
    workflow_graph = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    if not isinstance(workflow_graph, dict) or "nodes" in workflow_graph:
        print(
            "[FAIL] tavern_door.api.json looks like UI workflow format "
            "(contains 'nodes' / 'links'). Re-export from ComfyUI using "
            "Save (API Format)."
        )
        return 1

    patched = _patch_batch_size(workflow_graph, DEFAULT_BATCH_SIZE)
    if DEFAULT_BATCH_SIZE > 1 and patched == 0:
        print(
            f"[WARN] FORGEUE_COMFY_BATCH_SIZE={DEFAULT_BATCH_SIZE} but no "
            "EmptyLatentImage node found — workflow may use a non-standard "
            "latent source (e.g. img2img). batch will stay 1."
        )

    seed_used: int | None = None
    if SEED_OVERRIDE is not None:
        try:
            seed_used = int(SEED_OVERRIDE)
        except ValueError:
            print(f"[FAIL] FORGEUE_COMFY_SEED={SEED_OVERRIDE!r} is not an integer")
            return 1
        n_patched_seed = _patch_seed(workflow_graph, seed_used)
        if n_patched_seed == 0:
            print(
                f"[WARN] FORGEUE_COMFY_SEED={seed_used} set but no KSampler* "
                "node found — seed unchanged."
            )

    bundle = {
        "task": {
            "task_id": "task_comfy_smoke",
            "task_type": "asset_generation",
            "run_mode": "basic_llm",
            "title": "Local ComfyUI smoke (HTTPComfyWorker, single step)",
            "input_payload": {"prompt": DEFAULT_PROMPT},
            "expected_output": {
                "artifact_types": ["concept_image", "candidate_bundle"],
            },
            "project_id": "proj_comfy_smoke",
        },
        "workflow": {
            "workflow_id": "wf_comfy_smoke",
            "name": "comfy_smoke",
            "version": "1.0.0",
            "entry_step_id": "step_image",
            "step_ids": ["step_image"],
        },
        "steps": [
            {
                "step_id": "step_image",
                "type": "generate",
                "name": "comfy-local-txt2img",
                "risk_level": "medium",
                "capability_ref": "image.generation",
                "config": {
                    "num_candidates": DEFAULT_BATCH_SIZE,
                    "seed": 17,
                    "worker_timeout_s": 300,
                    "model_hint": "comfy-local",
                    "spec": {
                        "prompt_summary": DEFAULT_PROMPT,
                        "width": DEFAULT_WIDTH,
                        "height": DEFAULT_HEIGHT,
                        "workflow_graph": workflow_graph,
                    },
                },
            },
        ],
    }
    BUNDLE_PATH.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    n_nodes = len(workflow_graph)
    rel = BUNDLE_PATH.relative_to(REPO_ROOT)
    seed_str = f", seed={seed_used}" if seed_used is not None else ""
    print(
        f"[OK] wrote {rel} ({n_nodes} nodes inlined, "
        f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}, batch_size={DEFAULT_BATCH_SIZE}{seed_str})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
