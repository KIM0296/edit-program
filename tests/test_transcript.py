"""Frame-domain transcript word contract tests (synthetic, no media, no ASR)."""

import pytest

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.temporal_mapping import SourceFrameRange
from davinci_ai_editor.transcript import (
    TranscriptSnapshot,
    TranscriptTokenKind,
    TranscriptWord,
    WordTimingStatus,
)


def rng(start: int, end: int) -> SourceFrameRange:
    return SourceFrameRange(FrameRange(start, end))


def word(ref: str, text: str, start: int | None, end: int | None = None) -> TranscriptWord:
    if start is None:
        return TranscriptWord(ref, text, None, WordTimingStatus.MISSING)
    assert end is not None
    return TranscriptWord(ref, text, rng(start, end), WordTimingStatus.ALIGNED)


def snapshot(*words: TranscriptWord) -> TranscriptSnapshot:
    return TranscriptSnapshot("tx-1", "src-1", "producer-ev-1", 1, words)


def test_text_is_nfc_normalized_without_other_rewriting() -> None:
    decomposed = "가 ."  # NFD 가 + space + period
    assert word("w1", decomposed, 0, 2).text == "가 ."


def test_timed_status_and_range_must_agree() -> None:
    with pytest.raises(ValueError, match="Timed status"):
        TranscriptWord("w1", "어", None, WordTimingStatus.ALIGNED)
    with pytest.raises(ValueError, match="Timed status"):
        TranscriptWord("w1", "어", rng(0, 2), WordTimingStatus.MISSING)
    with pytest.raises(ValueError, match="Timed status"):
        TranscriptWord("w1", "어", rng(0, 2), WordTimingStatus.UNKNOWN)
    interpolated = TranscriptWord("w1", "어", rng(0, 2), WordTimingStatus.INTERPOLATED)
    assert interpolated.is_timed


@pytest.mark.parametrize("bad", ["", "  ", None, 3])
def test_blank_or_untyped_text_and_refs_are_refused(bad: object) -> None:
    with pytest.raises(ValueError):
        TranscriptWord("w1", bad, None, WordTimingStatus.MISSING)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        TranscriptWord(bad, "어", None, WordTimingStatus.MISSING)  # type: ignore[arg-type]


def test_untyped_enums_and_ranges_are_refused() -> None:
    with pytest.raises(TypeError):
        TranscriptWord("w1", "어", None, "MISSING")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        TranscriptWord(
            "w1",
            "어",
            None,
            WordTimingStatus.MISSING,
            kind="WORD",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        TranscriptWord(
            "w1",
            "어",
            FrameRange(0, 2),  # type: ignore[arg-type]
            WordTimingStatus.ALIGNED,
        )
    with pytest.raises(ValueError):
        TranscriptWord("w1", "어", None, WordTimingStatus.MISSING, speaker_ref=" ")


def test_snapshot_orders_timed_words_and_keeps_untimed_words() -> None:
    snap = snapshot(word("w1", "저는", 0, 5), word("w2", "음", None), word("w3", "학생", 5, 9))
    assert [w.word_ref for w in snap.timed_words] == ["w1", "w3"]
    assert snap.word("w2").source_range is None
    with pytest.raises(KeyError):
        snap.word("w9")


def test_snapshot_refuses_overlap_disorder_and_duplicates() -> None:
    with pytest.raises(ValueError, match="nonoverlapping"):
        snapshot(word("w1", "a", 0, 5), word("w2", "b", 4, 8))
    with pytest.raises(ValueError, match="nonoverlapping"):
        snapshot(word("w1", "a", 5, 8), word("w2", "b", 0, 4))
    with pytest.raises(ValueError, match="Duplicate"):
        snapshot(word("w1", "a", 0, 2), word("w1", "b", 2, 4))


def test_snapshot_requires_provenance_and_tolerance() -> None:
    with pytest.raises(ValueError, match="producer"):
        TranscriptSnapshot("tx", "src", " ", 0, ())
    with pytest.raises(ValueError, match="tolerance"):
        TranscriptSnapshot("tx", "src", "p", -1, ())
    with pytest.raises(ValueError, match="tolerance"):
        TranscriptSnapshot("tx", "src", "p", True, ())
    with pytest.raises(TypeError):
        TranscriptSnapshot("tx", "src", "p", 0, ("w",))  # type: ignore[arg-type]


def test_audio_event_tokens_are_distinct_kind() -> None:
    event = TranscriptWord(
        "e1", "(웃음)", rng(0, 3), WordTimingStatus.ALIGNED, TranscriptTokenKind.AUDIO_EVENT
    )
    assert event.kind is TranscriptTokenKind.AUDIO_EVENT
