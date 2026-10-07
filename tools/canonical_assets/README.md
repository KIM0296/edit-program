# Canonical asset generator (TASK-022)

Engineering tooling only. No Resolve API, media download, publication or production-edit entry point.

Required generation environment: Python **3.11.x**, NumPy **2.3.5**, explicitly supplied FFmpeg and
ffprobe executables. The executable versions, capability evidence fingerprint and actual executable
SHA-256 values are captured by preflight. A missing or incompatible toolchain stops generation.

From the repository root, using that Python interpreter:

```text
python -m tools.canonical_assets.generate preflight --ffmpeg <existing-ffmpeg-path> --ffprobe <existing-ffprobe-path>
python -m tools.canonical_assets.generate verify-reproducible --ffmpeg <existing-ffmpeg-path> --ffprobe <existing-ffprobe-path> --workspace <new-empty-parent/workspace> --sealed-destination <package-store/canonical-fixture-assets-1.0.0>
```

The workspace must not exist; its parent must exist. Commit generator source and dependency changes
before generation. The command captures the actual source commit, independently builds Run A and Run B,
compares all nine authoritative files, validates full media before sealing, and writes an external
comparison report and package-index candidate. It never publishes or updates repository approval.

Generation runs belong outside the Git repository. Do not add generated MOV/WAV assets to Git.
A failed build retains staging diagnostics and does not seal a package. A pending seal directory or
reservation is not silently overwritten. An existing identical sealed package is returned unchanged;
a version collision fails. The exclusive reservation coordinates this tool's writers, not hostile
external filesystem modifications.

`recipe.v1.json` records source constants, embedded glyphs and operation ordering. Source digests are
provenance only; final binary hashes and SHA256(checksums.sha256) identify a package. Package verification
rejects missing/extra files and checksum/schema changes. Sealing additionally requires actual complete
media validation with the locked toolchain; unit test synthetic byte bundles do not qualify.

Unit tests require NumPy but not FFmpeg. Full integration acceptance uses the explicit
`verify-reproducible` command and is not run by ordinary CI or editor workflows.

FFmpeg option references used during implementation:
[FFmpeg command documentation](https://ffmpeg.org/ffmpeg.html) and
[FFmpeg format documentation](https://ffmpeg.org/ffmpeg-formats.html).
The exact installed toolchain and actual output still require validation; documentation does not
establish runtime support.
