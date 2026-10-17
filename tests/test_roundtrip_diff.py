import json

import pytest
from support import roundtrip_fixtures as fx

from davinci_ai_editor.domain import FrameRange, ProtectedRange, TrackId
from davinci_ai_editor.handoff_model import HandoffTrackKind
from davinci_ai_editor.otio_json import read_otio, write_otio
from davinci_ai_editor.roundtrip_diff import (
    AttributeChange,
    ChangeKind,
    DiffReason,
    DiffStatus,
    IdentityStrength,
    MediaIdentityBasis,
    ProtectionUnavailable,
    RoundTripArtifactRef,
    RoundTripDiff,
    RoundTripFormat,
    derive_human_edit_protection,
    diff_otio_roundtrip,
    diff_roundtrip,
    roundtrip_artifact_ref,
    timeline_digest,
)
from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.timecode import frames_per_24_hours

V1 = TrackId("V1")


def _kinds(diff: RoundTripDiff) -> dict[str, ChangeKind]:
    return {c.change_id: c.kind for c in diff.changes}


def _base() -> tuple[str, RoundTripDiff]:
    text = fx.written(fx.expected_timeline())
    return text, fx.diff_text(fx.expected_timeline(), text)


def test_untouched_roundtrip_is_complete_and_unprotected() -> None:
    _, diff = _base()
    assert diff.status is DiffStatus.COMPLETE
    assert diff.evidence_class == "FILE_ROUNDTRIP" and diff.artifact.native_evidence is False
    assert diff.identity_basis is MediaIdentityBasis.DISPLAY_NAME
    assert set(_kinds(diff).values()) == {ChangeKind.UNCHANGED}
    assert len(diff.changes) == 5
    assert {c.identity for c in diff.changes} == {IdentityStrength.WEAK}
    assert derive_human_edit_protection(diff) == ()


def test_trim_tail() -> None:
    text, _ = _base()
    edited = fx.set_fields(text, "clipitem-3", end=160, out=330, duration=30)
    diff = fx.diff_text(fx.expected_timeline(), edited)
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.TRIMMED
    assert (change.head_delta, change.tail_delta, change.timeline_delta) == (0, -10, 0)
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(130, 170)),)


def test_trim_head_without_ripple() -> None:
    text, _ = _base()
    edited = fx.set_fields(text, "clipitem-3", start=135, **{"in": 305})
    diff = fx.diff_text(fx.expected_timeline(), edited)
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.TRIMMED and change.head_delta == 5
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(130, 170)),)


def test_move() -> None:
    text, _ = _base()
    edited = fx.set_fields(text, "clipitem-3", start=140, end=180)
    diff = fx.diff_text(fx.expected_timeline(), edited)
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.MOVED and change.timeline_delta == 10
    assert not change.track_changed
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(130, 180)),)


def test_delete() -> None:
    text, _ = _base()
    diff = fx.diff_text(fx.expected_timeline(), fx.delete_clip(text, "clipitem-3"))
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.REMOVED_BY_HUMAN and change.actual == ()
    assert diff.status is DiffStatus.COMPLETE
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(110, 150)),)


def test_ripple_delete_locks_cut_point_and_shifted_content() -> None:
    text, _ = _base()
    edited = fx.delete_clip(text, "clipitem-2")
    edited = fx.set_fields(edited, "clipitem-3", start=70, end=110)
    edited = edited.replace('<file id="file-2" />', fx.M2_FILE, 1)
    diff = fx.diff_text(fx.expected_timeline(), edited)
    assert diff.change("E:VIDEO:1:1").kind is ChangeKind.REMOVED_BY_HUMAN
    assert diff.change("E:VIDEO:1:3").kind is ChangeKind.MOVED
    protection = [p for p in derive_human_edit_protection(diff) if p.track_id == V1]
    assert protection == [
        ProtectedRange(V1, FrameRange(50, 110)),
        ProtectedRange(V1, FrameRange(130, 170)),
    ]


def test_insert() -> None:
    text, _ = _base()
    block = fx.clip_block("new", "N", 170, 200, 0, 30, fx.NEW_FILE)
    diff = fx.diff_text(fx.expected_timeline(), fx.insert_in_track(text, 0, block))
    added = [c for c in diff.changes if c.kind is ChangeKind.ADDED_BY_HUMAN]
    assert len(added) == 1 and added[0].change_id == "A:VIDEO:1:4"
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(170, 200)),)


def test_split() -> None:
    text, _ = _base()
    edited = fx.set_fields(text, "clipitem-2", end=80, out=230, duration=30)
    second = fx.clip_block("split", "B", 80, 110, 230, 260, '<file id="file-2"/>')
    edited = fx.insert_in_track(edited, 0, second)
    diff = fx.diff_text(fx.expected_timeline(), edited)
    change = diff.change("E:VIDEO:1:1")
    assert change.kind is ChangeKind.SPLIT and len(change.actual) == 2
    assert (change.head_delta, change.tail_delta) == (0, 0)
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(50, 110)),)


def test_merge_of_contiguous_cut_is_merged() -> None:
    expected = fx.cut_timeline()
    text = fx.written(expected)
    edited = fx.delete_clip(text, "clipitem-2")
    edited = fx.set_fields(edited, "clipitem-1", end=80, out=80, duration=80)
    diff = fx.diff_text(expected, edited)
    assert set(_kinds(diff).values()) == {ChangeKind.MERGED}
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(0, 80)),)


def test_replace() -> None:
    text, _ = _base()
    edited = fx.delete_clip(text, "clipitem-3")
    block = fx.clip_block("rep", "R", 130, 170, 0, 40, fx.NEW_FILE)
    diff = fx.diff_text(fx.expected_timeline(), fx.insert_in_track(edited, 0, block))
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.REPLACED and change.actual[0].clip.media.media_id == "m3"
    assert ChangeKind.ADDED_BY_HUMAN not in _kinds(diff).values()


def test_enabled_toggle_is_touched() -> None:
    text, _ = _base()
    edited = fx.set_fields(text, "clipitem-1", enabled="FALSE")
    diff = fx.diff_text(fx.expected_timeline(), edited)
    change = diff.change("E:VIDEO:1:0")
    assert change.kind is ChangeKind.UNCHANGED
    assert change.attribute_changes == (AttributeChange.ENABLED,)
    assert derive_human_edit_protection(diff) == (ProtectedRange(V1, FrameRange(0, 50)),)


def test_rate_change_makes_whole_diff_unknown_and_locks_everything() -> None:
    text, _ = _base()
    edited = text.replace("<timebase>25</timebase>", "<timebase>24</timebase>")
    diff = fx.diff_text(fx.expected_timeline(), edited)
    assert diff.status is DiffStatus.UNKNOWN and diff.reasons == (DiffReason.RATE_MISMATCH,)
    assert set(_kinds(diff).values()) == {ChangeKind.UNKNOWN}
    horizon = frames_per_24_hours(FrameRate(24, 1))
    assert derive_human_edit_protection(diff) == (
        ProtectedRange(V1, FrameRange(0, horizon)),
        ProtectedRange(TrackId("A1"), FrameRange(0, horizon)),
    )


def test_start_change_makes_whole_diff_unknown() -> None:
    text, _ = _base()
    edited = text.replace(
        "<string>00:00:00:00</string>\n      <frame>0</frame>",
        "<string>01:00:00:00</string>\n      <frame>90000</frame>",
        1,
    )
    diff = fx.diff_text(fx.expected_timeline(), edited)
    assert diff.status is DiffStatus.UNKNOWN and diff.reasons == (DiffReason.START_MISMATCH,)


def test_transition_added_is_unknown_not_guessed() -> None:
    text, _ = _base()
    edited = fx.insert_in_track(
        text, 0, "<transitionitem><start>100</start><end>120</end></transitionitem>"
    )
    diff = fx.diff_text(fx.expected_timeline(), edited)
    assert diff.status is DiffStatus.PARTIAL
    b = diff.change("E:VIDEO:1:1")
    assert b.kind is ChangeKind.UNKNOWN and b.reason is DiffReason.UNSUPPORTED_REGION
    assert diff.change("E:VIDEO:1:0").kind is ChangeKind.UNCHANGED
    assert diff.change("E:AUDIO:1:1").kind is ChangeKind.UNCHANGED
    protection = derive_human_edit_protection(diff)
    # transition region [50,120) plus the neighbourhood of the hidden clip B up to C
    assert protection == (ProtectedRange(V1, FrameRange(50, 130)),)


def test_duplicate_paste_is_ambiguous() -> None:
    text, _ = _base()
    block = fx.clip_block("dup", "C", 200, 240, 300, 340, '<file id="file-1"/>')
    diff = fx.diff_text(fx.expected_timeline(), fx.insert_in_track(text, 0, block))
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.UNKNOWN and change.reason is DiffReason.AMBIGUOUS_MATCH
    assert diff.status is DiffStatus.PARTIAL


def test_display_name_with_different_path_is_identity_unknown() -> None:
    text, _ = _base()
    edited = text.replace("file:///media/b.mov", "file:///other/b.mov")
    diff = fx.diff_text(fx.expected_timeline(), edited)
    change = diff.change("E:VIDEO:1:1")
    assert change.kind is ChangeKind.UNKNOWN and change.reason is DiffReason.IDENTITY_UNKNOWN


def test_cross_track_move() -> None:
    expected = fx.two_video_tracks()
    text = fx.written(expected)
    # move B from V2 onto V1 (same timeline position): editor flattened the tracks
    start = text.index('<clipitem id="clipitem-2">')
    end = text.index("</clipitem>", start) + len("</clipitem>")
    block = text[start:end]
    edited = text[:start] + text[end:]
    edited = fx.insert_in_track(edited, 0, block)
    diff = fx.diff_text(expected, edited)
    change = diff.change("E:VIDEO:2:1")
    assert change.kind is ChangeKind.MOVED and change.track_changed
    assert change.actual[0].track.kind is HandoffTrackKind.VIDEO
    assert change.actual[0].track.ordinal == 1


def test_otio_roundtrip_has_strong_identity() -> None:
    expected = fx.expected_timeline()
    text = write_otio(expected).text
    assert text is not None
    document = json.loads(text)
    clip = document["tracks"]["children"][0]["children"][3]
    clip["source_range"]["duration"]["value"] = 30
    mutated = json.dumps(document)
    artifact = roundtrip_artifact_ref("export.otio", mutated, RoundTripFormat.OTIO_JSON)
    diff = diff_otio_roundtrip(expected, read_otio(mutated), artifact_ref=artifact)
    change = diff.change("E:VIDEO:1:3")
    assert change.kind is ChangeKind.TRIMMED and change.identity is IdentityStrength.STRONG
    assert diff.identity_basis is MediaIdentityBasis.METADATA


def test_unreadable_otio_is_whole_unknown_without_protection() -> None:
    expected = fx.expected_timeline()
    text = write_otio(expected).text
    assert text is not None
    document = json.loads(text)
    document["tracks"]["children"][0]["children"].insert(
        1, {"OTIO_SCHEMA": "Transition.1", "name": "x"}
    )
    mutated = json.dumps(document)
    artifact = roundtrip_artifact_ref("export.otio", mutated, RoundTripFormat.OTIO_JSON)
    diff = diff_otio_roundtrip(expected, read_otio(mutated), artifact_ref=artifact)
    assert diff.status is DiffStatus.UNKNOWN and diff.reasons == (DiffReason.ACTUAL_UNREADABLE,)
    assert diff.actual_digest is None
    with pytest.raises(ProtectionUnavailable):
        derive_human_edit_protection(diff)


def test_determinism_and_digest_binding() -> None:
    text, diff = _base()
    again = fx.diff_text(fx.expected_timeline(), text)
    assert again == diff and again.digest == diff.digest
    assert diff.expected_digest == timeline_digest(fx.expected_timeline())
    edited = fx.set_fields(text, "clipitem-3", start=140, end=180)
    assert fx.diff_text(fx.expected_timeline(), edited).digest != diff.digest
    renamed = fx.diff_text(fx.expected_timeline(), text, ref="other.xml")
    assert renamed.digest != diff.digest


def test_artifact_ref_is_file_roundtrip_only() -> None:
    with pytest.raises(ValueError):
        RoundTripArtifactRef("x", RoundTripFormat.XMEML, "0" * 64, "NATIVE")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        RoundTripArtifactRef("x", RoundTripFormat.XMEML, "0" * 64, native_evidence=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        RoundTripArtifactRef("x", RoundTripFormat.XMEML, "nothex")


def test_unknown_format_is_whole_unknown() -> None:
    expected = fx.expected_timeline()
    artifact = roundtrip_artifact_ref("x", "x", RoundTripFormat.UNKNOWN)
    diff = diff_roundtrip(expected, fx.reimported(expected), artifact_ref=artifact)
    assert diff.status is DiffStatus.UNKNOWN and DiffReason.UNKNOWN_FORMAT in diff.reasons


def _otio_without_metadata(expected_text: str, clip_paths: list[tuple[int, int]]) -> str:
    document = json.loads(expected_text)
    for track_index, item_index in clip_paths:
        clip = document["tracks"]["children"][track_index]["children"][item_index]
        clip["media_references"]["DEFAULT_MEDIA"]["metadata"] = {}
    return json.dumps(document)


def test_otio_without_media_id_falls_back_to_weak_path_identity() -> None:
    expected = fx.expected_timeline()
    text = write_otio(expected).text
    assert text is not None
    every_clip = [(0, 0), (0, 1), (0, 3), (1, 0), (1, 1)]
    document = json.loads(_otio_without_metadata(text, every_clip))
    document["tracks"]["children"][0]["children"][3]["source_range"]["duration"]["value"] = 30
    mutated = json.dumps(document)
    artifact = roundtrip_artifact_ref("export.otio", mutated, RoundTripFormat.OTIO_JSON)
    result = read_otio(mutated)
    assert result.timeline is not None
    diff = diff_otio_roundtrip(expected, result, artifact_ref=artifact)
    assert diff.status is DiffStatus.COMPLETE
    assert diff.identity_basis is MediaIdentityBasis.PATH_FALLBACK
    assert {c.identity for c in diff.changes} == {IdentityStrength.WEAK}
    assert diff.change("E:VIDEO:1:3").kind is ChangeKind.TRIMMED
    assert diff.change("E:VIDEO:1:0").kind is ChangeKind.UNCHANGED


def test_otio_partial_metadata_loss_keeps_strong_where_present() -> None:
    expected = fx.expected_timeline()
    text = write_otio(expected).text
    assert text is not None
    mutated = _otio_without_metadata(text, [(0, 1)])
    artifact = roundtrip_artifact_ref("export.otio", mutated, RoundTripFormat.OTIO_JSON)
    diff = diff_otio_roundtrip(expected, read_otio(mutated), artifact_ref=artifact)
    assert diff.status is DiffStatus.COMPLETE
    assert diff.identity_basis is MediaIdentityBasis.PATH_FALLBACK
    assert diff.change("E:VIDEO:1:1").identity is IdentityStrength.WEAK
    assert diff.change("E:VIDEO:1:0").identity is IdentityStrength.STRONG


def test_otio_path_fallback_with_relinked_path_is_not_matched() -> None:
    expected = fx.expected_timeline()
    text = write_otio(expected).text
    assert text is not None
    document = json.loads(_otio_without_metadata(text, [(0, 1)]))
    ref = document["tracks"]["children"][0]["children"][1]["media_references"]["DEFAULT_MEDIA"]
    ref["target_url"] = "file:///elsewhere/b.mov"
    mutated = json.dumps(document)
    artifact = roundtrip_artifact_ref("export.otio", mutated, RoundTripFormat.OTIO_JSON)
    diff = diff_otio_roundtrip(expected, read_otio(mutated), artifact_ref=artifact)
    assert diff.change("E:VIDEO:1:1").kind is ChangeKind.REPLACED


def test_reimported_and_expected_never_share_a_digest() -> None:
    expected = fx.expected_timeline()
    assert timeline_digest(expected) != timeline_digest(fx.reimported(expected))
    with pytest.raises(TypeError):
        diff_roundtrip(
            expected,
            expected,  # type: ignore[arg-type]
            artifact_ref=roundtrip_artifact_ref("x", "x", RoundTripFormat.XMEML),
        )
