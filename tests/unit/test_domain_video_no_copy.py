"""tests/unit/test_domain_video_no_copy.py — domain_video.import_video_entry no-copy + source_uri 派生 + mismatch fence cluster.

OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.3:
1. 删 `shutil.copy2` + `movies_dir.mkdir`(framework Phase A.5 已 drop mp4 到 D12 final 位置)
2. `FileMediaSource.file_path` 从 `entry["source_uri"]` 派生(round 1 codex F3 修订:
   消除"验证一个 path / 引用另一个 path"latent design smell — 单源 truth)
3. mismatch fence:source_uri 反推 `(run_id, ue_name)` 与 target_object_path 反推
   必须相等(守门 manifest bug / hand-edit / re-run race)
4. source_uri 必须 startswith `Content/Movies/` AND 3-part(D12 layout 校验)
"""
import shutil
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def stub_unreal(monkeypatch):
    """stub `unreal` 模块 — 模拟 FileMediaSource asset 创建 + set_editor_property 拦截"""
    fake = types.ModuleType("unreal")

    class FakeAsset:
        def __init__(self):
            self._props = {}

        def set_editor_property(self, key, value):
            self._props[key] = value

        def get_outer(self):
            return None  # 简化 — 不触发 save_loaded_asset

    class FakeAssetTools:
        def __init__(self):
            self.create_calls = []
            self._asset = FakeAsset()

        def create_asset(self, asset_name, package_path, asset_class, factory):
            self.create_calls.append((asset_name, package_path, asset_class, factory))
            return self._asset

    fake_asset_tools = FakeAssetTools()

    class FakeAssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return fake_asset_tools

    class FakeEditorAssetLibrary:
        @staticmethod
        def does_directory_exist(folder):
            return True

        @staticmethod
        def make_directory(folder):
            pass

        @staticmethod
        def save_loaded_asset(asset):
            pass

    fake.AssetToolsHelpers = FakeAssetToolsHelpers
    fake.FileMediaSourceFactoryNew = type("FakeFactory", (), {})
    fake.FileMediaSource = type("FakeFileMediaSource", (), {})
    fake.EditorAssetLibrary = FakeEditorAssetLibrary

    monkeypatch.setitem(sys.modules, "unreal", fake)
    fake._asset_tools = fake_asset_tools  # expose for test inspection
    yield fake


@pytest.fixture
def domain_video(stub_unreal):
    """加 ue_scripts/ 到 sys.path + 清缓存 + 返 domain_video 模块"""
    ue_scripts_dir = Path(__file__).resolve().parent.parent.parent / "ue_scripts"
    if str(ue_scripts_dir) not in sys.path:
        sys.path.insert(0, str(ue_scripts_dir))
    sys.modules.pop("domain_video", None)
    import domain_video as dv
    yield dv
    sys.modules.pop("domain_video", None)


def _make_d12_mp4(tmp_path: Path, run_id: str, ue_name: str) -> Path:
    """模拟 framework Phase A.5 已落 mp4 到 D12 路径(Content/Movies/<run_id>/<ue_name>.mp4)"""
    movies_dir = tmp_path / "Content" / "Movies" / run_id
    movies_dir.mkdir(parents=True, exist_ok=True)
    mp4 = movies_dir / f"{ue_name}.mp4"
    mp4.write_bytes(b"fake mp4 data")
    return mp4


def test_domain_video_does_not_invoke_shutil_copy2(tmp_path, stub_unreal, domain_video, monkeypatch):
    """框架已 drop;UE 端不再 copy(round 1 codex F3 G4 删 copy)"""
    called = []
    monkeypatch.setattr(shutil, "copy2", lambda *a, **kw: called.append((a, kw)))
    _make_d12_mp4(tmp_path, "run_a", "MS_Scene1")
    entry = {
        "asset_entry_id": "ae_1", "asset_kind": "file_media_source",
        "source_uri": "Content/Movies/run_a/MS_Scene1.mp4",
        "target_object_path": "/Game/Generated/T/run_a/MS_Scene1",
        "target_package_path": "/Game/Generated/T/run_a/MS_Scene1",
        "ue_naming": {"prefix": "MS_", "ue_name": "MS_Scene1", "base_name": "Scene1"},
        "import_options": {},
    }
    result = domain_video.import_video_entry(entry, project_root=str(tmp_path))
    assert result["status"] == "success", f"expected success, got {result}"
    assert called == [], f"shutil.copy2 should NOT be invoked, was called {called}"


def test_domain_video_file_path_derived_from_source_uri(tmp_path, stub_unreal, domain_video):
    """round 1 codex F3 fence:set_editor_property('file_path', ...) value 等于 source_uri 去 'Content/' 前缀"""
    _make_d12_mp4(tmp_path, "run_a", "MS_Scene1")
    entry = {
        "asset_entry_id": "ae_1", "asset_kind": "file_media_source",
        "source_uri": "Content/Movies/run_a/MS_Scene1.mp4",
        "target_object_path": "/Game/Generated/T/run_a/MS_Scene1",
        "target_package_path": "/Game/Generated/T/run_a/MS_Scene1",
        "ue_naming": {"prefix": "MS_", "ue_name": "MS_Scene1", "base_name": "Scene1"},
        "import_options": {},
    }
    domain_video.import_video_entry(entry, project_root=str(tmp_path))
    asset = stub_unreal._asset_tools._asset
    # 派生路径:source_uri "Content/Movies/run_a/MS_Scene1.mp4" 去 "Content/" 前缀
    assert asset._props["file_path"] == "Movies/run_a/MS_Scene1.mp4"


def test_domain_video_rejects_non_d12_source_uri(tmp_path, stub_unreal, domain_video):
    """round 1 codex F3:source_uri 不以 'Content/Movies/' 起首 → return failed"""
    # legacy / hand-edit 场景:source_uri 在 Generated/ 而非 Movies/
    movies_dir = tmp_path / "Content" / "Generated" / "run_a"
    movies_dir.mkdir(parents=True, exist_ok=True)
    (movies_dir / "MS_Scene1.mp4").write_bytes(b"fake")
    entry = {
        "asset_entry_id": "ae_1", "asset_kind": "file_media_source",
        "source_uri": "Content/Generated/run_a/MS_Scene1.mp4",
        "target_object_path": "/Game/Generated/T/run_a/MS_Scene1",
        "target_package_path": "/Game/Generated/T/run_a/MS_Scene1",
        "ue_naming": {"prefix": "MS_", "ue_name": "MS_Scene1", "base_name": "Scene1"},
        "import_options": {},
    }
    result = domain_video.import_video_entry(entry, project_root=str(tmp_path))
    assert result["status"] == "failed"
    assert "D12" in result.get("error", "") or "Movies" in result.get("error", "")


def test_domain_video_returns_failed_on_source_target_mismatch(tmp_path, stub_unreal, domain_video):
    """round 1 codex F3:source_uri 反推 (run_id, ue_name) 与 target 反推不等 → failed"""
    _make_d12_mp4(tmp_path, "run_a", "MS_Scene1")  # source 物理存在
    entry = {
        "asset_entry_id": "ae_1", "asset_kind": "file_media_source",
        "source_uri": "Content/Movies/run_a/MS_Scene1.mp4",  # source: run_a / MS_Scene1
        "target_object_path": "/Game/Generated/T/run_b/MS_Scene2",  # target: run_b / MS_Scene2 mismatch
        "target_package_path": "/Game/Generated/T/run_b/MS_Scene2",
        "ue_naming": {"prefix": "MS_", "ue_name": "MS_Scene2", "base_name": "Scene2"},
        "import_options": {},
    }
    result = domain_video.import_video_entry(entry, project_root=str(tmp_path))
    assert result["status"] == "failed"
    assert "mismatch" in result.get("error", "").lower()


def test_domain_video_returns_failed_when_source_mp4_missing(tmp_path, stub_unreal, domain_video):
    """source_uri 物理文件不存在 → failed(防御路径)"""
    # 不创建 mp4 文件
    entry = {
        "asset_entry_id": "ae_1", "asset_kind": "file_media_source",
        "source_uri": "Content/Movies/run_a/MS_NotExist.mp4",
        "target_object_path": "/Game/Generated/T/run_a/MS_NotExist",
        "target_package_path": "/Game/Generated/T/run_a/MS_NotExist",
        "ue_naming": {"prefix": "MS_", "ue_name": "MS_NotExist", "base_name": "NotExist"},
        "import_options": {},
    }
    result = domain_video.import_video_entry(entry, project_root=str(tmp_path))
    assert result["status"] == "failed"
    assert "not found" in result.get("error", "").lower() or "missing" in result.get("error", "").lower()
