"""Bounded protocol coordinator. Operator supplies context changes outside this module."""

from dataclasses import dataclass
from typing import Protocol

from .adapter import ReadOnlyProbeAdapter
from .fixtures import FixtureInput, assess_fixture
from .model import Context, FixtureResult, ProbeSnapshot, RunBinding
from .qualification import CapturePair, RoundTrip, S1Series


class Sink(Protocol):
    def write(self, relative: str, value: object) -> None: ...
    def capture(self, relative: str, snapshot: ProbeSnapshot) -> None: ...


@dataclass(frozen=True)
class OperatorPreflight:
    registered_disposable_project: bool
    not_production_or_working: bool
    approved_package_verified: bool
    no_concurrent_edit: bool
    no_repair_planned: bool
    failed_pairs_retained: bool
    currentness_evidence_supplied: bool

    def __post_init__(self) -> None:
        if any(type(v) is not bool for v in self.values):
            raise TypeError("Explicit operator checklist facts required")

    @property
    def values(self) -> tuple[bool, ...]:
        return (
            self.registered_disposable_project,
            self.not_production_or_working,
            self.approved_package_verified,
            self.no_concurrent_edit,
            self.no_repair_planned,
            self.failed_pairs_retained,
            self.currentness_evidence_supplied,
        )

    @property
    def ready(self) -> bool:
        return all(self.values)


class QualificationRunner:
    def __init__(
        self,
        adapter: ReadOnlyProbeAdapter,
        binding: RunBinding,
        operator: OperatorPreflight,
        sink: Sink,
    ):
        self._adapter = adapter
        self._binding = binding
        self._operator = operator
        self._sink = sink
        self._sequence = 0
        self._series: list[S1Series] = []
        self._roundtrips: list[RoundTrip] = []
        self._started: set[Context] = set()
        self._pending: list[ProbeSnapshot] = []
        self._actions: list[str] = []
        self._blocked = False
        self._sink.write("environment/operator_preflight.json", operator)

    @property
    def series(self) -> tuple[S1Series, ...]:
        return tuple(self._series)

    @property
    def roundtrips(self) -> tuple[RoundTrip, ...]:
        return tuple(self._roundtrips)

    def _gate(self, current: RunBinding) -> None:
        if self._blocked or not self._operator.ready or current != self._binding:
            raise ValueError("Read qualification preflight/binding blocked")

    def _capture(self, fixture: FixtureInput, path: str) -> ProbeSnapshot:
        self._sequence += 1
        snapshot = self._adapter.capture(
            self._binding, fixture.context, fixture.timeline_id, self._sequence
        )
        self._sink.capture(path, snapshot)
        if any(f.startswith("STALE") for f in snapshot.findings):
            self._blocked = True
        return snapshot

    def s1(self, fixture: FixtureInput, current: RunBinding) -> S1Series:
        self._gate(current)
        if fixture.context in self._started:
            raise ValueError("S1 cannot be retried within this run")
        if self._started and not self._started | {fixture.context} <= {Context.F4_A, Context.F4_B}:
            raise ValueError("Different project fixtures require separate bound runs; OPEN-023")
        self._started.add(fixture.context)
        root = "fixtures/" + fixture.context.value
        self._sink.write(root + "/fixture_binding.json", fixture)
        audit = self._capture(fixture, root + "/preflight/diagnostic")
        assessment = assess_fixture(audit, fixture)
        self._sink.write(
            root + "/preflight/result.json",
            {
                "purpose": "PREFLIGHT_DIAGNOSTIC",
                "counts_toward_s1": False,
                "assessment": assessment,
            },
        )
        pairs = []
        if assessment.status == FixtureResult.MATCH and not self._blocked:
            for number in range(1, 11):
                path = root + f"/s1/pair-{number:02d}"
                a = self._capture(fixture, path + "/capture-A")
                b = self._capture(fixture, path + "/capture-B")
                pair = CapturePair(
                    number, a, b, assess_fixture(a, fixture), assess_fixture(b, fixture)
                )
                pairs.append(pair)
                self._sink.write(
                    path + "/pair-result.json",
                    {
                        "number": number,
                        "accepted": pair.accepted,
                        "a_sequence": a.sequence,
                        "b_sequence": b.sequence,
                        "assessment_a": pair.assessment_a,
                        "assessment_b": pair.assessment_b,
                        "semantic_equal": a.semantic_fields == b.semantic_fields,
                    },
                )
                if self._blocked or any(
                    r.status in (FixtureResult.MISMATCH, FixtureResult.STALE, FixtureResult.ABORTED)
                    for r in (pair.assessment_a, pair.assessment_b)
                ):
                    break
        result = S1Series(fixture, audit, assessment, tuple(pairs))
        self._series.append(result)
        self._sink.write(
            root + "/fixture-summary.json",
            {
                "qualified": result.qualified,
                "audit": assessment,
                "pair_count": len(pairs),
                "failed_pairs": [p.number for p in pairs if not p.accepted],
            },
        )
        return result

    def record_operator_interference(self, incident_ref: str) -> None:
        from .model import text

        text(incident_ref)
        self._blocked = True
        self._sink.write(
            f"findings/operator-{self._sequence}.json",
            {"finding": "OPERATOR_INTERFERENCE", "evidence_ref": incident_ref},
        )

    def s2_capture(
        self,
        number: int,
        stage: str,
        fixture: FixtureInput,
        current: RunBinding,
        operator_action_ref: str,
    ) -> ProbeSnapshot:
        from .model import text

        self._gate(current)
        text(operator_action_ref)
        if {s.fixture.context for s in self._series if s.qualified} != {Context.F4_A, Context.F4_B}:
            raise ValueError("Both F4 S1 contexts must qualify before S2")
        expected = ("A-before", "B", "A-after")[len(self._pending)]
        if stage != expected or number != len(self._roundtrips) + 1 or not 1 <= number <= 3:
            raise ValueError("No skipped/retried/reordered S2 stage")
        context = Context.F4_B if stage == "B" else Context.F4_A
        original = next(s.fixture for s in self._series if s.fixture.context == context)
        if fixture != original:
            raise ValueError("Exact registered A/B fixture required")
        path = f"fixtures/F4_IDENTITY_BOUNDARY/s2/roundtrip-{number:02d}"
        snapshot = self._capture(fixture, path + "/" + stage)
        self._pending.append(snapshot)
        self._actions.append(operator_action_ref)
        self._sink.write(
            path + "/" + stage + ".operator.json",
            {"stage": stage, "action_ref": operator_action_ref, "adapter_switched_timeline": False},
        )
        if assess_fixture(snapshot, fixture).status != FixtureResult.MATCH:
            self._blocked = True
        baseline = next(s.pairs[0].a for s in self._series if s.fixture.context == context)
        if snapshot.semantic_fields != baseline.semantic_fields:
            self._blocked = True
            self._sink.write(
                path + "/" + stage + ".drift.json", {"finding": "S2_DIFFERS_FROM_S1_BASELINE"}
            )

        if len(self._pending) == 3:
            trip = RoundTrip(
                number,
                self._pending[0],
                self._pending[1],
                self._pending[2],
                (self._actions[0], self._actions[1], self._actions[2]),
            )
            self._roundtrips.append(trip)
            self._pending = []
            self._actions = []
            self._sink.write(
                path + "/roundtrip-result.json",
                {
                    "number": number,
                    "accepted": trip.accepted,
                    "operator_actions": trip.operator_actions,
                },
            )
            if not trip.accepted:
                self._blocked = True
        return snapshot
