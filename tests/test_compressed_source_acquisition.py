"""CSA-001 TEST_ONLY_SUPPORT contracts; no real media, subprocess, or native access."""

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, replace
from itertools import pairwise
from pathlib import Path
from typing import cast

import pytest

from tools import compressed_source_acquisition as c

H = "a" * 64
J = "b" * 64
K = "c" * 64


def binary(name: str) -> c.ToolBinaryPin:
    return c.ToolBinaryPin(name, "synthetic-v1", H, J, "windows-x64", "x86_64")


def toolchain() -> c.ToolchainPin:
    return c.ToolchainPin(
        binary("ffmpeg"),
        binary("ffprobe"),
        (c.LibraryPin("avcodec", "synthetic-1", K),),
        "software-fixed",
        "C",
        1,
        H,
    )


def permission() -> c.PermissionBinding:
    return c.PermissionBinding(
        "permission-1",
        H,
        "2026-09-01T00:00:00+09:00",
        "2027-01-01T00:00:00+09:00",
        "retention-1",
        ("decode", "reextract", "retain"),
    )


def source() -> c.SourcePin:
    return c.SourcePin(
        "asset-1",
        "source-1",
        "session-1",
        "owner-1",
        "recorder-1",
        ("lineage-1",),
        H,
        J,
        10_000_000,
        "2026-10-01T12:00:00+09:00",
        permission(),
        "snapshot-1",
    )


def stream(
    *,
    sample_rate: int = 48_000,
    channels: int = 1,
    codec: str = "aac",
    profile: str = "LC",
) -> c.StreamFingerprint:
    order = (
        ("mono",)
        if channels == 1
        else ("FL", "FR")
        if channels == 2
        else tuple(f"C{i}" for i in range(channels))
    )
    return c.StreamFingerprint(
        c.ContainerFamily.M4A_MOV,
        1,
        0,
        "stream-1",
        codec,
        profile,
        H,
        sample_rate,
        channels,
        order,
        1,
        sample_rate,
        0,
    )


def profile() -> c.DecodeProfile:
    return c.DecodeProfile(
        c.PROFILE_REF,
        "conversion-policy-v1",
        H,
        "rounding-policy-kat-v1",
        "clipping-policy-kat-v1",
        "nonfinite-reject-v1",
        "channel-interleave-v1",
        "known-answer-suite-v1",
        c.digest(c.KnownAnswerSuite("known-answer-suite-v1", known_vectors())),
    )


def probe(value: c.StreamFingerprint | None = None) -> c.ProbeReceipt:
    return c.ProbeReceipt(
        source().source_sha256,
        source().source_bytes,
        c.digest(toolchain().ffprobe),
        1,
        value or stream(),
        K,
    )


def origin(*, status: c.OriginStatus = c.OriginStatus.ESTABLISHED) -> c.SampleOriginEvidence:
    return c.SampleOriginEvidence(
        status,
        0 if status == c.OriginStatus.ESTABLISHED else None,
        1024 if status == c.OriginStatus.ESTABLISHED else None,
        0 if status == c.OriginStatus.ESTABLISHED else None,
        512 if status == c.OriginStatus.ESTABLISHED else None,
        c.EditListState.ACCOUNTED if status == c.OriginStatus.ESTABLISHED else None,
        "origin-accounting-1",
        H,
    )


def request(
    *,
    stream_value: c.StreamFingerprint | None = None,
    source_value: c.SourcePin | None = None,
    args: tuple[str, ...] | None = None,
) -> c.ExtractionRequest:
    actual_source = source_value or source()
    actual_stream = stream_value or stream()
    actual_probe = replace(
        probe(actual_stream),
        source_sha256=actual_source.source_sha256,
        source_bytes=actual_source.source_bytes,
    )
    return c.ExtractionRequest(
        actual_source,
        actual_probe,
        toolchain(),
        profile(),
        0,
        "2026-10-14T12:00:00+09:00",
        "2026-10-14T12:15:00+09:00",
        origin(),
        args or c.canonical_argument_template(actual_stream.global_stream_index),
    )


def extraction(
    req: c.ExtractionRequest | None = None,
    *,
    operator: str = "operator-a",
    process: str = "process-a",
    attempt: str = "attempt-a",
) -> c.ExtractionReceipt:
    value = req or request()
    frames = 48_000 * 120
    channels = value.probe.stream.channels
    return c.ExtractionReceipt(
        c.digest(value),
        operator,
        process,
        attempt,
        value.source.source_sha256,
        value.source.source_sha256,
        value.source.source_bytes,
        value.source.source_bytes,
        H,
        frames * channels * 2,
        frames,
        frames * channels,
        48_000,
        channels,
        value.probe.stream.channel_order,
        value.selected_channel,
        c.digest(value.origin),
        True,
        True,
        0,
        f"restricted-{attempt}",
        c.AcquisitionStatus.READY,
    )


def changed_extraction(
    receipt: c.ExtractionReceipt, field: str, value: object
) -> c.ExtractionReceipt:
    if field == "status":
        assert isinstance(value, c.AcquisitionStatus)
        return replace(receipt, status=value)
    if field in ("eof_seen", "flush_complete"):
        assert isinstance(value, bool)
        return (
            replace(receipt, eof_seen=value)
            if field == "eof_seen"
            else replace(receipt, flush_complete=value)
        )
    if field in ("source_pre_sha256", "source_post_sha256", "origin_sha256", "request_sha256"):
        assert isinstance(value, str)
        if field == "source_pre_sha256":
            return replace(receipt, source_pre_sha256=value)
        if field == "source_post_sha256":
            return replace(receipt, source_post_sha256=value)
        if field == "origin_sha256":
            return replace(receipt, origin_sha256=value)
        return replace(receipt, request_sha256=value)
    assert type(value) is int
    if field == "output_bytes":
        return replace(receipt, output_bytes=value)
    if field == "scalar_samples":
        return replace(receipt, scalar_samples=value)
    if field == "sample_rate":
        return replace(receipt, sample_rate=value)
    assert field == "process_exit_code"
    return replace(receipt, process_exit_code=value)


def comparison(
    first: c.ExtractionReceipt,
    second: c.ExtractionReceipt,
) -> c.ComparisonReceipt:
    return c.ComparisonReceipt(
        "comparator-1",
        H,
        first.attempt_ref,
        second.attempt_ref,
        "BYTE_IDENTICAL",
        first.output_bytes,
        None,
        "BOUNDED_ACQUISITION_EVIDENCE_ONLY",
    )


def test_immutable_and_canonical_digest_is_stable() -> None:
    first = toolchain()
    second = replace(first, libraries=tuple(reversed(first.libraries)))
    assert c.digest(first) == c.digest(second)
    with pytest.raises(FrozenInstanceError):
        field_name = "threads"
        setattr(first, field_name, 2)


@pytest.mark.parametrize(
    "change",
    [
        {"threads": 2},
        {"locale": "ko-KR"},
        {"libraries": ()},
    ],
)
def test_toolchain_pin_is_fail_closed(change: dict[str, object]) -> None:
    with pytest.raises(c.Refusal, match="TOOLCHAIN_PIN_INVALID"):
        if "threads" in change:
            replace(toolchain(), threads=2)
        elif "locale" in change:
            replace(toolchain(), locale="ko-KR")
        else:
            replace(toolchain(), libraries=())


@pytest.mark.parametrize(
    "field,value",
    [
        ("resample_enabled", True),
        ("downmix_enabled", True),
        ("normalization_enabled", True),
        ("filter_enabled", True),
        ("dither_enabled", True),
        ("sample_rate", 44_100),
        ("threads", 2),
        ("output_format", "FLOAT32"),
    ],
)
def test_profile_forbids_processing_and_profile_drift(field: str, value: object) -> None:
    with pytest.raises(c.Refusal, match="DECODE_PROFILE_INVALID"):
        if field == "sample_rate":
            replace(profile(), sample_rate=44100)
        elif field == "threads":
            replace(profile(), threads=2)
        elif field == "output_format":
            replace(profile(), output_format="FLOAT32")
        elif field == "resample_enabled":
            replace(profile(), resample_enabled=True)
        elif field == "downmix_enabled":
            replace(profile(), downmix_enabled=True)
        elif field == "normalization_enabled":
            replace(profile(), normalization_enabled=True)
        elif field == "filter_enabled":
            replace(profile(), filter_enabled=True)
        else:
            replace(profile(), dither_enabled=True)


def test_permission_use_interval_is_explicit_and_timezone_aware() -> None:
    assert not c.validate_source_use(
        source(),
        use_start_at="2026-10-14T12:00:00+09:00",
        use_end_at="2026-10-14T12:15:00+09:00",
    )
    assert c.validate_source_use(
        source(),
        use_start_at="2027-01-01T00:00:00+09:00",
        use_end_at="2027-01-01T00:01:00+09:00",
    )
    assert c.validate_source_use(
        source(),
        use_start_at="2026-10-14T12:00:00",
        use_end_at="2026-10-14T12:15:00+09:00",
    )


def test_permission_requires_decode_operation() -> None:
    bad_permission = replace(permission(), permitted_operations=("retain",))
    bad = replace(source(), permission=bad_permission)
    assert {
        x.code
        for x in c.validate_source_use(
            bad,
            use_start_at="2026-10-14T12:00:00+09:00",
            use_end_at="2026-10-14T12:15:00+09:00",
        )
    } == {"PERMISSION_OPERATION_NOT_ALLOWED"}


def test_source_requires_lineage_and_bounded_bytes() -> None:
    with pytest.raises(c.Refusal, match="SOURCE_PIN_INVALID"):
        replace(source(), lineage_refs=())
    with pytest.raises(c.Refusal, match="SOURCE_PIN_INVALID"):
        replace(source(), source_bytes=c.SOURCE_BYTE_CAP + 1)


@pytest.mark.parametrize(
    "value,code",
    [
        (stream(sample_rate=44_100), "UNSUPPORTED_PROFILE"),
        (stream(codec="mp3", profile="UNKNOWN"), "UNSUPPORTED_CODEC"),
        (stream(channels=3), "CHANNEL_AMBIGUITY"),
    ],
)
def test_initial_profile_refuses_44k_mp3_and_more_than_stereo(
    value: c.StreamFingerprint, code: str
) -> None:
    assert code in {x.code for x in c.validate_supported_stream(value)}


def test_initial_profile_accepts_aac_lc_48k_mono_and_stereo() -> None:
    assert c.validate_supported_stream(stream()) == ()
    assert c.validate_supported_stream(stream(channels=2)) == ()


def test_argument_template_is_full_decode_exact_stream_and_no_processing_flags() -> None:
    args = c.canonical_argument_template(7)
    assert ("-map", "0:7") == (args[args.index("-map")], args[args.index("-map") + 1])
    assert "pcm_s16le" in args and "s16le" in args
    for forbidden in ("-ss", "-t", "-to", "-ar", "-ac", "-af", "-filter:a", "-filter_complex"):
        assert forbidden not in args


def test_request_binds_source_probe_toolchain_stream_channel_and_origin() -> None:
    value = request()
    assert value.selected_channel == 0
    assert value.ordered_arguments == c.canonical_argument_template(1)


@pytest.mark.parametrize(
    "case,code",
    [
        ("source", "SOURCE_HASH_DRIFT"),
        ("tool", "TOOLCHAIN_DRIFT"),
        ("rate", "UNSUPPORTED_PROFILE"),
        ("channel", "CHANNEL_AMBIGUITY"),
        ("origin", "SAMPLE_ORIGIN_UNESTABLISHED"),
        ("args", "ARGUMENT_POLICY_MISMATCH"),
    ],
)
def test_request_refuses_binding_and_policy_mismatch(case: str, code: str) -> None:
    if case == "source":
        bad_probe = replace(probe(), source_sha256=H)
        with pytest.raises(c.Refusal, match=code):
            c.ExtractionRequest(
                source(),
                bad_probe,
                toolchain(),
                profile(),
                0,
                "2026-10-14T12:00:00+09:00",
                "2026-10-14T12:15:00+09:00",
                origin(),
                c.canonical_argument_template(1),
            )
    elif case == "tool":
        bad_probe = replace(probe(), ffprobe_pin_sha256=H)
        with pytest.raises(c.Refusal, match=code):
            c.ExtractionRequest(
                source(),
                bad_probe,
                toolchain(),
                profile(),
                0,
                "2026-10-14T12:00:00+09:00",
                "2026-10-14T12:15:00+09:00",
                origin(),
                c.canonical_argument_template(1),
            )
    elif case == "rate":
        with pytest.raises(c.Refusal, match=code):
            request(stream_value=stream(sample_rate=44_100))
    elif case == "channel":
        value = stream(channels=2)
        with pytest.raises(c.Refusal, match=code):
            replace(request(stream_value=value), selected_channel=2)
    elif case == "origin":
        base = request()
        with pytest.raises(c.Refusal, match=code):
            replace(base, origin=origin(status=c.OriginStatus.UNKNOWN))
    else:
        with pytest.raises(c.Refusal, match=code):
            request(args=(*c.canonical_argument_template(1), "-ar", "48000"))


def test_origin_unknown_never_becomes_zero_by_default() -> None:
    unknown = origin(status=c.OriginStatus.UNKNOWN)
    with pytest.raises(c.Refusal, match="SAMPLE_ORIGIN_UNESTABLISHED"):
        unknown.require_established()


def test_extraction_receipt_exact_counts_and_binding() -> None:
    req = request()
    receipt = extraction(req)
    assert c.validate_extraction_receipt(req, receipt) == ()
    assert receipt.output_bytes == receipt.sample_frames * receipt.channels * 2


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("source_post_sha256", H, "SOURCE_HASH_DRIFT"),
        ("output_bytes", 3, "DECODE_LENGTH_MISMATCH"),
        ("scalar_samples", 1, "DECODE_LENGTH_MISMATCH"),
        ("sample_rate", 44_100, "PCM_FORMAT_MISMATCH"),
        ("origin_sha256", J, "SAMPLE_ORIGIN_UNESTABLISHED"),
        ("eof_seen", False, "DECODE_FAILURE"),
        ("flush_complete", False, "DECODE_FAILURE"),
        ("process_exit_code", 1, "DECODE_FAILURE"),
        ("status", c.AcquisitionStatus.QUARANTINED, "ACQUISITION_NOT_READY"),
    ],
)
def test_extraction_receipt_fail_closed(field: str, value: object, code: str) -> None:
    req = request()
    bad = changed_extraction(extraction(req), field, value)
    assert code in {x.code for x in c.validate_extraction_receipt(req, bad)}


def test_independent_comparison_byte_identical() -> None:
    req = request()
    first = extraction(req)
    second = extraction(req, operator="operator-b", process="process-b", attempt="attempt-b")
    assert c.validate_independent_comparison(req, first, second, comparison(first, second)) == ()


@pytest.mark.parametrize(
    "case",
    ["same-operator", "recorder-second", "same-process", "output", "comparison"],
)
def test_independent_comparison_refuses_non_independence_and_mismatch(case: str) -> None:
    req = request()
    first = extraction(req)
    second = extraction(req, operator="operator-b", process="process-b", attempt="attempt-b")
    comp = comparison(first, second)
    if case == "same-operator":
        second = replace(second, operator_ref=first.operator_ref)
    elif case == "recorder-second":
        second = replace(second, operator_ref=source().recorder_ref)
    elif case == "same-process":
        second = replace(second, process_ref=first.process_ref)
    elif case == "output":
        second = replace(second, output_sha256=J)
    else:
        comp = replace(comp, byte_comparison_result="MISMATCH", first_difference_offset=5)
    assert c.validate_independent_comparison(req, first, second, comp)


def test_first_extractor_may_be_recorder_second_must_be_independent() -> None:
    req = request()
    first = extraction(req, operator=source().recorder_ref)
    second = extraction(req, operator="operator-b", process="process-b", attempt="attempt-b")
    assert c.validate_independent_comparison(req, first, second, comparison(first, second)) == ()


def test_window_policy_exact_four_by_thirty_seconds_for_minimum_length() -> None:
    total = 4 * c.WINDOW_SAMPLE_FRAMES
    windows = c.plan_windows(total, channels=1)
    assert len(windows) == 4
    assert windows[0].start_sample == 0
    assert windows[-1].end_sample == total
    assert all(w.end_sample - w.start_sample == c.WINDOW_SAMPLE_FRAMES for w in windows)
    assert all(w.byte_count == 2 * c.WINDOW_SAMPLE_FRAMES for w in windows)


def test_window_policy_spreads_long_source_and_aligns_to_frame_lattice() -> None:
    total = 40 * 60 * c.SAMPLE_RATE + 777
    windows = c.plan_windows(total, channels=2)
    assert len(windows) == 4
    assert all(w.start_sample % c.SAMPLES_PER_FRAME == 0 for w in windows)
    assert all(a.end_sample <= b.start_sample for a, b in pairwise(windows))
    assert windows[-1].end_sample <= total
    assert all(w.byte_offset == 4 * w.start_sample for w in windows)


def test_window_policy_refuses_short_or_wrong_profile() -> None:
    with pytest.raises(c.Refusal, match="WINDOW_DURATION_INSUFFICIENT"):
        c.plan_windows(4 * c.WINDOW_SAMPLE_FRAMES - 1, channels=1)
    with pytest.raises(c.Refusal, match="WINDOW_POLICY_INPUT_INVALID"):
        c.plan_windows(4 * c.WINDOW_SAMPLE_FRAMES, channels=1, samples_per_frame=2000)


def test_window_manifest_keeps_hash_domains_separate() -> None:
    window = c.plan_windows(4 * c.WINDOW_SAMPLE_FRAMES, channels=1)[0]
    manifest = c.WindowManifest("w0", H, J, K, 0, window, H, 0)
    assert manifest.source_sha256 != manifest.full_pcm_sha256


def known_vectors() -> tuple[c.KnownAnswerVector, ...]:
    return (
        c.KnownAnswerVector("zero-mono", H, J, 4, 2, 1),
        c.KnownAnswerVector("stereo-order", J, K, 8, 2, 2),
    )


def known_runs() -> tuple[c.KnownAnswerRun, ...]:
    return tuple(
        c.KnownAnswerRun(
            v.vector_ref,
            c.digest(toolchain()),
            c.digest(profile()),
            v.expected_output_sha256,
            v.expected_output_bytes,
            v.expected_sample_frames,
            "BYTE_IDENTICAL",
        )
        for v in known_vectors()
    )


def test_known_answer_suite_binds_toolchain_profile_and_bytes() -> None:
    assert (
        c.validate_known_answer_suite(
            c.KnownAnswerSuite("known-answer-suite-v1", known_vectors()),
            known_runs(),
            toolchain(),
            profile(),
        )
        == ()
    )


@pytest.mark.parametrize("case", ["missing", "output", "toolchain", "profile"])
def test_known_answer_suite_refuses_incomplete_or_drift(case: str) -> None:
    runs = list(known_runs())
    if case == "missing":
        runs.pop()
    elif case == "output":
        runs[0] = replace(runs[0], output_sha256=K)
    elif case == "toolchain":
        runs[0] = replace(runs[0], toolchain_sha256=H)
    else:
        runs[0] = replace(runs[0], profile_sha256=H)
    assert c.validate_known_answer_suite(
        c.KnownAnswerSuite("known-answer-suite-v1", known_vectors()),
        tuple(runs),
        toolchain(),
        profile(),
    )


def test_public_receipt_is_test_only_and_numeric_digest_only() -> None:
    receipt = c.PublicReceipt(
        "receipt-1",
        "source-1",
        (("source", H), ("pcm", J)),
        (("sample_frames", 100),),
        ("NONE",),
    )
    data = json.loads(c.public_receipt_json(receipt))
    assert data["receipt"]["qualification"] == "TEST_ONLY_SUPPORT"
    assert data["sha256"] == c.digest(receipt)
    assert "raw" not in c.public_receipt_json(receipt).lower()


def test_public_receipt_rejects_promotion_and_pathlike_refs() -> None:
    receipt = c.PublicReceipt("r", "s", (), (), ())
    with pytest.raises(c.Refusal, match="PUBLIC_RECEIPT_INVALID"):
        replace(receipt, qualification="VERIFIED_LIVE")
    with pytest.raises(c.Refusal, match="PUBLIC_RECEIPT_INVALID"):
        c.PublicReceipt("r", "C:/private/file.m4a", (), (), ())


def test_architecture_has_no_subprocess_media_io_network_or_native_imports() -> None:
    tree = ast.parse(inspect.getsource(c))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(
        key in name
        for name in imports
        for key in ("subprocess", "pathlib", "os", "requests", "socket", "davinci_ai_editor")
    )
    calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(
        isinstance(fn, ast.Name) and fn.id in ("open", "round", "exec", "eval") for fn in calls
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("process_exit_code", 1),
        ("status", c.AcquisitionStatus.QUARANTINED),
        ("source_pre_sha256", H),
        ("origin_sha256", J),
        ("output_bytes", 3),
        ("scalar_samples", 1),
        ("request_sha256", H),
    ],
)
def test_identical_invalid_extractions_never_qualify(field: str, value: object) -> None:
    req = request()
    first = changed_extraction(extraction(req), field, value)
    second = replace(
        first, operator_ref="operator-b", process_ref="process-b", attempt_ref="attempt-b"
    )
    assert "INDEPENDENT_EXTRACTION_UNQUALIFIED" in {
        f.code
        for f in c.validate_independent_comparison(req, first, second, comparison(first, second))
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("presentation_start_pts", "0"),
        ("presentation_start_pts", True),
        ("presentation_start_pts", 0.0),
        ("priming_samples", True),
        ("skip_samples", True),
        ("end_padding_samples", True),
    ],
)
def test_origin_requires_exact_int_without_coercion(field: str, value: object) -> None:
    with pytest.raises(c.Refusal, match="SAMPLE_ORIGIN_UNESTABLISHED"):
        # Deliberately inject malformed external values; cast never coerces at runtime.
        if field == "presentation_start_pts":
            bad = replace(origin(), presentation_start_pts=cast(int, value))
        elif field == "priming_samples":
            bad = replace(origin(), priming_samples=True)
        elif field == "skip_samples":
            bad = replace(origin(), skip_samples=True)
        else:
            bad = replace(origin(), end_padding_samples=True)
        bad.require_established()


def test_probe_impossible_audio_ordinal_refused() -> None:
    with pytest.raises(c.Refusal, match="PROBE_RECEIPT_INVALID"):
        probe(replace(stream(), audio_ordinal=1))


def test_suite_content_pin_rejects_matching_forged_runs() -> None:
    original = known_vectors()
    variants = (
        (replace(original[0], input_sha256=K), original[1]),
        (*original, replace(original[0], vector_ref="extra")),
        original[:1],
        (replace(original[0], expected_output_sha256=K), original[1]),
        (replace(original[0], expected_output_bytes=6, expected_sample_frames=3), original[1]),
        tuple(reversed(original)),
    )
    for vectors in variants:
        suite = c.KnownAnswerSuite("known-answer-suite-v1", vectors)
        runs = tuple(
            c.KnownAnswerRun(
                v.vector_ref,
                c.digest(toolchain()),
                c.digest(profile()),
                v.expected_output_sha256,
                v.expected_output_bytes,
                v.expected_sample_frames,
                "BYTE_IDENTICAL",
            )
            for v in vectors
        )
        assert "KNOWN_ANSWER_SUITE_PIN_MISMATCH" in {
            f.code for f in c.validate_known_answer_suite(suite, runs, toolchain(), profile())
        }


def manifests(
    req: c.ExtractionRequest, receipt: c.ExtractionReceipt
) -> tuple[c.WindowManifest, ...]:
    return tuple(
        c.WindowManifest(
            f"w{i}",
            K,
            req.source.source_sha256,
            receipt.output_sha256,
            req.selected_channel,
            w,
            J,
            receipt.sample_frames % c.SAMPLES_PER_FRAME,
        )
        for i, w in enumerate(c.plan_windows(receipt.sample_frames, channels=receipt.channels))
    )


def test_window_manifests_bind_exact_request_extraction_and_plan() -> None:
    req = request(stream_value=stream(channels=2))
    raw = extraction(req)
    frames = raw.sample_frames + 777
    receipt = replace(raw, sample_frames=frames, output_bytes=frames * 4, scalar_samples=frames * 2)
    values = manifests(req, receipt)
    assert c.validate_window_manifests(req, receipt, K, values) == ()
    assert c.validate_window_manifests(req, receipt, K, tuple(reversed(values))) == ()


@pytest.mark.parametrize(
    "case",
    [
        "move",
        "source",
        "pcm",
        "channel",
        "offset",
        "tail",
        "missing",
        "duplicate",
        "index",
        "policy",
        "invalid-extraction",
    ],
)
def test_window_manifest_adversaries(case: str) -> None:
    req = request()
    receipt = extraction(req)
    values = list(manifests(req, receipt))
    first = values[0]
    if case == "move":
        values[0] = replace(
            first,
            window=replace(
                first.window,
                start_sample=1920,
                end_sample=first.window.end_sample + 1920,
                byte_offset=3840,
            ),
        )
    elif case == "source":
        values[0] = replace(first, source_sha256=H)
    elif case == "pcm":
        values[0] = replace(first, full_pcm_sha256=J)
    elif case == "channel":
        values[0] = replace(first, selected_channel=1)
    elif case == "offset":
        values[0] = replace(first, window=replace(first.window, byte_offset=2))
    elif case == "tail":
        values[0] = replace(first, tail_excluded_sample_frames=1)
    elif case == "missing":
        values.pop()
    elif case == "duplicate":
        values[1] = first
    elif case == "index":
        values[0] = replace(first, window=replace(first.window, index=4))
    elif case == "policy":
        values[0] = replace(first, policy_sha256=H)
    else:
        receipt = replace(receipt, process_exit_code=1)
    assert c.validate_window_manifests(req, receipt, K, tuple(values))


def test_profile_schema_explicit_supported_channel_set() -> None:
    path = Path(__file__).parent / "fixtures/compressed_source_acquisition/profile.schema.json"
    schema = json.loads(path.read_text())
    assert "supported_channels" in schema["required"]
    assert "channels" not in schema["properties"]
    assert schema["properties"]["supported_channels"]["prefixItems"] == [{"const": 1}, {"const": 2}]


@pytest.mark.parametrize("invalid_first", [True, False])
def test_either_invalid_extraction_blocks_comparison(invalid_first: bool) -> None:
    req = request()
    first = extraction(req)
    second = extraction(req, operator="b", process="b", attempt="b")
    if invalid_first:
        first = replace(first, process_exit_code=1)
    else:
        second = replace(second, process_exit_code=1)
    assert c.validate_independent_comparison(req, first, second, comparison(first, second))


def test_known_answer_fixture_pin_and_suite_reference() -> None:
    path = (
        Path(__file__).parent / "fixtures/compressed_source_acquisition/known_answer_manifest.json"
    )
    payload = json.loads(path.read_text())
    suite = c.KnownAnswerSuite(
        payload["suite_ref"], tuple(c.KnownAnswerVector(**v) for v in payload["vectors"])
    )
    assert c.digest(suite) == payload["suite_sha256"] == profile().known_answer_suite_sha256
    assert c.validate_known_answer_suite(suite, known_runs(), toolchain(), profile()) == ()
    changed = replace(suite, suite_ref="other-suite")
    assert c.validate_known_answer_suite(changed, known_runs(), toolchain(), profile())


def test_window_duplicate_ref_and_wrong_byte_count() -> None:
    req = request()
    receipt = extraction(req)
    values = manifests(req, receipt)
    duplicate = (values[0], replace(values[1], window_ref=values[0].window_ref), *values[2:])
    assert c.validate_window_manifests(req, receipt, K, duplicate)
    wrong_count = (replace(values[0], window=replace(values[0].window, byte_count=2)), *values[1:])
    assert c.validate_window_manifests(req, receipt, K, wrong_count)
