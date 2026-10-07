import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path

import pytest

from davinci_ai_editor import probe_evidence as p
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.execution_ir import EffectModelStatus as M
from davinci_ai_editor.execution_ir import NativeCapabilityStatus as C
from davinci_ai_editor.native_snapshot import IdentityScope

PROFILE = p.RuntimeProfile(
    "Resolve", "build", "Windows", "adapter", "1", "invoke-v1", "observe-v1", "v1", "v1", "v1"
)
BEFORE = p.SubjectState(
    "placement", p.SubjectKind.PLACEMENT, FrameRange(100, 200), FrameRange(0, 100), "media", "track"
)
AFTER = replace(BEFORE, timeline_range=FrameRange(80, 180))
SCOPE = p.ProbeObservationScope(
    "scope", ("placement",), tuple(p.SubjectKind), p.ScopeCompleteness.COMPLETE
)
DOMAIN = p.ApplicabilityDomain(
    "domain",
    "v1",
    ("declared-condition",),
    tuple(p.ChallengeDeclaration(c, True) for c in p.ChallengeClass),
)


def run(
    n, fixture_class, primitive=p.ProbePrimitive.TRANSLATE_PLACEMENT, challenge=None, domain=DOMAIN
):
    ref = f"run-{n}"
    binding = p.EvidenceBinding(PROFILE, (ref,))
    fixture = p.ProbeFixture(
        f"fixture-{fixture_class.value}",
        "1",
        fixture_class,
        "disposable-project",
        "registry-record",
        True,
        True,
        False,
        (BEFORE,),
    )
    if primitive == p.ProbePrimitive.TRANSLATE_PLACEMENT:
        invocation = p.NativeInvocationSpec(
            primitive, "invoke-v1", ("placement",), delta_frames=-20
        )
        after = AFTER
    else:
        invocation = p.NativeInvocationSpec(
            primitive, "invoke-v1", ("placement",), removed_range=FrameRange(180, 200)
        )
        after = replace(BEFORE, timeline_range=FrameRange(100, 180), source_range=FrameRange(0, 80))
    hypothesis = p.ProbeHypothesis((p.ObservedChange("placement", BEFORE, after),))
    case = p.ProbeCase(
        f"case-{fixture_class.value}", domain, fixture, "1", invocation, hypothesis, challenge
    )
    effect = p.NativeEffectEvidence(
        f"evidence-{n}", PROFILE, f"pre-{n}", f"post-{n}", (BEFORE,), (after,), SCOPE, "harness-1"
    )
    post = p.PostReadEvidence(
        f"read-{n}", binding, p.PostReadStatus.VERIFIED, True, SCOPE, ("read-proof",)
    )
    recon = p.ReconciliationEvidence(
        f"recon-{n}",
        binding,
        p.ReconciliationStatus.VERIFIED,
        (after,),
        (BEFORE,),
        (),
        post.evidence_ref,
        ("recon-proof",),
    )
    correspondence = p.IdentityCorrespondence(
        "placement",
        "pre-locator",
        "post-locator",
        p.IdentityBoundary.CROSS_SESSION,
        True,
        "correspondence",
    )
    identity = p.IdentityCapabilityEvidence(
        f"identity-{n}", binding, IdentityScope.PERSISTENT_VERIFIED, None, (correspondence,)
    )
    return p.ProbeRunResult(
        ref,
        f"clean-instance-{n}",
        case,
        p.ProbeRunStatus.PASS_OBSERVED,
        effect,
        post,
        recon,
        identity,
        native_success=True,
    )


def inputs(primitive=p.ProbePrimitive.TRANSLATE_PLACEMENT, domain=DOMAIN):
    policy = p.CapabilityVerificationPolicy(primitive)
    runs = []
    for c in policy.positive_classes:
        for _ in range(5):
            runs.append(run(len(runs), c, primitive, domain=domain))
    for declaration in domain.challenges:
        if declaration.applicable:
            for _ in range(3):
                runs.append(
                    run(len(runs), policy.positive_classes[0], primitive, declaration.kind, domain)
                )
    return p.ProbeDerivationInput(
        "model", p.ProbeCorpus(domain, PROFILE, primitive, tuple(runs)), policy, PROFILE, "session"
    )


def change_first(v, **changes):
    return replace(
        v, corpus=replace(v.corpus, runs=(replace(v.corpus.runs[0], **changes), *v.corpus.runs[1:]))
    )


def derive(v=None):
    return p.derive_capability(inputs() if v is None else v)


@pytest.mark.parametrize(
    "primitive,classes,count",
    [
        (p.ProbePrimitive.TRANSLATE_PLACEMENT, 4, 20),
        (p.ProbePrimitive.REMOVE_RANGE, 6, 30),
        (p.ProbePrimitive.COMPOUND_RIPPLE, 10, 50),
    ],
)
def test_exact_budget(primitive, classes, count):
    v = inputs(primitive)
    assert len(v.policy.positive_classes) == classes
    assert v.policy.minimum_positive_runs == count
    assert v.policy.runs_per_positive_class == 5
    assert v.policy.runs_per_challenge_class == 3
    assert (
        v.policy.allowed_conflicts
        == v.policy.allowed_side_effects
        == v.policy.allowed_containment_failures
        == v.policy.allowed_ambiguous_targets
        == 0
    )
    assert derive(v).model_status == M.VERIFIED
    assert derive(v).capability_status == C.SUPPORTED_VERIFIED
    assert derive(v).positive_count == count
    assert derive(v).challenge_count == 15
    assert len(v.corpus.runs) == count + 15


def test_axis_enums_are_independent_and_typed():
    assert {s.value for s in p.ScopeCompleteness} == {"COMPLETE", "PARTIAL", "UNKNOWN"}
    assert {s.value for s in p.ReconciliationStatus} == {
        "VERIFIED",
        "AMBIGUOUS",
        "UNVERIFIED",
        "STALE",
    }
    assert {s.value for s in p.FragmentEvidenceStatus} == {
        "VERIFIED",
        "AMBIGUOUS",
        "UNSUPPORTED",
        "UNKNOWN",
    }
    r = inputs().corpus.runs[0]
    with pytest.raises(TypeError):
        replace(r.reconciliation, status=M.VERIFIED)
    with pytest.raises(TypeError):
        replace(r.post_read, status=M.VERIFIED)
    with pytest.raises(TypeError):
        p.FragmentCorrespondenceEvidence("fragment", r.identity.binding, M.VERIFIED, ())


@pytest.mark.parametrize(
    "field,value",
    [("production", True), ("disposable", False), ("isolated", False), ("registry_ref", None)],
)
def test_invalid_fixture_nonqualifying(field, value):
    v = inputs()
    r = v.corpus.runs[0]
    v = change_first(v, case=replace(r.case, fixture=replace(r.case.fixture, **{field: value})))
    assert derive(v).model_status != M.VERIFIED
    assert not derive(v).runs[0].qualified


@pytest.mark.parametrize(
    "mode", ["dirty", "version", "reused-instance", "reused-run", "reused-evidence"]
)
def test_clean_independent_fixture_required(mode):
    v = inputs()
    r = v.corpus.runs[0]
    if mode == "dirty":
        v = change_first(v, effect=replace(r.effect, before=(replace(BEFORE, media_ref="dirty"),)))
    if mode == "version":
        v = change_first(v, case=replace(r.case, fixture_version="different"))
    if mode.startswith("reused"):
        second = v.corpus.runs[1]
        field = {
            "reused-instance": "instance_ref",
            "reused-run": "run_ref",
            "reused-evidence": "effect",
        }[mode]
        with pytest.raises(ValueError):
            replace(
                v.corpus, runs=(replace(r, **{field: getattr(second, field)}), *v.corpus.runs[1:])
            )
        return
    assert derive(v).model_status != M.VERIFIED


@pytest.mark.parametrize(
    "field",
    [
        "resolve_version",
        "resolve_build",
        "platform",
        "adapter_version",
        "invocation_contract",
        "observation_contract",
        "evidence_contract",
        "model_contract",
        "verification_policy_version",
    ],
)
def test_exact_profile_stale(field):
    v = inputs()
    assert (
        derive(replace(v, current_profile=replace(PROFILE, **{field: "changed"}))).model_status
        == M.STALE
    )


def test_mixed_profile_evidence_is_stale():
    v = inputs()
    r = v.corpus.runs[0]
    v = change_first(
        v, effect=replace(r.effect, profile=replace(PROFILE, adapter_version="different"))
    )
    assert derive(v).model_status == M.STALE


@pytest.mark.parametrize("completeness", [p.ScopeCompleteness.PARTIAL, p.ScopeCompleteness.UNKNOWN])
def test_incomplete_scope_blocks_even_with_extra_passes(completeness):
    v = inputs()
    r = v.corpus.runs[0]
    v = change_first(v, effect=replace(r.effect, scope=replace(SCOPE, completeness=completeness)))
    assert derive(v).model_status != M.VERIFIED


@pytest.mark.parametrize("size", [0, 1, 19])
def test_not_a_pass_rate(size):
    v = inputs()
    v = replace(v, corpus=replace(v.corpus, runs=v.corpus.runs[:size]))
    assert derive(v).model_status == (M.UNKNOWN if size == 0 else M.UNVERIFIED)
    assert derive(v).capability_status != C.SUPPORTED_VERIFIED


@pytest.mark.parametrize(
    "mode", ["positive-class", "challenge-class", "one-challenge-run", "extra-wrong-class"]
)
def test_coverage_not_just_total_count(mode):
    v = inputs()
    runs = list(v.corpus.runs)
    if mode == "positive-class":
        runs = [
            r
            for r in runs
            if r.case.challenge is not None
            or r.case.fixture.fixture_class != v.policy.positive_classes[-1]
        ]
    if mode == "challenge-class":
        runs = [r for r in runs if r.case.challenge != p.ChallengeClass.LINKED_AV]
    if mode == "one-challenge-run":
        runs.pop()
    if mode == "extra-wrong-class":
        runs.pop(0)
        runs.append(run(100, v.policy.positive_classes[1]))
    assert derive(replace(v, corpus=replace(v.corpus, runs=runs))).model_status == M.UNVERIFIED


def test_policy_explicit_cannot_weaken():
    with pytest.raises(TypeError):
        replace(inputs(), policy=None)
    with pytest.raises(TypeError):
        p.CapabilityVerificationPolicy(
            p.ProbePrimitive.TRANSLATE_PLACEMENT, runs_per_positive_class=1
        )
    v = inputs()
    assert derive(replace(v, policy=replace(v.policy, version="future"))).model_status != M.VERIFIED


def test_conflict_preserved_no_majority_recency_or_filtering():
    v = inputs()
    r = v.corpus.runs[0]
    extra = p.SubjectState("subtitle", p.SubjectKind.SUBTITLE, FrameRange(100, 110))
    effect = replace(
        r.effect,
        before=(BEFORE, extra),
        after=(AFTER, replace(extra, timeline_range=FrameRange(80, 90))),
        scope=replace(SCOPE, subject_refs=("placement", "subtitle")),
    )
    fixture = replace(r.case.fixture, canonical_state=effect.before)
    bad = replace(
        r,
        case=replace(r.case, fixture=fixture),
        effect=effect,
        status=p.ProbeRunStatus.FAIL_OBSERVED,
    )
    runs = (
        bad,
        *v.corpus.runs[1:],
        *(run(100 + i, v.policy.positive_classes[0]) for i in range(10)),
    )
    value = replace(v, corpus=replace(v.corpus, runs=runs))
    out = derive(value)
    assert out.model_status == M.CONFLICTING
    assert out.capability_status != C.SUPPORTED_VERIFIED
    assert len(out.inputs.corpus.runs[0].effect.observed_effects) == 2
    assert out == derive(replace(value, corpus=replace(value.corpus, runs=tuple(reversed(runs)))))
    assert r.case.hypothesis.effects != effect.observed_effects


def test_outside_domain_challenge_retained_unsupported_not_model_conflict():
    domain = replace(
        DOMAIN,
        challenges=tuple(
            replace(d, applicable=False) if d.kind == p.ChallengeClass.LINKED_AV else d
            for d in DOMAIN.challenges
        ),
    )
    v = inputs(domain=domain)
    r = run(999, v.policy.positive_classes[0], challenge=p.ChallengeClass.LINKED_AV, domain=domain)
    r = replace(
        r,
        effect=replace(r.effect, after=(replace(AFTER, timeline_range=FrameRange(70, 170)),)),
        status=p.ProbeRunStatus.FAIL_OBSERVED,
    )
    value = replace(v, corpus=v.corpus.append(r))
    out = derive(value)
    assert out.model_status == M.VERIFIED
    assert out.outside_domain_run_refs == (r.run_ref,)
    assert out.outside_domain_status == C.UNSUPPORTED


def test_domain_cannot_be_silently_narrowed_after_run():
    v = inputs()
    narrower = replace(DOMAIN, conditions=("narrower",))
    out = derive(replace(v, corpus=replace(v.corpus, domain=narrower)))
    assert out.model_status != M.VERIFIED
    assert any(p.QualificationReason.DOMAIN_MISMATCH in r.reasons for r in out.runs)


@pytest.mark.parametrize("field", ["containment_failure", "ambiguous_target"])
def test_zero_tolerance(field):
    v = change_first(inputs(), **{field: True})
    assert derive(v).model_status != M.VERIFIED


@pytest.mark.parametrize(
    "status",
    [
        p.ProbeRunStatus.FAIL_OBSERVED,
        p.ProbeRunStatus.INCONCLUSIVE,
        p.ProbeRunStatus.STALE,
        p.ProbeRunStatus.INVALID_FIXTURE,
        p.ProbeRunStatus.CONTAINMENT_FAILURE,
    ],
)
def test_run_failure_never_counts_as_pass(status):
    assert derive(change_first(inputs(), status=status)).model_status != M.VERIFIED


def test_api_success_alone_insufficient_and_availability():
    v = inputs()
    assert derive(change_first(v, effect=None, native_success=True)).model_status != M.VERIFIED
    empty = replace(v, corpus=replace(v.corpus, runs=()))
    assert derive(empty).capability_status == C.UNKNOWN
    for available, expected in [(True, C.SUPPORTED_UNVERIFIED), (False, C.UNSUPPORTED)]:
        a = p.AvailabilityEvidence("api", PROFILE, available, "surface-evidence")
        assert derive(replace(empty, availability=a)).capability_status == expected
    assert (
        derive(
            replace(v, availability=p.AvailabilityEvidence("api", PROFILE, False, "unavailable"))
        ).capability_status
        != C.SUPPORTED_VERIFIED
    )


@pytest.mark.parametrize(
    "mode",
    ["missing", "unverified", "not-independent", "partial", "missing-proof", "wrong-binding"],
)
def test_post_read_independent(mode):
    v = inputs()
    post = v.corpus.runs[0].post_read
    if mode == "missing":
        post = None
    if mode == "unverified":
        post = replace(post, status=p.PostReadStatus.UNVERIFIED)
    if mode == "not-independent":
        post = replace(post, independent=False)
    if mode == "partial":
        post = replace(post, scope=replace(SCOPE, completeness=p.ScopeCompleteness.PARTIAL))
    if mode == "missing-proof":
        post = replace(post, evidence_refs=())
    if mode == "wrong-binding":
        post = replace(post, binding=replace(post.binding, support_run_refs=("wrong-run",)))
    assert derive(change_first(v, post_read=post)).capability_status != C.SUPPORTED_VERIFIED


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "ambiguous",
        "unverified",
        "same-signatures",
        "wrong-signatures",
        "ambiguous-signatures",
        "wrong-read",
        "stale",
    ],
)
def test_reconciliation_axis(mode):
    v = inputs()
    r = v.corpus.runs[0].reconciliation
    if mode == "missing":
        r = None
    if mode == "ambiguous":
        r = replace(r, status=p.ReconciliationStatus.AMBIGUOUS)
    if mode == "unverified":
        r = replace(r, status=p.ReconciliationStatus.UNVERIFIED)
    if mode == "same-signatures":
        r = replace(r, applied_signature=r.not_applied_signature)
    if mode == "wrong-signatures":
        r = replace(r, applied_signature=(BEFORE,))
    if mode == "ambiguous-signatures":
        r = replace(r, ambiguous_signatures=("ambiguous",))
    if mode == "wrong-read":
        r = replace(r, post_read_ref="another")
    if mode == "stale":
        r = replace(r, status=p.ReconciliationStatus.STALE)
    assert derive(change_first(v, reconciliation=r)).capability_status != C.SUPPORTED_VERIFIED


@pytest.mark.parametrize("scope", [IdentityScope.UNKNOWN, IdentityScope.SNAPSHOT_LOCAL])
def test_weak_identity_not_execution_grade(scope):
    v = inputs()
    identity = replace(v.corpus.runs[0].identity, claimed_scope=scope)
    assert derive(change_first(v, identity=identity)).model_status != M.VERIFIED


def test_uuid_not_persistent_proof_and_session_staleness():
    v = inputs()
    identity = v.corpus.runs[0].identity
    uuid = "8bc665a4-12c8-4e2f-a114-434159772ceb"
    same = replace(
        identity.correspondences[0],
        pre_locator_ref=uuid,
        post_locator_ref=uuid,
        boundary=p.IdentityBoundary.SAME_SESSION,
    )
    assert (
        derive(change_first(v, identity=replace(identity, correspondences=(same,)))).model_status
        != M.VERIFIED
    )
    session = replace(
        identity,
        claimed_scope=IdentityScope.SESSION_LOCAL_VERIFIED,
        session_ref="session",
        correspondences=(same,),
    )
    assert derive(change_first(v, identity=session)).model_status == M.VERIFIED
    assert (
        derive(replace(change_first(v, identity=session), current_session="new")).model_status
        == M.STALE
    )
    assert (
        derive(change_first(v, identity=replace(session, session_ref=None))).model_status
        != M.VERIFIED
    )
    # Persistent cross-boundary evidence reuses profile qualification across sessions.
    assert derive(replace(v, current_session="new")).model_status == M.VERIFIED


@pytest.mark.parametrize("status", list(p.FragmentEvidenceStatus))
def test_fragment_status_independent(status):
    v = inputs()
    r = v.corpus.runs[0]
    link = p.FragmentCorrespondence(
        "placement", "fragment", "fragment-proof", p.FragmentBindingMethod.EXPLICIT_CORRESPONDENCE
    )
    fragment = p.FragmentCorrespondenceEvidence("fragments", r.identity.binding, status, (link,))
    case = replace(r.case, invocation=replace(r.case.invocation, produces_fragments=True))
    out = derive(change_first(v, case=case, fragment=fragment))
    assert (out.model_status == M.VERIFIED) == (status == p.FragmentEvidenceStatus.VERIFIED)


@pytest.mark.parametrize(
    "method",
    [
        p.FragmentBindingMethod.RETURNED_ORDER,
        p.FragmentBindingMethod.FILENAME,
        p.FragmentBindingMethod.POSITION,
    ],
)
def test_fragment_heuristics_not_proof(method):
    v = inputs()
    r = v.corpus.runs[0]
    fragment = p.FragmentCorrespondenceEvidence(
        "fragments",
        r.identity.binding,
        p.FragmentEvidenceStatus.VERIFIED,
        (p.FragmentCorrespondence("placement", "fragment", "proof", method),),
    )
    case = replace(r.case, invocation=replace(r.case.invocation, produces_fragments=True))
    assert derive(change_first(v, case=case, fragment=fragment)).model_status != M.VERIFIED


def test_immutable_copy_append_and_deterministic_result():
    v = inputs()
    before = deepcopy(v)
    raw = list(v.corpus.runs)
    corpus = replace(v.corpus, runs=raw)
    raw.clear()
    assert len(corpus.runs) == 35

    def frozen(value):
        if is_dataclass(value):
            f = fields(value)[0]
            with pytest.raises(FrozenInstanceError):
                setattr(value, f.name, getattr(value, f.name))
            for f in fields(value):
                frozen(getattr(value, f.name))
        elif isinstance(value, tuple):
            for item in value:
                frozen(item)

    frozen(derive(v))
    assert derive(v) == derive(v)
    assert v == before
    appended = corpus.append(run(999, v.policy.positive_classes[0]))
    assert len(corpus.runs) == 35 and len(appended.runs) == 36
    assert v.policy.production_editor_manual_probe_work == 0
    assert v.policy.full_suite_per_edit is False


def test_missing_provenance_rejected():
    with pytest.raises(ValueError):
        replace(PROFILE, adapter_version="")
    v = inputs()
    r = v.corpus.runs[0]
    with pytest.raises(ValueError):
        replace(r.effect, harness_version="")


def test_no_runtime_or_upstream_calls(monkeypatch):
    v = inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected call")

    from davinci_ai_editor import (
        authority,
        execution_ir,
        expected_diff,
        native_snapshot,
        transaction,
    )
    from davinci_ai_editor.fake_timeline import FakeTimeline

    for module, name in [
        (execution_ir, "validate_execution_ir"),
        (transaction, "transition"),
        (expected_diff, "verify_diff"),
        (authority, "transition"),
        (native_snapshot, "evaluate_readiness"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(FakeTimeline, "apply", forbidden)
    assert derive(v).model_status == M.VERIFIED
    tree = ast.parse(Path(p.__file__).read_text(encoding="utf-8-sig"))
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))
    assert {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} <= {
        "dataclasses",
        "enum",
        "typing",
        "collections",
        "domain",
        "execution_ir",
        "native_snapshot",
    }


@pytest.mark.parametrize("primitive", list(p.ProbePrimitive))
def test_one_missing_positive_with_all_challenges_never_qualifies(primitive):
    v = inputs(primitive)
    runs = list(v.corpus.runs)
    missing = next(r for r in runs if r.case.challenge is None)
    runs.remove(missing)
    assert derive(replace(v, corpus=replace(v.corpus, runs=runs))).model_status == M.UNVERIFIED


@pytest.mark.parametrize("field", ["pre_snapshot_ref", "post_snapshot_ref"])
def test_duplicate_capture_cannot_inflate_repetitions(field):
    v = inputs()
    r = v.corpus.runs[0]
    other = v.corpus.runs[1]
    with pytest.raises(ValueError):
        change_first(v, effect=replace(r.effect, **{field: getattr(other.effect, field)}))


def test_challenges_cannot_substitute_for_positive_budget():
    v = inputs()
    challenge_runs = tuple(r for r in v.corpus.runs if r.case.challenge is not None)
    out = derive(replace(v, corpus=replace(v.corpus, runs=challenge_runs)))
    assert out.positive_count == 0
    assert out.challenge_count == 15
    assert out.model_status == M.UNVERIFIED


@pytest.mark.parametrize("status", list(p.EvidenceStatus))
def test_raw_evidence_status_cannot_be_discarded(status):
    v = inputs()
    r = v.corpus.runs[0]
    out = derive(change_first(v, effect=replace(r.effect, status=status)))
    assert (out.model_status == M.VERIFIED) == (status == p.EvidenceStatus.VALID)
    if status == p.EvidenceStatus.CONFLICTING:
        assert out.model_status == M.CONFLICTING
    if status == p.EvidenceStatus.STALE:
        assert out.model_status == M.STALE


@pytest.mark.parametrize("kind", list(p.SubjectKind))
def test_observed_collateral_changes_never_filtered(kind):
    extra = p.SubjectState("collateral", kind, structure_ref="before")
    after = replace(extra, structure_ref="after")
    changes = p.observed_changes((BEFORE, extra), (AFTER, after))
    assert p.ObservedChange("collateral", extra, after) in changes
    assert len(changes) == 2


def test_observed_addition_and_deletion_not_lost():
    extra = p.SubjectState("new", p.SubjectKind.TRACK, structure_ref="track-state")
    changes = p.observed_changes((BEFORE,), (extra,))
    assert p.ObservedChange("placement", BEFORE, None) in changes
    assert p.ObservedChange("new", None, extra) in changes


def test_out_of_scope_observation_retained_and_fails_containment():
    v = inputs()
    r = v.corpus.runs[0]
    extra = p.SubjectState("outside", p.SubjectKind.MARKER, FrameRange(10, 11))
    raw = replace(r.effect, after=(AFTER, extra))
    out = derive(change_first(v, effect=raw))
    assert len(out.inputs.corpus.runs[0].effect.observed_effects) == 2
    assert p.QualificationReason.CONTAINMENT_FAILURE in out.reasons
    assert out.model_status != M.VERIFIED


def test_missing_observed_subject_and_category_incomplete():
    v = inputs()
    r = v.corpus.runs[0]
    for scope in (
        replace(SCOPE, subject_refs=("placement", "unobserved")),
        replace(SCOPE, kinds=()),
    ):
        out = derive(change_first(v, effect=replace(r.effect, scope=scope)))
        assert p.QualificationReason.OBSERVATION_INCOMPLETE in out.reasons
        assert out.model_status != M.VERIFIED


def test_extra_inconclusive_cannot_be_dropped_by_full_success_budget():
    v = inputs()
    extra = replace(run(999, v.policy.positive_classes[0]), status=p.ProbeRunStatus.INCONCLUSIVE)
    out = derive(replace(v, corpus=v.corpus.append(extra)))
    assert out.positive_count == 20 and out.challenge_count == 15
    assert out.model_status == M.UNVERIFIED
    assert extra in out.inputs.corpus.runs


def test_conflict_preserved_when_later_profile_stales():
    v = inputs()
    r = v.corpus.runs[0]
    changed = change_first(v, effect=replace(r.effect, status=p.EvidenceStatus.CONFLICTING))
    old = derive(changed)
    stale = derive(replace(changed, current_profile=replace(PROFILE, resolve_build="new")))
    assert old.model_status == M.CONFLICTING
    assert stale.model_status == M.STALE
    assert p.QualificationReason.SEMANTIC_CONFLICT in stale.reasons
    assert old.inputs.corpus == stale.inputs.corpus


@pytest.mark.parametrize("part", ["post_read", "reconciliation", "identity", "fragment"])
def test_independent_evidence_wrong_profile_cannot_be_promoted(part):
    v = inputs()
    r = v.corpus.runs[0]
    if part == "fragment":
        evidence = p.FragmentCorrespondenceEvidence(
            "fragment", r.identity.binding, p.FragmentEvidenceStatus.UNKNOWN, ()
        )
    else:
        evidence = getattr(r, part)
    bad = replace(
        evidence,
        binding=replace(evidence.binding, profile=replace(PROFILE, observation_contract="new")),
    )
    assert derive(change_first(v, **{part: bad})).model_status == M.STALE


def test_wrong_identity_subject_and_unverified_correspondence():
    v = inputs()
    e = v.corpus.runs[0].identity
    for correspondence in (
        replace(e.correspondences[0], subject_ref="other"),
        replace(e.correspondences[0], verified=False),
    ):
        assert (
            derive(
                change_first(v, identity=replace(e, correspondences=(correspondence,)))
            ).model_status
            != M.VERIFIED
        )


def test_fragment_required_but_missing():
    v = inputs()
    r = v.corpus.runs[0]
    case = replace(r.case, invocation=replace(r.case.invocation, produces_fragments=True))
    out = derive(change_first(v, case=case))
    assert out.model_status == M.UNVERIFIED
    assert out.runs[0].fragment_status == p.FragmentEvidenceStatus.UNKNOWN


def test_forged_derived_result_rejected():
    v = inputs()
    v = replace(v, corpus=replace(v.corpus, runs=v.corpus.runs[:1]))
    out = derive(v)
    with pytest.raises(ValueError):
        replace(out, model_status=M.VERIFIED, capability_status=C.SUPPORTED_VERIFIED)


def test_no_untyped_coercion_and_missing_domain_challenges():
    v = inputs()
    r = v.corpus.runs[0]
    with pytest.raises(TypeError):
        replace(r, containment_failure=0)
    with pytest.raises(TypeError):
        replace(r.effect, status="VALID")
    with pytest.raises(ValueError):
        replace(DOMAIN, challenges=())
    with pytest.raises(TypeError):
        replace(r.case.invocation, delta_frames=True)


def test_multiple_diagnostics_retained():
    v = inputs()
    r = v.corpus.runs[0]
    out = derive(
        change_first(
            v,
            containment_failure=True,
            ambiguous_target=True,
            post_read=None,
            effect=replace(
                r.effect, scope=replace(SCOPE, completeness=p.ScopeCompleteness.PARTIAL)
            ),
        )
    )
    assert set(out.reasons) >= {
        p.QualificationReason.CONTAINMENT_FAILURE,
        p.QualificationReason.AMBIGUOUS_TARGET,
        p.QualificationReason.POST_READ_UNVERIFIED,
        p.QualificationReason.OBSERVATION_INCOMPLETE,
    }


@pytest.mark.parametrize("primitive", list(p.ProbePrimitive))
def test_invocation_requires_explicit_bounded_parameters(primitive):
    with pytest.raises(ValueError):
        p.NativeInvocationSpec(primitive, "invoke-v1", ("placement",))
    with pytest.raises(ValueError):
        p.NativeInvocationSpec(primitive, "invoke-v1", ())


def test_authoritative_working_fixture_cannot_qualify():
    v = inputs()
    r = v.corpus.runs[0]
    fixture = replace(r.case.fixture, authoritative=True)
    assert derive(change_first(v, case=replace(r.case, fixture=fixture))).model_status != M.VERIFIED


def test_verified_effects_only_when_all_inside_runs_agree():
    v = inputs()
    assert derive(v).verified_effects == v.corpus.runs[0].effect.observed_effects
    r = v.corpus.runs[0]
    assert (
        derive(
            change_first(v, effect=replace(r.effect, status=p.EvidenceStatus.CONFLICTING))
        ).verified_effects
        is None
    )
