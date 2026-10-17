"""INT-002: integration of LAYER-001 with STUDIO-T0/T1 and WEB-001/002.

TEST_ONLY_SUPPORT. No Resolve, no media, no rendering.
"""

from dataclasses import replace

from davinci_ai_editor.apply_cuts import actual_binding_digest
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffMediaRef,
    HandoffTrack,
    HandoffTrackKind,
    ReimportedTimeline,
)
from davinci_ai_editor.temporal_mapping import FrameRate

RATE = FrameRate(25, 1)
CAM = HandoffMediaRef("cam.mov", "C:/media/cam.mov", FrameRange(0, 1000), 0)
REC = HandoffMediaRef("rec.wav", "C:/media/rec.wav", FrameRange(0, 1000), 0)


def _timeline(audio_media: HandoffMediaRef, link: str | None) -> ReimportedTimeline:
    video = HandoffClip("cam", CAM, FrameRange(0, 200), link_group=link)
    audio = HandoffClip("a", audio_media, FrameRange(0, 200), link_group=link)
    return ReimportedTimeline(
        "T",
        RATE,
        0,
        (
            HandoffTrack("Video 1", HandoffTrackKind.VIDEO, (video,)),
            HandoffTrack("Audio 1", HandoffTrackKind.AUDIO, (audio,)),
        ),
    )


def test_binding_digest_drops_only_link_groups_the_writer_rule_implies() -> None:
    # same media + range + source: the APPLY-001 rule links them anyway -> not bound
    assert actual_binding_digest(_timeline(CAM, "L1")) == actual_binding_digest(
        _timeline(CAM, None)
    )
    # separate-recorder audio linked by the file: real information -> stays bound
    assert actual_binding_digest(_timeline(REC, "L1")) != actual_binding_digest(
        _timeline(REC, None)
    )
    # a dangling (single-member) group is not implied either
    linked = _timeline(CAM, None)
    tracks = (
        replace(linked.tracks[0], items=(replace(linked.tracks[0].items[0], link_group="L9"),)),
        linked.tracks[1],
    )
    assert actual_binding_digest(replace(linked, tracks=tracks)) != actual_binding_digest(linked)
