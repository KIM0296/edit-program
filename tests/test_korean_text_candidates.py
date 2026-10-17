"""KOR-001 Korean lexical candidate tests (synthetic text, no media, no ASR, no kss import)."""

import dataclasses
import unicodedata

import pytest

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.korean_text_candidates import (
    AUTHORIZES_ACTION,
    HANGUL_SYLLABLE_COUNT,
    KOREAN_FILLER_LEXICON_V1,
    REPETITION_RULE_VERSION,
    SENTENCE_END_RULE_VERSION,
    CandidateEvidence,
    FillerLexicon,
    FillerLexiconEntry,
    FillerLexiconHit,
    KoreanTextCandidatePolicy,
    KoreanTextCandidates,
    LexicalAmbiguity,
    RepetitionCandidate,
    RepetitionKind,
    RepetitionTiming,
    SentenceEndHint,
    SentenceEndRule,
    compose_syllable,
    decompose_syllable,
    find_filler_lexicon_hits,
    find_repetition_candidates,
    find_sentence_end_hints,
    has_final_consonant,
    is_hangul_syllable,
    normalize_key,
    produce_korean_text_candidates,
    split_token_text,
)
from davinci_ai_editor.temporal_mapping import SourceFrameRange
from davinci_ai_editor.transcript import (
    TranscriptSnapshot,
    TranscriptTokenKind,
    TranscriptWord,
    WordTimingStatus,
)

POLICY = KoreanTextCandidatePolicy(max_repetition_gap_frames=6)


def timed(ref: str, text: str, start: int, end: int, speaker: str | None = None) -> TranscriptWord:
    return TranscriptWord(
        ref,
        text,
        SourceFrameRange(FrameRange(start, end)),
        WordTimingStatus.ALIGNED,
        speaker_ref=speaker,
    )


def untimed(ref: str, text: str) -> TranscriptWord:
    return TranscriptWord(ref, text, None, WordTimingStatus.MISSING)


def snap(*words: TranscriptWord, tolerance: int = 0) -> TranscriptSnapshot:
    return TranscriptSnapshot("tx-1", "src-1", "producer-ev-1", tolerance, words)


def text_snap(text: str) -> TranscriptSnapshot:
    return snap(*(untimed(f"w{i}", token) for i, token in enumerate(text.split())))


def texts(snapshot: TranscriptSnapshot, refs: tuple[str, ...]) -> list[str]:
    return [snapshot.word(ref).text for ref in refs]


# --- Hangul arithmetic ------------------------------------------------------


def test_jamo_round_trip_over_full_syllable_range() -> None:
    for code in range(0xAC00, 0xAC00 + HANGUL_SYLLABLE_COUNT):
        char = chr(code)
        assert is_hangul_syllable(char)
        initial, medial, final = decompose_syllable(char)
        assert compose_syllable(initial, medial, final) == char
        # Cross-check against Unicode canonical decomposition (independent oracle).
        nfd = unicodedata.normalize("NFD", char)
        assert ord(nfd[0]) - 0x1100 == initial
        assert ord(nfd[1]) - 0x1161 == medial
        assert (ord(nfd[2]) - 0x11A7 if len(nfd) == 3 else 0) == final
    assert chr(0xAC00 + HANGUL_SYLLABLE_COUNT - 1) == "힣"


def test_hangul_boundaries_and_known_values() -> None:
    assert decompose_syllable("가") == (0, 0, 0)
    assert decompose_syllable("힣") == (18, 20, 27)
    assert compose_syllable(18, 20, 27) == "힣"
    assert decompose_syllable("한") == (18, 0, 4)
    assert has_final_consonant("한") and not has_final_consonant("하")
    for bad in ("꯿", "힤", "ㄱ", "a", "", "가나"):
        assert not is_hangul_syllable(bad)
    with pytest.raises(ValueError):
        decompose_syllable("ㄱ")
    for args in ((19, 0, 0), (0, 21, 0), (0, 0, 28), (-1, 0, 0)):
        with pytest.raises(ValueError):
            compose_syllable(*args)


# --- Normalized keys and filler lexicon ------------------------------------


def test_punctuation_stripping_is_surrounding_only() -> None:
    assert normalize_key("  음...  ") == "음"
    assert normalize_key("어,") == "어"
    assert normalize_key("“그러니까?!”") == "그러니까"
    assert normalize_key("그러-") == "그러"
    assert normalize_key("뭐~") == "뭐"
    assert normalize_key("…") == ""
    assert normalize_key("하나.하나") == "하나.하나"
    assert split_token_text('"했다."') == ('"', "했다", '."')


def test_lexicon_hits_are_exact_match_only_and_always_ambiguous() -> None:
    s = text_snap("어, 어떻게 음... 음식 그 그것 저는 이제 이제야 막 막상 좀 좀비 약간의")
    hits = find_filler_lexicon_hits(s)
    assert texts(s, tuple(h.word_ref for h in hits)) == ["어,", "음...", "그", "이제", "막", "좀"]
    assert [h.form for h in hits] == ["어", "음", "그", "이제", "막", "좀"]
    for hit in hits:
        assert hit.ambiguity is LexicalAmbiguity.AMBIGUOUS
        assert hit.evidence is CandidateEvidence.LEXICAL_ONLY
        assert hit.lexicon_version == KOREAN_FILLER_LEXICON_V1.version
        assert hit.note


def test_homographs_stay_ambiguous_with_notes() -> None:
    s = text_snap("그 사람은 저 학생이고 음 맞아요")
    hits = {h.form: h for h in find_filler_lexicon_hits(s)}
    assert "determiner" in hits["그"].note
    assert "pronoun" in hits["저"].note
    assert "nominalizer" in hits["음"].note
    assert all(h.ambiguity is LexicalAmbiguity.AMBIGUOUS for h in hits.values())


def test_lexicon_v1_contents_and_validation() -> None:
    forms = {e.form for e in KOREAN_FILLER_LEXICON_V1.entries}
    required = "어 어어 음 으음 음음 그 저 저기 뭐 뭐랄까 그니까 그러니까 약간 이제 막 아 에"
    assert set(required.split()) <= forms
    assert all(e.note for e in KOREAN_FILLER_LEXICON_V1.entries)
    with pytest.raises(ValueError):
        FillerLexiconEntry("음.", "note")
    with pytest.raises(ValueError):
        FillerLexiconEntry("음", " ")
    with pytest.raises(ValueError):
        FillerLexicon("v", (FillerLexiconEntry("음", "a"), FillerLexiconEntry("음", "b")))
    with pytest.raises(ValueError):
        FillerLexicon(" ", (FillerLexiconEntry("음", "a"),))


def test_filler_hit_cannot_claim_certainty() -> None:
    with pytest.raises(ValueError):
        FillerLexiconHit("w1", "음", "v1", LexicalAmbiguity.UNKNOWN, "note")
    with pytest.raises(ValueError):
        FillerLexiconHit(
            "w1", "음", "v1", LexicalAmbiguity.AMBIGUOUS, "note", CandidateEvidence.TEXT_ONLY
        )


def test_audio_events_never_produce_lexical_hits() -> None:
    event = TranscriptWord(
        "e1", "음", None, WordTimingStatus.MISSING, TranscriptTokenKind.AUDIO_EVENT
    )
    assert find_filler_lexicon_hits(snap(event)) == ()


def test_nfd_input_matches_after_nfc_normalization() -> None:
    nfd = unicodedata.normalize("NFD", "그러니까")
    assert nfd != "그러니까"
    s = snap(untimed("w1", nfd), untimed("w2", unicodedata.normalize("NFD", "갔어요")))
    assert [h.form for h in find_filler_lexicon_hits(s)] == ["그러니까"]
    assert [h.rule_id for h in find_sentence_end_hints(s)] == [SentenceEndRule.KSS_FAST_YO]
    assert normalize_key(nfd) == "그러니까"


# --- Repetition candidates --------------------------------------------------


def test_exact_and_prefix_repetitions() -> None:
    s = text_snap("저는 저는 그 그러니까 그러- 그러니까 학교에 갔어요")
    reps = find_repetition_candidates(s, POLICY)
    got = [(r.kind, texts(s, r.word_refs)) for r in reps]
    assert got == [
        (RepetitionKind.EXACT_REPEAT, ["저는", "저는"]),
        (RepetitionKind.PREFIX_RESTART, ["그", "그러니까"]),
        (RepetitionKind.PREFIX_RESTART, ["그러-", "그러니까"]),
    ]
    for rep in reps:
        assert rep.evidence is CandidateEvidence.LEXICAL_ONLY
        assert rep.ambiguity is LexicalAmbiguity.AMBIGUOUS
        assert rep.rule_version == REPETITION_RULE_VERSION
        assert rep.timing is RepetitionTiming.UNKNOWN and rep.gap_frames is None


def test_reverse_prefix_and_unrelated_tokens_are_not_candidates() -> None:
    s = text_snap("그러니까 그러 학교 학생 하나하나")
    assert find_repetition_candidates(s, POLICY) == ()


def test_legit_reduplication_stays_an_ambiguous_candidate() -> None:
    s = text_snap("다시 다시 빨리 빨리 하나하나")
    reps = find_repetition_candidates(s, POLICY)
    assert [texts(s, r.word_refs) for r in reps] == [["다시", "다시"], ["빨리", "빨리"]]
    assert all(r.ambiguity is LexicalAmbiguity.AMBIGUOUS for r in reps)
    assert all("reduplication" in r.note for r in reps)


def test_gap_policy_in_frames_with_transcript_tolerance() -> None:
    s = snap(timed("a", "저는", 0, 10), timed("b", "저는", 16, 26), timed("c", "저는", 40, 50))
    reps = find_repetition_candidates(s, POLICY)
    assert [(r.word_refs, r.gap_frames, r.timing) for r in reps] == [
        (("a", "b"), 6, RepetitionTiming.TIMED)
    ]
    tolerant = snap(*s.words, tolerance=8)
    assert [r.gap_frames for r in find_repetition_candidates(tolerant, POLICY)] == [6, 14]
    strict = KoreanTextCandidatePolicy(max_repetition_gap_frames=0)
    assert find_repetition_candidates(s, strict) == ()
    touching = snap(timed("a", "다시", 0, 10), timed("b", "다시", 10, 20))
    assert [r.gap_frames for r in find_repetition_candidates(touching, strict)] == [0]


def test_untimed_or_mixed_timing_keeps_candidate_with_unknown_timing() -> None:
    s = snap(timed("a", "저는", 0, 10), untimed("b", "저는"), untimed("c", "저는"))
    reps = find_repetition_candidates(s, POLICY)
    assert [(r.word_refs, r.gap_frames, r.timing) for r in reps] == [
        (("a", "b"), None, RepetitionTiming.UNKNOWN),
        (("b", "c"), None, RepetitionTiming.UNKNOWN),
    ]


def test_adjacency_broken_by_audio_event_and_speaker_change() -> None:
    event = TranscriptWord(
        "e", "[laugh]", None, WordTimingStatus.MISSING, TranscriptTokenKind.AUDIO_EVENT
    )
    s = snap(untimed("a", "저는"), event, untimed("b", "저는"))
    assert find_repetition_candidates(s, POLICY) == ()
    speakers = snap(timed("a", "네", 0, 5, "S1"), timed("b", "네", 6, 9, "S2"))
    assert find_repetition_candidates(speakers, POLICY) == ()


def test_repetition_candidate_validation() -> None:
    with pytest.raises(ValueError):
        RepetitionCandidate(RepetitionKind.UNKNOWN, ("a", "b"), None, RepetitionTiming.UNKNOWN, "n")
    with pytest.raises(ValueError):
        RepetitionCandidate(
            RepetitionKind.EXACT_REPEAT, ("a", "a"), None, RepetitionTiming.UNKNOWN, "n"
        )
    with pytest.raises(ValueError):
        RepetitionCandidate(
            RepetitionKind.EXACT_REPEAT, ("a", "b"), None, RepetitionTiming.TIMED, "n"
        )
    with pytest.raises(ValueError):
        RepetitionCandidate(
            RepetitionKind.EXACT_REPEAT, ("a", "b"), 3, RepetitionTiming.UNKNOWN, "n"
        )
    with pytest.raises(ValueError):
        RepetitionCandidate(
            RepetitionKind.EXACT_REPEAT, ("a", "b"), -1, RepetitionTiming.TIMED, "n"
        )
    with pytest.raises(ValueError):
        RepetitionCandidate(
            RepetitionKind.EXACT_REPEAT,
            ("a", "b"),
            1,
            RepetitionTiming.TIMED,
            "n",
            ambiguity=LexicalAmbiguity.UNKNOWN,
        )
    with pytest.raises(ValueError):
        KoreanTextCandidatePolicy(max_repetition_gap_frames=-1)


# --- Sentence-end hints (expectations inspired by kss tests; no kss import) --


def hint_words(text: str) -> list[tuple[str, SentenceEndRule]]:
    s = text_snap(text)
    return [(s.word(h.word_ref).text, h.rule_id) for h in find_sentence_end_hints(s)]


def test_kss_readme_style_paragraph() -> None:
    text = (
        "회사 동료 분들과 다녀왔는데 분위기도 좋고 음식도 맛있었어요 다만, 강남 토끼정이 "
        "강남 쉑쉑버거 골목길로 쭉 올라가야 하는데 다들 쉑쉑버거의 유혹에 넘어갈 뻔 "
        "했답니다 강남역 맛집 토끼정의 외부 모습."
    )
    # kss splits after 맛있었어요 and 했답니다; the final fragment is end-of-text,
    # not a table-gated ending, so no hint is attached to 모습.
    assert hint_words(text) == [
        ("맛있었어요", SentenceEndRule.KSS_FAST_YO),
        ("했답니다", SentenceEndRule.KSS_FAST_DA),
    ]


def test_da_yo_jyo_and_punctuation_rules() -> None:
    assert hint_words("밥을 먹었다 그리고 잤어요 정말 좋았죠 그래. 응") == [
        ("먹었다", SentenceEndRule.KSS_FAST_DA),
        ("잤어요", SentenceEndRule.KSS_FAST_YO),
        ("좋았죠", SentenceEndRule.KSS_FAST_JYO),
        ("그래.", SentenceEndRule.KSS_FAST_SB),
    ]


def test_preceding_syllable_gate() -> None:
    # 바다 / 끝났다: preceding syllable not in kss DA table -> no hint (faithful port).
    assert hint_words("바다 끝났다 그리고") == []
    assert hint_words("요 다") == []


def test_next_token_and_trailing_punctuation_block_hints() -> None:
    assert hint_words("갔다 하더라") == []  # NEXT1 (하) after the ending
    assert hint_words("했다 는") == []  # NEXT table entry
    assert hint_words("좋네요, 근데") == []  # not_endpoint comma
    assert hint_words('했다" 라고') == []  # closing quote is not_endpoint
    assert hint_words('했다 "그래서"') == []  # opening quote starts next token
    assert hint_words("했다 에서") == []  # unavailable_next
    assert hint_words("했다 의 의미") == []  # unavailable_next with trailing space
    assert hint_words("했다 의미") == [("했다", SentenceEndRule.KSS_FAST_DA)]
    assert hint_words("했다 도") == [("했다", SentenceEndRule.KSS_FAST_DA)]  # NEXT2 splits


def test_non_hangul_endings_and_sb_fallback() -> None:
    # kss sf_exception-style tokens never reach a rule: the gate needs two syllables.
    assert hint_words("3장. 다음") == []
    assert hint_words("Dr. 김") == []
    assert hint_words("ok. 네") == []
    # 래 is not a YO preceding syllable, so 요 falls back to the punctuation rule.
    assert hint_words("그래요? 네") == [("그래요?", SentenceEndRule.KSS_FAST_SB)]
    assert hint_words("그래요 네") == []
    assert hint_words("했어요 네") == [("했어요", SentenceEndRule.KSS_FAST_YO)]


def test_last_token_and_audio_event_followers() -> None:
    event = TranscriptWord(
        "e", "[웃음]", None, WordTimingStatus.MISSING, TranscriptTokenKind.AUDIO_EVENT
    )
    s = snap(untimed("a", "갔다"), event, untimed("b", "하더라"))
    hints = find_sentence_end_hints(s)
    assert [(h.word_ref, h.ending, h.evidence, h.rule_version) for h in hints] == [
        ("a", "갔다", CandidateEvidence.TEXT_ONLY, SENTENCE_END_RULE_VERSION)
    ]


def test_sentence_end_hint_validation() -> None:
    with pytest.raises(ValueError):
        SentenceEndHint("w", SentenceEndRule.UNKNOWN, "다")
    with pytest.raises(ValueError):
        SentenceEndHint(
            "w", SentenceEndRule.KSS_FAST_DA, "다", evidence=CandidateEvidence.LEXICAL_ONLY
        )


# --- Bundle -----------------------------------------------------------------


def test_bundle_is_deterministic_versioned_and_authorizes_nothing() -> None:
    s = snap(
        timed("a", "어", 0, 4),
        timed("b", "저는", 6, 12),
        timed("c", "저는", 14, 20),
        timed("d", "갔어요.", 22, 30),
    )
    first = produce_korean_text_candidates(s, POLICY)
    second = produce_korean_text_candidates(snap(*s.words), POLICY)
    assert first == second and first.digest == second.digest
    assert len(first.digest) == 64
    assert first.authorizes_action is False and AUTHORIZES_ACTION is False
    assert first.lexicon_version == KOREAN_FILLER_LEXICON_V1.version
    assert [h.word_ref for h in first.filler_hits] == ["a"]
    assert [r.word_refs for r in first.repetitions] == [("b", "c")]
    assert [h.word_ref for h in first.sentence_end_hints] == ["d"]

    changed = snap(*s.words[:3], timed("d", "갔어", 22, 30))
    assert produce_korean_text_candidates(changed, POLICY).digest != first.digest
    other_policy = KoreanTextCandidatePolicy(max_repetition_gap_frames=7)
    assert produce_korean_text_candidates(s, other_policy).digest != first.digest


def test_bundle_has_no_editorial_or_boundary_fields() -> None:
    names = {f.name for f in dataclasses.fields(KoreanTextCandidates)}
    forbidden = ("action", "boundary", "signal", "content_mode", "is_filler", "confidence")
    assert not any(token in name for name in names for token in forbidden)
    for cls in (FillerLexiconHit, RepetitionCandidate, SentenceEndHint):
        field_names = {f.name for f in dataclasses.fields(cls)}
        assert not any(token in n for n in field_names for token in forbidden)


def test_bundle_validates_version_consistency_and_is_frozen() -> None:
    result = produce_korean_text_candidates(text_snap("음 갔어요"), POLICY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.digest = "x"  # type: ignore[misc]
    with pytest.raises(ValueError):
        dataclasses.replace(result, lexicon_version="OTHER")
    with pytest.raises(TypeError):
        produce_korean_text_candidates("not a snapshot", POLICY)  # type: ignore[arg-type]


def test_custom_lexicon_version_flows_into_provenance() -> None:
    lexicon = FillerLexicon("TEST-LEX", (FillerLexiconEntry("흠", "test-only note"),))
    policy = KoreanTextCandidatePolicy(max_repetition_gap_frames=3, lexicon=lexicon)
    result = produce_korean_text_candidates(text_snap("흠 음"), policy)
    assert [(h.form, h.lexicon_version) for h in result.filler_hits] == [("흠", "TEST-LEX")]
    assert result.lexicon_version == "TEST-LEX"
