"""Synthetic WEB-001 inputs: a faster-whisper style transcript and media facts (no media, no ASR).

At 25 fps the transcript projects to these source frames (= timeline frames):

- 안녕하세요 [0,15), 저는 [17,25), 저는 [27,35), <script>… [37,60)
- transcript gap 60..100 (1.6 s >= 1.0 s policy) -> candidate [63,97) with 3-frame padding
- 음 [100,108) (filler lexicon hit), 오늘은 [110,123), 이야기 [125,150)

Expected candidates: AIE-0001 repetition [17,27), AIE-0002 transcript gap [63,97),
AIE-0003 filler [100,108).
"""

import json
import re

XSS = "<script>alert(1)</script>"


def transcript_payload() -> dict[str, object]:
    return {
        "language": "ko",
        "language_probability": 0.97,
        "segments": [
            {
                "id": 1,
                "start": 0.0,
                "end": 2.4,
                "text": f" 안녕하세요 저는 저는 {XSS}",
                "words": [
                    {"start": 0.0, "end": 0.6, "word": " 안녕하세요", "probability": 0.9},
                    {"start": 0.7, "end": 1.0, "word": " 저는", "probability": 0.8},
                    {"start": 1.1, "end": 1.4, "word": " 저는", "probability": 0.8},
                    {"start": 1.5, "end": 2.4, "word": " " + XSS, "probability": 0.7},
                ],
            },
            {
                "id": 2,
                "start": 4.0,
                "end": 6.0,
                "text": " 음 오늘은 이야기",
                "words": [
                    {"start": 4.0, "end": 4.3, "word": " 음", "probability": 0.6},
                    {"start": 4.4, "end": 4.9, "word": " 오늘은", "probability": 0.9},
                    {"start": 5.0, "end": 6.0, "word": " 이야기", "probability": 0.9},
                ],
            },
        ],
    }


def transcript_bytes() -> bytes:
    return json.dumps(transcript_payload(), ensure_ascii=False).encode("utf-8")


def form(**overrides: str) -> dict[str, str]:
    values = {
        "tool": "faster-whisper",
        "tool_version": "1.1.1",
        "model_id": "large-v3",
        "offset_ms": "0",
        "media_path": "D:\\Footage\\interview.mov",
        "rate": "25/1",
        "duration_frames": "200",
        "media_start": "01:00:00:00",
        "profile": "RESOLVE",
        "timeline_name": "인터뷰",
        "timeline_start": "01:00:00:00",
        "gap_seconds": "1.0",
    }
    values.update(overrides)
    return values


def rename(text: str, old: str, new: str) -> str:
    needle = f"<name>{old}</name>"
    assert text.count(needle) == 1, old
    return text.replace(needle, f"<name>{new}</name>")


def editor_export(candidate_xml: str) -> str:
    """Simulated Resolve work: approve 0001 and 0002 (Korean alias), reject 0003."""
    text = rename(candidate_xml, "AIE-0001 ?", "AIE-0001 OK")
    text = rename(text, "AIE-0002 ?", "AIE-0002 승인")
    return rename(text, "AIE-0003 ?", "AIE-0003 X")


def reexport(applied_xml: str) -> str:
    """Simulated immediate re-export: Resolve renumbers clipitem ids."""
    return applied_xml.replace("clipitem-", "item-")


def csrf_token(page: str) -> str:
    match = re.search(r'name="csrf_token" value="([A-Za-z0-9_-]{32,64})"', page)
    assert match is not None, "csrf token missing"
    return match.group(1)


def hidden_digest(page: str) -> str:
    match = re.search(r'name="digest" value="([0-9a-f]{64})"', page)
    assert match is not None, "confirmation form missing"
    return match.group(1)
