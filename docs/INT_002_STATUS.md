# INT-002 — Integration of LAYER-001, STUDIO-T0/T1 and WEB-001/002

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here touched DaVinci Resolve; every Studio "Resolve" is the in-repo fake
(`tests/support/fake_resolve.py`); only generated synthetic media was used.
Native HOLD and Studio runtime HOLD stand; TASK-020 is still required.

## Branch and merges

Branch `wip/integration-v2` (not pushed), from integration-preview
`d4e342867e923b5e8b7f215d201fae90bf6a3c45` (TXE, KOR, LLM, PVP-001C, HANDOFF, RT,
VER, APPLY, docs). Merged with `--no-ff`, in order:

| merged | content |
|---|---|
| `41e4e634f7ab1052154f9636c72536d8a16ccc9d` | LAYER-001 + follow-up |
| `7c7276a` | docs: EDITION_DELIVERY_STRATEGY §2a, §7 |
| `b13c571fb629f2349de1e3d9d2e5562604ca5f38` | STUDIO-T0 + STUDIO-T1 |
| `69cbbdf4432e75eb8154003f541a6b74ea1f88dd` | WEB-001 + WEB-002 |

## Conflict resolution

- No textual conflicts. `roundtrip_diff.py` merged cleanly (STUDIO-T0's additive
  `RoundTripFormat.STUDIO_API_READ` + LAYER-001's layer findings).
- Semantic drift: one failure after the merges. LAYER-001's confirmation digest
  is colour-neutral, so the T0 parity assertion "digests differ by marker colour"
  became wrong. The binding (`apply_cuts.actual_binding_digest`) also had to drop
  file `<link>` groups that the Studio read cannot carry: they are dropped **only**
  when they equal the groups the APPLY-001 writer rule derives by itself (same
  media, timeline range, source range); any other link structure stays bound
  (tested). The evidence class is also neutralized (transport, not content).
  A file-path confirmation still cannot drive the live timeline (different
  Actual digest → STALE).
- WEB: no API drift (it calls `build_apply_confirmation` / `apply_approved_cuts`
  unchanged); wording that contradicted LAYER-001 ("cut on every track") fixed.

## Changes (commits after the merges)

1. Parity reconciled with the transport-neutral digest (above).
2. Core changes requested by STUDIO-T1:
   - **Evidence class**: `ReimportedTimeline`, `RoundTripArtifactRef`,
     `RoundTripDiff`, `VerificationReport` accept `STUDIO_API_READ` (must match the
     artifact format; `evidence_domain` = `TEST_ONLY_SUPPORT`; never native, never
     live). Studio reads are labelled `STUDIO_API_READ` end to end;
     `StudioEvidence.core_label_superseded` is now False.
   - **Expected split frames**: `diff_roundtrip / diff_xmeml_roundtrip /
     diff_studio_read(..., expected_splits={track: frames})`. An in-place,
     source-contiguous split of one clip at listed frames is `NEUTRAL_SPLIT`
     (no HARD_LOCK; marker edits beyond the approval channel still lock); any
     other split stays `SPLIT`. Split lists are bound in the diff digest; unknown /
     ambiguous tracks and non-positive frames refuse. Geometry rule
     `contiguous_split_frames` is shared with `studio_razor`. VER treats a
     neutral split like any split versus the plan (EXTRA_CUT).
   - **Studio policies**: the transport and tier planner take each cut's policies
     from the confirmation (overrides only via `build_apply_confirmation(
     track_overrides=...)`; the separate `track_policies` inputs were removed).
     CUT_WITH_SOURCE and SHIFT_WITH_RIPPLE apply in place; KEEP_IN_PLACE stays
     UNSUPPORTED in place (STUDIO-T0) and is carried by tier 1/2 imports.
3. Parity re-run against LAYER-001: candidates, colour-neutral digest, per-track
   effect (cut / shifted / unchanged), applied geometry per track and VER MATCH,
   incl. a music bed (default LAYER_CONFLICT on both; override → tier 1 import and
   test-only split reach the file-path geometry; in place without split →
   UNSUPPORTED).
4. Web: per-track effect table (자름 / 당김 N프레임 / 그대로 / 보류: LAYER_CONFLICT),
   layer notes (MARKER_MOVED_TO_CUT, SYNC_SHIFT, EFFECT_SPLIT_REVIEW,
   LAYER_LOSS_RISK), predicted LINK_NOT_PRESERVED (`predicted_link_warnings`,
   messages only), per-track override form (`POST /p/{id}/policy`; changes the
   digest; earlier approval stale; cleared by a new approval upload). Invite-code
   brute-force protection (`aie_web/ratelimit.py`: per-client 5 failures then
   30 s doubling up to 1 h, global 50/10 min → 5 min lock, 429 + Retry-After; a
   guessed trial cookie counts; no lookup while locked; in memory). VAD on by
   default with a per-project checkbox (recorded in producer facts). Studio
   wording per §7. `AIE_WEB_MAX_MEDIA_MB=95` documented for the Cloudflare tunnel.

## Validation (final state)

Python 3.12.10 venv, `PYTHONPATH=<worktree>/src`.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>      2649 passed, 3 skipped
AIE_REAL_ASR=1 pytest tests/web/test_web_002.py -k real          1 passed
python -m ruff check src tests tools apps                        All checks passed
python -m ruff format --check <37 changed .py>                   already formatted
python -m mypy                                                   Success, 65 source files
MYPYPATH=src;apps/web;tests/web;tests mypy --strict ... apps/web/aie_web tests/web   Success, 18 files
MYPYPATH=... mypy --strict <changed core + studio + tests>       Success, 12 files
git diff --check                                                 clean
uvicorn on 127.0.0.1:8767: GET / 200 text/html, /studio 200, Host evil.example 400; stopped
```

## Open items

- **Chat Gate sign-off** still needed for LAYER-001's loosened RT-001 region rule
  (pass-through-explained regions not UNKNOWN), and for INT-002's binding
  canonicalization (implied link groups and evidence class not bound) and the
  `NEUTRAL_SPLIT` rule (a listed razor is not a human edit).
- **Web flow vs Human Edit Wins**: a layer the editor adds in Resolve (e.g. a music
  bed) is ADDED_BY_HUMAN → HARD_LOCK, so "함께 자르기" changes the digest but the cut
  stays HUMAN_EDIT_LOCKED. Should an explicit CUT override on a wholly human-added
  track be allowed? (policy decision; not changed).
- **J/L-cut linking**: a linked partner that is not split is written unlinked
  (LINK_NOT_PRESERVED, now shown before confirming); re-linking to the nearest
  piece is not implemented.
- **OTIO refusal cases**: the OTIO writer still refuses pass-through items, track
  state, sequence markers and `source_track` (LAYER_LOSS_RISK); raw OTIO
  preservation is not implemented.
- Web confirm page does not offer razor-assist split lists for the file path yet
  (core `expected_splits` exists).
- Brute-force limiter is per process and lost on restart; global lock also
  delays legitimate testers during an attack.
- Native: all STUDIO_T0/T1 TASK-020 items unchanged.
