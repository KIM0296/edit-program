"""Local append-only evidence output. Hashes detect changes, not native authenticity."""

from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path, PurePosixPath

from .model import Context, ProbeSnapshot, RunBinding, RuntimeResult
from .qualification import RoundTrip, S1Series, classify_series
from .values import canonical


def record(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: record(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        if any(type(k) is not str for k in value):
            raise TypeError("Evidence object keys must be strings; native maps use typed entries")
        return {k: record(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [record(v) for v in value]
    if type(value) in (str, int, bool, float, type(None)):
        return value
    raise TypeError("Unserializable evidence object")


def safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or "\\" in relative
        or ":" in relative
        or any(x in ("", "..", ".") for x in relative.split("/"))
    ):
        raise ValueError("Unsafe evidence path")
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Evidence escape")
    if target.is_symlink():
        raise ValueError("Evidence symlink")
    return target


class EvidenceWriter:
    def __init__(self, root: Path, binding: RunBinding):
        self.root = root
        self.binding = binding
        self._sealed = False
        self._written: dict[str, str] = {}
        self._captures: set[ProbeSnapshot] = set()
        self._started = datetime.now(UTC).isoformat()
        root.mkdir(parents=False, exist_ok=False)
        self.write("run-start.json", {"binding": binding, "started_at": self._started})
        self.write("runtime_profile.json", binding.profile)
        self.write("environment/registration.json", binding)

    def write(self, relative: str, value: object) -> None:
        if self._sealed:
            raise ValueError("Sealed evidence cannot be modified")
        path = safe_path(self.root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = (
            value.encode("utf-8")
            if isinstance(value, str) and relative.endswith(".md")
            else canonical(record(value))
        )
        with path.open("xb") as stream:
            stream.write(blob)
        self._written[relative] = sha256(blob).hexdigest()

    def capture(self, relative: str, snapshot: ProbeSnapshot) -> None:
        if snapshot.binding != self.binding:
            raise ValueError("Cannot splice foreign run evidence")
        self.write(relative + ".raw.json", snapshot)
        self.write(
            relative + ".semantic.json",
            {
                "binding": snapshot.binding,
                "context": snapshot.context,
                "sequence": snapshot.sequence,
                "timeline_id": snapshot.timeline_id,
                "fields": snapshot.semantic_fields,
                "consistent": snapshot.consistent,
                "complete": snapshot.complete,
                "findings": snapshot.findings,
                "tier_c": {
                    "persistent_identity": "UNKNOWN",
                    "native_track_identity": "UNKNOWN",
                    "retime_curve": "UNKNOWN",
                    "transition_preservation": "UNKNOWN",
                    "effect_preservation": "UNKNOWN",
                    "keyframe_preservation": "UNKNOWN",
                },
            },
        )

        self._captures.add(snapshot)

    def finalize(
        self,
        series: tuple[S1Series, ...],
        roundtrips: tuple[RoundTrip, ...],
        findings: tuple[str, ...] = (),
    ) -> None:
        if any(s.audit.binding != self.binding for s in series) or any(
            t.before.binding != self.binding for t in roundtrips
        ):
            raise ValueError("Mixed evidence runs forbidden")
        for relative, digest in self._written.items():
            path = safe_path(self.root, relative)
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Capture evidence missing or modified before seal")
        required = [s.audit for s in series]
        required.extend(c for s in series for p in s.pairs for c in (p.a, p.b))
        required.extend(c for t in roundtrips for c in (t.before, t.other, t.after))
        if any(c not in self._captures for c in required):
            raise ValueError("Capture evidence was not persisted by this writer")
        contexts = {s.fixture.context for s in series}
        if len(contexts) != len(series):
            raise ValueError("Duplicate S1 evidence")
        has_operator_incident = bool(list((self.root / "findings").glob("operator-*.json")))
        statuses: dict[str, str] = {}
        for number in range(1, 45):
            case = f"RV-{number:03d}"
            values = [classify_series(s, case) for s in series]
            status = RuntimeResult.UNKNOWN
            if values:
                if RuntimeResult.SUPPORTED_UNSTABLE in values or has_operator_incident:
                    status = RuntimeResult.SUPPORTED_UNSTABLE
                elif all(v == RuntimeResult.SUPPORTED_STABLE for v in values):
                    status = RuntimeResult.SUPPORTED_STABLE
                elif all(v == RuntimeResult.UNSUPPORTED for v in values):
                    status = RuntimeResult.UNSUPPORTED
            if number in (41, 42, 44):
                status = (
                    RuntimeResult.SUPPORTED_STABLE
                    if series and all(s.qualified for s in series) and not has_operator_incident
                    else RuntimeResult.UNKNOWN
                )
            if number == 43:
                status = (
                    RuntimeResult.SUPPORTED_STABLE
                    if any(s.fixture.context == Context.F1 and s.qualified for s in series)
                    else RuntimeResult.UNKNOWN
                )
            if number in (38, 39):
                f3 = [s for s in series if s.fixture.context == Context.F3]
                cases = ("RV-016", "RV-021") if number == 38 else ("RV-024", "RV-025", "RV-026")
                if f3 and all(
                    classify_series(f3[0], c) == RuntimeResult.SUPPORTED_STABLE for c in cases
                ):
                    status = RuntimeResult.SUPPORTED_STABLE
            if number == 40 and not any(
                s.fixture.context == Context.F3 and s.qualified for s in series
            ):
                status = RuntimeResult.UNKNOWN
            statuses[case] = status.value
        self.write("summary/capability-results.json", statuses)
        self.write(
            "summary/fixture-results.json",
            [
                {
                    "context": s.fixture.context,
                    "qualified": s.qualified and not has_operator_incident,
                    "audit": s.audit_result,
                    "pairs": len(s.pairs),
                }
                for s in series
            ],
        )
        switch_stable = (
            len(roundtrips) == 3
            and tuple(t.number for t in roundtrips) == (1, 2, 3)
            and all(t.accepted for t in roundtrips)
            and {Context.F4_A, Context.F4_B}.issubset(contexts)
            and all(
                any(
                    s.fixture.context == c.context
                    and s.qualified
                    and s.pairs[0].a.semantic_fields == c.semantic_fields
                    for s in series
                )
                for t in roundtrips
                for c in (t.before, t.other, t.after)
            )
            and not has_operator_incident
        )
        self.write(
            "summary/identity-results.json",
            {
                "same_project_switch_stable": switch_stable,
                "identity_scope": "UNKNOWN",
                "S3": "NOT_EXECUTED",
                "S4": "NOT_EXECUTED",
                "persistent_verified": False,
            },
        )
        self.write("findings/findings.json", findings)
        # OPEN-023: do not invent one generation spanning the independent F0-F4 projects.
        complete = False  # Cross-project aggregate approval remains OPEN-023.
        report = [
            "# TASK_020_RUNTIME_REPORT",
            "",
            "## Run identity",
            "",
            "Run: " + self.binding.validation_run_id,
            "Adapter revision: " + self.binding.profile.adapter_revision,
            "Environment: "
            + self.binding.environment_ref
            + " / generation "
            + str(self.binding.project_generation),
            "Canonical package digest: " + self.binding.package_digest,
            "RuntimeProfile: runtime_profile.json",
            "Exact runtime version: " + self.binding.profile.version_string,
            "",
            "## Installed API discovery",
            "",
            "Installed stub SHA-256: " + self.binding.profile.stub_sha256,
            "Installed documentation is candidate evidence, not runtime support.",
            "Tier B not collected; Tier C remains UNKNOWN.",
            "",
            "## F0-F4 and S1 results",
            "",
        ]
        for context in Context:
            selected = next((s for s in series if s.fixture.context == context), None)
            report.extend(["### " + context.value, "", "| Pair | Result |", "| --- | --- |"])
            for n in range(1, 11):
                pair = (
                    next((p for p in selected.pairs if p.number == n), None) if selected else None
                )
                outcome = "PASS" if pair and pair.accepted else "FAILED" if pair else "NOT_EXECUTED"
                report.append(f"| {n:02d} | {outcome} |")
            report.append("")
        report.extend(["## S2 round trips", "", "| Round | Result |", "| --- | --- |"])
        for n in range(1, 4):
            trip = next((t for t in roundtrips if t.number == n), None)
            report.append(
                f"| {n} | {'PASS' if trip and trip.accepted else 'FAILED' if trip else 'NOT_EXECUTED'} |"
            )
        report.extend(["", "## RV-001..044", "", "| Case | Runtime status |", "| --- | --- |"])
        report.extend("| " + k + " | " + v + " |" for k, v in statuses.items())
        report.extend(
            [
                "",
                "## Findings / UNKNOWN / UNSUPPORTED",
                "",
                *findings,
                "Operator interference: " + str(has_operator_incident),
                "Raw capture findings and failed pair evidence are retained under fixtures/.",
                "No retry-until-green. Missing contexts remain NOT_EXECUTED.",
                "",
                "## Identity claims / non-claims",
                "",
                "S3/S4 NOT_EXECUTED; reopen/cross-session lifetime UNKNOWN.",
                "No PERSISTENT_VERIFIED, no native track persistent identity.",
                "No mutation, destructive capability, Safety clearance or authorization derived.",
                "No production-project safety inferred. No fixture repair.",
                "",
                "## Completion gate",
                "",
                "PASS" if complete else "HOLD",
                "OPEN-023: independent-project run aggregation requires Chat review.",
                "",
            ]
        )
        self.write("summary/TASK_020_RUNTIME_REPORT.md", "\n".join(report))
        self.write(
            "run.json",
            {
                "binding": self.binding,
                "started_at": self._started,
                "completed_at": datetime.now(UTC).isoformat(),
                "state": "COMPLETE" if complete else "HOLD",
                "S3": "NOT_EXECUTED",
                "S4": "NOT_EXECUTED",
            },
        )
        paths = sorted(p for p in self.root.rglob("*") if p.is_file())
        if any(p.is_symlink() for p in self.root.rglob("*")):
            raise ValueError("Symlink evidence forbidden")
        blob = "".join(
            sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(self.root).as_posix() + "\n"
            for p in paths
        ).encode()
        with (self.root / "evidence.sha256").open("xb") as stream:
            stream.write(blob)
        self._sealed = True


def verify_evidence(root: Path) -> None:
    manifest = root / "evidence.sha256"
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        if path in entries or len(digest) != 64:
            raise ValueError("Invalid checksum manifest")
        entries[path] = digest
        target = safe_path(root, path)
        if sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("Evidence checksum mismatch")
    inventory = {
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p != manifest
    }
    if inventory != set(entries):
        raise ValueError("Missing/extra evidence")
