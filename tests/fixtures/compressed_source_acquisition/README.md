# CSA-001 synthetic fixtures only

This directory contains **TEST_ONLY_SUPPORT** contracts for the first bounded
compressed-source acquisition implementation.

No real M4A/MP4/MOV/MP3 source, decoded PCM, source URL, permission record,
annotation, or private filesystem path belongs here.

The implementation under review:

- accepts only the initial profile **M4A/MP4/MOV family + AAC-LC + 48,000 Hz + 1–2 channels**;
- keeps channel order and uses an explicit 0-based selected channel;
- forbids resampling, downmix, normalization, AGC correction, filters and random-seek acquisition;
- models full-stream decode to headerless signed PCM16LE interleaved bytes;
- requires explicit source, stream, toolchain, conversion-policy and sample-origin evidence;
- retains exact sample-frame and byte-count accounting;
- requires a second independent extraction receipt and byte-identical comparison;
- produces public receipts containing pseudonymous refs, digests and bounded numeric counts only.

profile.schema.json is a documentation schema for the fixed TEST_ONLY_SUPPORT
profile surface. known_answer_manifest.json contains synthetic vector metadata
only; the listed hashes are not evidence about an installed FFmpeg build.

The module does **not**:

- run ffmpeg or ffprobe;
- read or write media;
- access Resolve;
- authenticate ownership, human identity, session independence or recording origin;
- qualify any real source;
- authorize G2;
- promote a decoder/configuration into production.

Actual toolchain qualification requires separately pinned binaries/libraries plus
known-answer executions. Real acquisition remains HOLD until that later Chat Gate.
