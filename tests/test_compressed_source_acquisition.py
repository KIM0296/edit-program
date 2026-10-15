"""CSA-001 TEST_ONLY_SUPPORT contracts; no real media, subprocess, or native access."""

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, replace
from itertools import pairwise

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
    order = ("mono",) if channels == 1 else ("FL", "FR") if channels == 2 else tuple(
        f"C{i}" for i in range(channels)
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
        J,
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
        replace(toolchain(), **change)


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
        replace(profile(), **{field: value})


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
    assert {x.code for x in c.validate_source_use(
        bad,
        use_start_at="2026-10-14T12:00:00+09:00",
        use_end_at="2026-10-14T12:15:00+09:00",
    )} == {"PERMISSION_OPERATION_NOT_ALLOWED"}


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
                source(), bad_probe, toolchain(), profile(), 0,
                "2026-10-14T12:00:00+09:00", "2026-10-14T12:15:00+09:00",
                origin(), c.canonical_argument_template(1),
            )
    elif case == "tool":
        bad_probe = replace(probe(), ffprobe_pin_sha256=H)
        with pytest.raises(c.Refusal, match=code):
            c.ExtractionRequest(
                source(), bad_probe, toolchain(), profile(), 0,
                "2026-10-14T12:00:00+09:00", "2026-10-14T12:15:00+09:00",
                origin(), c.canonical_argument_template(1),
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
    bad = replace(extraction(req), **{field: value})
    assert code in {x.code for x in c.validate_extraction_receipt(req, bad)}


def test_independent_comparison_byte_identical() -> None:
    req = request()
    first = extraction(req)
    second = extraction(req, operator="operator-b", process="process-b", attempt="attempt-b")
    assert c.validate_independent_comparison(
        source(), first, second, comparison(first, second)
    ) == ()


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
    assert c.validate_independent_comparison(source(), first, second, comp)


def test_first_extractor_may_be_recorder_second_must_be_independent() -> None:
    req = request()
    first = extraction(req, operator=source().recorder_ref)
    second = extraction(req, operator="operator-b", process="process-b", attempt="attempt-b")
    assert c.validate_independent_comparison(
        source(), first, second, comparison(first, second)
    ) == ()


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
    assert c.validate_known_answer_suite(known_vectors(), known_runs(), toolchain(), profile()) == ()


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
    assert c.validate_known_answer_suite(known_vectors(), tuple(runs), toolchain(), profile())


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
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
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
        isinstance(fn, ast.Name) and fn.id in ("open", "round", "exec", "eval")
        for fn in calls
    )
