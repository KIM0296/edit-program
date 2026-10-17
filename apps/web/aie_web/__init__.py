"""WEB-001: local development web server for the Resolve Free file round-trip.

Phase 1 only: binds 127.0.0.1, no deployment, no auth, no database, no media
upload, no ASR, no LLM and no network calls. Every generated file is an
Expected artifact; importing it into DaVinci Resolve is a manual user step.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
