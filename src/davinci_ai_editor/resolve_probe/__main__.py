"""Explicit read-only discovery/qualification CLI. Resolve activation is external."""

import argparse
import json
import platform
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

from ..probe_evidence import RuntimeProfile
from .adapter import ReadOnlyProbeAdapter, inspect_stub
from .connection import INSTALLED_SCRIPTING, connect_installed
from .fixtures import AssetBinding, FixtureInput
from .model import APPROVED_PACKAGE_DIGEST, Context, ReadProfile, RunBinding
from .runner import OperatorPreflight, QualificationRunner
from .surface import READS
from .values import canonical, freeze
from .writer import EvidenceWriter, record


def source_fingerprint() -> str:
    digest = sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def discovery(root: Path) -> int:
    root.mkdir(parents=False, exist_ok=False)
    (root / "installed_api").mkdir()
    inventory = inspect_stub(INSTALLED_SCRIPTING / "DaVinciResolveScript.pyi")
    adapter = ReadOnlyProbeAdapter(connect_installed, inventory)
    observations = adapter.discover_runtime()
    (root / "installed_api" / "api_inventory.json").write_bytes(
        canonical(
            record(
                {
                    "surface": inventory,
                    "candidates": READS,
                    "documentation": "installed Developer Scripting README.md / DaVinciResolveScript.pyi",
                    "documentation_sha256": sha256(
                        (INSTALLED_SCRIPTING / "README.md").read_bytes()
                    ).hexdigest(),
                }
            )
        )
    )
    (root / "connection-observations.raw.json").write_bytes(canonical(record(observations)))
    available = all(r.valid for r in observations) and len(observations) == 3
    (root / "run.json").write_bytes(
        canonical(
            {
                "purpose": "PREFLIGHT_DIAGNOSTIC",
                "counts_toward_s1": False,
                "runtime_available": available,
                "adapter_source_fingerprint": source_fingerprint(),
                "started_at": datetime.now(UTC).isoformat(),
                "fixture_qualification": "NOT_EXECUTED",
                "approval_or_attestation": False,
            }
        )
    )
    rows = "\n".join(f"| RV-{n:03d} | UNKNOWN |" for n in range(1, 45))
    (root / "summary").mkdir()
    report = (
        "# TASK_020_RUNTIME_REPORT\n\n"
        "Completion gate: HOLD\n\n"
        "Installed API discovery only. RuntimeProfile is not qualified.\n"
        "F0/F1/F2/F3/F4-A/F4-B S1: 0/10 pairs each.\n"
        "F4 S2: 0/3 round trips. S3/S4 NOT_EXECUTED.\n"
        "No registered fixture input or operator preflight was supplied.\n"
        "Native runtime connection available: " + str(available) + "\n\n"
        "| Case | Runtime status |\n| --- | --- |\n" + rows + "\n\n"
        "All runtime support is UNKNOWN; document presence is not support.\n"
        "No PERSISTENT_VERIFIED, native authenticity, mutation, fixture repair, or destructive support.\n"
    )
    (root / "summary" / "TASK_020_RUNTIME_REPORT.md").write_text(report, encoding="utf-8")
    blob = "".join(
        sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(root).as_posix() + "\n"
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ).encode()
    (root / "evidence.sha256").write_bytes(blob)
    print(
        canonical(
            {
                "status": "DISCOVERY_ONLY" if available else "RUNTIME_UNAVAILABLE",
                "qualification": "HOLD",
                "evidence_root": str(root),
            }
        ).decode(),
        end="",
    )
    return 0 if available else 2


def _object(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError("Configuration object required")
    return cast(dict[str, object], value)


def _string(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("Explicit nonempty string required")
    return value


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise ValueError("List required")
    return cast(list[object], value)


def qualify(config_path: Path, root: Path) -> int:
    # Configuration contains only typed bound facts, never callable/script/command fields.
    cfg = _object(json.loads(config_path.read_text(encoding="utf-8")))
    required = {
        "validation_run_id",
        "adapter_revision",
        "environment_ref",
        "registry_ref",
        "project_generation",
        "project_id",
        "library",
        "operator_session",
        "package_digest",
        "operator_preflight",
        "fixtures",
        "registration_evidence_ref",
        "currentness_evidence_ref",
    }
    if set(cfg) != required:
        raise ValueError("Missing/extra qualification configuration fields")
    inventory = inspect_stub(INSTALLED_SCRIPTING / "DaVinciResolveScript.pyi")
    adapter = ReadOnlyProbeAdapter(connect_installed, inventory)
    discovery_reads = adapter.discover_runtime()
    if len(discovery_reads) != 3 or not all(r.valid for r in discovery_reads):
        raise ValueError(
            "Runtime discovery is not typed/current; use discover to retain diagnostics"
        )
    native_version = discovery_reads[1].raw
    assert native_version is not None
    version = tuple(cast(int | str, v.scalar) for v in native_version.children)
    product = _string(discovery_reads[0].raw.scalar if discovery_reads[0].raw else None)
    version_string = _string(discovery_reads[2].raw.scalar if discovery_reads[2].raw else None)
    revision = _string(cfg["adapter_revision"])
    if revision != source_fingerprint():
        raise ValueError("Adapter source revision mismatch; use discovery fingerprint")
    profile = ReadProfile(
        RuntimeProfile(
            ".".join(str(v) for v in version[:3]),
            str(version[3]),
            platform.system(),
            "task020-read-only",
            "v1",
            "read-only-v1",
            "task020-v1",
            "v1",
            "not-produced",
            "ADR-033/038-v1",
        ),
        product,
        version,
        version_string,
        platform.machine(),
        revision,
        inventory.stub_sha256,
    )
    generation = cfg["project_generation"]
    if type(generation) is not int:
        raise ValueError("Exact generation integer required")
    binding = RunBinding(
        _string(cfg["validation_run_id"]),
        profile,
        _string(cfg["environment_ref"]),
        _string(cfg["registry_ref"]),
        generation,
        _string(cfg["project_id"]),
        freeze(cfg["library"]),
        _string(cfg["operator_session"]),
        _string(cfg["package_digest"]),
    )
    if binding.package_digest != APPROVED_PACKAGE_DIGEST:
        raise ValueError("Wrong package")
    operator_dict = _object(cfg["operator_preflight"])
    operator_keys = tuple(OperatorPreflight.__dataclass_fields__)
    if set(operator_dict) != set(operator_keys) or any(
        type(v) is not bool for v in operator_dict.values()
    ):
        raise ValueError("Complete typed operator checklist required")
    operator = OperatorPreflight(**cast(dict[str, bool], operator_dict))
    fixtures = []
    for raw in _list(cfg["fixtures"]):
        row = _object(raw)
        expected = {
            "context",
            "timeline_id",
            "fixture_instance",
            "assets",
            "coordinate_evidence_ref",
            "required_project_settings",
            "include_optional_audio",
            "item_marker_host_id",
        }
        if set(row) != expected:
            raise ValueError("Exact fixture input schema required")
        assets = []
        for raw_asset in _list(row["assets"]):
            asset = _object(raw_asset)
            if set(asset) != {
                "asset_role",
                "media_unique_id",
                "asset_sha256",
                "package_digest",
                "evidence_ref",
            }:
                raise ValueError("Explicit asset provenance required")
            assets.append(AssetBinding(**{k: _string(v) for k, v in asset.items()}))
        coordinate = row["coordinate_evidence_ref"]
        host = row["item_marker_host_id"]
        variant = row["include_optional_audio"]
        if type(variant) is not bool:
            raise ValueError("Explicit optional-audio variant")
        fixtures.append(
            FixtureInput(
                Context(_string(row["context"])),
                _string(row["timeline_id"]),
                _string(row["fixture_instance"]),
                tuple(assets),
                _string(coordinate) if coordinate is not None else None,
                tuple((k, freeze(v)) for k, v in _object(row["required_project_settings"]).items()),
                variant,
                _string(host) if host is not None else None,
            )
        )
    contexts = {f.context for f in fixtures}
    if (
        not fixtures
        or len(contexts) != len(fixtures)
        or (len(contexts) > 1 and contexts != {Context.F4_A, Context.F4_B})
    ):
        raise ValueError("One project generation per run; only F4 has two contexts")
    writer = EvidenceWriter(root, binding)
    writer.write("installed_api/api_inventory.json", {"surface": inventory, "candidates": READS})
    writer.write("installed_api/discovery.raw.json", discovery_reads)
    writer.write(
        "environment/currentness_preflight.json",
        {
            "registration_evidence_ref": _string(cfg["registration_evidence_ref"]),
            "currentness_evidence_ref": _string(cfg["currentness_evidence_ref"]),
            "not_native_attestation": True,
        },
    )
    runner = QualificationRunner(adapter, binding, operator, writer)
    findings = []
    try:
        for fixture in fixtures:
            input(
                "Externally select the exact registered "
                + fixture.context.value
                + " timeline; no editing. Press Enter to begin 10 uninterrupted pairs: "
            )
            runner.s1(fixture, binding)
        if contexts == {Context.F4_A, Context.F4_B} and all(s.qualified for s in runner.series):
            for number in range(1, 4):
                for stage, context in (
                    ("A-before", Context.F4_A),
                    ("B", Context.F4_B),
                    ("A-after", Context.F4_A),
                ):
                    action = input(
                        f"S2 {number} {stage}: switch externally to registered {context.value}; enter operator action evidence ref: "
                    )
                    runner.s2_capture(
                        number,
                        stage,
                        next(f for f in fixtures if f.context == context),
                        binding,
                        action,
                    )
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 - retain aborted run evidence
        findings.append(type(error).__name__ + ": " + str(error))
        writer.write(
            "findings/run-aborted.json", {"error": findings[-1], "qualification": "ABORTED"}
        )
    writer.finalize(runner.series, runner.roundtrips, tuple(findings))
    print(
        canonical(
            {
                "status": "EVIDENCE_SEALED",
                "overall_task_gate": "HOLD",
                "scope_results": [s.qualified for s in runner.series],
                "OPEN-023": "cross-project report grouping unresolved",
            }
        ).decode(),
        end="",
    )
    return 0 if runner.series and all(s.qualified for s in runner.series) and not findings else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("discover", "qualify"))
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--configuration", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "discover":
            return discovery(args.evidence_root)
        if args.configuration is None:
            parser.error("qualify requires explicit bound configuration")
        return qualify(args.configuration, args.evidence_root)
    except (OSError, ValueError) as error:
        print(
            canonical(
                {"status": "HOLD", "error": type(error).__name__ + ": " + str(error)}
            ).decode(),
            end="",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
