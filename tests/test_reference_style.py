"""TEST_ONLY_SUPPORT supplied catalogs, observations and approvals; no native qualification."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from davinci_ai_editor import authority as a
from davinci_ai_editor import reference_style as s
from davinci_ai_editor.evaluation import (
    FeedbackActor,
    FeedbackEvent,
    FeedbackEventType,
    FinalDecisionPayload,
)
from davinci_ai_editor.evidence import (
    EvidenceAssertion,
    EvidenceStrength,
    ProducerKind,
    ProducerRef,
)
from davinci_ai_editor.pause import PauseAction

D = s.StyleDimension
S = s.ReferenceResolutionStatus
P = s.PreferenceScope
R = s.StyleProblemReason
CATALOG = s.CatalogRef("authorized-catalog", "v1")
FAST = s.StylePreference(D.PACING, s.PacingPreference.FASTER)
CALM = s.StylePreference(D.PACING, s.PacingPreference.CALMER)
BALANCED = s.StylePreference(D.PACING, s.PacingPreference.BALANCED)
PRESERVE = s.StylePreference(D.PAUSE_PRESERVATION, s.PausePreference.PRESERVE_MORE)
TIGHTEN = s.StylePreference(D.PAUSE_PRESERVATION, s.PausePreference.TIGHTEN_MORE)
PRODUCER = ProducerRef(ProducerKind.HUMAN_SUPPLIED, "TEST_ONLY_SUPPORT", "v1", "v1")


def reference(item: str = "interview13", revision: str = "r1") -> s.ReferenceRef:
    return s.ReferenceRef(
        CATALOG,
        s.ReferenceKey("catalog-items", item, revision),
        s.ReferenceSource.APPROVED_OUTPUT,
        s.ReferenceForm.RENDERED,
        s.IdentityLifetime.PINNED_REVISION,
        ("TEST_ONLY_SUPPORT identity receipt",),
        ("Supplied fixture only",),
        locator=f"opaque-locator:{item}",
        title="previous-video-final",
    )


def catalog(*, complete: bool = True, count: int = 1) -> s.ReferenceCatalog:
    previous, other, current = reference(), reference("interview12"), reference("interview14")
    predecessors = (previous.key, other.key)[:count]
    relation = s.PredecessorRelation(
        "approved-series-order",
        "channel",
        current.key,
        predecessors,
        complete,
        ("TEST_ONLY_SUPPORT order",),
    )
    return s.ReferenceCatalog(
        CATALOG,
        tuple(s.ReferenceEntry(r, "channel") for r in (previous, other, current)),
        (relation,),
        (s.ReferenceAlias("previous interview", "channel", previous.key, ("alias-proof",)),),
    )


def explicit(ref: s.ReferenceRef | None = None) -> s.ReferenceQuery:
    return s.ReferenceQuery(
        "query",
        "explicit-user-selection",
        s.ReferenceQueryKind.EXPLICIT,
        target=(ref or reference()).key,
    )


def previous() -> s.ReferenceQuery:
    return s.ReferenceQuery(
        "query",
        "user-request",
        s.ReferenceQueryKind.PREVIOUS,
        "channel",
        anchor=reference("interview14").key,
        ordering_ref="approved-series-order",
    )


def intent(
    *preferences: s.StylePreference,
    dimensions: tuple[s.StyleDimension, ...] = (D.PACING, D.PAUSE_PRESERVATION),
) -> s.StyleIntent:
    return s.StyleIntent(
        "intent",
        ("user-request",),
        "edit-target",
        "accepted-work-excluded-scope",
        s.ScopeBinding(P.ONE_EDIT, "edit-1"),
        dimensions,
        preferences,
        comparative_baseline_ref="current-edit-baseline",
    )


def profile(name: str, scope: s.PreferenceScope, *preferences: s.StylePreference) -> s.StyleProfile:
    return s.StyleProfile(
        s.ProfileVersionRef(name, "v1"),
        "v1",
        None,
        "owner",
        s.ScopeBinding(scope, scope.value),
        preferences,
        ("explicit-profile-source",),
    )


def compose(
    value: s.StyleIntent, profiles: tuple[s.StyleProfile, ...] = (), **kwargs: object
) -> s.EffectiveStyleContext:
    # This helper deliberately has no untyped catch-all forwarding to production.
    assert not kwargs
    return s.compose_style(
        value,
        profiles=profiles,
        application_scopes=tuple(p.scope for p in profiles),
        capabilities=capabilities(),
        hard_constraint_refs=("supplied-hard-policy",),
        capability_refs=("supplied-style-consumer-support",),
    )


def capabilities() -> tuple[s.StyleCapability, ...]:
    return tuple(s.StyleCapability(d, True, ("TEST_ONLY_SUPPORT support",)) for d in D)


def selected(context: s.EffectiveStyleContext, dimension: s.StyleDimension) -> s.SelectedStyle:
    return next(v for v in context.selections if v.dimension == dimension)


def evidence(
    *,
    feature: s.StyleFeature = s.StyleFeature.PACING,
    knowledge: s.StyleKnowledge = s.StyleKnowledge.OBSERVED,
) -> s.StyleEvidence:
    value = s.PacingCharacter.BRISK if feature == s.StyleFeature.PACING else s.PauseCharacter.BRIEF
    return s.StyleEvidence(
        "evidence",
        reference(),
        "declared-output-section",
        PRODUCER,
        feature,
        knowledge,
        EvidenceAssertion.UNKNOWN
        if knowledge == s.StyleKnowledge.UNKNOWN
        else EvidenceAssertion.PRESENT,
        EvidenceStrength.UNKNOWN
        if knowledge == s.StyleKnowledge.UNKNOWN
        else EvidenceStrength.STRONG,
        None if knowledge == s.StyleKnowledge.UNKNOWN else value,
        ("independent-read-or-inference-basis",),
    )


def reference_intent(*dimensions: s.StyleDimension) -> s.StyleIntent:
    query = explicit()
    return replace(
        intent(dimensions=dimensions),
        reference_query=query,
        reference_resolution=s.resolve_reference(query, catalog()),
        inherit_dimensions=dimensions,
    )


def feedback() -> FeedbackEvent:
    return FeedbackEvent(
        "event",
        "case",
        "ai-proposal",
        1,
        FeedbackActor.EDITOR,
        FeedbackEventType.FINAL_DECISION_SET,
        FinalDecisionPayload(PauseAction.KEEP, None),
    )


def delta(base: s.StyleProfile) -> s.StyleProfileDeltaProposal:
    return s.StyleProfileDeltaProposal(
        "delta",
        base.reference,
        base.scope,
        (s.PreferenceChange(D.PACING, base.preferences[0], CALM),),
        (feedback(),),
        ("ai-proposal",),
        (),
        (),
        ("One correction does not establish a permanent preference",),
        ("TEST_ONLY_SUPPORT proposal",),
    )


def approval(proposal: s.StyleProfileDeltaProposal) -> s.StyleProfileApproval:
    return s.StyleProfileApproval(
        "explicit-profile-approval",
        proposal,
        "owner",
        "authorized-user",
        "v2",
        ("TEST_ONLY_SUPPORT explicit approval",),
    )


def test_explicit_exact_retains_catalog_object_and_revision() -> None:
    cat, query = catalog(), explicit()
    result = s.resolve_reference(query, cat)
    assert result.status == S.EXACT
    assert result.catalog is cat and result.query is query
    assert result.selected_ref is cat.entries[0].reference


@pytest.mark.parametrize(
    "complete,count,status",
    [
        (True, 1, S.CONTEXT_RESOLVED),
        (True, 2, S.AMBIGUOUS),
        (False, 1, S.UNRESOLVED),
        (False, 2, S.UNRESOLVED),
        (True, 0, S.UNRESOLVED),
    ],
)
def test_previous_requires_unique_complete_relation(
    complete: bool, count: int, status: s.ReferenceResolutionStatus
) -> None:
    result = s.resolve_reference(previous(), catalog(complete=complete, count=count))
    assert result.status == status
    assert (result.selected_ref is not None) == (status == S.CONTEXT_RESOLVED)


@pytest.mark.parametrize("field", ["scope_ref", "anchor", "ordering_ref"])
def test_previous_missing_explicit_context_never_guesses(field: str) -> None:
    query = previous()
    query = (
        replace(query, scope_ref=None)
        if field == "scope_ref"
        else replace(query, anchor=None)
        if field == "anchor"
        else replace(query, ordering_ref=None)
    )
    result = s.resolve_reference(query, catalog())
    assert result.status == S.UNRESOLVED and result.selected_ref is None


def test_absent_target_and_memory_are_not_identities() -> None:
    ghost = reference("model-memory-only")
    assert s.resolve_reference(explicit(ghost), catalog()).status == S.UNRESOLVED
    for candidate in (ghost, reference()):
        query = s.ReferenceQuery(
            "query",
            "chat-memory-proposal",
            s.ReferenceQueryKind.PROPOSED,
            proposed_candidates=(candidate.key,),
        )
        result = s.resolve_reference(query, catalog())
        assert result.status == S.UNRESOLVED and result.selected_ref is None
        assert bool(result.candidates) == (candidate == reference())


@pytest.mark.parametrize("target", [False, True])
def test_unavailable_catalog_or_target(target: bool) -> None:
    cat = catalog()
    cat = (
        replace(
            cat,
            entries=(
                replace(cat.entries[0], availability=s.ReferenceAvailability.UNAVAILABLE),
                *cat.entries[1:],
            ),
        )
        if target
        else replace(cat, available=False)
    )
    assert s.resolve_reference(explicit(), cat).status == S.UNAVAILABLE


@pytest.mark.parametrize("kind", ["alias", "revision", "catalog"])
def test_stale_binding_is_explicit(kind: str) -> None:
    cat, query = catalog(), explicit()
    if kind == "alias":
        query = s.ReferenceQuery(
            "query", "request", s.ReferenceQueryKind.ALIAS, "channel", alias="previous interview"
        )
        cat = replace(
            cat, aliases=(replace(cat.aliases[0], availability=s.ReferenceAvailability.STALE),)
        )
    elif kind == "revision":
        cat = replace(
            cat,
            entries=(
                replace(cat.entries[0], availability=s.ReferenceAvailability.STALE),
                *cat.entries[1:],
            ),
        )
    else:
        query = replace(query, expected_catalog=s.CatalogRef(CATALOG.catalog_id, "old"))
    result = s.resolve_reference(query, cat)
    assert result.status == S.STALE and result.selected_ref is None


def test_pinned_old_revision_valid_even_with_new_revision_and_stale_alias() -> None:
    cat = catalog()
    newer = replace(reference(revision="r2"), title="newest final")
    cat = replace(
        cat,
        entries=(*cat.entries, s.ReferenceEntry(newer, "channel")),
        aliases=(replace(cat.aliases[0], availability=s.ReferenceAvailability.STALE),),
    )
    result = s.resolve_reference(explicit(), cat)
    assert result.status == S.EXACT and result.selected_ref == reference()


def test_filename_locator_title_and_input_order_do_not_establish_identity() -> None:
    cat = catalog()
    query = replace(
        explicit(), target=s.ReferenceKey("catalog-items", "previous-video-final", "r1")
    )
    assert s.resolve_reference(query, cat).status == S.UNRESOLVED
    assert (
        s.resolve_reference(previous(), cat).selected_ref
        == s.resolve_reference(
            previous(), replace(cat, entries=tuple(reversed(cat.entries)))
        ).selected_ref
    )
    alias = s.ReferenceQuery(
        "q", "request", s.ReferenceQueryKind.ALIAS, "channel", alias=reference().locator
    )
    assert s.resolve_reference(alias, cat).status == S.UNRESOLVED


def test_explicit_alias_relation_and_duplicate_alias_ambiguity() -> None:
    cat = catalog()
    query = s.ReferenceQuery(
        "q", "request", s.ReferenceQueryKind.ALIAS, "channel", alias="previous interview"
    )
    assert s.resolve_reference(query, cat).status == S.CONTEXT_RESOLVED
    cat = replace(
        cat, aliases=(*cat.aliases, replace(cat.aliases[0], target=cat.entries[1].reference.key))
    )
    assert s.resolve_reference(query, cat).status == S.AMBIGUOUS


@pytest.mark.parametrize("status", [S.AMBIGUOUS, S.UNRESOLVED, S.STALE, S.UNAVAILABLE])
def test_non_success_cannot_expose_selected_ref(status: s.ReferenceResolutionStatus) -> None:
    good = s.resolve_reference(explicit(), catalog())
    with pytest.raises(ValueError, match="selected_ref"):
        replace(good, status=status)


def test_current_request_overrides_only_its_dimension() -> None:
    project = profile("project", P.PROJECT, CALM, PRESERVE)
    value = intent(FAST)
    result = compose(value, (project,))
    assert result.intent is value and result.profiles[0] is project
    assert selected(result, D.PACING).preference is FAST
    assert selected(result, D.PACING).origin == s.PreferenceOrigin.CURRENT_REQUEST
    assert selected(result, D.PAUSE_PRESERVATION).preference is PRESERVE


def test_project_precedence_over_channel_content_and_user() -> None:
    profiles = (
        profile("user", P.USER_DEFAULT, FAST),
        profile("content", P.CONTENT_TYPE, FAST),
        profile("channel", P.CHANNEL, FAST),
        profile("project", P.PROJECT, CALM),
    )
    result = compose(intent(dimensions=(D.PACING,)), profiles)
    assert selected(result, D.PACING).profiles == (profiles[-1],)


def test_one_edit_scope_is_not_implicitly_promoted_to_explicit_request() -> None:
    one_edit = profile("local", P.ONE_EDIT, FAST)
    project = profile("project", P.PROJECT, CALM)
    result = compose(intent(dimensions=(D.PACING,)), (one_edit, project))
    assert not result.selections and result.problems[0].reason == R.INTERPRETATION_UNRESOLVED
    explicit_result = compose(intent(CALM, dimensions=(D.PACING,)), (one_edit, project))
    assert selected(explicit_result, D.PACING).origin == s.PreferenceOrigin.CURRENT_REQUEST


@pytest.mark.parametrize("scope", [P.CHANNEL, P.CONTENT_TYPE, P.PROJECT])
def test_same_level_conflict_no_averaging_or_latest_wins(scope: s.PreferenceScope) -> None:
    other_scope = P.CONTENT_TYPE if scope == P.CHANNEL else scope
    a, b = profile("a", scope, FAST), profile("b", other_scope, CALM)
    for profiles in ((a, b), (b, a)):
        result = compose(intent(dimensions=(D.PACING,)), profiles)
        assert not result.selections and result.problems == (s.StyleProblem(D.PACING, R.CONFLICT),)


def test_same_level_agreement_retains_both_sources() -> None:
    a, b = profile("a", P.CHANNEL, FAST), profile("b", P.CONTENT_TYPE, FAST)
    result = compose(intent(dimensions=(D.PACING,)), (a, b))
    assert selected(result, D.PACING).profiles == (a, b)


def test_user_then_team_then_explicit_zero_shot_fallback() -> None:
    user, team = profile("user", P.USER_DEFAULT, CALM), profile("team", P.TEAM, FAST)
    value = intent(dimensions=(D.PACING,))
    assert selected(compose(value, (team, user)), D.PACING).preference is CALM
    assert selected(compose(value, (team,)), D.PACING).preference is FAST
    result = s.compose_style(value, defaults=(BALANCED,), capabilities=capabilities())
    assert selected(result, D.PACING).origin == s.PreferenceOrigin.ZERO_SHOT
    assert (
        s.compose_style(value, capabilities=capabilities()).problems[0].reason
        == R.PREFERENCE_MISSING
    )


@pytest.mark.parametrize("allowed", [(CALM,), (), None])
def test_hard_constraint_cannot_be_overridden(
    allowed: tuple[s.StylePreference, ...] | None,
) -> None:
    hard = s.HardStyleConstraint(D.PACING, allowed, ("approved-team-policy",))
    result = s.compose_style(
        intent(FAST, dimensions=(D.PACING,)),
        hard_constraints=(hard,),
        capabilities=capabilities(),
        hard_constraint_refs=("safety-policy-ref",),
    )
    assert not result.selections and result.problems[0].reason == R.HARD_CONSTRAINT
    assert result.hard_constraints[0] is hard and result.hard_constraint_refs == (
        "safety-policy-ref",
    )


@pytest.mark.parametrize("support", [False, None])
def test_style_cannot_enable_unsupported_or_unknown_capability(support: bool | None) -> None:
    capability = s.StyleCapability(D.PACING, support, ("consumer-support",))
    result = s.compose_style(intent(FAST, dimensions=(D.PACING,)), capabilities=(capability,))
    assert (
        not result.selections and result.problems[0].reason == R.CAPABILITY_UNSUPPORTED_OR_UNKNOWN
    )
    assert result.capabilities[0] is capability


def test_missing_capability_is_not_support() -> None:
    result = s.compose_style(intent(FAST, dimensions=(D.PACING,)))
    assert result.problems[0].reason == R.CAPABILITY_UNSUPPORTED_OR_UNKNOWN


def test_modification_scope_is_preserved_and_new_scope_needs_new_context() -> None:
    original = intent(FAST)
    context = compose(original)
    assert context.modification_scope_ref == original.modification_scope_ref
    with pytest.raises(ValueError, match="Modification scope"):
        replace(context, modification_scope_ref="reopen-frozen-work")
    newer = compose(replace(original, modification_scope_ref="explicitly-new-scope"))
    assert newer is not context and context.intent is original
    assert context.modification_scope_ref == "accepted-work-excluded-scope"


def test_scope_applicability_and_exclusions_are_not_inferred() -> None:
    project = profile("project", P.PROJECT, FAST)
    value = intent(dimensions=(D.PACING,))
    context = s.compose_style(value, profiles=(project,), capabilities=capabilities())
    assert not context.selections
    extra = s.ScopeBinding(P.CONTENT_TYPE, "interview")
    project = replace(project, applicability=(extra,))
    assert not compose(value, (project,)).selections
    context = s.compose_style(
        value,
        profiles=(project,),
        application_scopes=(project.scope, extra),
        capabilities=capabilities(),
    )
    assert context.selections
    project = replace(project, exclusions=(extra,))
    assert not s.compose_style(
        value,
        profiles=(project,),
        application_scopes=(project.scope, extra),
        capabilities=capabilities(),
    ).selections


def test_reference_selection_only_inherits_explicit_dimensions() -> None:
    value = reference_intent(D.PACING)
    pacing = evidence()
    pauses = replace(evidence(feature=s.StyleFeature.PAUSE_PRESERVATION), evidence_id="pauses")
    result = s.compose_style(value, evidence=(pacing, pauses), capabilities=capabilities())
    assert len(result.selections) == 1
    selection = selected(result, D.PACING)
    assert selection.preference is None and selection.reference_evidence == (pacing,)
    assert selection.reference_evidence[0] is pacing
    assert result.reference_resolutions[0] is value.reference_resolution
    assert "CAPTION_STYLE" not in s.StyleDimension.__members__


def test_reference_evidence_is_not_automatically_user_preference() -> None:
    result = s.compose_style(
        intent(dimensions=(D.PACING,)), evidence=(evidence(),), capabilities=capabilities()
    )
    assert not result.selections and result.problems[0].reason == R.PREFERENCE_MISSING


def test_reference_without_selected_dimensions_never_silently_uses_defaults() -> None:
    value = replace(reference_intent(D.PACING), inherit_dimensions=())
    result = s.compose_style(
        value, evidence=(evidence(),), defaults=(FAST,), capabilities=capabilities()
    )
    assert not result.selections
    assert result.problems == (s.StyleProblem(D.PACING, R.INTERPRETATION_UNRESOLVED),)


def test_explicit_preference_and_reference_inheritance_conflict_is_visible() -> None:
    value = replace(reference_intent(D.PACING), preferences=(FAST,))
    result = s.compose_style(value, evidence=(evidence(),), capabilities=capabilities())
    assert not result.selections and result.problems[0].reason == R.CONFLICT


def test_hard_constraints_are_conjunctive_and_do_not_block_unrelated_dimension() -> None:
    first = s.HardStyleConstraint(D.PACING, (FAST, CALM), ("policy-a",))
    second = s.HardStyleConstraint(D.PACING, (CALM,), ("policy-b",))
    result = s.compose_style(
        intent(FAST, PRESERVE), hard_constraints=(first, second), capabilities=capabilities()
    )
    assert len(result.selections) == 1 and result.selections[0].preference is PRESERVE
    assert result.problems == (s.StyleProblem(D.PACING, R.HARD_CONSTRAINT),)


def test_reference_descriptor_is_not_converted_to_satisfy_hard_policy() -> None:
    constraint = s.HardStyleConstraint(D.PACING, (FAST,), ("policy",))
    result = s.compose_style(
        reference_intent(D.PACING),
        evidence=(evidence(),),
        hard_constraints=(constraint,),
        capabilities=capabilities(),
    )
    assert not result.selections and result.problems[0].reason == R.HARD_CONSTRAINT


@pytest.mark.parametrize("knowledge", list(s.StyleKnowledge))
def test_observed_inferred_unknown_are_separate_from_assertion(knowledge: s.StyleKnowledge) -> None:
    record = evidence(knowledge=knowledge)
    result = s.compose_style(
        reference_intent(D.PACING), evidence=(record,), capabilities=capabilities()
    )
    assert result.evidence[0] is record
    assert bool(result.selections) == (knowledge == s.StyleKnowledge.OBSERVED)


def test_missing_evidence_remains_distinct_from_explicit_unknown() -> None:
    value = reference_intent(D.PACING)
    absent = s.compose_style(value, capabilities=capabilities())
    unknown = s.compose_style(
        value, evidence=(evidence(knowledge=s.StyleKnowledge.UNKNOWN),), capabilities=capabilities()
    )
    assert absent.evidence == () and len(unknown.evidence) == 1
    assert not absent.selections and not unknown.selections


def test_conflicting_reference_observations_not_ranked_by_strength() -> None:
    first = evidence()
    second = replace(
        first,
        evidence_id="other",
        value=s.PacingCharacter.UNHURRIED,
        strength=EvidenceStrength.WEAK,
    )
    result = s.compose_style(
        reference_intent(D.PACING), evidence=(first, second), capabilities=capabilities()
    )
    assert not result.selections and result.problems[0].reason == R.CONFLICT


@pytest.mark.parametrize(
    "feature",
    [
        s.StyleFeature.REMOVED_SOURCE,
        s.StyleFeature.REJECTED_TAKES,
        s.StyleFeature.HIDDEN_TRACKS,
        s.StyleFeature.EDITOR_INTENTION,
    ],
)
@pytest.mark.parametrize("knowledge", [s.StyleKnowledge.OBSERVED, s.StyleKnowledge.INFERRED])
def test_rendered_output_cannot_assert_hidden_decisions(
    feature: s.StyleFeature, knowledge: s.StyleKnowledge
) -> None:
    with pytest.raises(ValueError, match="hidden decisions"):
        replace(evidence(), feature=feature, knowledge=knowledge, value=None)
    unknown = replace(evidence(knowledge=s.StyleKnowledge.UNKNOWN), feature=feature)
    assert unknown.knowledge == s.StyleKnowledge.UNKNOWN


def test_editable_reference_can_retain_read_evidence_not_invent_editor_intent() -> None:
    editable = replace(reference(), form=s.ReferenceForm.EDITABLE)
    read = replace(evidence(), reference=editable, feature=s.StyleFeature.HIDDEN_TRACKS, value=None)
    assert read.reference is editable
    machine = replace(PRODUCER, producer_kind=ProducerKind.TIMELINE_ADAPTER)
    with pytest.raises(ValueError, match="editor intention"):
        replace(read, producer=machine, feature=s.StyleFeature.EDITOR_INTENTION)


def test_unresolved_reference_and_interpretation_block_without_fallback() -> None:
    value = reference_intent(D.PACING)
    query = explicit(reference("missing"))
    value = replace(
        value, reference_query=query, reference_resolution=s.resolve_reference(query, catalog())
    )
    context = s.compose_style(value, defaults=(FAST,), capabilities=capabilities())
    assert context.problems[0].reason == R.REFERENCE_UNRESOLVED and not context.selections
    context = compose(replace(intent(FAST), unresolved_interpretation=("ambiguous request",)))
    assert not context.selections


def test_one_feedback_event_never_mutates_profile_or_auto_approves() -> None:
    base = profile("user", P.USER_DEFAULT, FAST)
    proposal = delta(base)
    result = s.apply_profile_delta(base, proposal, None)
    assert result.status == s.ProfileUpdateStatus.APPROVAL_REQUIRED and result.profile is None
    assert result.base is base and base.preferences == (FAST,)
    assert proposal.supporting_feedback[0].event_id == "event"


def test_approved_delta_creates_immutable_version_preserving_old_context() -> None:
    base = profile("user", P.USER_DEFAULT, FAST)
    context = compose(intent(dimensions=(D.PACING,)), (base,))
    proposal = delta(base)
    explicit_approval = approval(proposal)
    result = s.apply_profile_delta(base, proposal, explicit_approval)
    updated = result.profile
    assert result.status == s.ProfileUpdateStatus.CREATED and updated is not None
    assert updated.reference.version == "v2" and updated.parent is base.reference
    assert updated.preferences == (CALM,) and base.preferences == (FAST,)
    assert context.profiles[0] is base and selected(context, D.PACING).preference is FAST
    assert result.approval is explicit_approval and result.proposal is proposal
    assert not isinstance(explicit_approval, a.ApproveCandidate)
    assert proposal.generalization_limitations[0] in updated.limitations
    with pytest.raises(FrozenInstanceError):
        updated.owner_ref = "other"  # type: ignore[misc]


def test_stale_delta_never_rebases_and_retains_evidence() -> None:
    base = profile("user", P.USER_DEFAULT, FAST)
    proposal = delta(base)
    newer = replace(base, reference=s.ProfileVersionRef("user", "v2"), parent=base.reference)
    result = s.apply_profile_delta(newer, proposal, approval(proposal))
    assert result.status == s.ProfileUpdateStatus.STALE and result.profile is None
    assert result.base is newer and result.proposal is proposal


@pytest.mark.parametrize("mismatch", ["owner", "scope", "before", "approval", "version"])
def test_delta_mismatch_is_not_repaired(mismatch: str) -> None:
    base = profile("user", P.USER_DEFAULT, FAST)
    proposal = delta(base)
    approved = approval(proposal)
    if mismatch == "owner":
        approved = replace(approved, owner_ref="other")
    elif mismatch == "scope":
        proposal = replace(proposal, requested_scope=s.ScopeBinding(P.CHANNEL, "channel"))
        approved = approval(proposal)
    elif mismatch == "before":
        proposal = replace(proposal, changes=(s.PreferenceChange(D.PACING, BALANCED, CALM),))
        approved = approval(proposal)
    elif mismatch == "approval":
        proposal = replace(proposal, proposal_id="substituted")
    else:
        approved = replace(approved, new_version="v1")
    result = s.apply_profile_delta(base, proposal, approved)
    assert result.status == s.ProfileUpdateStatus.CONFLICT and result.profile is None


def test_contrary_evidence_and_limitations_retained() -> None:
    base = profile("user", P.USER_DEFAULT, FAST)
    contrary = replace(feedback(), event_id="contrary", proposal_id="other-proposal")
    proposal = replace(
        delta(base), contrary_feedback=(contrary,), contrary_evidence_refs=("counterexample",)
    )
    result = s.apply_profile_delta(base, proposal, approval(proposal))
    assert result.proposal.contrary_feedback[0] is contrary
    assert result.proposal.generalization_limitations


def test_multiple_versions_do_not_choose_latest() -> None:
    first = profile("user", P.USER_DEFAULT, FAST)
    second = replace(first, reference=s.ProfileVersionRef("user", "v2"), parent=first.reference)
    result = compose(intent(dimensions=(D.PACING,)), (first, second))
    assert not result.selections and result.problems[0].reason == R.CONFLICT


def test_no_cross_dimension_values_or_mutable_collections() -> None:
    with pytest.raises(TypeError):
        s.StylePreference(D.PACING, s.PausePreference.BALANCED)
    original = intent(FAST)
    with pytest.raises(FrozenInstanceError):
        original.modification_scope_ref = "other"  # type: ignore[misc]
    with pytest.raises(ValueError):
        replace(original, inherit_dimensions=(D.PACING, D.PACING))


def test_removed_preference_requires_approval_and_retains_exact_parent() -> None:
    base = profile("user", P.USER_DEFAULT, FAST)
    proposal = replace(delta(base), changes=(s.PreferenceChange(D.PACING, FAST, None),))
    updated = s.apply_profile_delta(base, proposal, approval(proposal)).profile
    assert updated is not None and updated.preferences == ()
    assert updated.parent is base.reference and base.preferences == (FAST,)


def test_wrong_catalog_and_duplicate_identity_are_contract_errors() -> None:
    cat = catalog()
    with pytest.raises(ValueError, match="Cross-catalog"):
        replace(cat, reference=s.CatalogRef("another", "v1"))
    with pytest.raises(ValueError, match="Duplicate reference"):
        replace(cat, entries=(*cat.entries, cat.entries[0]))


def test_ast_domain_only_no_native_execution_or_duplicate_existing_types() -> None:
    tree = ast.parse(Path(s.__file__).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"dataclasses", "enum", "typing", "evaluation", "evidence"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert not classes & {
        "EvidenceStrength",
        "ProducerRef",
        "FeedbackEvent",
        "Candidate",
        "ExpectedDiff",
        "SafetyVerdict",
        "Transaction",
    }
    for cls in (s.StyleIntent, s.StyleProfile, s.EffectiveStyleContext, s.StyleProfileApproval):
        names = {f.name for f in fields(cls)}
        assert not names & {
            "command",
            "confidence",
            "geometry",
            "frames",
            "safety_verdict",
            "apply_authorization",
            "native_operation",
        }
    source = Path(s.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "resolve_api",
        "premiere",
        "socket",
        "subprocess",
        "os.walk",
        "mtime",
        "embedding",
        "local_reference_pause_frames",
    ):
        assert forbidden not in source.lower()
    assert isinstance(evidence().producer, ProducerRef)
    assert isinstance(evidence().strength, EvidenceStrength)
    assert isinstance(
        delta(profile("user", P.USER_DEFAULT, FAST)).supporting_feedback[0], FeedbackEvent
    )
