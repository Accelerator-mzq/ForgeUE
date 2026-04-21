"""Probe 输出目录 helper。

调用方:所有 `probes/smoke/*.py` 与 `probes/provider/*.py` 里的 `main()` 或
运行期 helper,用来拿一个"按日期 + 时间戳分桶"的写入目录。

约定(见 `probes/README.md`):
    ./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/

- `<tier>` ∈ {"smoke", "provider"},对应 `probes/` 下的子目录
- `<name>` 是 probe 基名(去掉 `probe_` 前缀),例如 `framework` / `glm_image_debug`
- `<HHMMSS>` 是本次 run 的启动时间戳;同一秒多次 run 会复用同一目录(极少见)

使用方式:

    from probes._output import probe_output_dir

    def main() -> None:
        out_dir = probe_output_dir("provider", "glm_image_debug")
        (out_dir / "result.png").write_bytes(img)
        print(f"[OK] wrote {out_dir}/result.png")

`mkdir(parents=True, exist_ok=True)` 已在 helper 内做好,caller 直接写文件即可。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

_BASE = Path("./demo_artifacts")
Tier = Literal["smoke", "provider"]


def probe_output_dir(tier: Tier, name: str, *, base: Path | None = None) -> Path:
    """Return a run-scoped output directory for a probe script.

    Args:
        tier: "smoke" or "provider" — matches the probe's subdir under probes/.
        name: probe basename without the "probe_" prefix (e.g. "framework",
              "glm_image_debug", "hunyuan_3d_format").
        base: optional override, defaults to ./demo_artifacts.

    Returns:
        A Path like ./demo_artifacts/2026-04-22/probes/provider/glm_image_debug/143012/
        The directory is created if it does not exist.
    """
    if tier not in ("smoke", "provider"):
        raise ValueError(f"tier must be 'smoke' or 'provider', got {tier!r}")
    if not name or name.startswith("probe_"):
        raise ValueError(
            f"name must be probe basename without 'probe_' prefix, got {name!r}"
        )

    now = datetime.now()
    root = base if base is not None else _BASE
    out = (
        root
        / now.strftime("%Y-%m-%d")
        / "probes"
        / tier
        / name
        / now.strftime("%H%M%S")
    )
    out.mkdir(parents=True, exist_ok=True)
    return out
