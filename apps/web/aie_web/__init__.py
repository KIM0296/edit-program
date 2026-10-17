"""AIE Free web flow (WEB-001 file round-trip + WEB-002 media upload, local ASR, trial mode).

Default: binds 127.0.0.1 and accepts only loopback Host headers. ASR
(faster-whisper, optional ``asr`` extra) runs on this machine from a locally
cached model; there is no LLM and no network call at runtime. Every generated
file is an Expected artifact; importing it into DaVinci Resolve is a manual
user step. See docs/WEB_001_STATUS.md and docs/WEB_002_STATUS.md.
"""

__all__ = ["__version__"]

__version__ = "0.2.0"
