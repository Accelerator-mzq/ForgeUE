"""Stdlib audio metadata parser fences.

OpenSpec change `audio-metadata-parser`(2026-05-04 follow-on for
`comfy-agent-cli-audio-adoption` D10):verify FLAC STREAMINFO / WAV fmt
chunk / MP3 first frame header parsing yields correct sample_rate and
(when available) duration_seconds.
"""
from __future__ import annotations

import struct

from framework.providers.workers.audio_metadata import parse_audio_metadata


# ---- FLAC ------------------------------------------------------------------


def _build_minimal_flac(sample_rate: int = 44100, total_samples: int = 44100 * 5) -> bytes:
    """Build a minimal FLAC file with a STREAMINFO block.

    Layout:
      - 4 bytes magic 'fLaC'
      - 1 byte block_header (0x80 = last_block + STREAMINFO type 0)
      - 3 bytes block length (34, big-endian)
      - 34 bytes STREAMINFO body:
        - 2 bytes min_block_size (16)
        - 2 bytes max_block_size (16)
        - 3 bytes min_frame_size (24)
        - 3 bytes max_frame_size (24)
        - 4 bytes packed: sample_rate (20 bits) + channels (3) + bits_per_sample (5) + total_samples_top4
        - 4 bytes total_samples_lower32
        - 16 bytes MD5 signature (zeros)
    """
    magic = b"fLaC"
    block_header = bytes([0x80 | 0x00])  # last_block=1 + type=0 (STREAMINFO)
    block_length = (34).to_bytes(3, "big")
    streaminfo = (
        struct.pack(">HH", 4096, 4096)  # min/max block size
        + (4096).to_bytes(3, "big")  # min frame size
        + (8192).to_bytes(3, "big")  # max frame size
    )
    # Packed 64-bit:
    # sample_rate (20 bits) + channels-1 (3) + bits/sample-1 (5) + total_samples (36 bits)
    channels_minus_1 = 1  # 2 channels
    bps_minus_1 = 15  # 16 bits per sample
    packed = (
        (sample_rate & 0xFFFFF) << 44
        | (channels_minus_1 & 0x7) << 41
        | (bps_minus_1 & 0x1F) << 36
        | (total_samples & 0xFFFFFFFFF)
    )
    streaminfo += struct.pack(">Q", packed)
    streaminfo += b"\x00" * 16  # MD5
    return magic + block_header + block_length + streaminfo


def test_parse_flac_extracts_sample_rate_and_duration():
    """FLAC STREAMINFO 解析 → sample_rate=44100, total_samples=220500
    → duration=5.0s"""
    flac = _build_minimal_flac(sample_rate=44100, total_samples=44100 * 5)
    duration, rate = parse_audio_metadata(flac, "flac")
    assert rate == 44100
    assert duration is not None
    assert abs(duration - 5.0) < 0.001, f"expected ~5.0s, got {duration}"


def test_parse_flac_invalid_magic_returns_none():
    """Non-FLAC bytes → (None, None) silent fallback。"""
    duration, rate = parse_audio_metadata(b"NOPE" + b"\x00" * 100, "flac")
    assert duration is None
    assert rate is None


# ---- WAV -------------------------------------------------------------------


def _build_minimal_wav(sample_rate: int = 22050, num_samples: int = 22050) -> bytes:
    """Build a minimal RIFF WAVE PCM mono 16-bit file with given samples."""
    channels = 1
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = num_samples * block_align
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)  # fmt size = 16 (PCM)
        + struct.pack("<HH", 1, channels)  # format=PCM, channels
        + struct.pack("<II", sample_rate, byte_rate)
        + struct.pack("<HH", block_align, bits)
    )
    data_chunk = b"data" + struct.pack("<I", data_size) + b"\x00" * data_size
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    return b"RIFF" + struct.pack("<I", riff_size) + b"WAVE" + fmt_chunk + data_chunk


def test_parse_wav_extracts_sample_rate_and_duration():
    """WAV fmt chunk + data chunk size 解析 → sample_rate=22050, 22050 samples
    → duration=1.0s。"""
    wav = _build_minimal_wav(sample_rate=22050, num_samples=22050)
    duration, rate = parse_audio_metadata(wav, "wav")
    assert rate == 22050
    assert duration is not None
    assert abs(duration - 1.0) < 0.001


def test_parse_wav_invalid_returns_none():
    duration, rate = parse_audio_metadata(b"NOTRIFF" + b"\x00" * 50, "wav")
    assert duration is None
    assert rate is None


# ---- MP3 -------------------------------------------------------------------


def _build_minimal_mp3_frame(*, version: int = 0b11, rate_idx: int = 0) -> bytes:
    """Build a minimal MP3 frame header.

    First byte = 0xFF (sync top 8 bits)
    Second byte = top 3 bits sync (0xE0) + version (2 bits) + layer (2 bits) + protection (1 bit)
                  use layer III (0b01) + no CRC (0b1)
                  → 0xE0 | (version << 3) | (0b01 << 1) | 0b1 = 0xE0 | (v<<3) | 0x3
    Third byte = bitrate_idx (4 bits, use 0b1001 = 128k for MPEG-1) + sample_rate_idx (2 bits)
                 + padding (1 bit) + private (1 bit)
                 → (0b1001 << 4) | (rate_idx << 2) | 0b00 = 0x90 | (rate_idx << 2)
    """
    b0 = 0xFF
    b1 = 0xE0 | ((version & 0x3) << 3) | (0b01 << 1) | 0b1  # MPEG version + Layer III + no CRC
    b2 = 0x90 | ((rate_idx & 0x3) << 2)
    b3 = 0x00  # mode=stereo (0b00 << 6), no private, etc.
    return bytes([b0, b1, b2, b3]) + b"\x00" * 100


def test_parse_mp3_extracts_sample_rate_for_mpeg1():
    """MPEG-1 frame, sample_rate_idx=0 → 44100 Hz."""
    mp3 = _build_minimal_mp3_frame(version=0b11, rate_idx=0)
    duration, rate = parse_audio_metadata(mp3, "mp3")
    assert rate == 44100
    # MP3 duration is best-effort; this MVP returns None unless Xing/LAME
    assert duration is None


def test_parse_mp3_with_id3v2_preamble_skipped():
    """ID3v2 header is correctly skipped before parsing first MPEG frame。"""
    # Build a minimal ID3v2 header(10 bytes header + 0 bytes body)+ frame
    id3 = b"ID3\x04\x00\x00" + bytes([0x00, 0x00, 0x00, 0x00])  # synchsafe size = 0
    frame = _build_minimal_mp3_frame(version=0b11, rate_idx=0)
    duration, rate = parse_audio_metadata(id3 + frame, "mp3")
    assert rate == 44100
    assert duration is None


# ---- Dispatch entry --------------------------------------------------------


def test_parse_audio_metadata_unknown_format_returns_none():
    """Unknown format string → (None, None);no exception。"""
    duration, rate = parse_audio_metadata(b"\x00" * 100, "ogg")  # type: ignore[arg-type]
    assert duration is None
    assert rate is None


def test_parse_audio_metadata_truncated_input_returns_none():
    """Truncated input(len < min header)→ silent (None, None)。"""
    duration, rate = parse_audio_metadata(b"fLaC", "flac")  # only magic, no body
    assert duration is None
    assert rate is None
