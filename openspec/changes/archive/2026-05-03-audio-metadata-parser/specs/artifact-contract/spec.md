# Spec delta — artifact-contract (audio-metadata-parser)

## ADDED Requirements

### Requirement: AudioCandidate duration_seconds and sample_rate MUST be parsed from audio bytes when format is supported

The system SHALL parse audio bytes via stdlib-only routines to populate
`AudioCandidate.duration_seconds` and `AudioCandidate.sample_rate` for
the three supported formats(`flac`, `mp3`, `wav`)before constructing
the candidate. The parser MUST NOT introduce any third-party codec
dependency(no `mutagen`, `pydub`, `soundfile`, etc.;NFR-MAINT
compliance).

The expected return values:

- **FLAC**: both `duration_seconds` and `sample_rate` SHALL be populated
  from the STREAMINFO block(METADATA_BLOCK_TYPE 0).
- **WAV**: both `duration_seconds`(from data-chunk-size / byte_rate)and
  `sample_rate`(from fmt chunk)SHALL be populated for canonical
  PCM/IEEE-float WAVs;non-canonical chunk orders MAY return
  `duration_seconds=None` while still populating `sample_rate`.
- **MP3**: only `sample_rate` SHALL be populated(from the first MPEG
  frame header after any ID3v2 preamble);`duration_seconds` MAY be
  `None` because MP3 CBR/VBR duration computation requires Xing/LAME
  header parsing which is out of scope for this change(reserved for
  a future follow-on).

If parsing fails(corrupt header / truncated input / unrecognised
sub-format), both fields MUST silently fall back to `None`(no
exception bubble);the audio Artifact persistence MUST NOT be
blocked by metadata parse failure.

#### Scenario: FLAC produces both duration and sample_rate

- **GIVEN** a `ComfyAgentWorker.generate_audio` call returns a candidate
  whose payload is a valid FLAC file with STREAMINFO declaring
  `sample_rate=44100`, `total_samples=441000`
- **WHEN** the worker constructs the `AudioCandidate`
- **THEN** `cand.sample_rate == 44100`
- **AND** `cand.duration_seconds` is approximately `10.0` seconds
  (within ±0.001 of `441000 / 44100`)
- **AND** the `Artifact.metadata` propagates both fields (not None)

#### Scenario: MP3 produces sample_rate but None duration

- **GIVEN** an MP3 payload with a valid first MPEG frame header
  (MPEG-1 layer III, sample_rate_idx=0)
- **WHEN** the parser runs
- **THEN** `cand.sample_rate == 44100`
- **AND** `cand.duration_seconds is None`(MP3 duration deferred to
  follow-on)

#### Scenario: Corrupt audio bytes silent fallback

- **GIVEN** an audio payload that fails magic-bytes secondary
  validation in `_run_once_audio`(this would already raise
  `WorkerUnsupportedResponse`, so parser is never reached)
- **OR GIVEN** an audio payload that passes magic bytes but has
  malformed STREAMINFO / fmt chunk / frame header
- **WHEN** the parser runs
- **THEN** both `duration_seconds` and `sample_rate` SHALL be `None`
- **AND** the audio Artifact SHALL still be persisted with the audio
  bytes intact and the missing-metadata fields as `None`

#### Scenario: Live Stable Audio Open FLAC end-to-end

- **GIVEN** a real ComfyUI subprocess call to the
  `Audio_Workflows/audio_stable_audio_example` workflow with
  `duration_seconds=10.0` declared in the bundle
- **WHEN** the worker reads the resulting FLAC bytes(typically
  ~1.17 MB at 44.1 kHz, 16-bit, stereo, ~10s)
- **THEN** the parser SHALL extract `sample_rate=44100`
- **AND** `duration_seconds` SHALL match the bundle's declared value
  within ±10%(typical observed ε is ~0.5% — Stable Audio Open's
  output sample count is not exactly bundle-declared seconds × 44100
  due to model-internal frame alignment;a wider tolerance avoids
  brittle production fences while still catching gross misparses)
