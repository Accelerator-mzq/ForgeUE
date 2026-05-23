"""FOR-26 framework.run remote audio worker wiring tests。"""
from __future__ import annotations

from framework.core.enums import RiskLevel, StepType
from framework.core.task import Step
from framework.providers.workers.minimax_music_worker import MiniMaxMusicWorker
from framework.providers.workers.remote_audio_worker import RemoteHttpAudioWorker
from framework.runtime.executors.generate_audio import GenerateAudioExecutor
from framework.run import _build_orchestrator


def _resolve_audio_executor(tmp_path):
    orch, _store, _repo = _build_orchestrator(tmp_path)
    step = Step(
        step_id="audio",
        type=StepType.generate,
        name="audio",
        risk_level=RiskLevel.medium,
        capability_ref="audio.t2a",
    )
    executor = orch.executors.resolve(step)
    assert isinstance(executor, GenerateAudioExecutor)
    return executor


def test_build_orchestrator_injects_remote_audio_worker_from_env(monkeypatch, tmp_path):
    """设置 FORGEUE_REMOTE_AUDIO_URL 后,CLI 路径应注入远端 audio worker。"""
    monkeypatch.setenv("FORGEUE_REMOTE_AUDIO_URL", "https://audio.example.test/generate")
    monkeypatch.setenv("FORGEUE_REMOTE_AUDIO_API_KEY", "sk-remote")
    monkeypatch.setenv("FORGEUE_REMOTE_AUDIO_MODEL", "music-test")
    monkeypatch.setenv("MINIMAX_KEY", "sk-minimax")

    executor = _resolve_audio_executor(tmp_path)

    assert isinstance(executor._worker, RemoteHttpAudioWorker)
    assert executor._worker._endpoint_url == "https://audio.example.test/generate"
    assert executor._worker._api_key == "sk-remote"
    assert executor._worker._model == "music-test"


def test_build_orchestrator_injects_minimax_music_worker_from_env(monkeypatch, tmp_path):
    """只有 MINIMAX_KEY 时,CLI 路径应注入 MiniMax 原生 music worker。"""
    monkeypatch.delenv("FORGEUE_REMOTE_AUDIO_URL", raising=False)
    monkeypatch.delenv("FORGEUE_REMOTE_AUDIO_API_KEY", raising=False)
    monkeypatch.delenv("FORGEUE_REMOTE_AUDIO_MODEL", raising=False)
    monkeypatch.setenv("MINIMAX_KEY", "sk-minimax")
    monkeypatch.setenv("FORGEUE_MINIMAX_MUSIC_MODEL", "music-2.6")

    executor = _resolve_audio_executor(tmp_path)

    assert isinstance(executor._worker, MiniMaxMusicWorker)
    assert executor._worker._api_key == "sk-minimax"
    assert executor._worker._endpoint_url == "https://api.minimaxi.com/v1/music_generation"
    assert executor._worker._model == "music-2.6"


def test_build_orchestrator_keeps_audio_worker_unset_without_remote_url(monkeypatch, tmp_path):
    """未配置 URL 时保持现状:远端 worker 不启用,ComfyUI 分支仍靠 prepared_routes。"""
    monkeypatch.delenv("FORGEUE_REMOTE_AUDIO_URL", raising=False)
    monkeypatch.delenv("FORGEUE_REMOTE_AUDIO_API_KEY", raising=False)
    monkeypatch.delenv("FORGEUE_REMOTE_AUDIO_MODEL", raising=False)
    monkeypatch.delenv("MINIMAX_KEY", raising=False)
    monkeypatch.delenv("FORGEUE_MINIMAX_MUSIC_MODEL", raising=False)

    executor = _resolve_audio_executor(tmp_path)

    assert executor._worker is None
