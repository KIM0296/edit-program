"""Integer RGB24 source; returned arrays are independent writable frame buffers."""

from collections.abc import Iterable
from hashlib import sha256

import numpy as np
from numpy.typing import NDArray

from .glyphs_5x7 import glyph
from .model import AssetRole, Recipe, role_check


def _draw(image: NDArray[np.uint8], text: str, x: int, y: int, cell: int) -> None:
    for index, char in enumerate(text):
        for row, bits in enumerate(glyph(char)):
            for column, bit in enumerate(bits):
                if bit == "1":
                    left = x + (index * 6 + column) * cell
                    top = y + row * cell
                    image[top : top + cell, left : left + cell] = (255, 255, 255)


def frame(role: AssetRole, index: int) -> NDArray[np.uint8]:
    role_check(role)
    if not role.has_video:
        raise ValueError("Audio-only role has no frames")
    if type(index) is not int or not 0 <= index < Recipe.frames:
        raise ValueError("Frame index outside 0..719")
    backgrounds = {
        AssetRole.ALPHA: (32, 96, 160),
        AssetRole.BETA: (160, 96, 32),
        AssetRole.GAMMA: (112, 48, 160),
        AssetRole.REPEAT: (96, 96, 96),
        AssetRole.VIDEO_ONLY: (32, 128, 64),
    }
    image = np.empty((720, 1280, 3), dtype=np.uint8)
    image[:] = backgrounds[role]
    image[:8] = image[-8:] = (235, 235, 235)
    image[:, :8] = image[:, -8:] = (235, 235, 235)
    code = {
        AssetRole.ALPHA: "A",
        AssetRole.BETA: "B",
        AssetRole.GAMMA: "G",
        AssetRole.REPEAT: "R",
        AssetRole.VIDEO_ONLY: "V",
    }[role]
    _draw(image, code, 40, 40, 16)
    _draw(image, f"{index:04d}", 40, 180, 12)
    _draw(image, f"{index % 24:02d}", 40, 300, 12)
    for bit in range(10):
        value = 240 if index & (1 << (9 - bit)) else 16
        image[400:448, 40 + bit * 36 : 68 + bit * 36] = (value, value, value)
    x = 200 + (index * 13) % 1000
    image[520:672, x : x + 16] = (240, 220, 32)
    image[40:120, 1120:1224] = (255, 64, 64) if index % 24 == 0 else (32, 32, 32)
    return image


def source_digest(frames: Iterable[NDArray[np.uint8]]) -> str:
    digest = sha256()
    for image in frames:
        if image.shape != (720, 1280, 3) or image.dtype != np.uint8:
            raise ValueError("RGB24 frame required")
        digest.update(image.tobytes(order="C"))
    return digest.hexdigest()
