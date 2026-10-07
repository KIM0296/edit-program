"""Integer triangle oscillator; signed floor division order is recipe-authoritative."""

import numpy as np
from numpy.typing import NDArray

from .model import AssetRole, Recipe, role_check

BASE_A = 524288
ACCENT_A = 2097152


def samples(role: AssetRole) -> NDArray[np.int64]:
    role_check(role)
    if not role.has_audio:
        raise ValueError("Video-only role has no PCM")
    frequencies = {
        AssetRole.ALPHA: (440, 880),
        AssetRole.BETA: (500, 1000),
        AssetRole.GAMMA: (600, 1200),
        AssetRole.REPEAT: (700, 1400),
        AssetRole.AUDIO_ONLY: (800, 1600),
    }
    n = np.arange(Recipe.sample_count, dtype=np.int64)
    offset = n % 48000
    amplitude = np.full(Recipe.sample_count, BASE_A, dtype=np.int64)
    attack = offset < 240
    amplitude[attack] = BASE_A + (ACCENT_A - BASE_A) * offset[attack] // 239
    amplitude[(offset >= 240) & (offset < 720)] = ACCENT_A
    release = (offset >= 720) & (offset < 960)
    amplitude[release] = ACCENT_A + (BASE_A - ACCENT_A) * (offset[release] - 720) // 239
    result = np.empty((Recipe.sample_count, 2), dtype=np.int64)
    for channel, frequency in enumerate(frequencies[role]):
        phase = (n * frequency) % 48000
        numerator = np.where(
            phase < 12000,
            4 * phase,
            np.where(phase < 36000, 96000 - 4 * phase, -192000 + 4 * phase),
        )
        result[:, channel] = (amplitude * numerator) // 48000
    return result


def pack_s24le(values: NDArray[np.int64]) -> bytes:
    if values.dtype != np.int64:
        raise TypeError("Signed int64 source samples required")
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("Stereo rows required")
    if np.any(values < -8388608) or np.any(values > 8388607):
        raise ValueError("PCM outside signed 24-bit; no clamp")
    unsigned = values.reshape(-1) & 0xFFFFFF
    out = np.empty((unsigned.size, 3), dtype=np.uint8)
    out[:, 0] = unsigned & 255
    out[:, 1] = (unsigned >> 8) & 255
    out[:, 2] = (unsigned >> 16) & 255
    return out.tobytes()


def pcm(role: AssetRole) -> bytes:
    return pack_s24le(samples(role))
