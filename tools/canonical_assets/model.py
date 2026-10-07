"""Fixed recipe and closed failure vocabulary."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class AssetRole(str, Enum):
    ALPHA = "ALPHA"
    BETA = "BETA"
    GAMMA = "GAMMA"
    REPEAT = "REPEAT"
    VIDEO_ONLY = "VIDEO_ONLY"
    AUDIO_ONLY = "AUDIO_ONLY"

    @property
    def has_video(self) -> bool:
        return self != AssetRole.AUDIO_ONLY

    @property
    def has_audio(self) -> bool:
        return self != AssetRole.VIDEO_ONLY

    @property
    def relative_path(self) -> str:
        return "assets/" + self.value.lower() + "_v1" + (".mov" if self.has_video else ".wav")

    @property
    def asset_id(self) -> str:
        return "canonical:ASSET_" + self.value + ":v1"


@dataclass(frozen=True)
class Recipe:
    width: ClassVar[int] = 1280
    height: ClassVar[int] = 720
    frames: ClassVar[int] = 720
    sample_count: ClassVar[int] = 1440000
    sample_rate: ClassVar[int] = 48000
    numpy_version: ClassVar[str] = "2.3.5"
    version: ClassVar[str] = "v1"
    package_name: ClassVar[str] = "canonical-fixture-assets"
    package_version: ClassVar[str] = "1.0.0"


class FailureStatus(str, Enum):
    TOOLCHAIN_UNSUPPORTED = "TOOLCHAIN_UNSUPPORTED"
    SOURCE_GENERATION_FAILURE = "SOURCE_GENERATION_FAILURE"
    ENCODE_FAILURE = "ENCODE_FAILURE"
    MUX_FAILURE = "MUX_FAILURE"
    STRUCTURE_MISMATCH = "STRUCTURE_MISMATCH"
    FRAME_COUNT_MISMATCH = "FRAME_COUNT_MISMATCH"
    SAMPLE_COUNT_MISMATCH = "SAMPLE_COUNT_MISMATCH"
    AUDIO_DECODE_MISMATCH = "AUDIO_DECODE_MISMATCH"
    NONDETERMINISTIC_OUTPUT = "NONDETERMINISTIC_OUTPUT"
    MANIFEST_FAILURE = "MANIFEST_FAILURE"
    CHECKSUM_FAILURE = "CHECKSUM_FAILURE"
    PACKAGE_VERSION_COLLISION = "PACKAGE_VERSION_COLLISION"


class BuildError(ValueError):
    def __init__(self, status: FailureStatus, detail: str):
        self.status = status
        super().__init__(f"{status.value}: {detail}")


def role_check(role: AssetRole) -> None:
    if type(role) is not AssetRole:
        raise TypeError("Typed asset role required")
