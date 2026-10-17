# Edition Delivery Strategy — Free (web) vs Studio (in-Resolve)

Status: **PRODUCT DIRECTION (user decision 2026-10-17)**. Builds on ADR-041
(edition/transport split), ADR-042 (cross-edition semantic parity) and ADR-043
(same conversational interface). Changes no gate.

## 1. Roles

| Edition | Role | Transport | User experience |
|---|---|---|---|
| **Resolve Free** | **Persuasion**: demonstrate every core outcome so the editor trusts the product | Web service + file round-trip (FCP7 XML default, OTIO secondary, SRT) | Upload in a browser, approve and edit inside Resolve, import the result. No local install. |
| **Resolve Studio** | **Production**: the detailed, advanced product | In-Resolve script (Workspace > Scripts; later a Workflow Integration panel) using the Resolve scripting API | Everything happens inside Resolve. No web and no separate app after a one-time script install. |

Resolve 21.1 moved Python scripting to Studio, and built-in transcription is
Studio-only (see COMPETITIVE_LANDSCAPE_2026_10.md). A Free in-app path is
therefore not planned.

## 2. Parity rule (what "same result" means)

One shared core (pure, dependency-free modules) serves both editions. For the
**core feature set** below, the same inputs must produce the same semantic
result in both editions:

- the same candidates (pause/long breath, filler and repetition candidates,
  rough-cut proposal validation);
- the same approval semantics (marker selection ≠ approval; explicit
  confirmation bound to a digest; Human Edit Wins; HARD_LOCK on human edits);
- the same applied edit (approved cuts on video and audio at identical frames,
  ripple, untouched locked regions);
- the same verification vocabulary (MATCH / MISMATCH / UNVERIFIED; UNKNOWN
  never becomes MATCH).

Parity tests: a shared fixture runs through the file transport and the
(fake, later native) Studio transport and must yield identical candidate sets,
confirmation digests over the same approved cut set, and identical applied
cut geometry.

## 2a. Layer preservation precondition (user decision 2026-10-17)

Applies to both editions and every feature. Tracks (layers) are never merged
or flattened before the final render; each layer is edited on its own.

- Approved cuts apply only to tracks whose items at the cut come from the
  candidate's source media (dialogue and its linked A/V): CUT_WITH_SOURCE.
- Every other layer (B-roll, titles, graphics, SFX) is not cut; items after the
  cut shift by the removed duration (SHIFT_WITH_RIPPLE), or stay in place if
  the user chooses (KEEP_IN_PLACE, with a sync warning).
- An item that spans a cut on a non-cut layer (music bed, long title) is never
  split automatically; that cut is skipped as LAYER_CONFLICT until the user
  sets that layer to cut.
- Track count, order, names, kinds and lock state are preserved; empty tracks
  remain.
- Free file path: items the core does not model are preserved verbatim and
  only re-timed; if anything would be lost, no file is emitted
  (LAYER_LOSS_RISK). Resolve-only grades/Fusion may still not survive FCP7 XML
  (format limit, UNVERIFIED).
- Studio: per-track in-place edits on the current timeline; never rebuild the
  timeline. Per-track ripple capability in the Resolve API is being verified.
- Verification checks every layer (cut / shifted by the expected delta /
  unchanged); a lost layer item is MISMATCH.

## 3. Studio is a superset: detail and depth

Studio must reach the same core results and then go further. Planned
Studio-only depth (each still behind native qualification gates):

| Area | Free (web) | Studio (in-Resolve) |
|---|---|---|
| Applying cuts | new timeline file to import; grades/effects/mixes on the old timeline do not carry over | applied to the **current** timeline in place; grades, effects, mixes, bins preserved |
| Human-edit awareness | from an exported XML at the moment of upload | read live from the timeline at every run; continuous re-runs without export |
| Verification | file round-trip evidence (FILE_ROUNDTRIP) | native post-edit read-back (Expected ≠ Actual on the native timeline) |
| Approval UI | marker rename in Resolve, confirmation in the browser | marker rename plus a confirmation dialog inside Resolve |
| Precision | Whisper word timings on the server clock (tolerance ≥ 1 frame) | frame-exact native item boundaries, linked-item and track-state awareness |
| Scope | one timeline per round-trip | multiple timelines, per-track policies, protected ranges from native state |
| Transcription | server ASR | Resolve built-in transcription where usable (granularity to verify), or server ASR |
| Rendering | none; final render in Deliver | none; final render in Deliver |

## 4. What Free must show (persuasion checklist)

Every core outcome must be visible in the Free path, with its limits stated
honestly in the UI:

1. candidates as Resolve markers with reasons;
2. marker-based approval inside Resolve;
3. a confirmation summary (cut count, seconds removed, skipped items and why);
4. an edited timeline (video + audio, ripple, linked A/V) ready to import, with
   no intermediate rendering;
5. human-edit protection on re-run;
6. a verification report after re-export;
7. an explicit "in Studio this happens in place, without files" note at each
   step where Studio differs (Section 3).

## 5. Delivery order

1. **WEB-001**: Free web service, local development server first (no deploy):
   upload → candidate XML → approval XML upload → confirmation → applied XML,
   verification report. Transcript JSON upload first; server ASR later.
2. **STUDIO-T0**: Studio transport designed on the same core, tested against a
   fake Resolve (no native access), with parity tests (Section 2).
3. After Free validates value with design partners: Studio license, TASK-020
   native qualification, lift native mutation HOLD via the existing gates,
   then ship the in-Resolve Studio path.

## 7. Decisions (user, 2026-10-17, later the same day)

- **Studio-only product.** The commercial product is Studio-only; customers are
  expected to buy DaVinci Resolve Studio. This supersedes the handoff principle
  "the product must not require a Studio purchase". Free remains only as a
  persuasion demo.
- **Free = founder-led demo (option B).** No public service, accounts or
  long-term storage now. Demos run on the founder's machine or as a short
  external trial: time-limited invite codes (72 h from first use, up to 5
  projects, videos up to 10 min), consent notice, automatic deletion of all
  data at code expiry, HTTPS via a temporary tunnel or a temporary cloud VM
  deleted after the trial. Revisit hosted trials (option C) when demand exceeds
  about 10 trial requests per month.
- **Engineering focus.** Studio path first: STUDIO-T1 tiered apply on the fake,
  then a Studio license and TASK-020 native qualification, then the existing
  gates to lift native mutation HOLD, then Studio distribution (script install
  and product licensing).
- **Studio apply tiers.** (1) before grading: build and import a new version
  timeline inside Resolve, confirm only; (2) after grading: same plus grade and
  Fusion transfer where the API supports it (to verify); (3) cuts on item
  boundaries: in-place DeleteClips; (4) fallback razor assist. The Resolve API
  has no documented split-at-frame call (STUDIO-T0).
- **Customer-safe claim until native verification:** "confirm only" is promised
  for tier 1 (before grading) only.

## 6. Open decisions before a public web service

ASR hosting (self-hosted GPU faster-whisper recommended vs external API),
hosting provider, customer media retention (e.g. delete originals after 24 h),
and a server-side real-media gate replacing the local-only G2 definition.
