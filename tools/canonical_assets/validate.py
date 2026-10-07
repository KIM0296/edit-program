"""Strict observed stream parsing plus independent complete decode checks."""

from dataclasses import asdict, dataclass
from typing import cast

from .checksums import JSON, parse_json
from .model import AssetRole, BuildError, FailureStatus, role_check
from .wav import wav_data


@dataclass(frozen=True)
class VideoFacts:
    codec_name: str
    profile: str
    width: int
    height: int
    pix_fmt: str
    r_frame_rate: str
    avg_frame_rate: str
    field_order: str
    sample_aspect_ratio: str


@dataclass(frozen=True)
class AudioFacts:
    codec_name: str
    sample_rate: int
    channels: int
    bits_per_sample: int
    channel_layout: str


@dataclass(frozen=True)
class StreamFacts:
    role: AssetRole
    video: VideoFacts | None
    audio: AudioFacts | None

    def __post_init__(self) -> None:
        role_check(self.role)
        if self.video != (
            VideoFacts(
                "dnxhd", "DNXHR LB", 1280, 720, "yuv422p", "24/1", "24/1", "progressive", "1:1"
            )
            if self.role.has_video
            else None
        ):
            raise BuildError(FailureStatus.STRUCTURE_MISMATCH, "Wrong video facts")
        if self.audio != (
            AudioFacts("pcm_s24le", 48000, 2, 24, "stereo") if self.role.has_audio else None
        ):
            raise BuildError(FailureStatus.STRUCTURE_MISMATCH, "Wrong audio facts")

    def record(self) -> dict[str, JSON]:
        return {
            "video": cast(dict[str, JSON], asdict(self.video)) if self.video else None,
            "audio": cast(dict[str, JSON], asdict(self.audio)) if self.audio else None,
        }


def object_value(value: JSON) -> dict[str, JSON]:
    if not isinstance(value, dict):
        raise TypeError("JSON object required")
    return value


def _integer(value: JSON) -> int:
    if type(value) is not int:
        raise ValueError("Observed integer required")
    return value


def _string(value: JSON) -> str:
    if type(value) is not str:
        raise ValueError("Observed string required")
    return value


@dataclass(frozen=True)
class DecodedVideoEvidence:
    frame_count: int
    width: int
    height: int
    interlaced_frame: int

    def __post_init__(self) -> None:
        values = (self.frame_count, self.width, self.height, self.interlaced_frame)
        if any(type(v) is not int for v in values) or values != (720, 1280, 720, 0):
            raise BuildError(
                FailureStatus.STRUCTURE_MISMATCH, "Complete progressive decode required"
            )


def parse_streams(
    blob: bytes,
    role: AssetRole,
    *,
    decoded_video: DecodedVideoEvidence | None = None,
    canonical_wav: bytes | None = None,
) -> StreamFacts:
    role_check(role)
    try:
        canonical_stereo = False
        if canonical_wav is not None:
            if role is not AssetRole.AUDIO_ONLY or len(wav_data(canonical_wav)) != 8640000:
                raise ValueError("Canonical stereo WAV required")
            canonical_stereo = True
        data = object_value(parse_json(blob))
        streams = data["streams"]
        if not isinstance(streams, list):
            raise TypeError("Stream list required")
        expected = (
            ["video", "audio"]
            if role.has_video and role.has_audio
            else ["video"]
            if role.has_video
            else ["audio"]
        )
        records = [object_value(v) for v in streams]
        if [v.get("codec_type") for v in records] != expected:
            raise ValueError("Unexpected stream layout")
        video = None
        audio = None
        for index, record in enumerate(records):
            if type(record.get("index")) is not int or record.get("index") != index:
                raise ValueError("Stream order mismatch")
            if record["codec_type"] == "video":
                video = VideoFacts(
                    _string(record["codec_name"]),
                    _string(record["profile"]),
                    _integer(record["width"]),
                    _integer(record["height"]),
                    _string(record["pix_fmt"]),
                    _string(record["r_frame_rate"]),
                    _string(record["avg_frame_rate"]),
                    _string(record["field_order"])
                    if "field_order" in record
                    else "progressive"
                    if isinstance(decoded_video, DecodedVideoEvidence)
                    else _string(record["field_order"]),
                    _string(record["sample_aspect_ratio"]),
                )
            else:
                if "bits_per_raw_sample" in record and record["bits_per_raw_sample"] != "24":
                    raise ValueError("Contradictory raw sample depth")
                audio = AudioFacts(
                    _string(record["codec_name"]),
                    int(_string(record["sample_rate"])),
                    _integer(record["channels"]),
                    _integer(record["bits_per_sample"]),
                    _string(record["channel_layout"])
                    if "channel_layout" in record
                    else "stereo"
                    if canonical_stereo
                    else _string(record["channel_layout"]),
                )
        return StreamFacts(role, video, audio)
    except (KeyError, ValueError, TypeError) as error:
        raise BuildError(FailureStatus.STRUCTURE_MISMATCH, str(error)) from error


def validate_frame_records(blob: bytes) -> DecodedVideoEvidence:
    try:
        data = object_value(parse_json(blob))
        frames = data["frames"]
        if not isinstance(frames, list) or len(frames) != 720:
            raise BuildError(
                FailureStatus.FRAME_COUNT_MISMATCH, "Exactly 720 decoded frames required"
            )
        for value in frames:
            f = object_value(value)
            if (
                f.get("media_type"),
                _integer(f.get("width")),
                _integer(f.get("height")),
                _integer(f.get("interlaced_frame")),
            ) != ("video", 1280, 720, 0):
                raise BuildError(
                    FailureStatus.STRUCTURE_MISMATCH, "Decoded frame raster/interlace mismatch"
                )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, BuildError):
            raise
        raise BuildError(FailureStatus.FRAME_COUNT_MISMATCH, str(error)) from error

    return DecodedVideoEvidence(720, 1280, 720, 0)


def validate_audio(source: bytes, decoded: bytes) -> None:
    if len(source) != 8640000 or len(decoded) != 8640000:
        raise BuildError(
            FailureStatus.SAMPLE_COUNT_MISMATCH, "Exactly 1440000 stereo samples required"
        )
    if source != decoded:
        raise BuildError(FailureStatus.AUDIO_DECODE_MISMATCH, "Decoded PCM differs from source")
