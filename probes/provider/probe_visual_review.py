"""Opt-in live probe: real providers' visual review打分 on fixture PNGs.

TBD-008 (2026-04-22) Phase C — the offline契约 layer
(test_p2/p3/l4 with fixture images + FakeAdapter scripted ranking) proves
the pipeline correctly routes scored candidates to verdicts. This probe
is the SEPARATE质量 layer: does a REAL provider's visual judge produce
sensible打分 distribution on real Qwen PNGs?

Opt-in: `FORGEUE_PROBE_VISUAL_REVIEW=1` to run. Without the flag the probe
SKIPs — keeps CI / casual `python -m probes.provider` runs free.

What this probe does:
- Load 3 fixture PNGs (`tests/fixtures/review_images/tavern_door_v{1,2,3}.png`)
- Build a temporary ArtifactRepository + StepContext per judge
- Call `ReviewExecutor.execute()` twice:
  - Round 1: `review_judge` alias → Anthropic Opus 4.6 via PackyCode
  - Round 2: `review_judge_visual` alias → GLM-4.6V (Zhipu)
- Dump per-judge report + verdict to `demo_artifacts/<today>/probes/
  provider/visual_review/<HHMMSS>/`
- Print ASCII comparison table (per-candidate 5-dim scores + winner)

Cost: one call per judge (~$0.01-0.05 each) × 3 fixture candidates.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# TBD-008 Codex R2 fix (2026-04-22): Windows GBK console crashes on Chinese
# / special punctuation (… ⋯ 中文) in print output. Mirror the pattern from
# `probes/smoke/probe_framework.py:21` so live-review output is safe on
# default PowerShell / cmd consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _out_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "visual_review" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


def _seed_fixtures(repo, run_id: str) -> list[tuple[str, str]]:
    """Seed 3 fixture PNGs into repo as file-backed image artifacts.

    Returns [(artifact_id, fixture_name), ...]."""
    from framework.core.artifact import ArtifactType, ProducerRef
    from framework.core.enums import ArtifactRole, PayloadKind
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.fixtures import load_review_image

    out = []
    for i, fixture in enumerate(
        ["tavern_door_v1", "tavern_door_v2", "tavern_door_v3"]
    ):
        aid = f"{run_id}_cand_{i}"
        repo.put(
            artifact_id=aid, value=load_review_image(fixture),
            artifact_type=ArtifactType(
                modality="image", shape="raster", display_name="concept_image"),
            role=ArtifactRole.intermediate,
            format="png", mime_type="image/png",
            payload_kind=PayloadKind.file,
            producer=ProducerRef(run_id=run_id, step_id="upstream", provider="fixture"),
            file_suffix=".png",
        )
        out.append((aid, fixture))
    return out


def _run_review(alias_name: str, artifact_ids: list[str], run_id: str,
                 repo, *, out_dir: Path) -> dict:
    """Resolve alias → ProviderPolicy, drive ReviewExecutor once, dump report."""
    from datetime import datetime, timezone
    from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
    from framework.core.policies import ProviderPolicy, PreparedRoute
    from framework.core.task import Run, Step, Task
    from framework.providers import CapabilityRouter
    from framework.providers.litellm_adapter import LiteLLMAdapter
    from framework.providers.model_registry import get_model_registry
    from framework.runtime.executors.base import StepContext
    from framework.runtime.executors import ReviewExecutor

    # Resolve alias → list of prepared routes
    reg = get_model_registry()
    alias = reg.resolve(alias_name)
    # TBD-008 Codex R1 fix (2026-04-22): pricing fields are
    # `input_per_1k_usd` / `output_per_1k_usd` / `per_image_usd` /
    # `per_task_usd` per `ModelPricing` dataclass (model_registry.py:106-109).
    # Prior buggy version used `*_per_1m` fields that don't exist and early-
    # returned after first non-None, dropping output_per_1k_usd. `to_dict()`
    # already drops None entries; BudgetTracker keys off the full pricing
    # shape so both fields must flow.
    routes = [PreparedRoute(
        model=r.model, api_key_env=r.api_key_env, api_base=r.api_base,
        kind=r.kind,
        pricing=r.pricing.to_dict() if r.pricing else None,
    ) for r in alias.routes()]

    # Router: QwenMultimodalAdapter (for qwen/ prefix) + LiteLLMAdapter wildcard
    router = CapabilityRouter()
    from framework.providers.qwen_multimodal_adapter import QwenMultimodalAdapter
    router.register(QwenMultimodalAdapter())
    router.register(LiteLLMAdapter())

    step = Step(
        step_id="step_review", type=StepType.review, name="review",
        risk_level=RiskLevel.medium, capability_ref="review.judge",
        provider_policy=ProviderPolicy(
            capability_required="review.judge",
            prepared_routes=routes,
        ),
        config={
            "review_mode": "single_judge",
            "review_scope": "image",
            "review_id": f"probe_{alias_name}",
            "rubric_ref": "ue_visual_quality",
            "selection_policy": "single_best",
            "visual_mode": True,
            "compress_images": True,
            "compress_max_dim": 768,
            "compress_quality": 80,
            "compress_threshold_bytes": 256 * 1024,
        },
    )
    task = Task(
        task_id="t_probe", task_type=TaskType.asset_review,
        run_mode=RunMode.standalone_review, title="probe",
        input_payload={}, expected_output={}, project_id="p_probe",
    )
    run = Run(
        run_id=run_id, task_id="t_probe", project_id="p_probe",
        status=RunStatus.running, started_at=datetime.now(timezone.utc),
        workflow_id="w_probe", trace_id="tr_probe",
    )
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=artifact_ids,
    )

    print(f"[.. ] {alias_name} review starting …")
    try:
        result = ReviewExecutor(router=router).execute(ctx)
    except Exception as exc:
        print(f"[FAIL] {alias_name}: {type(exc).__name__}: {exc}")
        return {"alias": alias_name, "error": str(exc)}

    report_art = next((a for a in result.artifacts
                        if a.artifact_type.shape == "review"), None)
    verdict_art = next((a for a in result.artifacts
                         if a.artifact_type.shape == "verdict"), None)
    report_payload = repo.read_payload(report_art.artifact_id) if report_art else None
    verdict_payload = repo.read_payload(verdict_art.artifact_id) if verdict_art else None

    out_file = out_dir / f"{alias_name}.json"
    out_file.write_text(
        json.dumps({
            "alias": alias_name,
            "routes": [r.model for r in routes],
            "report": report_payload,
            "verdict": verdict_payload,
            "metrics": result.metrics,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    winner = (verdict_payload or {}).get("selected_candidate_ids") or []
    confidence = (verdict_payload or {}).get("confidence")
    print(f"[OK ] {alias_name}: decision={verdict_payload.get('decision', '?')!r} "
          f"winner={winner} confidence={confidence!r}")
    return {
        "alias": alias_name,
        "report": report_payload,
        "verdict": verdict_payload,
    }


def _print_comparison(results: list[dict], fixture_map: list[tuple[str, str]]) -> str:
    """ASCII table comparing per-candidate 5-dim scores across judges."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("  Visual review judge comparison (TBD-008 Phase C probe)")
    lines.append("=" * 80)
    dims = ["constraint_fit", "style_consistency", "production_readiness",
            "technical_validity", "risk_score"]

    for cand_id, fixture in fixture_map:
        lines.append(f"\n{cand_id} ({fixture}.png):")
        lines.append(f"  {'dimension':<22} " + "  ".join(
            f"{r['alias']:>25}" for r in results if 'report' in r))
        for dim in dims:
            row = f"  {dim:<22} "
            for r in results:
                if 'report' not in r or r['report'] is None:
                    row += f"  {'-':>25}"
                    continue
                scores = (r['report'].get('scores_by_candidate') or {}).get(cand_id) or {}
                val = scores.get(dim)
                row += f"  {('%.2f' % val if val is not None else '-'):>25}"
            lines.append(row)

    lines.append("\n" + "-" * 80)
    lines.append("  Verdicts:")
    for r in results:
        v = r.get('verdict') or {}
        lines.append(f"    {r['alias']:<25} "
                     f"decision={v.get('decision', '?'):<12} "
                     f"winner={v.get('selected_candidate_ids') or []} "
                     f"conf={v.get('confidence', '?')!r}")
    lines.append("=" * 80)
    return "\n".join(lines)


def main() -> int:
    if os.environ.get("FORGEUE_PROBE_VISUAL_REVIEW") != "1":
        print("[SKIP] probe opt-in: set FORGEUE_PROBE_VISUAL_REVIEW=1 to run "
              "(makes ~2 paid review calls to Anthropic/PackyCode + Zhipu/GLM)")
        return 0

    # TBD-008 Codex R2 fix (2026-04-22): use the project-standard hydrate_env
    # which strips wrapping quotes from values (`KEY="value"` / `KEY='value'`).
    # The previous hand-rolled splitter would pass `"..."` through unchanged,
    # causing the live review call to auth-fail with a malformed token.
    from framework.observability.secrets import hydrate_env
    hydrate_env()
    missing = [k for k in ("PACKYCODE_KEY", "ZHIPU_API_KEY")
                if not os.environ.get(k)]
    if missing:
        print(f"[SKIP] missing env keys: {missing} — need at least these to run "
              "review_judge (Anthropic via PackyCode) + review_judge_visual (GLM)")
        return 0

    out_dir = _out_dir()
    print(f"[OK ] output dir: {out_dir}")

    from framework.artifact_store import ArtifactRepository, get_backend_registry
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_root:
        reg_backend = get_backend_registry(artifact_root=str(tmp_root))
        repo = ArtifactRepository(backend_registry=reg_backend)
        run_id = "probe_visual_review"

        fixture_map = _seed_fixtures(repo, run_id)
        artifact_ids = [aid for aid, _ in fixture_map]

        results: list[dict] = []
        for alias_name in ("review_judge", "review_judge_visual"):
            results.append(
                _run_review(alias_name, artifact_ids, run_id, repo,
                             out_dir=out_dir)
            )

    table = _print_comparison(results, fixture_map)
    print("\n" + table)
    table_file = out_dir / "comparison_table.md"
    table_file.write_text(f"```\n{table}\n```\n", encoding="utf-8")
    print(f"\n[OK ] comparison table: {table_file}")

    # Probe is for eyeballing judge discriminative power — no hard assertions.
    # Exit non-zero only if BOTH judges failed entirely.
    if all("error" in r for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
