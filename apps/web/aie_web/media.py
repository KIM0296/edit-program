"""Media facts from an uploaded file (PyAV, installed with the optional ``asr`` extra).

Two layers so the policy is testable without PyAV:

- :func:`read_streams` (PyAV): demux only — container/stream metadata and the
  presentation timestamps of the first video packets. Nothing is decoded,
  nothing from the file is executed.
- :func:`evaluate` (pure): turns :class:`StreamFacts` into :class:`MediaProbe`
  or a Korean refusal. The frame rate must be constant and on the SMPTE
  whitelist; the start timecode comes only from a tag (never assumed 0).
"""

import importlib
import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

from davinci_ai_editor.handoff_model import is_windows_absolute
from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.timecode import SMPTE_RATES, parse_timecode

from .pipeline import PipelineError, clean_text

PTS_SAMPLE_PACKETS = 600
CFR_MESSAGE = "CFR로 변환 후 다시 올려 주세요"

MEDIA_EXTENSIONS = frozenset(
    {".mp4", ".mov", ".m4v", ".mkv", ".mxf", ".avi", ".wav", ".mp3", ".m4a", ".aac", ".flac"}
)
# FCP7 XML needs an absolute pathurl. Without a user-entered folder the clip points
# here on purpose, so Resolve shows it offline and the user relinks it.
RELINK_FOLDER = "/AIE-RELINK"


def safe_filename(name: str) -> str:
    """The original file name as text only (never used as a filesystem path)."""
    base = clean_text(name.replace("\\", "/").rsplit("/", 1)[-1], 200)
    if not base or base in (".", "..") or base.startswith("."):
        raise PipelineError("파일 이름을 읽을 수 없습니다.", ("BAD_FILENAME",))
    if PurePosixPath(base).suffix.lower() not in MEDIA_EXTENSIONS:
        raise PipelineError(
            "지원하지 않는 파일 형식입니다 (mp4, mov, m4v, mkv, mxf, avi, wav, mp3, m4a, aac, flac).",
            ("UNSUPPORTED_EXTENSION",),
        )
    return base


def resolve_media_path(folder: str, filename: str) -> str:
    """Folder as Resolve sees it + original file name; no folder -> relink placeholder."""
    text = clean_text(folder, 900)
    if not text:
        return f"{RELINK_FOLDER}/{filename}"
    if "://" in text:
        raise PipelineError("URL이 아닌 폴더 경로를 입력하세요.", ("UNSUPPORTED_PATH",))
    windows = is_windows_absolute(text) or text.startswith("\\\\")
    if not windows and not text.startswith("/"):
        raise PipelineError(
            "폴더는 절대 경로로 입력하세요 (예: D:\\Footage 또는 /Volumes/Footage).",
            ("RELATIVE_FOLDER",),
        )
    separator = "\\" if windows else "/"
    stripped = text.rstrip("\\/")
    return f"{stripped}{separator}{filename}"


@dataclass(frozen=True)
class StreamFacts:
    """Raw facts as the demuxer reports them (times in seconds as exact Fractions)."""

    container_duration: Fraction | None
    has_video: bool
    video_avg_rate: Fraction | None = None
    video_base_rate: Fraction | None = None
    video_time_base: Fraction | None = None
    video_frames: int | None = None
    video_duration: Fraction | None = None
    video_start: Fraction | None = None
    pts_deltas: tuple[int, ...] = ()
    has_audio: bool = False
    audio_start: Fraction | None = None
    audio_duration: Fraction | None = None
    timecode_tag: str | None = None


@dataclass(frozen=True)
class MediaProbe:
    """Evaluated media facts. ``rate`` is None only for audio-only files (user picks)."""

    rate: FrameRate | None
    duration_frames: int | None
    duration_seconds: Fraction
    start_frame: int | None
    timecode_tag: str | None
    offset_ms: int
    audio_only: bool
    notes: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "rate": None if self.rate is None else f"{self.rate.numerator}/{self.rate.denominator}",
            "duration_frames": self.duration_frames,
            "duration_seconds": str(self.duration_seconds),
            "start_frame": self.start_frame,
            "timecode_tag": self.timecode_tag,
            "offset_ms": self.offset_ms,
            "audio_only": self.audio_only,
            "notes": list(self.notes),
        }


Prober = Callable[[Path], StreamFacts]


def _rate_label(value: Fraction) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def whitelisted_rate(value: Fraction) -> FrameRate | None:
    for rate in SMPTE_RATES:
        if Fraction(rate.numerator, rate.denominator) == value:
            return rate
    return None


def frames_for(seconds: Fraction, rate: FrameRate) -> int:
    """Whole frames that fit in ``seconds`` (floor: never longer than the media)."""
    return math.floor(seconds * Fraction(rate.numerator, rate.denominator) + Fraction(1, 1000))


def _check_cfr(facts: StreamFacts, rate_value: Fraction) -> None:
    if (
        facts.video_avg_rate is not None
        and facts.video_base_rate is not None
        and facts.video_avg_rate != facts.video_base_rate
    ):
        raise PipelineError(
            f"가변 프레임레이트(VFR)로 보입니다 (평균 {_rate_label(facts.video_avg_rate)} fps ≠ "
            f"기준 {_rate_label(facts.video_base_rate)} fps). {CFR_MESSAGE}.",
            ("VFR_DETECTED", "AVG_NE_BASE_RATE"),
        )
    if facts.video_time_base is None or not facts.pts_deltas:
        return
    ticks = 1 / (rate_value * facts.video_time_base)
    allowed = {math.floor(ticks), math.ceil(ticks)}
    odd = [d for d in facts.pts_deltas if d not in allowed]
    if odd:
        raise PipelineError(
            f"프레임 간격이 일정하지 않습니다 (가변 프레임레이트, VFR). {CFR_MESSAGE}.",
            ("VFR_DETECTED", f"PTS_DELTA_IRREGULAR {len(odd)}/{len(facts.pts_deltas)}"),
        )


def _start_frame(tag: str | None, rate: FrameRate | None) -> tuple[int | None, tuple[str, ...]]:
    if tag is None or rate is None:
        return None, ()
    try:
        frames, _ = parse_timecode(tag.strip(), rate)
    except ValueError:
        return None, (f"시작 타임코드 태그 '{tag[:32]}'를 읽을 수 없어 직접 입력을 요청합니다.",)
    return frames, ()


def evaluate(facts: StreamFacts, max_seconds: int) -> MediaProbe:
    if not facts.has_audio:
        raise PipelineError(
            "오디오 트랙이 없습니다. 전사할 소리가 있는 영상/오디오 파일을 올려 주세요.",
            ("NO_AUDIO",),
        )
    notes: list[str] = []
    rate: FrameRate | None = None
    duration_frames: int | None = None
    if facts.has_video:
        rate_value = facts.video_avg_rate or facts.video_base_rate
        if rate_value is None or rate_value <= 0:
            raise PipelineError(
                f"영상의 프레임레이트를 알 수 없습니다. {CFR_MESSAGE}.", ("RATE_UNKNOWN",)
            )
        _check_cfr(facts, rate_value)
        rate = whitelisted_rate(rate_value)
        if rate is None:
            raise PipelineError(
                f"프레임레이트 {_rate_label(rate_value)} fps ({rate_value})는 지원 목록"
                f"(23.976/24/25/29.97/30/47.952/48/50/59.94/60)에 없습니다. "
                f"표준 프레임레이트의 {CFR_MESSAGE}.",
                ("RATE_NOT_WHITELISTED",),
            )
        seconds = facts.video_duration or facts.container_duration
        if facts.video_frames:
            duration_frames = facts.video_frames
            if seconds is None:
                seconds = Fraction(duration_frames) / Fraction(rate.numerator, rate.denominator)
        elif seconds is not None:
            duration_frames = frames_for(seconds, rate)
        if seconds is None or not duration_frames:
            raise PipelineError("미디어 길이를 알 수 없습니다.", ("DURATION_UNKNOWN",))
    else:
        seconds = facts.audio_duration or facts.container_duration
        if seconds is None or seconds <= 0:
            raise PipelineError("미디어 길이를 알 수 없습니다.", ("DURATION_UNKNOWN",))
        notes.append("영상 트랙이 없는 오디오 파일입니다. 타임라인 프레임레이트를 골라 주세요.")
    if seconds > max_seconds:
        raise PipelineError(
            f"미디어가 너무 깁니다 ({float(seconds) / 60:.1f}분). 최대 {max_seconds // 60}분까지 "
            "올릴 수 있습니다.",
            ("MEDIA_TOO_LONG",),
        )
    offset_ms = 0
    if facts.has_video and facts.video_start is not None and facts.audio_start is not None:
        delta = facts.audio_start - facts.video_start
        frame = 1 / Fraction(rate.numerator, rate.denominator) if rate else Fraction(1, 25)
        if delta >= frame:
            offset_ms = math.floor(delta * 1000)
            notes.append(f"오디오가 영상보다 {offset_ms} ms 늦게 시작해 전사 시각에 반영했습니다.")
        elif delta <= -frame:
            raise PipelineError(
                "오디오가 영상보다 먼저 시작하는 파일은 지원하지 않습니다. "
                "편집 프로그램에서 오디오/영상을 맞춰 다시 내보낸 뒤 올려 주세요.",
                ("AUDIO_BEFORE_VIDEO",),
            )
    start_frame, start_notes = _start_frame(facts.timecode_tag, rate)
    notes.extend(start_notes)
    return MediaProbe(
        rate=rate,
        duration_frames=duration_frames,
        duration_seconds=seconds,
        start_frame=start_frame,
        timecode_tag=facts.timecode_tag,
        offset_ms=offset_ms,
        audio_only=not facts.has_video,
        notes=tuple(notes),
    )


# --------------------------------------------------------------------------- PyAV


def _fraction(value: Any) -> Fraction | None:
    if value is None:
        return None
    try:
        result = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return result if result > 0 else None


def _tag(metadata: object) -> str | None:
    if isinstance(metadata, dict):
        value = metadata.get("timecode")
        if isinstance(value, str) and value.strip():
            return value.strip()[:64]
    return None


def read_streams(path: Path) -> StreamFacts:  # pragma: no cover - exercised with PyAV only
    """Demux-only probe with PyAV. Raises :class:`PipelineError` when not media."""
    try:
        av: Any = importlib.import_module("av")
    except ImportError as exc:
        raise PipelineError(
            '미디어 분석 구성요소(PyAV)가 설치되지 않았습니다. 관리자: pip install -e ".[web,asr]"',
            ("ASR_EXTRA_NOT_INSTALLED",),
        ) from exc
    try:
        container = av.open(str(path), mode="r")
    except Exception as exc:  # PyAV raises many FFmpeg error types
        raise PipelineError(
            "영상/오디오 파일로 읽을 수 없습니다.", ("NOT_MEDIA", type(exc).__name__)
        ) from exc
    try:
        video = container.streams.video[0] if container.streams.video else None
        audio = container.streams.audio[0] if container.streams.audio else None
        tag = _tag(dict(container.metadata))
        for stream in container.streams:
            tag = tag or _tag(dict(stream.metadata))
        duration = Fraction(container.duration, 1_000_000) if container.duration else None
        audio_start = audio_duration = None
        if audio is not None:
            atb = _fraction(audio.time_base)
            if atb is not None and audio.start_time is not None:
                audio_start = audio.start_time * atb
            if atb is not None and audio.duration:
                audio_duration = audio.duration * atb
        if video is None:
            return StreamFacts(
                container_duration=duration,
                has_video=False,
                has_audio=audio is not None,
                audio_start=audio_start,
                audio_duration=audio_duration,
                timecode_tag=tag,
            )
        vtb = _fraction(video.time_base)
        pts: list[int] = []
        for packet in container.demux(video):
            if packet.pts is not None:
                pts.append(int(packet.pts))
            if len(pts) >= PTS_SAMPLE_PACKETS:
                break
        pts.sort()
        return StreamFacts(
            container_duration=duration,
            has_video=True,
            video_avg_rate=_fraction(video.average_rate),
            video_base_rate=_fraction(video.base_rate),
            video_time_base=vtb,
            video_frames=int(video.frames) if video.frames else None,
            video_duration=(video.duration * vtb) if vtb and video.duration else None,
            video_start=(video.start_time * vtb) if vtb and video.start_time is not None else None,
            pts_deltas=tuple(b - a for a, b in itertools.pairwise(pts)),
            has_audio=audio is not None,
            audio_start=audio_start,
            audio_duration=audio_duration,
            timecode_tag=tag,
        )
    finally:
        container.close()
