"""LAYER-001: layers are never merged; each track is edited on its own.

Synthetic multi-layer timeline (no media, no Resolve, no rendering). Editor
actions are text edits of written xmeml:

V1 interview | V2 B-roll clip with a colour filter | V3 title generatoritem
A1/A2 interview (linked to V1) | A3 music bed spanning the cuts | A4 SFX after the cut
"""

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest
from support import roundtrip_fixtures as fx

from davinci_ai_editor.apply_cuts import (
    ApplyConfirmation,
    ApplyRefused,
    SkipReason,
    apply_approved_cuts,
    build_apply_confirmation,
)
from davinci_ai_editor.candidate_markers import (
    CandidateDecision,
    CandidateHandoff,
    CutCandidate,
    attach_candidate_markers,
    read_marker_selections,
)
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffDiagnosticCode,
    HandoffGap,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    LayerItemKind,
    PassthroughItem,
    ReimportedTimeline,
)
from davinci_ai_editor.layer_policy import (
    LayerFindingKind,
    LayerIssueCode,
    TrackEditPolicy,
    TrackEffectKind,
    TrackPolicyOverride,
)
from davinci_ai_editor.otio_json import read_otio, write_otio
from davinci_ai_editor.roundtrip_diff import (
    DiffStatus,
    RoundTripDiff,
    RoundTripFormat,
    diff_otio_roundtrip,
    roundtrip_artifact_ref,
)
from davinci_ai_editor.roundtrip_verification import (
    ActualProvenance,
    ItemStatus,
    VerificationStatus,
    verify_roundtrip,
)
from davinci_ai_editor.xmeml_reader import read_xmeml
from davinci_ai_editor.xmeml_writer import write_xmeml

INTERVIEW = HandoffMediaRef("int", "/media/interview.mov", FrameRange(0, 2000), 0)
BROLL = HandoffMediaRef("broll", "/media/broll.mov", FrameRange(0, 2000), 0)
MUSIC = HandoffMediaRef("music", "/media/music.wav", FrameRange(0, 2000), 0)
SFX = HandoffMediaRef("sfx", "/media/whoosh.wav", FrameRange(0, 2000), 0)

FILTER = (
    "<filter><effect><name>Color Correction</name><effectid>colorcorrection</effectid>"
    "<effecttype>filter</effecttype><mediatype>video</mediatype><parameter>"
    "<parameterid>brightness</parameterid><value>10</value>"
    "<keyframe><when>0</when><value>5</value></keyframe>"
    "<keyframe><when>40</when><value>15</value></keyframe>"
    "</parameter></effect></filter>"
)
AUDIO_FILTER = (
    "<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid>"
    "<effecttype>filter</effecttype><mediatype>audio</mediatype><parameter>"
    "<parameterid>level</parameterid><value>0.8</value></parameter></effect></filter>"
)
RETIME = (
    "<filter><effect><name>Time Remap</name><effectid>timeremap</effectid>"
    "<effecttype>motion</effecttype></effect></filter>"
)


def _generator(start: int, end: int) -> str:
    return (
        '<generatoritem id="gen-7"><name>Lower Third</name>'
        f"<duration>{end - start}</duration>"
        "<rate><timebase>25</timebase><ntsc>FALSE</ntsc></rate>"
        f"<start>{start}</start><end>{end}</end><enabled>TRUE</enabled>"
        f"<in>0</in><out>{end - start}</out>"
        "<effect><name>Text</name><effectid>Text</effectid><effectcategory>Text</effectcategory>"
        "<effecttype>generator</effecttype><mediatype>video</mediatype>"
        "<parameter><parameterid>str</parameterid><name>Text</name><value>Jane Doe</value>"
        "</parameter></effect></generatoritem>"
    )


CUT_1 = CutCandidate("AIE-0001", FrameRange(100, 130), "long pause")
CUT_2 = CutCandidate("AIE-0002", FrameRange(320, 330), "um under the title")


def _base(*, stereo: bool = True) -> HandoffTimeline:
    v1 = HandoffTrack(
        "V1", HandoffTrackKind.VIDEO, (HandoffClip("Interview", INTERVIEW, FrameRange(0, 400)),)
    )
    v2 = HandoffTrack(
        "V2",
        HandoffTrackKind.VIDEO,
        (HandoffGap(200), HandoffClip("Broll", BROLL, FrameRange(100, 160))),
    )
    v3 = HandoffTrack("V3", HandoffTrackKind.VIDEO, ())
    a1 = HandoffTrack(
        "A1", HandoffTrackKind.AUDIO, (HandoffClip("Int L", INTERVIEW, FrameRange(0, 400)),)
    )
    a2 = HandoffTrack(
        "A2", HandoffTrackKind.AUDIO, (HandoffClip("Int R", INTERVIEW, FrameRange(0, 400)),)
    )
    a3 = HandoffTrack(
        "A3", HandoffTrackKind.AUDIO, (HandoffClip("Music", MUSIC, FrameRange(0, 400)),)
    )
    a4 = HandoffTrack(
        "A4",
        HandoffTrackKind.AUDIO,
        (HandoffGap(250), HandoffClip("SFX", SFX, FrameRange(0, 20))),
    )
    audio = (a1, a2, a3, a4) if stereo else (a1, a3, a4)
    return HandoffTimeline("Interview", fx.RATE, 0, (v1, v2, v3, *audio))


def _insert_into_clip(text: str, clip_id: str, xml: str) -> str:
    pattern = re.compile(rf'(<clipitem id="{re.escape(clip_id)}">.*?)(\s*</clipitem>)', re.DOTALL)
    result, count = pattern.subn(lambda m: m.group(1) + xml + m.group(2), text, count=1)
    assert count == 1, clip_id
    return result


def _fill_track(text: str, index: int, xml: str) -> str:
    """Put raw xml into the n-th <track> (document order), empty or not."""
    matches = list(re.finditer(r"<track\s*/>|<track>", text))
    match = matches[index]
    if match.group(0).endswith("/>"):
        return text[: match.start()] + f"<track>{xml}</track>" + text[match.end() :]
    close = text.index("</track>", match.end())
    return text[:close] + xml + text[close:]


def _source_track(index: int) -> str:
    return (
        f"<sourcetrack><mediatype>audio</mediatype><trackindex>{index}</trackindex></sourcetrack>"
    )


SEQUENCE_MARKERS = (
    "<marker><name>chapter 2</name><comment>c</comment><in>150</in><out>-1</out></marker>"
    "<marker><name>breath note</name><comment /><in>110</in><out>115</out></marker>"
)


def _editor_original(
    *,
    stereo: bool = True,
    audio_filter: bool = False,
    sourcetrack: bool = True,
    markers: bool = False,
) -> str:
    """The editor's own multi-layer timeline as exported before the handoff."""
    text = fx.written(_base(stereo=stereo))
    text = _insert_into_clip(text, "clipitem-2", FILTER)  # V2 B-roll colour filter
    text = _fill_track(text, 2, _generator(300, 350))  # V3 title
    if stereo and sourcetrack:  # one stereo file: A1 = left, A2 = right channel
        text = _insert_into_clip(text, "clipitem-3", _source_track(1))
        text = _insert_into_clip(text, "clipitem-4", _source_track(2))
    if audio_filter:
        text = _insert_into_clip(text, "clipitem-3", AUDIO_FILTER)  # A1 levels
    if markers:
        text = text.replace("</media>", "</media>" + SEQUENCE_MARKERS, 1)
    return text


def _rename(text: str, old: str, new: str) -> str:
    needle = f"<name>{old}</name>"
    assert text.count(needle) == 1, old
    return text.replace(needle, f"<name>{new}</name>")


def _expected(original_text: str) -> CandidateHandoff:
    read = read_xmeml(original_text)
    assert read.timeline is not None, read.diagnostics
    original = read.timeline
    expected = HandoffTimeline(
        original.name, original.rate, original.start_frame, original.tracks, original.markers
    )
    return attach_candidate_markers(expected, (CUT_1, CUT_2))


def _approve_all(handoff: CandidateHandoff) -> str:
    text = fx.written(handoff.timeline)
    text = _rename(text, "AIE-0001 ?", "AIE-0001 OK")
    return _rename(text, "AIE-0002 ?", "AIE-0002 OK")


def _confirm(
    handoff: CandidateHandoff,
    exported: str,
    overrides: tuple[TrackPolicyOverride, ...] = (),
) -> tuple[RoundTripDiff, ApplyConfirmation]:
    read = read_xmeml(exported)
    assert read.timeline is not None, read.diagnostics
    diff = fx.diff_text(handoff.timeline, exported)
    selection = read_marker_selections(read.timeline, handoff.candidates)
    confirmation = build_apply_confirmation(
        selection, handoff.timeline, diff, track_overrides=overrides
    )
    return diff, confirmation


def _tracks(text: str, kind: str) -> list[ET.Element]:
    return ET.fromstring(text).findall(f"sequence/media/{kind}/track")


def _timing(element: ET.Element) -> tuple[str | None, ...]:
    return tuple(element.findtext(tag) for tag in ("start", "end", "in", "out"))


def _without(element: ET.Element, *tags: str) -> str:
    copy = ET.fromstring(ET.tostring(element))
    copy.attrib.pop("id", None)
    for child in list(copy):
        if child.tag in tags:
            copy.remove(child)
    for node in copy.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        node.tail = None
    return ET.tostring(copy, encoding="unicode")


A3_CUT = (TrackPolicyOverride("Audio 3", TrackEditPolicy.CUT_WITH_SOURCE),)
MONO_MUSIC_CUT = (TrackPolicyOverride("Audio 2", TrackEditPolicy.CUT_WITH_SOURCE),)


def _scenario(
    *, stereo: bool = True, sourcetrack: bool = True
) -> tuple[str, CandidateHandoff, str, RoundTripDiff, ApplyConfirmation]:
    original = _editor_original(stereo=stereo, sourcetrack=sourcetrack)
    handoff = _expected(original)
    exported = _approve_all(handoff)
    music = A3_CUT if stereo else MONO_MUSIC_CUT
    diff, confirmation = _confirm(handoff, exported, music)
    return original, handoff, exported, diff, confirmation


def test_reader_keeps_unmodelled_items_as_verbatim_passthrough() -> None:
    read = read_xmeml(_editor_original())
    assert read.timeline is not None
    v2, v3 = read.timeline.tracks[1], read.timeline.tracks[2]
    assert v2.items == ()  # the filtered clip is not modelled (trailing gap dropped) ...
    (broll,) = v2.passthrough  # ... but kept verbatim, cuttable 1:1
    assert broll.kind is LayerItemKind.EFFECT_CLIP and broll.has_filters
    assert broll.timeline_range == FrameRange(200, 260)
    assert broll.source_range == FrameRange(100, 160) and broll.media_id == "broll"
    assert "<effectid>colorcorrection</effectid>" in broll.raw_xml
    assert "<file><name>broll</name>" in broll.raw_xml  # file reference inlined, id removed
    (title,) = v3.passthrough
    assert title.kind is LayerItemKind.GENERATOR and not title.cuttable
    assert title.timeline_range == FrameRange(300, 350)
    assert "Jane Doe" in title.raw_xml and 'id="gen-7"' not in title.raw_xml
    assert [r.construct.value for r in read.unknown_regions] == ["FILTER", "GENERATOR"]


def test_written_expected_reemits_passthrough_and_round_trips_identically() -> None:
    handoff = _expected(_editor_original())
    text = fx.written(handoff.timeline)
    video = _tracks(text, "video")
    assert len(video) == 3 and len(_tracks(text, "audio")) == 4
    (generator,) = video[2].findall("generatoritem")
    assert generator.get("id") == "passthrough-2"
    assert generator.findtext("effect/parameter/value") == "Jane Doe"
    (broll,) = video[1].findall("clipitem")
    assert broll.find("filter/effect/effectid") is not None
    broll_file = broll.find("file")
    assert broll_file is not None and broll_file.get("id") == "pt-file-1"
    diff = fx.diff_text(handoff.timeline, text)
    assert diff.unknown_regions == () and diff.status is DiffStatus.COMPLETE
    assert {f.kind for f in diff.layer_findings} == {LayerFindingKind.MATCH}
    reread = read_xmeml(text)
    assert reread.timeline is not None
    assert [t.passthrough for t in reread.timeline.tracks] == [
        t.passthrough for t in handoff.timeline.tracks
    ]


def test_default_policy_skips_cuts_that_would_cut_the_music_bed_or_title() -> None:
    handoff = _expected(_editor_original())
    diff, confirmation = _confirm(handoff, _approve_all(handoff))
    assert diff.unknown_regions == ()
    assert confirmation.approved_cuts == ()
    skipped = {s.candidate_id: s for s in confirmation.skipped}
    assert skipped["AIE-0001"].reason is SkipReason.LAYER_CONFLICT
    assert "Audio 3 [AUDIO:3] clip 'Music' [0,400) spans or overlaps" in skipped["AIE-0001"].detail
    assert skipped["AIE-0002"].reason is SkipReason.LAYER_CONFLICT
    assert "Video 3 [VIDEO:3] GENERATOR 'Lower Third' [300,350)" in skipped["AIE-0002"].detail
    effects = {e.track_name: e for e in confirmation.track_effects}
    assert effects["Audio 3"].effect is TrackEffectKind.CONFLICT
    assert effects["Audio 3"].conflicts == ("AIE-0001", "AIE-0002")
    assert effects["Video 1"].effect is TrackEffectKind.UNCHANGED
    summary = confirmation.summary
    assert "AIE-0001 LAYER_CONFLICT" in summary and "Audio 3 [AUDIO:3]" in summary
    assert "트랙별 결과 / per-track effect:" in summary
    with pytest.raises(ApplyRefused):
        apply_approved_cuts(confirmation, confirmed_digest="0" * 64)


def test_multi_layer_end_to_end_with_override_and_verification() -> None:
    original, _, _, diff, confirmation = _scenario()
    assert diff.unknown_regions == () and diff.status is DiffStatus.COMPLETE
    # --- confirmation with A3=CUT override ---
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0001"]
    (cut,) = confirmation.approved_cuts
    policies = {a.track_name: (a.policy, a.source.value) for a in cut.track_policies}
    assert policies == {
        "Video 1": (TrackEditPolicy.CUT_WITH_SOURCE, "DEFAULT"),
        "Video 2": (TrackEditPolicy.SHIFT_WITH_RIPPLE, "DEFAULT"),
        "Video 3": (TrackEditPolicy.SHIFT_WITH_RIPPLE, "DEFAULT"),
        "Audio 1": (TrackEditPolicy.CUT_WITH_SOURCE, "DEFAULT"),
        "Audio 2": (TrackEditPolicy.CUT_WITH_SOURCE, "DEFAULT"),
        "Audio 3": (TrackEditPolicy.CUT_WITH_SOURCE, "OVERRIDE"),
        "Audio 4": (TrackEditPolicy.SHIFT_WITH_RIPPLE, "DEFAULT"),
    }
    (skip,) = confirmation.skipped
    assert skip.candidate_id == "AIE-0002" and skip.reason is SkipReason.LAYER_CONFLICT
    assert "Video 3" in skip.detail and "Lower Third" in skip.detail
    effects = {
        e.track_name: (e.effect, e.cut_frames, e.shift_frames) for e in confirmation.track_effects
    }
    assert effects == {
        "Video 1": (TrackEffectKind.CUT, 30, 0),
        "Video 2": (TrackEffectKind.SHIFTED, 0, 30),
        "Video 3": (TrackEffectKind.SHIFTED, 0, 30),
        "Audio 1": (TrackEffectKind.CUT, 30, 0),
        "Audio 2": (TrackEffectKind.CUT, 30, 0),
        "Audio 3": (TrackEffectKind.CUT, 30, 0),
        "Audio 4": (TrackEffectKind.SHIFTED, 0, 30),
    }
    summary = confirmation.summary
    assert "Audio 3=CUT(override)" in summary and "Video 2=SHIFT" in summary
    assert "Video 2 [VIDEO:2] per-cut default -> SHIFTED: shifted by -30f" in summary
    assert "Audio 3 [AUDIO:3] CUT_WITH_SOURCE (override) -> CUT: cut 30f" in summary
    assert confirmation.loss_risks == ()
    # the digest binds the per-track plan
    with pytest.raises(ValueError):
        replace(confirmation, track_effects=confirmation.track_effects[:-1])
    # --- approval and apply ---
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    assert [t.name for t in applied.timeline.tracks] == [
        "Video 1",
        "Video 2",
        "Video 3",
        "Audio 1",
        "Audio 2",
        "Audio 3",
        "Audio 4",
    ]
    assert applied.remaining_candidate_ids == ("AIE-0002",)
    # --- written XML parsed back ---
    text = fx.written(applied.timeline)
    video, audio = _tracks(text, "video"), _tracks(text, "audio")
    assert len(video) == 3 and len(audio) == 4
    v1 = [_timing(c) for c in video[0].findall("clipitem")]
    assert v1 == [("0", "100", "0", "100"), ("100", "370", "130", "400")]
    for track in audio[:3]:  # A1, A2 interview and A3 music cut at the same frames
        assert [_timing(c) for c in track.findall("clipitem")] == v1
    (broll,) = video[1].findall("clipitem")
    assert _timing(broll) == ("170", "230", "100", "160")  # shifted exactly -30
    original_root = ET.fromstring(original)
    original_broll = original_root.findall("sequence/media/video/track")[1].find("clipitem")
    assert original_broll is not None
    filters = (broll.find("filter"), original_broll.find("filter"))
    assert filters[0] is not None and filters[1] is not None
    assert _without(filters[0]) == _without(filters[1])
    (title,) = video[2].findall("generatoritem")
    assert _timing(title)[:2] == ("270", "320")
    original_title = original_root.findall("sequence/media/video/track")[2].find("generatoritem")
    assert original_title is not None
    assert _without(title, "start", "end") == _without(original_title, "start", "end")
    (sfx,) = audio[3].findall("clipitem")
    assert _timing(sfx) == ("220", "240", "0", "20")
    # linked A/V intact: each V1 piece links A1 and A2 pieces (not the music)
    for index, piece in enumerate(video[0].findall("clipitem"), start=1):
        refs = {
            (link.findtext("mediatype"), link.findtext("trackindex"))
            for link in piece.findall("link")
        }
        assert refs == {("video", "1"), ("audio", "1"), ("audio", "2")}, index
    assert all(not c.findall("link") for c in audio[2].findall("clipitem"))
    shifted = {
        (str(d.track_id), d.original_range, d.delta_frames) for d in applied.ripple_displacements
    }
    assert ("Video 3", FrameRange(300, 350), -30) in shifted
    assert ("Video 2", FrameRange(200, 260), -30) in shifted
    assert ("Audio 4", FrameRange(250, 270), -30) in shifted
    # --- VER-001 on a simulated immediate re-export with renumbered ids ---
    reexport = text.replace("clipitem-", "item-").replace("passthrough-", "resolve-")
    verify_diff = fx.diff_text(applied.timeline, reexport, ref="reexport.xml")
    assert verify_diff.unknown_regions == ()
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        verify_diff,
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    layer_items = [i for i in report.items if i.item_id.startswith("L")]
    assert {i.item_id for i in layer_items} == {"L:VIDEO:2:0", "L:VIDEO:3:0"}
    assert all(i.status is ItemStatus.MATCH for i in layer_items)
    # A1/A2 are the two channels of one file, told apart by <sourcetrack>
    assert report.status is VerificationStatus.MATCH, report.reasons


def test_dual_mono_without_sourcetrack_evidence_stays_identity_ambiguous() -> None:
    _, _, _, _, confirmation = _scenario(sourcetrack=False)
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    text = fx.written(applied.timeline)
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, text.replace("clipitem-", "item-"), ref="re.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.status is VerificationStatus.UNVERIFIED
    assert report.reasons == ("IDENTITY_AMBIGUOUS",)
    unknown = {i.track.label for i in report.items if i.status is ItemStatus.UNKNOWN}
    assert unknown == {"AUDIO:1", "AUDIO:2"}


def test_layer_preservation_verifies_match_with_mono_dialogue() -> None:
    _, _, _, _, confirmation = _scenario(stereo=False)
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0001"]
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    text = fx.written(applied.timeline)
    reexport = text.replace("clipitem-", "item-")
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, reexport, ref="reexport.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.status is VerificationStatus.MATCH, report.reasons
    assert report.item("L:VIDEO:3:0").status is ItemStatus.MATCH
    assert report.item("L:VIDEO:2:0").status is ItemStatus.MATCH


def test_verification_reports_a_lost_title_as_layer_lost_mismatch() -> None:
    _, _, _, _, confirmation = _scenario(stereo=False)
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    text = fx.written(applied.timeline)
    lost = re.sub(r"\s*<generatoritem .*?</generatoritem>", "", text, flags=re.DOTALL)
    assert lost != text
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, lost, ref="lost.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.status is VerificationStatus.MISMATCH
    assert report.item("L:VIDEO:3:0").status is ItemStatus.LAYER_LOST
    # a shifted-by-one title is drift; an unreadable file is UNVERIFIED
    drift = text.replace("<start>270</start>", "<start>271</start>").replace(
        "<end>320</end>", "<end>321</end>"
    )
    drift_report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, drift, ref="drift.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert drift_report.item("L:VIDEO:3:0").status is ItemStatus.FRAME_DRIFT
    assert drift_report.status is VerificationStatus.MISMATCH
    unreadable = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, "<xmeml/>", ref="broken.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert unreadable.status is VerificationStatus.UNVERIFIED


def test_verification_reports_a_lost_track_and_changed_track_state() -> None:
    _, _, _, _, confirmation = _scenario(stereo=False)
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    text = fx.written(applied.timeline)
    flattened = re.sub(r"\s*<track>\s*<generatoritem .*?</track>", "", text, flags=re.DOTALL)
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, flattened, ref="flat.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.item("T:VIDEO:3").status is ItemStatus.LAYER_LOST
    assert report.status is VerificationStatus.MISMATCH
    locked = text.replace("</generatoritem>", "</generatoritem><locked>TRUE</locked>", 1)
    state = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, locked, ref="locked.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert state.item("T:VIDEO:3").status is ItemStatus.TRACK_STATE_CHANGED
    assert state.status is VerificationStatus.MISMATCH


def test_filtered_clip_that_is_cut_keeps_filters_on_each_piece_with_review_flag() -> None:
    handoff = _expected(_editor_original(audio_filter=True))
    _, confirmation = _confirm(handoff, _approve_all(handoff), A3_CUT)
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0001"]
    codes = [(w.code, w.track_name) for w in confirmation.layer_warnings]
    assert codes == [(LayerIssueCode.EFFECT_SPLIT_REVIEW, "Audio 1")]
    handoff_write = write_xmeml(handoff.timeline)  # A1 links re-mapped to the new ids
    assert HandoffDiagnosticCode.LINK_NOT_PRESERVED not in {
        d.code for d in handoff_write.diagnostics
    }
    assert "EFFECT_SPLIT_REVIEW AIE-0001 Audio 1 [AUDIO:1]" in confirmation.summary
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    text = fx.written(applied.timeline)
    pieces = _tracks(text, "audio")[0].findall("clipitem")
    assert [_timing(p) for p in pieces] == [("0", "100", "0", "100"), ("100", "370", "130", "400")]
    for piece in pieces:
        assert piece.findtext("filter/effect/effectid") == "audiolevels"
        assert piece.findtext("duration") == str(
            int(piece.findtext("end") or 0) - int(piece.findtext("start") or 0)
        )
    # the preserved A1 pieces stay linked with the matching V1 and A2 pieces
    for index, piece in enumerate(pieces):
        video_piece = _tracks(text, "video")[0].findall("clipitem")[index]
        refs = {link.findtext("linkclipref") for link in piece.findall("link")}
        assert video_piece.get("id") in refs and piece.get("id") in refs and len(refs) == 3
    reread = read_xmeml(text)
    assert reread.timeline is not None
    assert [p.source_range for p in reread.timeline.tracks[3].passthrough] == [
        FrameRange(0, 100),
        FrameRange(130, 400),
    ]


def test_unsupported_item_in_a_cut_track_is_never_cut() -> None:
    original = _editor_original()
    original = _insert_into_clip(original, "clipitem-4", RETIME)  # A2 interview retimed
    handoff = _expected(original)
    a2 = handoff.timeline.tracks[4]
    assert a2.passthrough[0].kind is LayerItemKind.RETIMED_CLIP
    _, confirmation = _confirm(handoff, _approve_all(handoff), A3_CUT)
    skipped = {s.candidate_id: s for s in confirmation.skipped}
    assert skipped["AIE-0001"].reason is SkipReason.LAYER_UNSUPPORTED_ITEM
    assert "Audio 2 [AUDIO:2] RETIMED_CLIP 'Int R' [0,400)" in skipped["AIE-0001"].detail
    assert confirmation.approved_cuts == ()


def test_keep_in_place_override_warns_about_sync_shift() -> None:
    handoff = _expected(_editor_original())
    overrides = (*A3_CUT, TrackPolicyOverride("AUDIO:4", TrackEditPolicy.KEEP_IN_PLACE))
    _, confirmation = _confirm(handoff, _approve_all(handoff), overrides)
    (cut,) = confirmation.approved_cuts
    assert cut.track_policies[-1].policy is TrackEditPolicy.KEEP_IN_PLACE
    (sync,) = [w for w in confirmation.layer_warnings if w.code is LayerIssueCode.SYNC_SHIFT]
    assert "Audio 4 clip 'SFX' [250,270)" in sync.detail
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    (sfx,) = _tracks(fx.written(applied.timeline), "audio")[3].findall("clipitem")
    assert _timing(sfx) == ("250", "270", "0", "20")  # not moved


def test_overrides_must_name_exactly_one_track() -> None:
    handoff = _expected(_editor_original())
    exported = _approve_all(handoff)
    for bad in ("Audio 9", "A3"):
        with pytest.raises(ValueError):
            _confirm(
                handoff, exported, (TrackPolicyOverride(bad, TrackEditPolicy.CUT_WITH_SOURCE),)
            )
    twice = (*A3_CUT, TrackPolicyOverride("AUDIO:3", TrackEditPolicy.KEEP_IN_PLACE))
    with pytest.raises(ValueError):
        _confirm(handoff, exported, twice)
    with pytest.raises(ValueError):
        TrackPolicyOverride("Audio 3", TrackEditPolicy.UNKNOWN)


def test_sequence_markers_are_preserved_shifted_and_verified() -> None:
    handoff = _expected(_editor_original(markers=True))
    assert [m.name for m in handoff.timeline.markers] == ["chapter 2", "breath note"]
    diff, confirmation = _confirm(handoff, _approve_all(handoff), A3_CUT)
    assert {f.kind for f in diff.layer_findings} == {LayerFindingKind.MATCH}
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0001"]
    assert confirmation.loss_risks == ()
    moved = [w for w in confirmation.layer_warnings if w.code is LayerIssueCode.MARKER_MOVED_TO_CUT]
    assert len(moved) == 1 and "'breath note' [110,115)" in moved[0].detail
    assert "MARKER_MOVED_TO_CUT AIE-0001" in confirmation.summary
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    assert [(m.name, m.frame_range) for m in applied.timeline.markers] == [
        ("chapter 2", FrameRange(120, 121)),  # rippled -30
        ("breath note", FrameRange(100, 101)),  # inside the cut: kept at the cut point
    ]
    text = fx.written(applied.timeline)
    sequence = ET.fromstring(text).find("sequence")
    assert sequence is not None
    written = [
        (m.findtext("name"), m.findtext("in"), m.findtext("out"))
        for m in sequence.findall("marker")
    ]
    assert written == [("chapter 2", "120", "-1"), ("breath note", "100", "101")]
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, text.replace("clipitem-", "item-"), ref="re.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.status is VerificationStatus.MATCH, report.reasons
    assert report.item("M:SEQUENCE:0").status is ItemStatus.MATCH
    root = ET.fromstring(text)
    seq = root.find("sequence")
    assert seq is not None
    seq.remove(seq.findall("marker")[0])
    lost = ET.tostring(root, encoding="unicode")
    lost_report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        fx.diff_text(applied.timeline, lost, ref="lost.xml"),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert lost_report.item("M:SEQUENCE:0").status is ItemStatus.MARKER_LOST
    assert lost_report.status is VerificationStatus.MISMATCH


def test_malformed_sequence_marker_still_refuses_with_layer_loss_risk() -> None:
    handoff = _expected(_editor_original())
    exported = _approve_all(handoff)
    exported = exported.replace("</media>", "</media><marker><name>bad</name></marker>", 1)
    _, confirmation = _confirm(handoff, exported, A3_CUT)
    (risk,) = confirmation.loss_risks
    assert risk.code is LayerIssueCode.LAYER_LOSS_RISK and "bad" in risk.detail
    assert "LAYER_LOSS_RISK - apply refused" in confirmation.summary
    with pytest.raises(ApplyRefused, match="LAYER_LOSS_RISK"):
        apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)


RECORDER = HandoffMediaRef("rec", "/media/recorder.wav", FrameRange(0, 2000), 0)


def _double_system(*, linked: bool) -> CandidateHandoff:
    """V1 camera clip + A1 separate-recorder audio (another file), linked or not."""
    group = "g1" if linked else None
    v1 = HandoffTrack(
        "V1",
        HandoffTrackKind.VIDEO,
        (HandoffClip("Cam", INTERVIEW, FrameRange(0, 400), link_group=group),),
    )
    a1 = HandoffTrack(
        "A1",
        HandoffTrackKind.AUDIO,
        (HandoffClip("Rec", RECORDER, FrameRange(0, 400), link_group=group),),
    )
    read = read_xmeml(fx.written(HandoffTimeline("DS", fx.RATE, 0, (v1, a1))))
    assert read.timeline is not None
    expected = HandoffTimeline("DS", fx.RATE, 0, read.timeline.tracks)
    return attach_candidate_markers(expected, (CUT_1,))


def test_file_link_groups_count_as_linked_av_for_the_default_policy() -> None:
    linked = _double_system(linked=True)
    recorder = linked.timeline.tracks[1].items[0]
    assert isinstance(recorder, HandoffClip) and recorder.link_group == "L1"
    text = _rename(fx.written(linked.timeline), "AIE-0001 ?", "AIE-0001 OK")
    _, confirmation = _confirm(linked, text)
    (cut,) = confirmation.approved_cuts
    assert [a.policy for a in cut.track_policies] == [TrackEditPolicy.CUT_WITH_SOURCE] * 2
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    written = fx.written(applied.timeline)
    for video, audio in zip(
        _tracks(written, "video")[0].findall("clipitem"),
        _tracks(written, "audio")[0].findall("clipitem"),
        strict=True,
    ):
        assert _timing(video) == _timing(audio)
        refs = {link.findtext("linkclipref") for link in audio.findall("link")}
        assert refs == {video.get("id"), audio.get("id")}
    unlinked = _double_system(linked=False)
    text = _rename(fx.written(unlinked.timeline), "AIE-0001 ?", "AIE-0001 OK")
    _, refused = _confirm(unlinked, text)
    assert refused.skipped[0].reason is SkipReason.LAYER_CONFLICT


def test_link_with_a_missing_end_is_reported_not_silent() -> None:
    lone = HandoffTrack(
        "V1",
        HandoffTrackKind.VIDEO,
        (HandoffClip("Cam", INTERVIEW, FrameRange(0, 100), link_group="g9"),),
    )
    result = write_xmeml(HandoffTimeline("T", fx.RATE, 0, (lone,)))
    assert result.text is not None and "<link>" not in result.text
    assert HandoffDiagnosticCode.LINK_NOT_PRESERVED in {d.code for d in result.diagnostics}


def _otio_confirmation(color: str, name: str = "AIE-0001 OK") -> ApplyConfirmation:
    clip = HandoffClip("Cam", INTERVIEW, FrameRange(0, 400))
    base = HandoffTimeline("C", fx.RATE, 0, (HandoffTrack("V1", HandoffTrackKind.VIDEO, (clip,)),))
    handoff = attach_candidate_markers(base, (CUT_1,))
    otio_text = write_otio(handoff.timeline).text
    assert otio_text is not None
    document = json.loads(otio_text)
    marker = document["tracks"]["children"][0]["children"][0]["markers"][0]
    marker["name"], marker["color"] = name, color
    mutated = json.dumps(document)
    read = read_otio(mutated)
    assert read.timeline is not None
    artifact = roundtrip_artifact_ref("c.otio", mutated, RoundTripFormat.OTIO_JSON)
    diff = diff_otio_roundtrip(handoff.timeline, read, artifact_ref=artifact)
    selection = read_marker_selections(read.timeline, handoff.candidates)
    return build_apply_confirmation(selection, handoff.timeline, diff)


def test_confirmation_digest_binds_resolved_status_not_raw_marker_colour() -> None:
    green = _otio_confirmation("GREEN")
    blue = _otio_confirmation("BLUE")
    assert green.actual_digest != blue.actual_digest  # the raw files differ ...
    assert green.confirmation_digest == blue.confirmation_digest  # ... the approval does not
    assert [s.decision for s in green.candidate_statuses] == [CandidateDecision.APPROVED]
    conflict = _otio_confirmation("RED")  # name OK + RED = UNKNOWN: a different approval
    assert conflict.candidate_statuses[0].decision is CandidateDecision.UNKNOWN
    assert conflict.confirmation_digest != green.confirmation_digest
    with pytest.raises(ValueError):
        replace(green, candidate_statuses=conflict.candidate_statuses)


def test_writers_refuse_instead_of_dropping_layer_items() -> None:
    _, _, _, _, confirmation = _scenario()
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    otio = write_otio(applied.timeline)
    assert otio.refused
    assert {d.code for d in otio.diagnostics} == {HandoffDiagnosticCode.LAYER_LOSS_RISK}
    v3 = applied.timeline.tracks[2]
    title = v3.passthrough[0]
    assert title.timeline_range is not None
    corrupt = replace(title, timeline_range=FrameRange(0, 50))
    broken = replace(
        applied.timeline,
        tracks=(
            *applied.timeline.tracks[:2],
            replace(v3, passthrough=(corrupt,)),
            *applied.timeline.tracks[3:],
        ),
    )
    result = write_xmeml(broken)
    assert result.refused
    assert any(d.code is HandoffDiagnosticCode.LAYER_LOSS_RISK for d in result.diagnostics)


def test_track_flags_settings_and_empty_tracks_survive() -> None:
    text = fx.written(_base())
    tracks = list(re.finditer(r"<track\s*/>|<track>", text))
    # A4 disabled + locked with a settings child and an attribute; V3 stays empty
    a4 = tracks[6]
    text = text[: a4.start()] + '<track TL.SQTrackShy="0">' + text[a4.end() :]
    close = [m.start() for m in re.finditer(r"</track>", text)][-1]
    text = (
        text[:close]
        + "<outputchannelindex>4</outputchannelindex><enabled>FALSE</enabled><locked>TRUE</locked>"
        + text[close:]
    )
    read = read_xmeml(text)
    assert read.timeline is not None
    a4_read = read.timeline.tracks[6]
    assert (a4_read.enabled, a4_read.locked) == (False, True)
    assert a4_read.attributes == (("TL.SQTrackShy", "0"),)
    assert a4_read.extra_xml == ("<outputchannelindex>4</outputchannelindex>",)
    assert a4_read.items == () and a4_read.passthrough[0].kind is LayerItemKind.UNMODELLED_CLIP
    assert read.timeline.tracks[2].items == () and read.timeline.tracks[2].passthrough == ()
    expected = HandoffTimeline("Interview", fx.RATE, 0, read.timeline.tracks)
    written = fx.written(expected)
    again = read_xmeml(written)
    assert again.timeline is not None and again.timeline.tracks == read.timeline.tracks
    assert len(_tracks(written, "video")) == 3 and len(_tracks(written, "audio")) == 4
    diff = fx.diff_text(expected, written)
    assert diff.unknown_regions == () and diff.status is DiffStatus.COMPLETE


def test_passthrough_must_not_overlap_modelled_clips() -> None:
    clip = HandoffClip("I", INTERVIEW, FrameRange(0, 100))
    item = PassthroughItem(LayerItemKind.GENERATOR, "t", FrameRange(50, 80), "<generatoritem />")
    with pytest.raises(ValueError):
        HandoffTrack("V1", HandoffTrackKind.VIDEO, (clip,), (item,))
    with pytest.raises(ValueError):
        PassthroughItem(
            LayerItemKind.EFFECT_CLIP,
            "x",
            FrameRange(0, 10),
            "<clipitem />",
            None,
            FrameRange(0, 10),
        )
    actual = ReimportedTimeline("X", fx.RATE, 0, (), unpreserved=("sequence marker",))
    assert actual.unpreserved == ("sequence marker",)


def test_layer_pipeline_is_deterministic() -> None:
    first = _scenario()[4]
    second = _scenario()[4]
    assert first == second and first.summary == second.summary
    a = apply_approved_cuts(first, confirmed_digest=first.confirmation_digest)
    b = apply_approved_cuts(second, confirmed_digest=second.confirmation_digest)
    assert a == b and fx.written(a.timeline) == fx.written(b.timeline)
    assert json.dumps(first.summary) == json.dumps(second.summary)
