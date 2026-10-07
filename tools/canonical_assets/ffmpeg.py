"""Typed constant recipes; no shell, arbitrary flags, discovery or downloads."""

import platform
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np

from .checksums import file_hash, staging_path, valid_hash
from .model import BuildError, FailureStatus, Recipe

_REQUIRED = ("dnxhd", "dnxhr_lb", "yuv422p", "mov", "wav", "pcm_s24le", "bitexact")


@dataclass(frozen=True)
class ToolchainProfile:
    ffmpeg: Path
    ffprobe: Path
    python_version: str
    numpy_version: str
    ffmpeg_version: str
    ffprobe_version: str
    configuration_digest: str
    ffmpeg_sha256: str
    ffprobe_sha256: str
    capabilities: tuple[str, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        if not isinstance(self.ffmpeg, Path) or not isinstance(self.ffprobe, Path):
            raise TypeError("Explicit executable Paths required")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        if self.capabilities != _REQUIRED or self.contract_version != "v1":
            raise BuildError(
                FailureStatus.TOOLCHAIN_UNSUPPORTED, "Required capability evidence missing"
            )
        if (
            not self.python_version.startswith("3.11.")
            or self.numpy_version != Recipe.numpy_version
        ):
            raise BuildError(
                FailureStatus.TOOLCHAIN_UNSUPPORTED, "Python 3.11.x / pinned NumPy required"
            )
        if not self.ffmpeg_version.startswith(
            "ffmpeg version "
        ) or not self.ffprobe_version.startswith("ffprobe version "):
            raise BuildError(FailureStatus.TOOLCHAIN_UNSUPPORTED, "Version evidence missing")
        if not all(
            valid_hash(x)
            for x in (self.configuration_digest, self.ffmpeg_sha256, self.ffprobe_sha256)
        ):
            raise BuildError(
                FailureStatus.TOOLCHAIN_UNSUPPORTED, "Executable/configuration hashes required"
            )


def _capture(tokens: tuple[str, ...], failure: FailureStatus) -> bytes:
    try:
        result = subprocess.run(
            tokens,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            shell=False,
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BuildError(failure, str(error)) from error
    if result.returncode != 0 or result.stderr.strip():
        raise BuildError(failure, result.stderr.decode("utf-8", errors="replace")[-4000:])
    return result.stdout


def preflight(ffmpeg: Path, ffprobe: Path) -> ToolchainProfile:
    failure = FailureStatus.TOOLCHAIN_UNSUPPORTED
    if platform.python_version_tuple()[:2] != ("3", "11") or np.__version__ != Recipe.numpy_version:
        raise BuildError(
            failure, "Generation requires Python 3.11.x and NumPy " + Recipe.numpy_version
        )
    for path, expected in ((ffmpeg, "ffmpeg"), (ffprobe, "ffprobe")):
        if not isinstance(path, Path) or not path.is_file() or path.stem.lower() != expected:
            raise BuildError(failure, "Explicit existing " + expected + " executable required")
    ffmpeg, ffprobe = ffmpeg.resolve(), ffprobe.resolve()

    def read(*args: str) -> str:
        return _capture((str(ffmpeg), "-hide_banner", *args), failure).decode(
            "utf-8", errors="strict"
        )

    version = read("-version")
    probe = _capture((str(ffprobe), "-version"), failure).decode("utf-8")
    encoder = read("-h", "encoder=dnxhd")
    muxers = read("-muxers")
    pcm_encoder = read("-h", "encoder=pcm_s24le")
    options = read("-h", "full")
    if (
        not all(x in encoder for x in ("dnxhd", "dnxhr_lb", "yuv422p"))
        or not all(x in muxers for x in ("mov", "wav"))
        or "pcm_s24le" not in pcm_encoder
        or "bitexact" not in options
    ):
        raise BuildError(failure, "Missing encoder/profile/muxer/PCM/bitexact capability")
    evidence = version + "\n" + encoder + "\n" + muxers + "\n" + pcm_encoder + "\n" + options
    return ToolchainProfile(
        ffmpeg,
        ffprobe,
        platform.python_version(),
        np.__version__,
        version,
        probe,
        sha256(evidence.encode()).hexdigest(),
        file_hash(ffmpeg),
        file_hash(ffprobe),
        _REQUIRED,
    )


def verify_toolchain(profile: ToolchainProfile) -> None:
    try:
        if (
            platform.python_version() != profile.python_version
            or np.__version__ != profile.numpy_version
            or file_hash(profile.ffmpeg) != profile.ffmpeg_sha256
            or file_hash(profile.ffprobe) != profile.ffprobe_sha256
        ):
            raise BuildError(FailureStatus.TOOLCHAIN_UNSUPPORTED, "Locked toolchain changed")
    except OSError as error:
        raise BuildError(FailureStatus.TOOLCHAIN_UNSUPPORTED, str(error)) from error


def _base(tool: ToolchainProfile) -> tuple[str, ...]:
    if type(tool) is not ToolchainProfile:
        raise TypeError("Typed toolchain required")
    return (str(tool.ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-xerror")


_METADATA = (
    "-map_metadata",
    "-1",
    "-map_chapters",
    "-1",
    "-fflags",
    "+bitexact",
    "-flags:v",
    "+bitexact",
    "-metadata",
    "creation_time=",
    "-metadata",
    "encoder=",
    "-metadata:s:v",
    "encoder=",
    "-metadata:s:v",
    "language=und",
    "-write_tmcd",
    "0",
)


def encode_tokens(tool: ToolchainProfile, root: Path, output: str) -> tuple[str, ...]:
    destination = staging_path(root, output)
    return (
        *_base(tool),
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        "1280x720",
        "-framerate",
        "24/1",
        "-i",
        "pipe:0",
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "dnxhd",
        "-profile:v",
        "dnxhr_lb",
        "-pix_fmt",
        "yuv422p",
        "-frames:v",
        "720",
        "-r",
        "24/1",
        "-enc_time_base",
        "1:24",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-vf",
        "scale=in_range=full:out_range=limited:out_color_matrix=bt709,setsar=1",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_range",
        "tv",
        *_METADATA,
        "-f",
        "mov",
        str(destination),
    )


def mux_tokens(
    tool: ToolchainProfile, root: Path, video: str, audio: str, output: str
) -> tuple[str, ...]:
    return (
        *_base(tool),
        "-i",
        str(staging_path(root, video)),
        "-i",
        str(staging_path(root, audio)),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        *_METADATA,
        "-metadata:s:a",
        "language=und",
        "-f",
        "mov",
        str(staging_path(root, output)),
    )


def probe_tokens(
    tool: ToolchainProfile, root: Path, asset: str, *, frames: bool = False
) -> tuple[str, ...]:
    path = staging_path(root, asset)
    fields = (
        (
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=media_type,width,height,interlaced_frame",
        )
        if frames
        else ("-show_streams", "-show_format")
    )
    return (str(tool.ffprobe), "-v", "error", *fields, "-of", "json", str(path))


def decode_tokens(
    tool: ToolchainProfile, root: Path, asset: str, *, audio: bool
) -> tuple[str, ...]:
    path = staging_path(root, asset)
    if audio:
        return (
            *_base(tool),
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "pcm_s24le",
            "-flags:a",
            "+bitexact",
            "-f",
            "s24le",
            "pipe:1",
        )
    return (*_base(tool), "-i", str(path), "-map", "0:v:0", "-an", "-vsync", "0", "-f", "null", "-")
