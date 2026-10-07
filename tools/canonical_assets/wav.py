"""Exactly fmt/data RIFF chunks; no metadata or native writer defaults."""

import struct


def wav_bytes(pcm: bytes) -> bytes:
    if type(pcm) is not bytes or len(pcm) % 6 or len(pcm) > 0xFFFFFFFF - 36:
        raise ValueError("Bounded complete stereo PCM required")
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 2, 48000, 288000, 6, 24)
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


def wav_data(blob: bytes) -> bytes:
    if len(blob) < 44 or blob != wav_bytes(blob[44:]):
        raise ValueError("Noncanonical WAV")
    return blob[44:]
