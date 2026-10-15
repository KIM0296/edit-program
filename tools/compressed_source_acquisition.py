"""CSA-001 synthetic compressed-source acquisition contracts.

No subprocess, media file IO, native Resolve access, decoding, or qualification occurs here.
All values are caller-supplied evidence and consistency claims until separately qualified.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Final


SCHEMA: Final = "csa-001-test-only-v1"
PROFILE_REF: Final = "csa-aac48-pcm16le-v1"
SOURCE_BYTE_CAP: Final = 128 * 1024 * 1024
DECODED_DURATION_CAP_SECONDS: Final = 3600
MAX_OUTPUT_BYTES: Final = 691_200_000
SCRATCH_CAP_BYTES: Final = 1 * 1024 * 1024 * 1024
MEMORY_CAP_BYTES: Final = 1 * 1024 * 1024 * 1024
WALL_TIME_CAP_SECONDS: Final = 15 * 60
SAMPLE_RATE: Final = 48_000
FRAME_RATE: Final = 25
SAMPLES_PER_FRAME: Final = 1_920
WINDOW_SECONDS: Final = 30
WINDOW_SAMPLE_FRAMES: Final = SAMPLE_RATE * WINDOW_SECONDS


class Refusal(ValueError):
    """Typed fail-closed contract refusal."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ContainerFamily(str, Enum):
    M4A_MOV = "M4A_MOV"


class EditListState(str, Enum):
    ABSENT = "ABSENT"
    ACCOUNTED = "ACCOUNTED"


class OriginStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    UNKNOWN = "UNKNOWN"


class AcquisitionStatus(str, Enum):
    READY = "READY"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str


def _pseudo(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value))


def _sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value)}
    raise Refusal("NON_CANONICAL_VALUE")


def digest(value: object) -> str:
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parse_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Refusal("TIMESTAMP_INVALID") from exc
    if result.utcoffset() is None:
        raise Refusal("TIMEZONE_MISSING")
    return result


@dataclass(frozen=True)
class LibraryPin:
    name: str
    version: str
    sha256: str

    def __post_init__(self) -> None:
        if not _pseudo(self.name) or not self.version or not _sha(self.sha256):
            raise Refusal("LIBRARY_PIN_INVALID")


@dataclass(frozen=True)
class ToolBinaryPin:
    tool_ref: str
    version_text: str
    executable_sha256: str
    build_configuration_sha256: str
    platform_ref: str
    architecture_ref: str

    def __post_init__(self) -> None:
        if (
            not _pseudo(self.tool_ref)
            or not self.version_text.strip()
            or not _sha(self.executable_sha256)
            or not _sha(self.build_configuration_sha256)
            or not _pseudo(self.platform_ref)
            or not _pseudo(self.architecture_ref)
        ):
            raise Refusal("TOOL_BINARY_PIN_INVALID")


@dataclass(frozen=True)
class ToolchainPin:
    ffmpeg: ToolBinaryPin
    ffprobe: ToolBinaryPin
    libraries: tuple[LibraryPin, ...]
    cpu_policy_ref: str
    locale: str
    threads: int
    procedure_sha256: str

    def __post_init__(self) -> None:
        libraries = tuple(sorted(tuple(self.libraries), key=lambda x: x.name))
        object.__setattr__(self, "libraries", libraries)
        if (
            not libraries
            or len({x.name for x in libraries}) != len(libraries)
            or not _pseudo(self.cpu_policy_ref)
            or self.locale != "C"
            or self.threads != 1
            or not _sha(self.procedure_sha256)
        ):
            raise Refusal("TOOLCHAIN_PIN_INVALID")


@dataclass(frozen=True)
class PermissionBinding:
    permission_ref: str
    evidence_sha256: str
    valid_from: str
    expiry: str
    retention_ref: str
    permitted_operations: tuple[str, ...]

    def __post_init__(self) -> None:
        operations = tuple(sorted(set(self.permitted_operations)))
        object.__setattr__(self, "permitted_operations", operations)
        if (
            not _pseudo(self.permission_ref)
            or not _sha(self.evidence_sha256)
            or not _pseudo(self.retention_ref)
            or not operations
            or any(not _pseudo(x) for x in operations)
        ):
            raise Refusal("PERMISSION_BINDING_INVALID")
        _parse_time(self.valid_from)
        _parse_time(self.expiry)


@dataclass(frozen=True)
class SourcePin:
    asset_ref: str
    source_ref: str
    session_ref: str
    source_owner_ref: str
    recorder_ref: str
    lineage_refs: tuple[str, ...]
    independence_evidence_sha256: str
    source_sha256: str
    source_bytes: int
    acquired_at: str
    permission: PermissionBinding
    snapshot_ref: str

    def __post_init__(self) -> None:
        lineages = tuple(sorted(set(self.lineage_refs)))
        object.__setattr__(self, "lineage_refs", lineages)
        if (
            any(
                not _pseudo(x)
                for x in (
                    self.asset_ref,
                    self.source_ref,
                    self.session_ref,
                    self.source_owner_ref,
                    self.recorder_ref,
                    self.snapshot_ref,
                )
            )
            or not lineages
            or any(not _pseudo(x) for x in lineages)
            or not _sha(self.independence_evidence_sha256)
            or not _sha(self.source_sha256)
            or type(self.source_bytes) is not int
            or not 0 < self.source_bytes <= SOURCE_BYTE_CAP
        ):
            raise Refusal("SOURCE_PIN_INVALID")
        _parse_time(self.acquired_at)


def validate_source_use(
    source: SourcePin,
    *,
    use_start_at: str,
    use_end_at: str,
    required_operation: str = "decode",
) -> tuple[Finding, ...]:
    try:
        acquired = _parse_time(source.acquired_at)
        valid_from = _parse_time(source.permission.valid_from)
        expiry = _parse_time(source.permission.expiry)
        start = _parse_time(use_start_at)
        end = _parse_time(use_end_at)
    except Refusal as exc:
        return (Finding(exc.code, source.source_ref),)
    issues: list[Finding] = []
    if required_operation not in source.permission.permitted_operations:
        issues.append(Finding("PERMISSION_OPERATION_NOT_ALLOWED", source.source_ref))
    if not valid_from <= acquired <= start <= end < expiry:
        issues.append(Finding("PERMISSION_INVALID_AT_USE", source.source_ref))
    return tuple(issues)


@dataclass(frozen=True)
class StreamFingerprint:
    container: ContainerFamily
    global_stream_index: int
    audio_ordinal: int
    stream_id: str | None
    codec_name: str
    codec_profile: str
    codec_extradata_sha256: str | None
    sample_rate: int
    channels: int
    channel_order: tuple[str, ...]
    time_base_numerator: int
    time_base_denominator: int
    start_pts: int | None

    def __post_init__(self) -> None:
        order = tuple(self.channel_order)
        object.__setattr__(self, "channel_order", order)
        if (
            not isinstance(self.container, ContainerFamily)
            or type(self.global_stream_index) is not int
            or self.global_stream_index < 0
            or type(self.audio_ordinal) is not int
            or self.audio_ordinal < 0
            or (self.stream_id is not None and not _pseudo(self.stream_id))
            or not self.codec_name
            or not self.codec_profile
            or (
                self.codec_extradata_sha256 is not None
                and not _sha(self.codec_extradata_sha256)
            )
            or type(self.sample_rate) is not int
            or type(self.channels) is not int
            or self.channels <= 0
            or len(order) != self.channels
            or len(set(order)) != len(order)
            or any(not _pseudo(x) for x in order)
            or type(self.time_base_numerator) is not int
            or type(self.time_base_denominator) is not int
            or self.time_base_numerator <= 0
            or self.time_base_denominator <= 0
            or (self.start_pts is not None and type(self.start_pts) is not int)
        ):
            raise Refusal("STREAM_FINGERPRINT_INVALID")


@dataclass(frozen=True)
class DecodeProfile:
    profile_ref: str
    conversion_policy_ref: str
    conversion_policy_sha256: str
    rounding_policy_ref: str
    clipping_policy_ref: str
    nonfinite_policy_ref: str
    interleave_policy_ref: str
    known_answer_suite_ref: str
    known_answer_suite_sha256: str
    sample_rate: int = SAMPLE_RATE
    output_format: str = "PCM16LE"
    signed: bool = True
    bit_depth: int = 16
    little_endian: bool = True
    interleaved: bool = True
    dither_enabled: bool = False
    resample_enabled: bool = False
    downmix_enabled: bool = False
    normalization_enabled: bool = False
    filter_enabled: bool = False
    max_source_bytes: int = SOURCE_BYTE_CAP
    max_duration_seconds: int = DECODED_DURATION_CAP_SECONDS
    max_output_bytes: int = MAX_OUTPUT_BYTES
    scratch_cap_bytes: int = SCRATCH_CAP_BYTES
    memory_cap_bytes: int = MEMORY_CAP_BYTES
    wall_time_cap_seconds: int = WALL_TIME_CAP_SECONDS
    threads: int = 1

    def __post_init__(self) -> None:
        policy_refs = (
            self.conversion_policy_ref,
            self.rounding_policy_ref,
            self.clipping_policy_ref,
            self.nonfinite_policy_ref,
            self.interleave_policy_ref,
            self.known_answer_suite_ref,
        )
        if (
            self.profile_ref != PROFILE_REF
            or any(not _pseudo(x) for x in policy_refs)
            or not _sha(self.conversion_policy_sha256)
            or not _sha(self.known_answer_suite_sha256)
            or self.sample_rate != SAMPLE_RATE
            or self.output_format != "PCM16LE"
            or self.signed is not True
            or self.bit_depth != 16
            or self.little_endian is not True
            or self.interleaved is not True
            or self.dither_enabled
            or self.resample_enabled
            or self.downmix_enabled
            or self.normalization_enabled
            or self.filter_enabled
            or self.max_source_bytes != SOURCE_BYTE_CAP
            or self.max_duration_seconds != DECODED_DURATION_CAP_SECONDS
            or self.max_output_bytes != MAX_OUTPUT_BYTES
            or self.scratch_cap_bytes != SCRATCH_CAP_BYTES
            or self.memory_cap_bytes != MEMORY_CAP_BYTES
            or self.wall_time_cap_seconds != WALL_TIME_CAP_SECONDS
            or self.threads != 1
        ):
            raise Refusal("DECODE_PROFILE_INVALID")


def validate_supported_stream(stream: StreamFingerprint) -> tuple[Finding, ...]:
    issues: list[Finding] = []
    subject = str(stream.global_stream_index)
    if stream.container != ContainerFamily.M4A_MOV:
        issues.append(Finding("UNSUPPORTED_CONTAINER", subject))
    if stream.codec_name.lower() != "aac" or stream.codec_profile.upper() != "LC":
        issues.append(Finding("UNSUPPORTED_CODEC", subject))
    if stream.sample_rate != SAMPLE_RATE:
        issues.append(Finding("UNSUPPORTED_PROFILE", subject))
    if stream.channels not in (1, 2):
        issues.append(Finding("CHANNEL_AMBIGUITY", subject))
    return tuple(issues)


@dataclass(frozen=True)
class ProbeReceipt:
    source_sha256: str
    source_bytes: int
    ffprobe_pin_sha256: str
    audio_stream_count: int
    stream: StreamFingerprint
    probe_receipt_sha256: str

    def __post_init__(self) -> None:
        if (
            not _sha(self.source_sha256)
            or type(self.source_bytes) is not int
            or self.source_bytes <= 0
            or not _sha(self.ffprobe_pin_sha256)
            or type(self.audio_stream_count) is not int
            or self.audio_stream_count <= 0
            or not _sha(self.probe_receipt_sha256)
        ):
            raise Refusal("PROBE_RECEIPT_INVALID")


@dataclass(frozen=True)
class SampleOriginEvidence:
    status: OriginStatus
    presentation_start_pts: int | None
    priming_samples: int | None
    skip_samples: int | None
    end_padding_samples: int | None
    edit_list_state: EditListState | None
    accounting_ref: str
    accounting_sha256: str
    canonical_sample_origin: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status, OriginStatus)
            or not _pseudo(self.accounting_ref)
            or not _sha(self.accounting_sha256)
            or self.canonical_sample_origin != 0
        ):
            raise Refusal("ORIGIN_EVIDENCE_INVALID")

    def require_established(self) -> None:
        values = (self.priming_samples, self.skip_samples, self.end_padding_samples)
        if (
            self.status != OriginStatus.ESTABLISHED
            or self.presentation_start_pts is None
            or any(type(v) is not int or v < 0 for v in values)
            or not isinstance(self.edit_list_state, EditListState)
        ):
            raise Refusal("SAMPLE_ORIGIN_UNESTABLISHED")


def canonical_argument_template(global_stream_index: int) -> tuple[str, ...]:
    if type(global_stream_index) is not int or global_stream_index < 0:
        raise Refusal("STREAM_INDEX_INVALID")
    return (
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "1",
        "-i",
        "{SOURCE}",
        "-map",
        f"0:{global_stream_index}",
        "-vn",
        "-sn",
        "-dn",
        "-c:a",
        "pcm_s16le",
        "-f",
        "s16le",
        "{OUTPUT}",
    )


@dataclass(frozen=True)
class ExtractionRequest:
    source: SourcePin
    probe: ProbeReceipt
    toolchain: ToolchainPin
    profile: DecodeProfile
    selected_channel: int
    use_start_at: str
    use_end_at: str
    origin: SampleOriginEvidence
    ordered_arguments: tuple[str, ...]

    def __post_init__(self) -> None:
        args = tuple(self.ordered_arguments)
        object.__setattr__(self, "ordered_arguments", args)
        if validate_source_use(
            self.source, use_start_at=self.use_start_at, use_end_at=self.use_end_at
        ):
            raise Refusal("PERMISSION_INVALID_AT_USE")
        if (
            self.probe.source_sha256 != self.source.source_sha256
            or self.probe.source_bytes != self.source.source_bytes
        ):
            raise Refusal("SOURCE_HASH_DRIFT")
        if self.probe.ffprobe_pin_sha256 != digest(self.toolchain.ffprobe):
            raise Refusal("TOOLCHAIN_DRIFT")
        stream_issues = validate_supported_stream(self.probe.stream)
        if stream_issues:
            raise Refusal(stream_issues[0].code)
        if (
            type(self.selected_channel) is not int
            or not 0 <= self.selected_channel < self.probe.stream.channels
        ):
            raise Refusal("CHANNEL_AMBIGUITY")
        self.origin.require_established()
        if args != canonical_argument_template(self.probe.stream.global_stream_index):
            raise Refusal("ARGUMENT_POLICY_MISMATCH")


@dataclass(frozen=True)
class ExtractionReceipt:
    request_sha256: str
    operator_ref: str
    process_ref: str
    attempt_ref: str
    source_pre_sha256: str
    source_post_sha256: str
    source_pre_bytes: int
    source_post_bytes: int
    output_sha256: str
    output_bytes: int
    sample_frames: int
    scalar_samples: int
    sample_rate: int
    channels: int
    channel_order: tuple[str, ...]
    selected_channel: int
    origin_sha256: str
    eof_seen: bool
    flush_complete: bool
    process_exit_code: int
    restricted_output_ref: str
    status: AcquisitionStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel_order", tuple(self.channel_order))


def validate_extraction_receipt(
    request: ExtractionRequest, receipt: ExtractionReceipt
) -> tuple[Finding, ...]:
    issues: list[Finding] = []

    def fail(code: str) -> None:
        issues.append(Finding(code, receipt.attempt_ref))

    stream = request.probe.stream
    if receipt.request_sha256 != digest(request):
        fail("REQUEST_BINDING_MISMATCH")
    if any(not _pseudo(x) for x in (receipt.operator_ref, receipt.process_ref, receipt.attempt_ref)):
        fail("EXTRACTION_IDENTITY_INVALID")
    if (
        receipt.source_pre_sha256 != request.source.source_sha256
        or receipt.source_post_sha256 != request.source.source_sha256
        or receipt.source_pre_bytes != request.source.source_bytes
        or receipt.source_post_bytes != request.source.source_bytes
    ):
        fail("SOURCE_HASH_DRIFT")
    if (
        not _sha(receipt.output_sha256)
        or type(receipt.sample_frames) is not int
        or receipt.sample_frames <= 0
        or type(receipt.output_bytes) is not int
        or receipt.output_bytes != receipt.sample_frames * stream.channels * 2
        or receipt.output_bytes > request.profile.max_output_bytes
        or receipt.scalar_samples != receipt.sample_frames * stream.channels
    ):
        fail("DECODE_LENGTH_MISMATCH")
    if (
        receipt.sample_rate != stream.sample_rate
        or receipt.channels != stream.channels
        or receipt.channel_order != stream.channel_order
        or receipt.selected_channel != request.selected_channel
    ):
        fail("PCM_FORMAT_MISMATCH")
    if receipt.origin_sha256 != digest(request.origin):
        fail("SAMPLE_ORIGIN_UNESTABLISHED")
    if not receipt.eof_seen or not receipt.flush_complete or receipt.process_exit_code != 0:
        fail("DECODE_FAILURE")
    if not _pseudo(receipt.restricted_output_ref):
        fail("RESTRICTED_OUTPUT_REF_INVALID")
    if receipt.status != AcquisitionStatus.READY:
        fail("ACQUISITION_NOT_READY")
    return tuple(issues)


@dataclass(frozen=True)
class ComparisonReceipt:
    comparator_ref: str
    comparator_sha256: str
    first_attempt_ref: str
    second_attempt_ref: str
    byte_comparison_result: str
    compared_bytes: int
    first_difference_offset: int | None
    result: str


def validate_independent_comparison(
    source: SourcePin,
    first: ExtractionReceipt,
    second: ExtractionReceipt,
    comparison: ComparisonReceipt,
) -> tuple[Finding, ...]:
    issues: list[Finding] = []

    def fail(code: str) -> None:
        issues.append(Finding(code, comparison.comparator_ref))

    if (
        not _pseudo(comparison.comparator_ref)
        or not _sha(comparison.comparator_sha256)
        or comparison.first_attempt_ref != first.attempt_ref
        or comparison.second_attempt_ref != second.attempt_ref
    ):
        fail("COMPARISON_RECEIPT_INVALID")
    if (
        first.operator_ref == second.operator_ref
        or second.operator_ref == source.recorder_ref
        or first.process_ref == second.process_ref
        or first.attempt_ref == second.attempt_ref
    ):
        fail("INDEPENDENT_EXTRACTION_MISMATCH")
    if (
        first.request_sha256 != second.request_sha256
        or first.output_sha256 != second.output_sha256
        or first.output_bytes != second.output_bytes
        or first.sample_frames != second.sample_frames
        or first.scalar_samples != second.scalar_samples
        or first.sample_rate != second.sample_rate
        or first.channels != second.channels
        or first.channel_order != second.channel_order
        or first.selected_channel != second.selected_channel
        or first.origin_sha256 != second.origin_sha256
    ):
        fail("INDEPENDENT_EXTRACTION_MISMATCH")
    if (
        comparison.byte_comparison_result != "BYTE_IDENTICAL"
        or comparison.compared_bytes != first.output_bytes
        or comparison.first_difference_offset is not None
        or comparison.result != "BOUNDED_ACQUISITION_EVIDENCE_ONLY"
    ):
        fail("BYTE_COMPARISON_MISMATCH")
    return tuple(issues)


@dataclass(frozen=True)
class PlannedWindow:
    index: int
    start_sample: int
    end_sample: int
    byte_offset: int
    byte_count: int


def plan_windows(
    canonical_sample_frames: int,
    *,
    channels: int,
    samples_per_frame: int = SAMPLES_PER_FRAME,
    window_sample_frames: int = WINDOW_SAMPLE_FRAMES,
) -> tuple[PlannedWindow, ...]:
    if (
        type(canonical_sample_frames) is not int
        or canonical_sample_frames <= 0
        or channels not in (1, 2)
        or samples_per_frame != SAMPLES_PER_FRAME
        or window_sample_frames != WINDOW_SAMPLE_FRAMES
    ):
        raise Refusal("WINDOW_POLICY_INPUT_INVALID")
    usable = samples_per_frame * (canonical_sample_frames // samples_per_frame)
    if usable < 4 * window_sample_frames:
        raise Refusal("WINDOW_DURATION_INSUFFICIENT")
    remaining = usable - 4 * window_sample_frames
    windows = []
    for index in range(4):
        offset_frames = (index * remaining) // (3 * samples_per_frame)
        start = index * window_sample_frames + samples_per_frame * offset_frames
        end = start + window_sample_frames
        windows.append(
            PlannedWindow(
                index,
                start,
                end,
                2 * channels * start,
                2 * channels * window_sample_frames,
            )
        )
    return tuple(windows)


@dataclass(frozen=True)
class WindowManifest:
    window_ref: str
    policy_sha256: str
    source_sha256: str
    full_pcm_sha256: str
    selected_channel: int
    window: PlannedWindow
    window_pcm_sha256: str
    tail_excluded_sample_frames: int

    def __post_init__(self) -> None:
        if (
            not _pseudo(self.window_ref)
            or not _sha(self.policy_sha256)
            or not _sha(self.source_sha256)
            or not _sha(self.full_pcm_sha256)
            or not _sha(self.window_pcm_sha256)
            or self.selected_channel < 0
            or type(self.tail_excluded_sample_frames) is not int
            or self.tail_excluded_sample_frames < 0
        ):
            raise Refusal("WINDOW_MANIFEST_INVALID")


@dataclass(frozen=True)
class KnownAnswerVector:
    vector_ref: str
    input_sha256: str
    expected_output_sha256: str
    expected_output_bytes: int
    expected_sample_frames: int
    channels: int

    def __post_init__(self) -> None:
        if (
            not _pseudo(self.vector_ref)
            or not _sha(self.input_sha256)
            or not _sha(self.expected_output_sha256)
            or self.expected_output_bytes <= 0
            or self.expected_sample_frames <= 0
            or self.channels not in (1, 2)
            or self.expected_output_bytes != self.expected_sample_frames * self.channels * 2
        ):
            raise Refusal("KNOWN_ANSWER_VECTOR_INVALID")


@dataclass(frozen=True)
class KnownAnswerRun:
    vector_ref: str
    toolchain_sha256: str
    profile_sha256: str
    output_sha256: str
    output_bytes: int
    sample_frames: int
    result: str


def validate_known_answer_suite(
    vectors: tuple[KnownAnswerVector, ...],
    runs: tuple[KnownAnswerRun, ...],
    toolchain: ToolchainPin,
    profile: DecodeProfile,
) -> tuple[Finding, ...]:
    vector_map = {v.vector_ref: v for v in vectors}
    run_map = {r.vector_ref: r for r in runs}
    if (
        not vectors
        or len(vector_map) != len(vectors)
        or len(run_map) != len(runs)
        or set(vector_map) != set(run_map)
    ):
        return (Finding("KNOWN_ANSWER_SUITE_INCOMPLETE", profile.profile_ref),)
    issues: list[Finding] = []
    tool_sha = digest(toolchain)
    profile_sha = digest(profile)
    for ref, vector in vector_map.items():
        run = run_map[ref]
        if (
            run.toolchain_sha256 != tool_sha
            or run.profile_sha256 != profile_sha
            or run.output_sha256 != vector.expected_output_sha256
            or run.output_bytes != vector.expected_output_bytes
            or run.sample_frames != vector.expected_sample_frames
            or run.result != "BYTE_IDENTICAL"
        ):
            issues.append(Finding("KNOWN_ANSWER_MISMATCH", ref))
    return tuple(issues)


@dataclass(frozen=True)
class PublicReceipt:
    receipt_ref: str
    source_ref: str
    input_digests: tuple[tuple[str, str], ...]
    numeric_counts: tuple[tuple[str, int], ...]
    diagnostic_codes: tuple[str, ...]
    qualification: str = "TEST_ONLY_SUPPORT"

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_digests", tuple(self.input_digests))
        object.__setattr__(self, "numeric_counts", tuple(self.numeric_counts))
        object.__setattr__(self, "diagnostic_codes", tuple(self.diagnostic_codes))
        if (
            not _pseudo(self.receipt_ref)
            or not _pseudo(self.source_ref)
            or self.qualification != "TEST_ONLY_SUPPORT"
            or any(not _pseudo(k) or not _sha(v) for k, v in self.input_digests)
            or any(not _pseudo(k) or type(v) is not int or v < 0 for k, v in self.numeric_counts)
            or any(not _pseudo(x) for x in self.diagnostic_codes)
        ):
            raise Refusal("PUBLIC_RECEIPT_INVALID")


def public_receipt_json(receipt: PublicReceipt) -> str:
    return (
        json.dumps(
            {"schema": SCHEMA, "receipt": _canonical(receipt), "sha256": digest(receipt)},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
