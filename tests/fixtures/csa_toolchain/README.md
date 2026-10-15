# CSA-002 synthetic toolchain fixture

This directory contains only a generated **synthetic** AAC-LC 48 kHz stereo
fixture and its GitHub-hosted Linux reference receipt.

It contains no user media, no source URL, no annotation, no Resolve state, and no
permission document.

The base64 fixture was created during the CSA-002 CI reference probe and then
frozen by SHA-256. The qualification runner decodes this fixed compressed byte
sequence twice with an exact toolchain pin and requires byte-identical PCM plus
the committed known-answer hash/counts.

The receipt pins:

- FFmpeg/ffprobe executable hashes and version/build-configuration digests;
- the eight FFmpeg core shared-library hashes used by the reference package;
- package version `7:6.1.1-3ubuntu5`;
- AAC-LC / 48,000 Hz / stereo stream facts;
- the fixed compressed fixture hash;
- expected PCM hash, byte count, sample-frame count;
- exact probe/decode argument contracts.

Scope is deliberately limited to **GitHub-hosted Ubuntu reference qualification**.
It does not qualify the user's Windows host, real acquisition, session lineage,
native Resolve identity, or G2.
