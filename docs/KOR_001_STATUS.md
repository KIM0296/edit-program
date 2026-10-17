# KOR-001 — Korean Lexical Candidate Producers

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. Lexical candidate
production over an already-built `TranscriptSnapshot` only. No media, no ASR,
no Resolve, no editorial decision and no edit authority.

## Purpose

The v1 dialogue scope (docs/PRODUCT_SPEC.md, "v1 dialogue scope") includes
immediate restarts, short repetitions and *conservative filler candidates*, and
excludes fully automatic filler removal. KOR-001 supplies the Korean text side
of that evidence: deterministic, versioned, text-only candidates that later
stages may show to a reviewer or combine with other evidence.

Base: `038f1cefc5c20e476e9aee50008aecf3fcfb618c` (TXE transcript contract).

Changed files:

1. `src/davinci_ai_editor/korean_text_candidates.py` (new)
2. `tests/test_korean_text_candidates.py` (new)
3. `licenses/kss-LICENSE.txt` (new, verbatim kss BSD-3 license)
4. `docs/KOR_001_STATUS.md` (this file)

No existing module, dependency or config was changed. Stdlib only.

## Producers

All producers are pure functions of `(TranscriptSnapshot, KoreanTextCandidatePolicy)`.
Only `TranscriptTokenKind.WORD` tokens are read; audio events / unknown tokens
never produce candidates and break adjacency.

- **Hangul helpers**: `is_hangul_syllable`, `decompose_syllable`,
  `compose_syllable`, `has_final_consonant` — written fresh from the Unicode
  Standard (§3.12): `S = 0xAC00 + initial*588 + medial*28 + final`.
- **Normalized key**: NFC, strip whitespace and *surrounding* punctuation
  (`. , ? ! … ~ - – — · : ;` quotes and brackets). Inner text is untouched;
  no lowercasing, no fuzzy or jamo-level matching.
- **`find_filler_lexicon_hits`** → `FillerLexiconHit(word_ref, form,
  lexicon_version, ambiguity=AMBIGUOUS, note, evidence=LEXICAL_ONLY)`. Exact key
  match only (`어떻게`, `음식`, `이제야`, `좀비` never hit). The constructor refuses
  any ambiguity other than AMBIGUOUS.
- **`find_repetition_candidates`** → `RepetitionCandidate(kind, word_refs,
  gap_frames, timing, note, evidence=LEXICAL_ONLY, ambiguity=AMBIGUOUS,
  rule_version="KOR-001-REPETITION-V1")` over immediately adjacent WORD pairs
  (same speaker when both speakers are known):
  - `EXACT_REPEAT`: equal keys (`저는 저는`, `다시 다시`).
  - `PREFIX_RESTART`: first key is a strict syllable prefix of the second
    (`그 그러니까`, `그러- 그러니까`).
  - Gap policy: both timed → `gap_frames = next.start - prev.end`; the pair is a
    candidate only if `gap_frames <= max_repetition_gap_frames +
    snapshot.timing_tolerance_frames` (transcript timings are approximate).
    Any untimed side → `gap_frames=None`, `timing=UNKNOWN`, still a candidate.
  - Legitimate reduplication (`다시 다시`, `빨리 빨리`) is never suppressed; it is a
    candidate marked AMBIGUOUS whose note says it may be emphatic
    reduplication. Single-token reduplication (`하나하나`) is one token and
    produces nothing.
- **`find_sentence_end_hints`** → `SentenceEndHint(word_ref, rule_id, ending,
  rule_version="KOR-001-SENTENCE-END-V1", evidence=TEXT_ONLY)` with rule ids
  `KSS_FAST_DA | KSS_FAST_YO | KSS_FAST_JYO | KSS_FAST_SB`. A hint is attached to
  a token whose last two characters are Hangul syllables matching a kss ending
  table, unless its trailing punctuation starts with a kss `not_endpoint`
  character or the following WORD token blocks it (kss NEXT/NEXT1 table entry,
  `not_endpoint` opener, or `unavailable_next` prefix). These are hints, never
  `PauseBoundaryKind.SENTENCE_BOUNDARY`.
- **`produce_korean_text_candidates(snapshot, policy)`** → `KoreanTextCandidates`
  bundling the three tuples with `transcript_id`, a `snapshot_fingerprint`
  (sha256 over every token field), lexicon/rule versions, the gap policy and a
  deterministic sha256 `digest` recomputed in `__post_init__`.
  `authorizes_action` is always `False` (`AUTHORIZES_ACTION = False`).

## Lexicon `KOR-FILLER-LEXICON-V1`

| Form | Ambiguity note |
| --- | --- |
| 어 | also interjection of surprise/acknowledgement |
| 어어 | also emphatic acknowledgement or alarm |
| 음 | also nominalizer -음 when attached; alone may be agreement |
| 으음 | may be considered agreement or doubt |
| 음음 | may be affirmative back-channel 'mm-hm' |
| 아 | also interjection of realization/pain; vocative particle |
| 에 | also locative particle -에 when attached; alone may be 'yes' |
| 그 | also determiner 'that' and pronoun 'he' |
| 저 | also humble pronoun 'I' and determiner 'that (over there)' |
| 저기 | also deictic 'over there' and attention-getting address |
| 뭐 | also interrogative/indefinite pronoun 'what/something' |
| 뭐랄까 | hedge that may carry the speaker's stance |
| 그니까 | colloquial 그러니까; may be a real connective 'so' |
| 그러니까 | also connective 'therefore/that is' |
| 약간 | also degree adverb 'slightly' with real meaning |
| 이제 | also temporal adverb 'now' |
| 인제 | dialect/colloquial 이제; also temporal adverb 'now' |
| 막 | also adverb 'just now / recklessly / vigorously' |
| 좀 | also adverb 'a little' and politeness softener 'please' |
| 있잖아 | also verb phrase 'there is, you know' with content |

Changing any entry requires a new lexicon version string.

## What this does NOT authorize

- No statement that a token *is* a filler, hesitation or restart.
- No `PauseBoundaryKind`, `PauseSignal`, `ContentMode`, `PauseAction`,
  confidence band, routing, Shadow Candidate or timeline mutation.
- No sentence boundary: text-derived endings are `TEXT_ONLY` hints.
- No acoustic claim: repetition gaps are approximate transcript timings,
  `LEXICAL_ONLY` evidence.
- No automatic filler removal (PRODUCT_SPEC exclusion stays in force).

## Provenance

Adapted from **kss** (Korean Sentence Splitter, BSD-3-Clause, Copyright (C)
2021 Hyunwoong Ko and Sang-Kil Park; license text in `licenses/kss-LICENSE.txt`,
attribution comment in the module). Read-only study; kss was never executed,
imported or installed.

- `kss/_modules/sentences/sentence_splitter_fast.py`: `ID` bit flags and the
  `Stats.DA`, `Stats.YO`, `Stats.JYO`, `Stats.SB` tables, copied verbatim (74 /
  38 / 47 / 39 entries; verified equal by parsing the kss source text), plus the
  SB trigger punctuation `. ! ? … ~`. The character-stream state machine was
  re-expressed at transcript-token granularity.
- `kss/_utils/const.py`: `not_endpoint` (`,` `:` U+200B, quotes/brackets, `<` `>`).
  `sf_exception` was studied but not ported: every rule requires the final two
  characters to be table-gated Hangul syllables, which already excludes all of
  its entries (tested: `3장.`, `Dr.`, `ok.`).
- `kss/_modules/sentences/sentence_splitter.py`: `unavailable_next` set.
- Not used: `kss/_modules/preprocessing/reduce_repeats.py` (soynlp-derived) and
  anything from konlpy (GPL). Hangul arithmetic is original.

Known faithful-port limitations: syllables missing from the kss tables do not
trigger (e.g. `끝났다`, `그래요` without punctuation); NEXT1 after a token
boundary is treated as blocking; end of transcript is not itself a hint.

## Validation

Interpreter: `.venv` Python 3.12.10 with `PYTHONPATH=<worktree>/src`.

```
python -m pytest -q -p no:cacheprovider --basetemp=<tmp> tests/test_korean_text_candidates.py
  27 passed
python -m pytest -q -p no:cacheprovider --basetemp=<tmp>
  2148 passed, 2 skipped
python -m ruff check src tests tools                       All checks passed!
python -m ruff format --check <new src> <new test>         2 files already formatted
python -m mypy                                             no issues (43 source files)
python -m mypy --strict --explicit-package-bases <new src> <new test>   no issues
git diff --check                                           clean
```

Tests cover jamo round-trip over all 11,172 syllables (cross-checked against
Unicode NFD), exact-only lexicon matching, punctuation stripping, homographs
staying AMBIGUOUS, exact/prefix/gap/tolerance/untimed/reduplication/speaker and
audio-event adjacency, sentence-end hints against hand-written expectations
inspired by kss tests, determinism/digest sensitivity, NFD input and the absence
of editorial fields.
