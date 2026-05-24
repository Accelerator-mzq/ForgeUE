from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_SCRIPTS_DIR = REPO_ROOT / "engine_scripts" / "unreal"
EXPECTED_SCRIPT_NAMES = {
    "a1_run.py",
    "domain_audio.py",
    "domain_material.py",
    "domain_mesh.py",
    "domain_texture.py",
    "domain_video.py",
    "evidence_writer.py",
    "manifest_reader.py",
    "run_import.py",
}


def test_engine_scripts_unreal_directory_contains_expected_entrypoints():
    assert ENGINE_SCRIPTS_DIR.is_dir()
    actual = {path.name for path in ENGINE_SCRIPTS_DIR.glob("*.py")}
    assert EXPECTED_SCRIPT_NAMES <= actual


def test_engine_scripts_unreal_do_not_import_framework_package():
    offenders: list[str] = []
    for path in ENGINE_SCRIPTS_DIR.glob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import framework") or stripped.startswith("from framework"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}:{line}")
    assert offenders == []


def test_engine_scripts_unreal_a1_run_docstring_uses_new_path():
    source = (ENGINE_SCRIPTS_DIR / "a1_run.py").read_text(encoding="utf-8")
    assert "engine_scripts" in source
    assert "ue_scripts" not in source
