"""INT-002: integration of LAYER-001 with STUDIO-T0/T1 (core changes requested by T1).

TEST_ONLY_SUPPORT. No Resolve, no media, no rendering. File-path editor actions are
edits of our own re-read timeline; Studio editor actions edit the fake object graph.
"""

import itertools
from dataclasses import replace

import pytest
from test_studio_parity import (
    CANDIDATES,
    RATE,
    Studio,
    _rename_xml,
    _written,
    file_path,
    fixture,
)

from davinci_ai_editor.apply_cuts import (
    ApplyConfirmation,
    SkipReason,
    actual_binding_digest,
    apply_approved_cuts,
    apply_locks,
    build_apply_confirmation,
)
from davinci_ai_editor.candidate_markers import attach_candidate_markers, read_marker_selections
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffItem,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    ReimportedTimeline,
)
from davinci_ai_editor.roundtrip_diff import (
    ChangeKind,
    RoundTripArtifactRef,
    RoundTripDiff,
    RoundTripFormat,
    contiguous_split_frames,
    diff_roundtrip,
    roundtrip_artifact_ref,
)
from davinci_ai_editor.roundtrip_verification import (
    ActualProvenance,
    VerificationStatus,
    render_report,
    verify_roundtrip,
)
from davinci_ai_editor.studio_razor import SplitChangeKind, classify_split_change
from davinci_ai_editor.studio_transport import (
    MutationStatus,
    cut_geometry,
    diff_studio_read,
)
from davinci_ai_editor.trust_evidence import artifact_revision
from davinci_ai_editor.xmeml_reader import read_xmeml

CAM = HandoffMediaRef("cam.mov", "C:/media/cam.mov", FrameRange(0, 1000), 0)
REC = HandoffMediaRef("rec.wav", "C:/media/rec.wav", FrameRange(0, 1000), 0)
MUSIC = HandoffMediaRef("music.wav", "C:/media/music.wav", FrameRange(0, 1000), 0)
SPLITS: dict[str, tuple[int, ...]] = {"Video 1": (30, 40), "Audio 1": (30, 40)}


# --- confirmation binding (commit 1) --------------------------------------------------


def _linked(audio_media: HandoffMediaRef, link: str | None) -> ReimportedTimeline:
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
    assert actual_binding_digest(_linked(CAM, "L1")) == actual_binding_digest(_linked(CAM, None))
    # separate-recorder audio linked by the file: real information -> stays bound
    assert actual_binding_digest(_linked(REC, "L1")) != actual_binding_digest(_linked(REC, None))
    # a dangling (single-member) group is not implied either
    linked = _linked(CAM, None)
    video = linked.tracks[0].items[0]
    assert isinstance(video, HandoffClip)
    tracks = (
        replace(linked.tracks[0], items=(replace(video, link_group="L9"),)),
        linked.tracks[1],
    )
    assert actual_binding_digest(replace(linked, tracks=tracks)) != actual_binding_digest(linked)
    # the transport label is not content
    studio = replace(_linked(CAM, None), evidence_class="STUDIO_API_READ")
    assert actual_binding_digest(studio) == actual_binding_digest(_linked(CAM, None))


# --- (a) non-file evidence class ------------------------------------------------------


def test_studio_reads_are_studio_api_read_end_to_end_never_file_roundtrip() -> None:
    studio = Studio()
    handoff = studio.handoff()
    live = studio.read_port.read()
    assert live.actual is not None
    assert live.actual.evidence_class == "STUDIO_API_READ"
    assert live.artifact_ref.evidence_class == "STUDIO_API_READ"
    assert live.artifact_ref.evidence_domain == "TEST_ONLY_SUPPORT"
    diff = diff_studio_read(handoff.timeline, live)
    assert diff.evidence_class == "STUDIO_API_READ" and diff.evidence_domain == "TEST_ONLY_SUPPORT"
    report = verify_roundtrip(
        artifact_revision("t", handoff.timeline.name, handoff.timeline),
        handoff.timeline,
        diff,
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.evidence_class == "STUDIO_API_READ" and report.native_evidence is False
    assert report.verified_live is False
    assert "Evidence: STUDIO_API_READ (Studio API read, TEST_ONLY_SUPPORT" in render_report(report)
    # the file path stays FILE_ROUNDTRIP
    _, actual_file, conf_file, _ = file_path()
    assert actual_file.evidence_class == "FILE_ROUNDTRIP"
    assert conf_file.actual.evidence_class == "FILE_ROUNDTRIP"


def test_evidence_class_and_format_cannot_be_mixed() -> None:
    with pytest.raises(ValueError, match="does not match format"):
        RoundTripArtifactRef("x", RoundTripFormat.XMEML, "0" * 64, "STUDIO_API_READ")
    with pytest.raises(ValueError, match="does not match format"):
        RoundTripArtifactRef("x", RoundTripFormat.STUDIO_API_READ, "0" * 64)
    with pytest.raises(ValueError, match="never native"):
        replace(_linked(CAM, None), evidence_class="NATIVE")  # type: ignore[arg-type]
    studio_actual = replace(_linked(CAM, None), evidence_class="STUDIO_API_READ")
    expected = HandoffTimeline("T", RATE, 0, studio_actual.tracks)
    with pytest.raises(ValueError, match="different evidence classes"):
        diff_roundtrip(
            expected,
            studio_actual,
            artifact_ref=roundtrip_artifact_ref("f.xml", "x", RoundTripFormat.XMEML),
        )


# --- (b) expected split frames: NEUTRAL_SPLIT on the file path ------------------------


def _razor(actual: ReimportedTimeline, splits: dict[str, tuple[int, ...]]) -> ReimportedTimeline:
    """The editor's blade at timeline frames (Resolve keeps name, media, enabled)."""
    tracks: list[HandoffTrack] = []
    for track in actual.tracks:
        frames = sorted(splits.get(track.name, ()))
        items: list[HandoffItem] = []
        cursor = 0
        for item in track.items:
            start, end = cursor, cursor + item.duration
            cursor = end
            inner = [f for f in frames if start < f < end]
            if not isinstance(item, HandoffClip) or not inner:
                items.append(item)
                continue
            bounds = [start, *inner, end]
            for k, (a, b) in enumerate(itertools.pairwise(bounds)):
                src = FrameRange(
                    item.source_range.start + a - start, item.source_range.start + b - start
                )
                markers = tuple(m for m in item.markers if src.contains(m.frame_range))
                group = None if item.link_group is None else f"{item.link_group}.r{k}"
                items.append(replace(item, source_range=src, markers=markers, link_group=group))
        tracks.append(replace(track, items=tuple(items)))
    return replace(actual, tracks=tuple(tracks))


def _file_razor_flow(
    splits: dict[str, tuple[int, ...]], listed: dict[str, tuple[int, ...]] | None
) -> tuple[RoundTripDiff, ApplyConfirmation]:
    handoff = attach_candidate_markers(fixture(), CANDIDATES)
    exported = _rename_xml(_written(handoff.timeline), {"AIE-0003": "OK"})
    read = read_xmeml(exported)
    assert read.timeline is not None and read.complete
    razored = _razor(read.timeline, splits)
    diff = diff_roundtrip(
        handoff.timeline,
        razored,
        artifact_ref=roundtrip_artifact_ref("razor.xml", "razored", RoundTripFormat.XMEML),
        expected_splits=listed,
    )
    selection = read_marker_selections(razored, handoff.candidates)
    return diff, build_apply_confirmation(selection, handoff.timeline, diff)


def test_editor_razor_at_listed_frames_is_neutral_on_the_file_path() -> None:
    diff, confirmation = _file_razor_flow(SPLITS, SPLITS)
    kinds = {c.change_id: c.kind for c in diff.changes}
    assert kinds["E:VIDEO:1:0"] is ChangeKind.NEUTRAL_SPLIT
    assert kinds["E:AUDIO:1:0"] is ChangeKind.NEUTRAL_SPLIT
    assert apply_locks(diff) == ()  # the renamed marker is the approval channel, not an edit
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0003"]
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    _, _, _, no_razor = file_path({"AIE-0003": "OK"})
    assert cut_geometry(applied.timeline) == cut_geometry(no_razor.timeline)


@pytest.mark.parametrize(
    "listed",
    [None, {"Video 1": (30, 41), "Audio 1": (30, 41)}],
    ids=["not-listed", "unlisted-frame"],
)
def test_razor_not_at_listed_frames_stays_a_human_split(
    listed: dict[str, tuple[int, ...]] | None,
) -> None:
    diff, confirmation = _file_razor_flow(SPLITS, listed)
    kinds = {c.change_id: c.kind for c in diff.changes}
    assert kinds["E:VIDEO:1:0"] is ChangeKind.SPLIT
    assert apply_locks(diff)  # HARD_LOCK
    skipped = {s.candidate_id: s.reason for s in confirmation.skipped}
    assert skipped["AIE-0003"] is SkipReason.HUMAN_EDIT_LOCKED


def test_expected_split_references_are_never_guessed() -> None:
    handoff = attach_candidate_markers(fixture(), CANDIDATES)
    actual = ReimportedTimeline(
        handoff.timeline.name, RATE, handoff.timeline.start_frame, handoff.timeline.tracks
    )
    ref = roundtrip_artifact_ref("x.xml", "x", RoundTripFormat.XMEML)
    for bad in ({"Video 9": (30,)}, {"Video 1": (0,)}, {"Video 1": (30,), "VIDEO:1": (40,)}):
        with pytest.raises(ValueError):
            diff_roundtrip(handoff.timeline, actual, artifact_ref=ref, expected_splits=bad)
    diff = diff_roundtrip(
        handoff.timeline, actual, artifact_ref=ref, expected_splits={"video:1": (40, 30)}
    )
    assert diff.expected_splits[0][1] == (30, 40)  # bound by the diff digest
    assert all(c.kind is ChangeKind.UNCHANGED for c in diff.changes)


def test_split_geometry_rule_is_shared() -> None:
    clip = HandoffClip("A", CAM, FrameRange(0, 100))
    pieces = (
        (0, replace(clip, source_range=FrameRange(0, 30))),
        (30, replace(clip, source_range=FrameRange(30, 100))),
    )
    assert contiguous_split_frames(0, clip, pieces, lambda p: True) == (30,)
    moved = ((0, pieces[0][1]), (31, pieces[1][1]))
    assert isinstance(contiguous_split_frames(0, clip, moved, lambda p: True), str)
    assert contiguous_split_frames(0, clip, pieces, lambda p: False) == "item changed"


def test_studio_razor_and_rt001_agree_on_neutral_splits() -> None:
    studio = Studio()
    handoff = studio.handoff()
    studio.decide({"AIE-0003": "OK"})
    before = studio.read_port.read().actual
    assert before is not None
    for frame in (30, 40):
        studio.project.timeline._playhead = 86400 + frame
        assert studio.project.timeline._blade("video", 1)
        assert studio.project.timeline._blade("audio", 1)
    live = studio.read_port.read()
    assert live.actual is not None
    plan = {name: frozenset(frames) for name, frames in SPLITS.items()}
    assert classify_split_change(before, live.actual, plan).kind is SplitChangeKind.NEUTRAL_SPLIT
    diff = diff_studio_read(handoff.timeline, live, expected_splits=SPLITS)
    assert diff.change("E:VIDEO:1:0").kind is ChangeKind.NEUTRAL_SPLIT
    selection = read_marker_selections(live.actual, handoff.candidates)
    confirmation = build_apply_confirmation(selection, handoff.timeline, diff)
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0003"]
    # the razored cut is now on item boundaries: applied in place, same geometry as the file
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    _, _, _, applied_file = file_path({"AIE-0003": "OK"})
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    assert cut_geometry(outcome.readback_read.actual) == cut_geometry(applied_file.timeline)
    # without the list the same razor is a human SPLIT (HARD_LOCK)
    assert diff_studio_read(handoff.timeline, live).change("E:VIDEO:1:0").kind is ChangeKind.SPLIT
