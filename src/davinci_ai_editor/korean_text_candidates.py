"""KOR-001 Korean lexical candidates over a TranscriptSnapshot; never edits or meaning.

Three pure, deterministic producers read only transcript token text (and, for
repetition gaps, the producer's approximate word timings):

* filler lexicon hits: exact normalized-key matches against a versioned in-repo
  lexicon. Every hit is AMBIGUOUS: each form is also an ordinary word
  (determiner, pronoun, adverb, particle, interjection...).
* repetition candidates: immediately adjacent EXACT_REPEAT / PREFIX_RESTART pairs.
  Legitimate reduplication ("다시 다시") stays a candidate marked AMBIGUOUS.
* sentence-end hints: text-only ending heuristics adapted from kss (BSD-3).

Outputs are lexical CANDIDATES with rule/lexicon version provenance. Nothing here
states that a token "is" a filler, emits PauseBoundaryKind / PauseSignal /
ContentMode, a SENTENCE_BOUNDARY, a PauseAction or any edit authority.
"""

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from itertools import pairwise
from types import MappingProxyType
from typing import Final

from .transcript import TranscriptSnapshot, TranscriptTokenKind, TranscriptWord

AUTHORIZES_ACTION: Final = False
REPETITION_RULE_VERSION: Final = "KOR-001-REPETITION-V1"
SENTENCE_END_RULE_VERSION: Final = "KOR-001-SENTENCE-END-V1"

# ---------------------------------------------------------------------------
# Hangul syllable arithmetic (fresh, from the Unicode Standard ch. 3.12)
# ---------------------------------------------------------------------------

HANGUL_SYLLABLE_BASE: Final = 0xAC00
HANGUL_INITIAL_COUNT: Final = 19
HANGUL_MEDIAL_COUNT: Final = 21
HANGUL_FINAL_COUNT: Final = 28  # index 0 = no final consonant
HANGUL_MEDIAL_FINAL_COUNT: Final = HANGUL_MEDIAL_COUNT * HANGUL_FINAL_COUNT  # 588
HANGUL_SYLLABLE_COUNT: Final = HANGUL_INITIAL_COUNT * HANGUL_MEDIAL_FINAL_COUNT  # 11172


def is_hangul_syllable(char: str) -> bool:
    """True for one precomposed syllable in U+AC00..U+D7A3."""
    if not isinstance(char, str) or len(char) != 1:
        return False
    return 0 <= ord(char) - HANGUL_SYLLABLE_BASE < HANGUL_SYLLABLE_COUNT


def decompose_syllable(char: str) -> tuple[int, int, int]:
    """Return (initial, medial, final) indices; final 0 means no final consonant."""
    if not is_hangul_syllable(char):
        raise ValueError("Precomposed Hangul syllable required")
    offset = ord(char) - HANGUL_SYLLABLE_BASE
    initial, rest = divmod(offset, HANGUL_MEDIAL_FINAL_COUNT)
    medial, final = divmod(rest, HANGUL_FINAL_COUNT)
    return initial, medial, final


def compose_syllable(initial: int, medial: int, final: int = 0) -> str:
    """Inverse of decompose_syllable; indices are range-checked."""
    for value, limit in (
        (initial, HANGUL_INITIAL_COUNT),
        (medial, HANGUL_MEDIAL_COUNT),
        (final, HANGUL_FINAL_COUNT),
    ):
        if type(value) is not int or not 0 <= value < limit:
            raise ValueError("Jamo index out of range")
    return chr(
        HANGUL_SYLLABLE_BASE
        + initial * HANGUL_MEDIAL_FINAL_COUNT
        + medial * HANGUL_FINAL_COUNT
        + final
    )


def has_final_consonant(char: str) -> bool:
    return decompose_syllable(char)[2] != 0


# ---------------------------------------------------------------------------
# Normalized lexical keys
# ---------------------------------------------------------------------------

# Surrounding punctuation stripped from a token to form its lexical key. Inner
# characters are never touched; there is no fuzzy or jamo-level matching.
SURROUNDING_PUNCTUATION: Final = frozenset(".,?!…~-–—·:;\"'“”‘’()[]{}<>「」『』《》〈〉")


def split_token_text(text: str) -> tuple[str, str, str]:
    """Split NFC text into (leading punctuation, core, trailing punctuation)."""
    value = unicodedata.normalize("NFC", text).strip()
    start, end = 0, len(value)
    while start < end and value[start] in SURROUNDING_PUNCTUATION:
        start += 1
    while end > start and value[end - 1] in SURROUNDING_PUNCTUATION:
        end -= 1
    return value[:start], value[start:end], value[end:]


def normalize_key(text: str) -> str:
    """NFC + strip whitespace and surrounding punctuation; may return ''."""
    return split_token_text(text)[1]


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class LexicalAmbiguity(str, Enum):
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class CandidateEvidence(str, Enum):
    LEXICAL_ONLY = "LEXICAL_ONLY"
    TEXT_ONLY = "TEXT_ONLY"
    UNKNOWN = "UNKNOWN"


class RepetitionKind(str, Enum):
    EXACT_REPEAT = "EXACT_REPEAT"
    PREFIX_RESTART = "PREFIX_RESTART"
    UNKNOWN = "UNKNOWN"


class RepetitionTiming(str, Enum):
    TIMED = "TIMED"
    UNKNOWN = "UNKNOWN"


class SentenceEndRule(str, Enum):
    KSS_FAST_DA = "KSS_FAST_DA"
    KSS_FAST_YO = "KSS_FAST_YO"
    KSS_FAST_JYO = "KSS_FAST_JYO"
    KSS_FAST_SB = "KSS_FAST_SB"
    UNKNOWN = "UNKNOWN"


def _nonblank(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value


# ---------------------------------------------------------------------------
# Filler lexicon
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FillerLexiconEntry:
    form: str
    note: str

    def __post_init__(self) -> None:
        form = _nonblank(self.form, "Nonblank lexicon form required")
        _nonblank(self.note, "Every lexicon entry needs an ambiguity note")
        if normalize_key(form) != form or unicodedata.normalize("NFC", form) != form:
            raise ValueError("Lexicon form must already be an NFC normalized key")


@dataclass(frozen=True)
class FillerLexicon:
    version: str
    entries: tuple[FillerLexiconEntry, ...]
    _index: Mapping[str, FillerLexiconEntry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _nonblank(self.version, "Explicit lexicon version required")
        entries = tuple(self.entries)
        if not entries or any(not isinstance(e, FillerLexiconEntry) for e in entries):
            raise TypeError("Nonempty typed lexicon entries required")
        forms = [entry.form for entry in entries]
        if len(set(forms)) != len(forms):
            raise ValueError("Duplicate lexicon form")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "_index", MappingProxyType({e.form: e for e in entries}))

    def lookup(self, key: str) -> FillerLexiconEntry | None:
        return self._index.get(key)


KOREAN_FILLER_LEXICON_V1: Final = FillerLexicon(
    "KOR-FILLER-LEXICON-V1",
    (
        FillerLexiconEntry("어", "also interjection of surprise/acknowledgement"),
        FillerLexiconEntry("어어", "also emphatic acknowledgement or alarm"),
        FillerLexiconEntry("음", "also nominalizer -음 when attached; alone may be agreement"),
        FillerLexiconEntry("으음", "may be considered agreement or doubt"),
        FillerLexiconEntry("음음", "may be affirmative back-channel 'mm-hm'"),
        FillerLexiconEntry("아", "also interjection of realization/pain; vocative particle"),
        FillerLexiconEntry("에", "also locative particle -에 when attached; alone may be 'yes'"),
        FillerLexiconEntry("그", "also determiner 'that' and pronoun 'he'"),
        FillerLexiconEntry("저", "also humble pronoun 'I' and determiner 'that (over there)'"),
        FillerLexiconEntry("저기", "also deictic 'over there' and attention-getting address"),
        FillerLexiconEntry("뭐", "also interrogative/indefinite pronoun 'what/something'"),
        FillerLexiconEntry("뭐랄까", "hedge that may carry the speaker's stance"),
        FillerLexiconEntry("그니까", "colloquial 그러니까; may be a real connective 'so'"),
        FillerLexiconEntry("그러니까", "also connective 'therefore/that is'"),
        FillerLexiconEntry("약간", "also degree adverb 'slightly' with real meaning"),
        FillerLexiconEntry("이제", "also temporal adverb 'now'"),
        FillerLexiconEntry("인제", "dialect/colloquial 이제; also temporal adverb 'now'"),
        FillerLexiconEntry("막", "also adverb 'just now / recklessly / vigorously'"),
        FillerLexiconEntry("좀", "also adverb 'a little' and politeness softener 'please'"),
        FillerLexiconEntry("있잖아", "also verb phrase 'there is, you know' with content"),
    ),
)


@dataclass(frozen=True)
class FillerLexiconHit:
    """A token whose normalized key equals a lexicon form; NOT a filler verdict."""

    word_ref: str
    form: str
    lexicon_version: str
    ambiguity: LexicalAmbiguity
    note: str
    evidence: CandidateEvidence = CandidateEvidence.LEXICAL_ONLY

    def __post_init__(self) -> None:
        _nonblank(self.word_ref, "Explicit word reference required")
        _nonblank(self.form, "Matched form required")
        _nonblank(self.lexicon_version, "Lexicon version provenance required")
        _nonblank(self.note, "Ambiguity note required")
        if self.ambiguity is not LexicalAmbiguity.AMBIGUOUS:
            raise ValueError("Filler lexicon hits are always AMBIGUOUS")
        if self.evidence is not CandidateEvidence.LEXICAL_ONLY:
            raise ValueError("Filler lexicon hits are LEXICAL_ONLY evidence")


def _is_word(token: TranscriptWord) -> bool:
    return token.kind is TranscriptTokenKind.WORD


def find_filler_lexicon_hits(
    snapshot: TranscriptSnapshot, lexicon: FillerLexicon = KOREAN_FILLER_LEXICON_V1
) -> tuple[FillerLexiconHit, ...]:
    if not isinstance(snapshot, TranscriptSnapshot) or not isinstance(lexicon, FillerLexicon):
        raise TypeError("Typed snapshot and lexicon required")
    hits: list[FillerLexiconHit] = []
    for token in snapshot.words:
        if not _is_word(token):
            continue
        entry = lexicon.lookup(normalize_key(token.text))
        if entry is not None:
            hits.append(
                FillerLexiconHit(
                    token.word_ref,
                    entry.form,
                    lexicon.version,
                    LexicalAmbiguity.AMBIGUOUS,
                    entry.note,
                )
            )
    return tuple(hits)


# ---------------------------------------------------------------------------
# Repetition candidates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KoreanTextCandidatePolicy:
    """``max_repetition_gap_frames`` bounds the frame gap between a timed pair.

    The snapshot's timing tolerance is added before comparing, because transcript
    boundaries are approximate; untimed pairs are kept with timing UNKNOWN.
    """

    max_repetition_gap_frames: int
    lexicon: FillerLexicon = KOREAN_FILLER_LEXICON_V1

    def __post_init__(self) -> None:
        gap = self.max_repetition_gap_frames
        if type(gap) is not int or gap < 0:
            raise ValueError("Nonnegative integer max repetition gap required")
        if not isinstance(self.lexicon, FillerLexicon):
            raise TypeError("Typed filler lexicon required")


@dataclass(frozen=True)
class RepetitionCandidate:
    kind: RepetitionKind
    word_refs: tuple[str, str]
    gap_frames: int | None
    timing: RepetitionTiming
    note: str
    evidence: CandidateEvidence = CandidateEvidence.LEXICAL_ONLY
    ambiguity: LexicalAmbiguity = LexicalAmbiguity.AMBIGUOUS
    rule_version: str = REPETITION_RULE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RepetitionKind) or self.kind is RepetitionKind.UNKNOWN:
            raise ValueError("Concrete repetition kind required")
        refs = tuple(self.word_refs)
        if len(refs) != 2 or refs[0] == refs[1]:
            raise ValueError("Exactly two distinct word references required")
        for ref in refs:
            _nonblank(ref, "Explicit word reference required")
        object.__setattr__(self, "word_refs", refs)
        if not isinstance(self.timing, RepetitionTiming):
            raise TypeError("Typed repetition timing required")
        if self.gap_frames is None:
            if self.timing is not RepetitionTiming.UNKNOWN:
                raise ValueError("Missing gap requires UNKNOWN timing")
        elif type(self.gap_frames) is not int or self.gap_frames < 0:
            raise ValueError("Gap must be nonnegative integer frames or None")
        elif self.timing is not RepetitionTiming.TIMED:
            raise ValueError("A measured gap requires TIMED timing")
        _nonblank(self.note, "Repetition note required")
        if self.evidence is not CandidateEvidence.LEXICAL_ONLY:
            raise ValueError("Repetition candidates are LEXICAL_ONLY evidence")
        if self.ambiguity is not LexicalAmbiguity.AMBIGUOUS:
            raise ValueError("Repetition candidates are always AMBIGUOUS")
        _nonblank(self.rule_version, "Rule version provenance required")


_EXACT_NOTE: Final = (
    "adjacent identical tokens; may be a restart or legitimate emphatic reduplication"
)
_PREFIX_NOTE: Final = (
    "first token is a syllable prefix of the next; may be a cut-off restart or two words"
)


def _gap(first: TranscriptWord, second: TranscriptWord) -> int | None:
    if first.source_range is None or second.source_range is None:
        return None
    return second.source_range.frames.start - first.source_range.frames.end


def find_repetition_candidates(
    snapshot: TranscriptSnapshot, policy: KoreanTextCandidatePolicy
) -> tuple[RepetitionCandidate, ...]:
    if not isinstance(snapshot, TranscriptSnapshot):
        raise TypeError("Typed snapshot required")
    if not isinstance(policy, KoreanTextCandidatePolicy):
        raise TypeError("Typed policy required")
    limit = policy.max_repetition_gap_frames + snapshot.timing_tolerance_frames
    out: list[RepetitionCandidate] = []
    words = snapshot.words
    for first, second in pairwise(words):
        if not (_is_word(first) and _is_word(second)):
            continue  # an intervening audio event / unknown token breaks adjacency
        if (
            first.speaker_ref is not None
            and second.speaker_ref is not None
            and first.speaker_ref != second.speaker_ref
        ):
            continue
        a, b = normalize_key(first.text), normalize_key(second.text)
        if not a or not b:
            continue
        if a == b:
            kind, note = RepetitionKind.EXACT_REPEAT, _EXACT_NOTE
        elif len(a) < len(b) and b.startswith(a):
            kind, note = RepetitionKind.PREFIX_RESTART, _PREFIX_NOTE
        else:
            continue
        gap = _gap(first, second)
        if gap is not None and gap > limit:
            continue
        timing = RepetitionTiming.UNKNOWN if gap is None else RepetitionTiming.TIMED
        out.append(RepetitionCandidate(kind, (first.word_ref, second.word_ref), gap, timing, note))
    return tuple(out)


# ---------------------------------------------------------------------------
# Sentence-end hints
#
# Adapted from kss (Korean Sentence Splitter), BSD-3-Clause,
# Copyright (C) 2021 Hyunwoong Ko and Sang-Kil Park; see
# licenses/kss-LICENSE.txt. Ported, at transcript-token granularity:
#   * kss/_modules/sentences/sentence_splitter_fast.py: the ID bit flags and the
#     Stats.DA / Stats.YO / Stats.JYO / Stats.SB preceding/next syllable tables
#     (copied verbatim below) and the "." "!" "?" "…" "~" SB trigger set;
#   * kss/_utils/const.py: not_endpoint (",", ":", quotes/brackets, "<", ">").
#     sf_exception (abbreviations, digit + 항/조/...) is NOT ported: every rule
#     here requires the final two characters to be Hangul syllables gated by the
#     tables, which already excludes all sf_exception entries;
#   * kss/_modules/sentences/sentence_splitter.py: the unavailable_next set.
# kss splits a character stream; here a hint is attached to the token whose
# final syllable triggers an ending and whose following token does not block it.
# ---------------------------------------------------------------------------

_PREV: Final = 1 << 0
_NEXT: Final = 1 << 2
_NEXT1: Final = 1 << 3
_NEXT2: Final = 1 << 4


def _table(spec: str) -> Mapping[str, int]:
    """Parse 'syllable:FLAGS' pairs, flags P=PREV N=NEXT 1=NEXT1 2=NEXT2."""
    bits = {"P": _PREV, "N": _NEXT, "1": _NEXT1, "2": _NEXT2}
    table: dict[str, int] = {}
    for item in spec.split():
        key, flags = item.split(":")
        table[key] = sum(bits[f] for f in flags)
    return MappingProxyType(table)


_DA_TABLE: Final = _table(
    "갔:P 간:P 겠:P 겼:P 같:P 놨:P 녔:P 니:P 논:P 낸:P 냈:P 뒀:P 때:P 랐:P 럽:P 렵:P "
    "렸:P 뤘:P 린:P 몄:P 밌:P 볐:P 볍:P 봤:P 섰:P 샜:P 셨:P 싼:P 싸:P 않:P 았:P 없:P "
    "었:P 였:P 온:P 웠:P 이:P 인:P 있:P 진:P 졌:P 쳤:P 췄:P 챘:P 켰:P 켠:P 캔:P 팠:P "
    "펐:P 폈:P 했:P 혔:P 한:N 가:N 고:N2 는:N2 라:N 시:N 던:N 든:N 지:2 를:N 운:N "
    "만:N 며:N2 면:N12 서:P2 싶:PN 죠:N 죵:N 쥬:N 하:1 해:1 도:2"
)
_YO_TABLE: Final = _table(
    "겨:P 거:P 구:P 군:P 걸:P 까:P 께:P 껴:P 네:P 나:P 니:P 데:P 든:P 려:P 서:P 세:P "
    "아:P 어:P 워:P 에:P 예:P 을:P 져:P 줘:P 지:P 춰:P 해:P 먼:P 만:P 고:2 는:N 라:1 "
    "를:N 즘:N 소:N 며:2 면:P2 하:1"
)
_JYO_TABLE: Final = _table(
    "거:P 가:P 갔:P 겠:P 같:P 놨:P 녔:P 냈:P 니:P 뒀:P 르:P 랐:P 럽:P 렵:P 렸:P 맞:P "
    "몄:P 밌:P 볐:P 볍:P 봤:P 서:P 섰:P 셨:P 샜:P 았:P 않:P 없:P 었:P 였:P 이:P 졌:P "
    "쳤:P 챘:P 켰:P 팠:P 폈:P 펐:P 하:P 했:P 혔:P 고:P2 는:N 라:1 를:N 며:2 면:P2"
)
_SB_TABLE: Final = _table(
    "것:P 거:P 가:P 까:P 걸:P 껄:P 나:P 니:P 네:P 다:P 도:P 쎄:P 래:P 데:P 지:P 든:P "
    "덩:P 등:P 랴:P 마:P 봐:P 서:P 셈:P 아:P 어:P 오:P 요:P 용:P 을:P 자:P 죠:P 쥬:P "
    "죵:P 고:P2 는:N 라:PN 며:2 면:2 하:1"
)

_SB_PUNCTUATION: Final = frozenset(".!?…~")
# kss const.not_endpoint: comma, colon, zero-width space, quotes/brackets, < >.
_NOT_ENDPOINT: Final = frozenset(",:\u200b\"'“”‘’`″()[]{}<>「」『』《》〈〉")
# kss sentence_splitter.unavailable_next (trailing-space items match a whole token).
_UNAVAILABLE_NEXT: Final = (
    ("시피", "거나", "의 ")
    + tuple("에" + s for s in ("서", "선", "는", "도 "))
    + tuple("라" + s for s in ("서", "는", "도 ", "던", "지만", "고", "건", "거나", "며", "면서"))
    + tuple(
        "하" + s for s in ("여서", "여도", "였", "고는 ", "고서 ", "곤 ", "다는", "는데.", "며")
    )
    + ("할텐데",)
)


@dataclass(frozen=True)
class SentenceEndHint:
    """Text-only hint that a token may end a sentence; never SENTENCE_BOUNDARY."""

    word_ref: str
    rule_id: SentenceEndRule
    ending: str
    rule_version: str = SENTENCE_END_RULE_VERSION
    evidence: CandidateEvidence = CandidateEvidence.TEXT_ONLY

    def __post_init__(self) -> None:
        _nonblank(self.word_ref, "Explicit word reference required")
        if not isinstance(self.rule_id, SentenceEndRule) or self.rule_id is SentenceEndRule.UNKNOWN:
            raise ValueError("Concrete sentence-end rule required")
        _nonblank(self.ending, "Matched ending required")
        _nonblank(self.rule_version, "Rule version provenance required")
        if self.evidence is not CandidateEvidence.TEXT_ONLY:
            raise ValueError("Sentence-end hints are TEXT_ONLY evidence")


def _ending_rule(core: str, trail: str) -> tuple[SentenceEndRule, Mapping[str, int]] | None:
    if len(core) < 2:
        return None
    last, prev = core[-1], core[-2]
    if not (is_hangul_syllable(last) and is_hangul_syllable(prev)):
        return None
    if last == "다" and _DA_TABLE.get(prev, 0) & _PREV:
        return SentenceEndRule.KSS_FAST_DA, _DA_TABLE
    if last == "요" and _YO_TABLE.get(prev, 0) & _PREV:
        return SentenceEndRule.KSS_FAST_YO, _YO_TABLE
    if last in ("죠", "죵") and _JYO_TABLE.get(prev, 0) & _PREV:
        return SentenceEndRule.KSS_FAST_JYO, _JYO_TABLE
    if trail[:1] in _SB_PUNCTUATION and _SB_TABLE.get(last, 0) & _PREV:
        return SentenceEndRule.KSS_FAST_SB, _SB_TABLE
    return None


def _next_blocks(table: Mapping[str, int], token: TranscriptWord | None) -> bool:
    if token is None:
        return False
    raw = unicodedata.normalize("NFC", token.text).strip()
    if raw[:1] in _NOT_ENDPOINT:
        return True
    core = normalize_key(raw)
    if not core:
        return False
    if table.get(core[0], 0) & (_NEXT | _NEXT1):
        return True
    for item in _UNAVAILABLE_NEXT:
        if item.endswith(" "):
            if core == item.rstrip():
                return True
        elif core.startswith(item):
            return True
    return False


def find_sentence_end_hints(snapshot: TranscriptSnapshot) -> tuple[SentenceEndHint, ...]:
    if not isinstance(snapshot, TranscriptSnapshot):
        raise TypeError("Typed snapshot required")
    hints: list[SentenceEndHint] = []
    words = snapshot.words
    for index, token in enumerate(words):
        if not _is_word(token):
            continue
        _, core, trail = split_token_text(token.text)
        if not core or trail[:1] in _NOT_ENDPOINT:
            continue
        matched = _ending_rule(core, trail)
        if matched is None:
            continue
        rule, table = matched
        following = words[index + 1] if index + 1 < len(words) else None
        if following is not None and not _is_word(following):
            following = None
        if _next_blocks(table, following):
            continue
        ending = core[-2:] + (trail[:1] if rule is SentenceEndRule.KSS_FAST_SB else "")
        hints.append(SentenceEndHint(token.word_ref, rule, ending))
    return tuple(hints)


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_fingerprint(snapshot: TranscriptSnapshot) -> str:
    """Content digest of every token field the producers can observe."""
    return _digest(
        [
            snapshot.transcript_id,
            snapshot.source_ref,
            snapshot.producer_ref,
            snapshot.timing_tolerance_frames,
            [
                [
                    w.word_ref,
                    w.text,
                    None
                    if w.source_range is None
                    else [w.source_range.frames.start, w.source_range.frames.end],
                    w.timing_status.value,
                    w.kind.value,
                    w.speaker_ref,
                ]
                for w in snapshot.words
            ],
        ]
    )


@dataclass(frozen=True)
class KoreanTextCandidates:
    """Lexical candidates for one transcript snapshot; authorizes nothing."""

    transcript_id: str
    snapshot_fingerprint: str
    lexicon_version: str
    repetition_rule_version: str
    sentence_end_rule_version: str
    max_repetition_gap_frames: int
    filler_hits: tuple[FillerLexiconHit, ...]
    repetitions: tuple[RepetitionCandidate, ...]
    sentence_end_hints: tuple[SentenceEndHint, ...]
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        for value, message in (
            (self.transcript_id, "Explicit transcript ID required"),
            (self.snapshot_fingerprint, "Snapshot fingerprint required"),
            (self.lexicon_version, "Lexicon version required"),
            (self.repetition_rule_version, "Repetition rule version required"),
            (self.sentence_end_rule_version, "Sentence-end rule version required"),
        ):
            _nonblank(value, message)
        if type(self.max_repetition_gap_frames) is not int or self.max_repetition_gap_frames < 0:
            raise ValueError("Nonnegative integer max repetition gap required")
        for name, kind in (
            ("filler_hits", FillerLexiconHit),
            ("repetitions", RepetitionCandidate),
            ("sentence_end_hints", SentenceEndHint),
        ):
            items = tuple(getattr(self, name))
            if any(not isinstance(item, kind) for item in items):
                raise TypeError(f"Typed {name} required")
            object.__setattr__(self, name, items)
        if any(h.lexicon_version != self.lexicon_version for h in self.filler_hits):
            raise ValueError("Filler hit lexicon version mismatch")
        if any(r.rule_version != self.repetition_rule_version for r in self.repetitions):
            raise ValueError("Repetition rule version mismatch")
        if any(h.rule_version != self.sentence_end_rule_version for h in self.sentence_end_hints):
            raise ValueError("Sentence-end rule version mismatch")
        object.__setattr__(self, "digest", _digest(self._payload()))

    @property
    def authorizes_action(self) -> bool:
        return AUTHORIZES_ACTION

    def _payload(self) -> object:
        return {
            "transcript_id": self.transcript_id,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "lexicon_version": self.lexicon_version,
            "repetition_rule_version": self.repetition_rule_version,
            "sentence_end_rule_version": self.sentence_end_rule_version,
            "max_repetition_gap_frames": self.max_repetition_gap_frames,
            "filler_hits": [
                [h.word_ref, h.form, h.lexicon_version, h.ambiguity.value, h.note, h.evidence.value]
                for h in self.filler_hits
            ],
            "repetitions": [
                [
                    r.kind.value,
                    list(r.word_refs),
                    r.gap_frames,
                    r.timing.value,
                    r.note,
                    r.evidence.value,
                    r.ambiguity.value,
                    r.rule_version,
                ]
                for r in self.repetitions
            ],
            "sentence_end_hints": [
                [h.word_ref, h.rule_id.value, h.ending, h.rule_version, h.evidence.value]
                for h in self.sentence_end_hints
            ],
        }


def produce_korean_text_candidates(
    snapshot: TranscriptSnapshot, policy: KoreanTextCandidatePolicy
) -> KoreanTextCandidates:
    """Pure, deterministic bundle of the three lexical candidate lists."""
    if not isinstance(snapshot, TranscriptSnapshot):
        raise TypeError("Typed snapshot required")
    if not isinstance(policy, KoreanTextCandidatePolicy):
        raise TypeError("Typed policy required")
    return KoreanTextCandidates(
        transcript_id=snapshot.transcript_id,
        snapshot_fingerprint=snapshot_fingerprint(snapshot),
        lexicon_version=policy.lexicon.version,
        repetition_rule_version=REPETITION_RULE_VERSION,
        sentence_end_rule_version=SENTENCE_END_RULE_VERSION,
        max_repetition_gap_frames=policy.max_repetition_gap_frames,
        filler_hits=find_filler_lexicon_hits(snapshot, policy.lexicon),
        repetitions=find_repetition_candidates(snapshot, policy),
        sentence_end_hints=find_sentence_end_hints(snapshot),
    )
