"""Pure ADR-033 classifications. Coverage is necessary; success percentages are not used."""

from .model import ReadObservation, RuntimeResult


def classify_observations(
    reads: tuple[ReadObservation, ...], *, coverage_complete: bool, unstable_context: bool = False
) -> RuntimeResult:
    reads = tuple(reads)
    if not reads:
        return RuntimeResult.UNKNOWN
    if all(r.documented_absent for r in reads):
        return RuntimeResult.UNSUPPORTED
    if any(not r.valid for r in reads):
        return RuntimeResult.UNKNOWN
    if unstable_context or len({r.semantic_value for r in reads}) > 1:
        return RuntimeResult.SUPPORTED_UNSTABLE
    if coverage_complete and len(reads) >= 20:
        return RuntimeResult.SUPPORTED_STABLE
    return RuntimeResult.UNKNOWN


from dataclasses import dataclass

from .fixtures import FixtureAssessment, FixtureInput
from .model import FixtureResult, ProbeSnapshot


@dataclass(frozen=True)
class CapturePair:
    number: int
    a: ProbeSnapshot
    b: ProbeSnapshot
    assessment_a: FixtureAssessment
    assessment_b: FixtureAssessment

    def __post_init__(self) -> None:
        if not all(isinstance(s, ProbeSnapshot) for s in (self.a, self.b)) or not all(
            isinstance(a, FixtureAssessment) for a in (self.assessment_a, self.assessment_b)
        ):
            raise TypeError("Immutable capture and assessment required")
        if type(self.number) is not int or not 1 <= self.number <= 10:
            raise ValueError("S1 pair number must be 1..10")
        if (
            self.a.binding != self.b.binding
            or self.a.context != self.b.context
            or self.a.timeline_id != self.b.timeline_id
        ):
            raise ValueError("Mixed capture pair binding")
        if self.b.sequence != self.a.sequence + 1:
            raise ValueError("Back-to-back capture sequence required")

    @property
    def accepted(self) -> bool:
        return (
            self.a.complete
            and self.b.complete
            and not self.a.operator_interference
            and not self.b.operator_interference
            and self.a.semantic_fields == self.b.semantic_fields
            and self.assessment_a.status == self.assessment_b.status == FixtureResult.MATCH
        )


@dataclass(frozen=True)
class S1Series:
    fixture: FixtureInput
    audit: ProbeSnapshot
    audit_result: FixtureAssessment
    pairs: tuple[CapturePair, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.fixture, FixtureInput)
            or not isinstance(self.audit, ProbeSnapshot)
            or not isinstance(self.audit_result, FixtureAssessment)
        ):
            raise TypeError("Typed S1 evidence required")
        object.__setattr__(self, "pairs", tuple(self.pairs))
        if any(not isinstance(p, CapturePair) for p in self.pairs):
            raise TypeError("Typed pairs required")
        if tuple(p.number for p in self.pairs) != tuple(range(1, len(self.pairs) + 1)):
            raise ValueError("Cannot drop/renumber/duplicate S1 pairs")
        if len(self.pairs) > 10:
            raise ValueError("No retry pairs")
        for p in self.pairs:
            if p.a.binding != self.audit.binding or p.a.context != self.audit.context:
                raise ValueError("Mixed S1 run")
        sequences = [s.sequence for p in self.pairs for s in (p.a, p.b)]
        if sequences != sorted(set(sequences)) or (
            sequences and sequences[0] <= self.audit.sequence
        ):
            raise ValueError("Explicit monotonic capture ordering")

    @property
    def qualified(self) -> bool:
        return (
            self.audit_result.status == FixtureResult.MATCH
            and len(self.pairs) == 10
            and all(
                p.accepted and p.a.semantic_fields == self.pairs[0].a.semantic_fields
                for p in self.pairs
            )
        )


@dataclass(frozen=True)
class RoundTrip:
    number: int
    before: ProbeSnapshot
    other: ProbeSnapshot
    after: ProbeSnapshot
    operator_actions: tuple[str, str, str]

    def __post_init__(self) -> None:
        from .model import Context, text

        if type(self.number) is not int or not 1 <= self.number <= 3:
            raise ValueError("Exactly three S2 round trips")
        object.__setattr__(self, "operator_actions", tuple(self.operator_actions))
        if len(self.operator_actions) != 3:
            raise ValueError("Explicit external actions required")
        for action in self.operator_actions:
            text(action)
        if not self.before.binding == self.other.binding == self.after.binding:
            raise ValueError("Mixed round-trip run")
        if (self.before.context, self.other.context, self.after.context) != (
            Context.F4_A,
            Context.F4_B,
            Context.F4_A,
        ):
            raise ValueError("Exact A-B-A required")
        if not self.before.sequence < self.other.sequence < self.after.sequence:
            raise ValueError("Nonmonotonic round trip")

    @property
    def accepted(self) -> bool:
        return (
            all(
                s.complete and not s.operator_interference
                for s in (self.before, self.other, self.after)
            )
            and self.before.timeline_id == self.after.timeline_id
            and self.before.timeline_id != self.other.timeline_id
            and self.before.semantic_fields == self.after.semantic_fields
        )


def classify_series(series: S1Series, case_id: str) -> RuntimeResult:
    captures = tuple(s for p in series.pairs for s in (p.a, p.b))
    if not captures:
        return RuntimeResult.UNKNOWN
    keys = {r.key for s in captures for r in s.reads if r.case_id == case_id}
    if not keys:
        return RuntimeResult.UNKNOWN
    coverage = len(series.pairs) == 10
    unstable = any(not s.consistent or s.operator_interference for s in captures)
    statuses = []
    for key in sorted(keys):
        observations = tuple(r for s in captures for r in s.reads if r.key == key)
        # Linked-ID helper reads are multisets; their RV-034 owner is the qualification field.
        if key[0].startswith("linked-of/"):
            continue
        if len(observations) != len(captures):
            statuses.append(RuntimeResult.UNKNOWN)
        else:
            statuses.append(
                classify_observations(
                    observations, coverage_complete=coverage, unstable_context=unstable
                )
            )
    if not statuses:
        return RuntimeResult.UNKNOWN
    for status in (
        RuntimeResult.SUPPORTED_UNSTABLE,
        RuntimeResult.UNKNOWN,
        RuntimeResult.UNSUPPORTED,
    ):
        if status in statuses:
            return status
    return RuntimeResult.SUPPORTED_STABLE
