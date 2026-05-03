"""Stdlib-only audio metadata parser for FLAC / WAV / MP3.

OpenSpec change `audio-metadata-parser`(2026-05-04 follow-on for
`comfy-agent-cli-audio-adoption` D10):reads sample_rate + duration_seconds
from raw audio bytes without any third-party codec dependency.

Supported formats:

- **FLAC**:parses METADATA_BLOCK_STREAMINFO (block type 0). Extracts
  sample_rate (20 bits) and total_samples (36 bits), computes
  ``duration_seconds = total_samples / sample_rate``.
- **WAV**:parses RIFF / WAVE fmt chunk (PCM/IEEE-float headers).
  Extracts sample_rate from the fmt chunk, computes duration from the
  data chunk size and byte_rate.
- **MP3**:parses the first MPEG frame header (4 bytes after any ID3v2
  preamble). Extracts sample_rate from the version+sample-rate-index
  bits. ``duration_seconds`` is best-effort: only set if the file
  contains a Xing/Info VBR header (LAME tag) or a constant-bitrate
  frame allows simple length estimation; otherwise returns None
  (caller is expected to treat None as "duration unknown for MP3 CBR
  streams without TLEN").

All functions return ``(duration_seconds, sample_rate)`` tuples where
either value MAY be None when the format does not encode it explicitly.
On parse failure, both values are None (silent — caller may fallback).
"""
from __future__ import annotations

import struct
from typing import Literal


def parse_audio_metadata(
    data: bytes,
    fmt: Literal["flac", "mp3", "wav"],
) -> tuple[float | None, int | None]:
    """Dispatch entry point.

    Returns
    -------
    (duration_seconds, sample_rate) : tuple
        Either or both may be None when the format does not encode
        the value, or when parsing fails.
    """
    try:
        if fmt == "flac":
            return _parse_flac(data)
        if fmt == "wav":
            return _parse_wav(data)
        if fmt == "mp3":
            return _parse_mp3(data)
    except (struct.error, IndexError, ValueError):
        # Best-effort: silent fallback to (None, None) on parse error
        return (None, None)
    return (None, None)


# ---------------------------------------------------------------------------
# FLAC
# ---------------------------------------------------------------------------


def _parse_flac(data: bytes) -> tuple[float | None, int | None]:
    """Parse FLAC STREAMINFO (always the first metadata block per spec).

    Layout:
        bytes [0:4]  : 'fLaC' magic
        bytes [4]    : METADATA_BLOCK_HEADER (1 byte) — last_metadata_block (1 bit) + block_type (7 bits)
                       block_type == 0 == STREAMINFO
        bytes [5:8]  : STREAMINFO length (24-bit big-endian, usually 34)
        bytes [8:18] : min_block_size (16) + max_block_size (16) + min_frame_size (24) + max_frame_size (24)
        bytes [18:22]: 32-bit packed field:
                        sample_rate (20 bits, top)
                        + channels (3 bits)
                        + bits_per_sample (5 bits)
                        + total_samples (4 bits, top of 36-bit total_samples field)
        bytes [22:26]: total_samples (lower 32 bits of 36-bit field)
    """
    if len(data) < 38 or data[:4] != b"fLaC":
        return (None, None)
    block_header = data[4]
    block_type = block_header & 0x7F
    if block_type != 0:  # MUST be STREAMINFO first
        return (None, None)
    # bytes 18..22 contain the packed sample_rate / channels / bits / top of total_samples
    packed = struct.unpack(">I", data[18:22])[0]
    sample_rate = (packed >> 12) & 0xFFFFF  # 20 bits
    total_samples_top4 = packed & 0xF  # bottom 4 bits
    total_samples_bot32 = struct.unpack(">I", data[22:26])[0]
    total_samples = (total_samples_top4 << 32) | total_samples_bot32
    if sample_rate <= 0 or total_samples <= 0:
        return (None, sample_rate or None)
    duration_seconds = total_samples / sample_rate
    return (duration_seconds, sample_rate)


# ---------------------------------------------------------------------------
# WAV
# ---------------------------------------------------------------------------


def _parse_wav(data: bytes) -> tuple[float | None, int | None]:
    """Parse WAV (RIFF/WAVE) header.

    Layout:
        bytes [0:4]   : 'RIFF'
        bytes [4:8]   : RIFF chunk size (excluding first 8 bytes)
        bytes [8:12]  : 'WAVE'
        bytes [12:16] : 'fmt ' chunk id
        bytes [16:20] : fmt chunk size (usually 16 for PCM, 18 for non-PCM with cbSize)
        bytes [20:22] : audio_format (1 = PCM, 3 = IEEE float, ...)
        bytes [22:24] : channels
        bytes [24:28] : sample_rate (32-bit LE)
        bytes [28:32] : byte_rate (sample_rate * channels * bits_per_sample / 8)
        bytes [32:34] : block_align
        bytes [34:36] : bits_per_sample
        ... (then data chunk)
    """
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return (None, None)
    if data[12:16] != b"fmt ":
        # Non-canonical header; some WAVs interleave chunks. Skip parse.
        return (None, None)
    fmt_size = struct.unpack("<I", data[16:20])[0]
    sample_rate = struct.unpack("<I", data[24:28])[0]
    byte_rate = struct.unpack("<I", data[28:32])[0]
    if sample_rate <= 0 or byte_rate <= 0:
        return (None, sample_rate or None)
    # Find data chunk: after fmt chunk (header 8 + fmt_size body)
    data_chunk_start = 20 + fmt_size
    if len(data) < data_chunk_start + 8:
        return (None, sample_rate)
    if data[data_chunk_start:data_chunk_start + 4] != b"data":
        # Some WAVs have intervening chunks (LIST INFO, etc.). For MVP, give up
        # on duration but return sample_rate.
        return (None, sample_rate)
    data_size = struct.unpack(
        "<I", data[data_chunk_start + 4:data_chunk_start + 8]
    )[0]
    duration_seconds = data_size / byte_rate
    return (duration_seconds, sample_rate)


# ---------------------------------------------------------------------------
# MP3
# ---------------------------------------------------------------------------

# MPEG sample-rate index tables (Hz) per MPEG version.
# version code: 0b11 = MPEG-1, 0b10 = MPEG-2, 0b00 = MPEG-2.5
_MP3_SAMPLE_RATES = {
    0b11: (44100, 48000, 32000, None),  # MPEG-1
    0b10: (22050, 24000, 16000, None),  # MPEG-2
    0b00: (11025, 12000, 8000, None),   # MPEG-2.5
}


def _parse_mp3(data: bytes) -> tuple[float | None, int | None]:
    """Parse first MPEG frame header to extract sample_rate.

    duration_seconds is intentionally returned as None unless a Xing/Info
    VBR header is found(advanced; not implemented in this MVP). MP3 CBR
    streams without TLEN ID3 tag would require summing frame counts to
    compute duration — out of scope for a stdlib-only quick-parse.

    Skips ID3v2 preamble if present(`'ID3' [version 2 bytes] [flags 1 byte]
    [size 4 bytes synchsafe]`)→ data + (10 + size) bytes is start of
    audio frames.
    """
    pos = 0
    if data[:3] == b"ID3":
        # ID3v2 header is 10 bytes;size is 4 bytes synchsafe (each byte's high bit is 0)
        if len(data) < 10:
            return (None, None)
        size_bytes = data[6:10]
        size = (
            (size_bytes[0] & 0x7F) << 21
            | (size_bytes[1] & 0x7F) << 14
            | (size_bytes[2] & 0x7F) << 7
            | (size_bytes[3] & 0x7F)
        )
        pos = 10 + size
    if len(data) < pos + 4:
        return (None, None)
    # Frame sync: 11 bits all 1 → first byte 0xFF, next byte top 3 bits 111
    b0, b1, b2, b3 = data[pos], data[pos + 1], data[pos + 2], data[pos + 3]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return (None, None)
    version = (b1 >> 3) & 0x03  # 2 bits
    sample_rate_idx = (b2 >> 2) & 0x03  # 2 bits
    rates = _MP3_SAMPLE_RATES.get(version)
    if rates is None:
        return (None, None)
    sample_rate = rates[sample_rate_idx]
    return (None, sample_rate)
