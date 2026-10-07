"""Explicit engineering CLI. No automatic tool installation or network publication."""

import argparse
import subprocess
from pathlib import Path

from .checksums import canonical_json
from .ffmpeg import preflight
from .model import BuildError, FailureStatus
from .package import build_package, compare_packages, package_index, seal_packages


def source_commit() -> str:
    repository = Path(__file__).resolve().parents[2]
    base = ("git", "-c", "safe.directory=" + repository.as_posix(), "-C", str(repository))

    def git(*args: str) -> str:
        result = subprocess.run(
            (*base, *args),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            shell=False,
            check=False,
            timeout=30,
        )
        if result.returncode:
            raise BuildError(
                FailureStatus.SOURCE_GENERATION_FAILURE, "Cannot establish repository revision"
            )
        return result.stdout.decode("utf-8").strip()

    if git("status", "--porcelain", "--", "tools/canonical_assets", "pyproject.toml"):
        raise BuildError(
            FailureStatus.SOURCE_GENERATION_FAILURE,
            "Commit generator source and dependency lock before generation",
        )
    return git("rev-parse", "HEAD")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preflight", "verify-reproducible"))
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--sealed-destination", type=Path)
    args = parser.parse_args()
    try:
        tool = preflight(args.ffmpeg, args.ffprobe)
        if args.operation == "preflight":
            print(
                canonical_json(
                    {
                        "status": "TOOLCHAIN_READY",
                        "python_version": tool.python_version,
                        "numpy_version": tool.numpy_version,
                        "ffmpeg_sha256": tool.ffmpeg_sha256,
                        "ffprobe_sha256": tool.ffprobe_sha256,
                    }
                ).decode(),
                end="",
            )
            return 0
        if args.workspace is None or args.sealed_destination is None:
            parser.error("verify-reproducible requires --workspace and --sealed-destination")
        workspace: Path = args.workspace
        destination: Path = args.sealed_destination
        if workspace.exists():
            raise BuildError(FailureStatus.SOURCE_GENERATION_FAILURE, "Fresh workspace required")
        commit = source_commit()
        workspace.mkdir(parents=False, exist_ok=False)
        a = build_package(workspace / "run-a", tool, commit)
        b = build_package(workspace / "run-b", tool, commit)
        comparison = compare_packages(a, b)
        result = seal_packages(a, b, destination, tool)
        (workspace / "package-index.candidate.json").write_bytes(package_index(result.destination))
        report = canonical_json(
            {
                "status": result.status.value,
                "source_commit": commit,
                "package_digest": comparison.package_digest,
                "equal_paths": list(comparison.equal_paths),
                "run_a": str(a.resolve()),
                "run_b": str(b.resolve()),
                "sealed_location": str(result.destination.resolve()),
                "resolve_validation": False,
                "chat_approval": "pending",
            }
        )
        (workspace / "comparison-report.json").write_bytes(report)
        print(report.decode(), end="")
        return 0
    except (BuildError, OSError) as error:
        status = (
            error.status.value
            if isinstance(error, BuildError)
            else FailureStatus.SOURCE_GENERATION_FAILURE.value
        )
        print(canonical_json({"status": status, "detail": str(error)}).decode(), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
