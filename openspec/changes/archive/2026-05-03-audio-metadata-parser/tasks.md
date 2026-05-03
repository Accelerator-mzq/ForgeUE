# Tasks — audio-metadata-parser

## 1. Code

- [x] 1.1 New module `src/framework/providers/workers/audio_metadata.py` 含 `parse_audio_metadata` dispatch + `_parse_flac` + `_parse_wav` + `_parse_mp3` + `_MP3_SAMPLE_RATES` 表
- [x] 1.2 `src/framework/providers/workers/comfy_worker.py::_run_once_audio` 调 `parse_audio_metadata` fill `AudioCandidate.duration_seconds` + `sample_rate`(替换 always-None pre-fix 行为)

## 2. Fences

- [x] 2.1 `tests/unit/test_audio_metadata.py` 8 fence(2 FLAC + 2 WAV + 2 MP3 + 2 dispatch)

## 3. Verify

- [x] 3.1 `pytest -q` 1323 passed(prior 1315 + 8 metadata fence)
- [x] 3.2 **L2 audio live smoke**:`audio_smoke_meta_l2_v3` 真实 ComfyUI Stable Audio
  Open FLAC 1.17 MB;parser 提取 `duration_seconds=10.031s`(within ±0.5% of bundle
  declared 10.0s)+ `sample_rate=44100 Hz`;evidence
  `notes/live_smoke_audio_metadata_20260504.md`

## 4. Commit

- [x] 4.1 commit:`feat(audio): stdlib metadata parser for FLAC/WAV/MP3 (D10 follow-on)`

## 5. Archive

- [x] 5.1 finish gate exit 0
- [x] 5.2 `openspec validate --strict` PASS
- [x] 5.3 `openspec archive --yes`
