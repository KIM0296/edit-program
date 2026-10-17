"""HANDOFF-001 SRT / WebVTT subtitle artifacts (stdlib only).

Writers convert frame ranges to a covering millisecond span (floor start, ceil
end, exact rationals). Cues that cannot be written are *refused* with an
explicit diagnostic, never silently dropped. A written subtitle file is an
Expected artifact; it is not evidence of any NLE subtitle track state.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .handoff_model import (
    ARTIFACT_KIND,
    HandoffDiagnostic,
    HandoffDiagnosticCode,
    HandoffSubtitleCue,
    has_refusal,
    refusal,
)
from .temporal_mapping import FrameRate
from .timecode import frame_span_to_ms

# Adapted from srt (Christopher Down), srt.py make_legal_content /
# MULTI_WS_REGEX and SUBTITLE_SKIP_CONDITIONS, MIT License.
# See licenses/srt-LICENSE.txt. Skip conditions become explicit refusals here.
_MULTI_NEWLINE = re.compile(r"\n\n+")
_ARROW = "-->"
BOM = chr(0xFEFF)


@dataclass(frozen=True)
class SubtitleWriteResult:
    text: str
    written_count: int
    diagnostics: tuple[HandoffDiagnostic, ...]
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.artifact_kind != ARTIFACT_KIND or self.authorizes_import is not False:
            raise ValueError("Subtitle results are artifacts that never authorize import")

    @property
    def complete(self) -> bool:
        """True only when no cue was refused."""
        return not has_refusal(self.diagnostics)


@dataclass(frozen=True)
class SrtCue:
    index: int
    start_ms: int
    end_ms: int
    text: str

    def __post_init__(self) -> None:
        if type(self.index) is not int or type(self.start_ms) is not int:
            raise TypeError("SRT cue index and start must be ints")
        if type(self.end_ms) is not int or not isinstance(self.text, str):
            raise TypeError("SRT cue end must be an int and text a string")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("SRT cue requires 0 <= start < end")


@dataclass(frozen=True)
class SrtReadResult:
    cues: tuple[SrtCue, ...]
    diagnostics: tuple[HandoffDiagnostic, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cues", tuple(self.cues))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @property
    def ok(self) -> bool:
        return not self.diagnostics


def legalize_text(text: str) -> str:
    """Normalize newlines, strip outer blank lines, collapse inner blank lines."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return _MULTI_NEWLINE.sub("\n", normalized.strip("\n"))


def _split_ms(ms: int) -> tuple[int, int, int, int]:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return hours, minutes, seconds, millis


def ms_to_srt_timestamp(ms: int) -> str:
    if type(ms) is not int or ms < 0:
        raise ValueError("Timestamp must be a nonnegative int of milliseconds")
    h, m, s, f = _split_ms(ms)
    return f"{h:02d}:{m:02d}:{s:02d},{f:03d}"


def ms_to_vtt_timestamp(ms: int) -> str:
    if type(ms) is not int or ms < 0:
        raise ValueError("Timestamp must be a nonnegative int of milliseconds")
    h, m, s, f = _split_ms(ms)
    return f"{h:02d}:{m:02d}:{s:02d}.{f:03d}"


def _prepare(
    cues: Sequence[HandoffSubtitleCue], rate: FrameRate
) -> tuple[list[tuple[int, int, str]], list[HandoffDiagnostic]]:
    """Validate + order cues. Returns (start_ms, end_ms, text) and refusals."""
    accepted: list[tuple[int, int, int, str]] = []
    diagnostics: list[HandoffDiagnostic] = []
    for position, cue in enumerate(cues):
        if not isinstance(cue, HandoffSubtitleCue):
            raise TypeError("Subtitle writer requires HandoffSubtitleCue values")
        location = f"cue[{position}]"
        text = legalize_text(cue.text)
        if not text.strip():
            diagnostics.append(
                refusal(HandoffDiagnosticCode.EMPTY_TEXT, location, "Cue has no content")
            )
            continue
        if _ARROW in text:
            diagnostics.append(
                refusal(HandoffDiagnosticCode.ARROW_IN_TEXT, location, "Cue text contains '-->'")
            )
            continue
        start_ms, end_ms = frame_span_to_ms(cue.frame_range.start, cue.frame_range.end, rate)
        accepted.append((start_ms, end_ms, position, text))
    accepted.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(s, e, t) for s, e, _, t in accepted], diagnostics


def write_srt(cues: Sequence[HandoffSubtitleCue], rate: FrameRate) -> SubtitleWriteResult:
    """Compose SRT: renumbered from 1, ``HH:MM:SS,mmm``, LF line endings."""
    prepared, diagnostics = _prepare(cues, rate)
    blocks = [
        f"{n}\n{ms_to_srt_timestamp(s)} --> {ms_to_srt_timestamp(e)}\n{text}\n\n"
        for n, (s, e, text) in enumerate(prepared, start=1)
    ]
    return SubtitleWriteResult("".join(blocks), len(prepared), tuple(diagnostics))


def escape_vtt_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_vtt(cues: Sequence[HandoffSubtitleCue], rate: FrameRate) -> SubtitleWriteResult:
    """Compose WebVTT with ``WEBVTT`` header; text escaped for ``& < >``."""
    prepared, diagnostics = _prepare(cues, rate)
    blocks = [
        f"{ms_to_vtt_timestamp(s)} --> {ms_to_vtt_timestamp(e)}\n{escape_vtt_text(text)}\n\n"
        for s, e, text in prepared
    ]
    return SubtitleWriteResult("WEBVTT\n\n" + "".join(blocks), len(prepared), tuple(diagnostics))


_SRT_TIMESTAMP = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
_SRT_TIMING = re.compile(rf"^{_SRT_TIMESTAMP} --> {_SRT_TIMESTAMP}$")
_SRT_INDEX = re.compile(r"^[1-9]\d*$")


def _timestamp_ms(groups: tuple[str, ...]) -> int:
    h, m, s, f = (int(g) for g in groups)
    return ((h * 60 + m) * 60 + s) * 1000 + f


def read_srt(text: str) -> SrtReadResult:
    """Strict SRT reader: BOM and CRLF tolerated; anything else malformed is reported.

    Each block must be ``index`` / ``start --> end`` / one or more text lines.
    Indices must be sequential from 1. Malformed blocks are reported and not
    returned; ``ok`` is False if any diagnostic exists.
    """
    if not isinstance(text, str):
        raise TypeError("SRT input must be a string")
    text = text.removeprefix(BOM)
    normalized = text.replace("\r\n", "\n")
    diagnostics: list[HandoffDiagnostic] = []
    if "\r" in normalized:
        diagnostics.append(
            refusal(HandoffDiagnosticCode.MALFORMED_DOCUMENT, "document", "Bare CR line ending")
        )
        return SrtReadResult((), tuple(diagnostics))
    body = normalized.strip("\n")
    if not body:
        return SrtReadResult((), ())
    cues: list[SrtCue] = []
    for position, block in enumerate(re.split(r"\n[ \t]*\n+", body)):
        location = f"block[{position}]"
        lines = block.split("\n")
        if len(lines) < 3:
            diagnostics.append(
                refusal(HandoffDiagnosticCode.MALFORMED_BLOCK, location, "Block is incomplete")
            )
            continue
        index_line, timing_line, *text_lines = lines
        if not _SRT_INDEX.match(index_line):
            diagnostics.append(
                refusal(HandoffDiagnosticCode.BAD_INDEX, location, "Index is not an integer")
            )
            continue
        expected = len(cues) + 1
        if int(index_line) != expected:
            diagnostics.append(
                refusal(
                    HandoffDiagnosticCode.BAD_INDEX,
                    location,
                    f"Index {index_line} is not sequential (expected {expected})",
                )
            )
        timing = _SRT_TIMING.match(timing_line)
        if timing is None:
            diagnostics.append(
                refusal(HandoffDiagnosticCode.BAD_TIMESTAMP, location, "Malformed timing line")
            )
            continue
        start_ms = _timestamp_ms(timing.groups()[:4])
        end_ms = _timestamp_ms(timing.groups()[4:])
        if end_ms <= start_ms:
            diagnostics.append(
                refusal(
                    HandoffDiagnosticCode.NONPOSITIVE_DURATION, location, "Start is not before end"
                )
            )
            continue
        content = "\n".join(text_lines)
        if not content.strip():
            diagnostics.append(refusal(HandoffDiagnosticCode.EMPTY_TEXT, location, "No content"))
            continue
        cues.append(SrtCue(int(index_line), start_ms, end_ms, content))
    return SrtReadResult(tuple(cues), tuple(diagnostics))
