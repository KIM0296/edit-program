"""Immutable reference/style context only; no analysis, execution, or profile store.

Supplied catalog relations and provenance are assertions, not authenticated identity.
Style preferences never become observed pause facts or permission to modify work.
"""

from dataclasses import dataclass, replace
from enum import Enum
from typing import TypeVar

from .evaluation import FeedbackEvent
from .evidence import EvidenceAssertion, EvidenceStrength, ProducerKind, ProducerRef

T = TypeVar("T")


def _text(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("Explicit nonempty references required")


def _tuple(values: tuple[T, ...], kind: type[T]) -> tuple[T, ...]:
    result = tuple(values)
    if any(not isinstance(value, kind) for value in result):
        raise TypeError("Typed immutable values required")
    return result


def _refs(values: tuple[str, ...], *, required: bool = False) -> tuple[str, ...]:
    result = _tuple(values, str)
    _text(*result)
    if required and not result:
        raise ValueError("Provenance required")
    return result


def _enum(value: object, kind: type[Enum]) -> None:
    if not isinstance(value, kind):
        raise TypeError("Typed enum required")


@dataclass(frozen=True)
class CatalogRef:
    catalog_id: str
    version: str

    def __post_init__(self) -> None:
        _text(self.catalog_id, self.version)


@dataclass(frozen=True)
class ReferenceKey:
    namespace: str
    item_id: str
    revision: str

    def __post_init__(self) -> None:
        _text(self.namespace, self.item_id, self.revision)


class ReferenceSource(str, Enum):
    USER_URL = "USER_URL"
    USER_FILE = "USER_FILE"
    AUTHORIZED_TIMELINE = "AUTHORIZED_TIMELINE"
    APPROVED_OUTPUT = "APPROVED_OUTPUT"
    SAVED_ENTRY = "SAVED_ENTRY"
    CHANNEL_CATALOG = "CHANNEL_CATALOG"
    PROJECT_CATALOG = "PROJECT_CATALOG"


class ReferenceForm(str, Enum):
    RENDERED = "RENDERED"
    EDITABLE = "EDITABLE"
    UNKNOWN = "UNKNOWN"


class IdentityLifetime(str, Enum):
    PINNED_REVISION = "PINNED_REVISION"
    SESSION = "SESSION"
    SNAPSHOT = "SNAPSHOT"
    UNKNOWN = "UNKNOWN"


class ReferenceAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ReferenceRef:
    catalog: CatalogRef
    key: ReferenceKey
    source: ReferenceSource
    form: ReferenceForm
    lifetime: IdentityLifetime
    provenance_refs: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    locator: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, CatalogRef) or not isinstance(self.key, ReferenceKey):
            raise TypeError("Catalog and exact revision required")
        _enum(self.source, ReferenceSource)
        _enum(self.form, ReferenceForm)
        _enum(self.lifetime, IdentityLifetime)
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs, required=True))
        object.__setattr__(self, "limitations", _refs(self.limitations))
        for value in (self.locator, self.title):
            if value is not None:
                _text(value)


@dataclass(frozen=True)
class ReferenceEntry:
    reference: ReferenceRef
    scope_ref: str
    availability: ReferenceAvailability = ReferenceAvailability.AVAILABLE

    def __post_init__(self) -> None:
        if not isinstance(self.reference, ReferenceRef):
            raise TypeError("Reference required")
        _text(self.scope_ref)
        _enum(self.availability, ReferenceAvailability)


@dataclass(frozen=True)
class ReferenceAlias:
    alias: str
    scope_ref: str
    target: ReferenceKey
    provenance_refs: tuple[str, ...]
    availability: ReferenceAvailability = ReferenceAvailability.AVAILABLE

    def __post_init__(self) -> None:
        _text(self.alias, self.scope_ref)
        if not isinstance(self.target, ReferenceKey):
            raise TypeError("Exact alias target required")
        _enum(self.availability, ReferenceAvailability)
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs, required=True))


@dataclass(frozen=True)
class PredecessorRelation:
    relation_ref: str
    scope_ref: str
    anchor: ReferenceKey
    predecessors: tuple[ReferenceKey, ...]
    complete: bool
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.relation_ref, self.scope_ref)
        if not isinstance(self.anchor, ReferenceKey) or type(self.complete) is not bool:
            raise TypeError("Explicit anchor and completeness required")
        values = _tuple(self.predecessors, ReferenceKey)
        if len(set(values)) != len(values) or self.anchor in values:
            raise ValueError("Duplicate/self predecessor")
        object.__setattr__(self, "predecessors", values)
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs, required=True))


@dataclass(frozen=True)
class ReferenceCatalog:
    reference: CatalogRef
    entries: tuple[ReferenceEntry, ...]
    relations: tuple[PredecessorRelation, ...] = ()
    aliases: tuple[ReferenceAlias, ...] = ()
    available: bool = True
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reference, CatalogRef) or type(self.available) is not bool:
            raise TypeError("Typed catalog reference and availability required")
        for name, kind in (
            ("entries", ReferenceEntry),
            ("relations", PredecessorRelation),
            ("aliases", ReferenceAlias),
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name), kind))
        if any(e.reference.catalog != self.reference for e in self.entries):
            raise ValueError("Cross-catalog entry")
        keys = [e.reference.key for e in self.entries]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate reference revision")
        relations = [(r.scope_ref, r.anchor, r.relation_ref) for r in self.relations]
        if len(set(relations)) != len(relations):
            raise ValueError("Duplicate ordering relation")
        object.__setattr__(self, "limitations", _refs(self.limitations))


class ReferenceQueryKind(str, Enum):
    EXPLICIT = "EXPLICIT"
    ALIAS = "ALIAS"
    PREVIOUS = "PREVIOUS"
    PROPOSED = "PROPOSED"


@dataclass(frozen=True)
class ReferenceQuery:
    query_id: str
    request_ref: str
    kind: ReferenceQueryKind
    scope_ref: str | None = None
    target: ReferenceKey | None = None
    alias: str | None = None
    anchor: ReferenceKey | None = None
    ordering_ref: str | None = None
    expected_catalog: CatalogRef | None = None
    proposed_candidates: tuple[ReferenceKey, ...] = ()

    def __post_init__(self) -> None:
        _text(self.query_id, self.request_ref)
        _enum(self.kind, ReferenceQueryKind)
        for value in (self.scope_ref, self.alias, self.ordering_ref):
            if value is not None:
                _text(value)
        for key in (self.target, self.anchor):
            if key is not None and not isinstance(key, ReferenceKey):
                raise TypeError("Identity key required; locator is not identity")
        if self.expected_catalog is not None and not isinstance(self.expected_catalog, CatalogRef):
            raise TypeError("Catalog reference required")
        object.__setattr__(
            self, "proposed_candidates", _tuple(self.proposed_candidates, ReferenceKey)
        )


class ReferenceResolutionStatus(str, Enum):
    EXACT = "EXACT"
    CONTEXT_RESOLVED = "CONTEXT_RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ReferenceResolution:
    query: ReferenceQuery
    catalog: ReferenceCatalog
    status: ReferenceResolutionStatus
    candidates: tuple[ReferenceRef, ...]
    reasons: tuple[str, ...]
    selected_ref: ReferenceRef | None = None
    rule_version: str = "reference-resolution-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.query, ReferenceQuery) or not isinstance(
            self.catalog, ReferenceCatalog
        ):
            raise TypeError("Exact query/catalog required")
        _enum(self.status, ReferenceResolutionStatus)
        candidates = _tuple(self.candidates, ReferenceRef)
        if any(c not in tuple(e.reference for e in self.catalog.entries) for c in candidates):
            raise ValueError("Candidate absent from supplied catalog")
        success = self.status in (
            ReferenceResolutionStatus.EXACT,
            ReferenceResolutionStatus.CONTEXT_RESOLVED,
        )
        if success:
            if len(candidates) != 1 or self.selected_ref != candidates[0]:
                raise ValueError("Resolved result requires exactly one selected catalog reference")
        elif self.selected_ref is not None:
            raise ValueError("Non-success must not expose selected_ref")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "reasons", _refs(self.reasons, required=True))
        _text(self.rule_version)


def resolve_reference(query: ReferenceQuery, catalog: ReferenceCatalog) -> ReferenceResolution:
    """Only declared catalog identity/relations resolve; no search or recency heuristic."""
    S = ReferenceResolutionStatus
    entries = {e.reference.key: e for e in catalog.entries}

    def result(
        status: ReferenceResolutionStatus, reason: str, keys: tuple[ReferenceKey, ...] = ()
    ) -> ReferenceResolution:
        refs = tuple(
            entries[k].reference
            for k in sorted(set(keys), key=lambda k: (k.namespace, k.item_id, k.revision))
            if k in entries
        )
        selected = refs[0] if status in (S.EXACT, S.CONTEXT_RESOLVED) else None
        return ReferenceResolution(query, catalog, status, refs, (reason,), selected)

    if not catalog.available:
        return result(S.UNAVAILABLE, "CATALOG_UNAVAILABLE")
    if query.expected_catalog is not None and query.expected_catalog != catalog.reference:
        return result(S.STALE, "CATALOG_BINDING_CHANGED")
    keys: tuple[ReferenceKey, ...] = ()
    success = S.CONTEXT_RESOLVED
    if query.kind == ReferenceQueryKind.EXPLICIT:
        keys = (query.target,) if query.target is not None else ()
        success = S.EXACT
    elif query.kind == ReferenceQueryKind.PROPOSED:
        return result(
            S.UNRESOLVED,
            "PROPOSED_CANDIDATES_REQUIRE_EXPLICIT_SELECTION",
            query.proposed_candidates,
        )
    elif query.kind == ReferenceQueryKind.ALIAS:
        if query.scope_ref is None or query.alias is None:
            return result(S.UNRESOLVED, "ALIAS_SCOPE_REQUIRED")
        aliases = tuple(
            a for a in catalog.aliases if a.scope_ref == query.scope_ref and a.alias == query.alias
        )
        keys = tuple(a.target for a in aliases)
        if any(a.availability == ReferenceAvailability.STALE for a in aliases):
            return result(S.STALE, "ALIAS_STALE", keys)
        if any(a.availability == ReferenceAvailability.UNAVAILABLE for a in aliases):
            return result(S.UNAVAILABLE, "ALIAS_UNAVAILABLE", keys)
    else:
        if query.scope_ref is None or query.anchor is None or query.ordering_ref is None:
            return result(S.UNRESOLVED, "PREVIOUS_REQUIRES_SCOPE_ANCHOR_ORDER")
        anchor = entries.get(query.anchor)
        if anchor is None or anchor.scope_ref != query.scope_ref:
            return result(S.UNRESOLVED, "ANCHOR_NOT_IN_SCOPE")
        if anchor.availability != ReferenceAvailability.AVAILABLE:
            return result(S(anchor.availability.value), "ANCHOR_NOT_AVAILABLE")
        relations = tuple(
            r
            for r in catalog.relations
            if r.scope_ref == query.scope_ref
            and r.anchor == query.anchor
            and r.relation_ref == query.ordering_ref
        )
        if not relations:
            return result(S.UNRESOLVED, "ORDERING_RELATION_MISSING")
        relation = relations[0]
        keys = relation.predecessors
        if not relation.complete:
            return result(S.UNRESOLVED, "ORDERING_COVERAGE_INCOMPLETE", keys)
    if not keys:
        return result(S.UNRESOLVED, "NO_CANDIDATE")
    if any(k not in entries for k in keys):
        return result(S.UNRESOLVED, "IDENTITY_NOT_IN_CATALOG", keys)
    if query.scope_ref is not None and any(entries[k].scope_ref != query.scope_ref for k in keys):
        return result(S.UNRESOLVED, "CANDIDATE_OUTSIDE_SCOPE", keys)
    if any(entries[k].availability == ReferenceAvailability.STALE for k in keys):
        return result(S.STALE, "REVISION_BINDING_STALE", keys)
    if any(entries[k].availability == ReferenceAvailability.UNAVAILABLE for k in keys):
        return result(S.UNAVAILABLE, "TARGET_UNAVAILABLE", keys)
    if len(set(keys)) != 1:
        return result(S.AMBIGUOUS, "MULTIPLE_CANDIDATES", keys)
    return result(success, "DECLARED_IDENTITY_OR_RELATION", keys)


class PreferenceScope(str, Enum):
    ONE_EDIT = "ONE_EDIT"
    PROJECT = "PROJECT"
    CONTENT_TYPE = "CONTENT_TYPE"
    CHANNEL = "CHANNEL"
    USER_DEFAULT = "USER_DEFAULT"
    TEAM = "TEAM"


@dataclass(frozen=True)
class ScopeBinding:
    scope: PreferenceScope
    reference: str

    def __post_init__(self) -> None:
        _enum(self.scope, PreferenceScope)
        _text(self.reference)


class StyleDimension(str, Enum):
    PACING = "PACING"
    PAUSE_PRESERVATION = "PAUSE_PRESERVATION"


class PacingPreference(str, Enum):
    CALMER = "CALMER"
    BALANCED = "BALANCED"
    FASTER = "FASTER"


class PausePreference(str, Enum):
    PRESERVE_MORE = "PRESERVE_MORE"
    BALANCED = "BALANCED"
    TIGHTEN_MORE = "TIGHTEN_MORE"


@dataclass(frozen=True)
class StylePreference:
    dimension: StyleDimension
    value: PacingPreference | PausePreference

    def __post_init__(self) -> None:
        _enum(self.dimension, StyleDimension)
        _enum(
            self.value,
            PacingPreference if self.dimension == StyleDimension.PACING else PausePreference,
        )


def _preferences(values: tuple[StylePreference, ...]) -> tuple[StylePreference, ...]:
    result = _tuple(values, StylePreference)
    if len({v.dimension for v in result}) != len(result):
        raise ValueError("One preference per dimension required")
    return result


@dataclass(frozen=True)
class StyleIntent:
    intent_id: str
    request_refs: tuple[str, ...]
    target_scope_ref: str
    modification_scope_ref: str
    preference_scope: ScopeBinding
    requested_dimensions: tuple[StyleDimension, ...]
    preferences: tuple[StylePreference, ...] = ()
    inherit_dimensions: tuple[StyleDimension, ...] = ()
    reference_query: ReferenceQuery | None = None
    reference_resolution: ReferenceResolution | None = None
    comparative_baseline_ref: str | None = None
    unresolved_interpretation: tuple[str, ...] = ()
    unresolved_dimensions: tuple[StyleDimension, ...] = ()

    def __post_init__(self) -> None:
        _text(self.intent_id, self.target_scope_ref, self.modification_scope_ref)
        if not isinstance(self.preference_scope, ScopeBinding):
            raise TypeError("Preference scope is separate from modification scope")
        object.__setattr__(self, "request_refs", _refs(self.request_refs, required=True))
        for name in ("requested_dimensions", "inherit_dimensions", "unresolved_dimensions"):
            values = _tuple(getattr(self, name), StyleDimension)
            if len(set(values)) != len(values):
                raise ValueError("Duplicate dimension")
            object.__setattr__(self, name, values)
        object.__setattr__(self, "preferences", _preferences(self.preferences))
        specified = (
            {p.dimension for p in self.preferences}
            | set(self.inherit_dimensions)
            | set(self.unresolved_dimensions)
        )
        if not specified <= set(self.requested_dimensions):
            raise ValueError("Preference/inheritance must name requested dimensions")
        if self.reference_query is not None and not isinstance(
            self.reference_query, ReferenceQuery
        ):
            raise TypeError("Typed query required")
        if self.reference_resolution is not None and (
            not isinstance(self.reference_resolution, ReferenceResolution)
            or self.reference_resolution.query != self.reference_query
        ):
            raise ValueError("Resolution must bind the supplied query")
        if self.comparative_baseline_ref is not None:
            _text(self.comparative_baseline_ref)
        object.__setattr__(self, "unresolved_interpretation", _refs(self.unresolved_interpretation))


class StyleKnowledge(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class StyleFeature(str, Enum):
    PACING = "PACING"
    PAUSE_PRESERVATION = "PAUSE_PRESERVATION"
    REMOVED_SOURCE = "REMOVED_SOURCE"
    REJECTED_TAKES = "REJECTED_TAKES"
    HIDDEN_TRACKS = "HIDDEN_TRACKS"
    EDITOR_INTENTION = "EDITOR_INTENTION"


class PacingCharacter(str, Enum):
    UNHURRIED = "UNHURRIED"
    MODERATE = "MODERATE"
    BRISK = "BRISK"


class PauseCharacter(str, Enum):
    EXTENDED = "EXTENDED"
    MIXED = "MIXED"
    BRIEF = "BRIEF"


@dataclass(frozen=True)
class StyleEvidence:
    evidence_id: str
    reference: ReferenceRef
    observed_scope_ref: str
    producer: ProducerRef
    feature: StyleFeature
    knowledge: StyleKnowledge
    assertion: EvidenceAssertion
    strength: EvidenceStrength
    value: PacingCharacter | PauseCharacter | None
    basis_refs: tuple[str, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.evidence_id, self.observed_scope_ref)
        if not isinstance(self.reference, ReferenceRef) or not isinstance(
            self.producer, ProducerRef
        ):
            raise TypeError("Reference and existing ProducerRef required")
        for value, kind in (
            (self.feature, StyleFeature),
            (self.knowledge, StyleKnowledge),
            (self.assertion, EvidenceAssertion),
            (self.strength, EvidenceStrength),
        ):
            _enum(value, kind)
        visible = self.feature in (StyleFeature.PACING, StyleFeature.PAUSE_PRESERVATION)
        if self.knowledge == StyleKnowledge.UNKNOWN:
            if self.assertion != EvidenceAssertion.UNKNOWN or self.value is not None:
                raise ValueError("UNKNOWN must not invent a value or negative assertion")
        elif self.assertion == EvidenceAssertion.UNKNOWN:
            raise ValueError("Unknown assertion requires UNKNOWN knowledge")
        elif visible and self.assertion == EvidenceAssertion.PRESENT:
            _enum(
                self.value,
                PacingCharacter if self.feature == StyleFeature.PACING else PauseCharacter,
            )
        elif self.value is not None:
            raise ValueError("Absent or hidden feature has no visible-style value")
        if (
            not visible
            and self.reference.form != ReferenceForm.EDITABLE
            and self.knowledge != StyleKnowledge.UNKNOWN
        ):
            raise ValueError("Rendered/unknown representation cannot establish hidden decisions")
        if (
            self.feature == StyleFeature.EDITOR_INTENTION
            and self.knowledge == StyleKnowledge.OBSERVED
            and self.producer.producer_kind != ProducerKind.HUMAN_SUPPLIED
        ):
            raise ValueError("Project structure does not directly reveal editor intention")
        object.__setattr__(self, "basis_refs", _refs(self.basis_refs, required=True))
        object.__setattr__(self, "limitations", _refs(self.limitations))


@dataclass(frozen=True)
class ProfileVersionRef:
    profile_id: str
    version: str

    def __post_init__(self) -> None:
        _text(self.profile_id, self.version)


@dataclass(frozen=True)
class StyleProfile:
    reference: ProfileVersionRef
    schema_version: str
    parent: ProfileVersionRef | None
    owner_ref: str
    scope: ScopeBinding
    preferences: tuple[StylePreference, ...]
    provenance_refs: tuple[str, ...]
    applicability: tuple[ScopeBinding, ...] = ()
    exclusions: tuple[ScopeBinding, ...] = ()
    approved_delta_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reference, ProfileVersionRef) or not isinstance(
            self.scope, ScopeBinding
        ):
            raise TypeError("Typed profile version/scope required")
        _text(self.schema_version, self.owner_ref)
        if self.parent is not None and (
            not isinstance(self.parent, ProfileVersionRef)
            or self.parent.profile_id != self.reference.profile_id
            or self.parent == self.reference
        ):
            raise ValueError("Exact distinct parent of the same profile required")
        object.__setattr__(self, "preferences", _preferences(self.preferences))
        for name in ("applicability", "exclusions"):
            object.__setattr__(self, name, _tuple(getattr(self, name), ScopeBinding))
        for name in ("provenance_refs", "approved_delta_refs", "approval_refs", "limitations"):
            object.__setattr__(
                self, name, _refs(getattr(self, name), required=name == "provenance_refs")
            )


@dataclass(frozen=True)
class HardStyleConstraint:
    """Supplied preference envelope, not a Safety verdict or policy engine."""

    dimension: StyleDimension
    allowed: tuple[StylePreference, ...] | None
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _enum(self.dimension, StyleDimension)
        if self.allowed is not None:
            values = _tuple(self.allowed, StylePreference)
            if any(p.dimension != self.dimension for p in values):
                raise ValueError("Wrong constraint dimension")
            object.__setattr__(self, "allowed", values)
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs, required=True))


@dataclass(frozen=True)
class StyleCapability:
    """Supplied support for consuming a dimension; never native qualification."""

    dimension: StyleDimension
    supported: bool | None
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _enum(self.dimension, StyleDimension)
        if self.supported is not None and type(self.supported) is not bool:
            raise TypeError("Explicit supplied support or unknown required")
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs, required=True))


class PreferenceOrigin(str, Enum):
    CURRENT_REQUEST = "CURRENT_REQUEST"
    REFERENCE = "REFERENCE"
    PROFILE = "PROFILE"
    ZERO_SHOT = "ZERO_SHOT"


@dataclass(frozen=True)
class SelectedStyle:
    dimension: StyleDimension
    origin: PreferenceOrigin
    preference: StylePreference | None
    profiles: tuple[StyleProfile, ...] = ()
    reference_evidence: tuple[StyleEvidence, ...] = ()

    def __post_init__(self) -> None:
        _enum(self.dimension, StyleDimension)
        _enum(self.origin, PreferenceOrigin)
        object.__setattr__(self, "profiles", _tuple(self.profiles, StyleProfile))
        object.__setattr__(
            self, "reference_evidence", _tuple(self.reference_evidence, StyleEvidence)
        )
        if self.origin == PreferenceOrigin.REFERENCE:
            if self.preference is not None or not self.reference_evidence:
                raise ValueError(
                    "Reference selection retains descriptors, not fabricated preference"
                )
        elif self.preference is None or self.preference.dimension != self.dimension:
            raise ValueError("Matching semantic preference required")


class StyleProblemReason(str, Enum):
    INTERPRETATION_UNRESOLVED = "INTERPRETATION_UNRESOLVED"
    REFERENCE_UNRESOLVED = "REFERENCE_UNRESOLVED"
    EVIDENCE_MISSING_OR_UNCERTAIN = "EVIDENCE_MISSING_OR_UNCERTAIN"
    CONFLICT = "CONFLICT"
    PREFERENCE_MISSING = "PREFERENCE_MISSING"
    HARD_CONSTRAINT = "HARD_CONSTRAINT"
    CAPABILITY_UNSUPPORTED_OR_UNKNOWN = "CAPABILITY_UNSUPPORTED_OR_UNKNOWN"


@dataclass(frozen=True)
class StyleProblem:
    dimension: StyleDimension
    reason: StyleProblemReason

    def __post_init__(self) -> None:
        _enum(self.dimension, StyleDimension)
        _enum(self.reason, StyleProblemReason)


@dataclass(frozen=True)
class EffectiveStyleContext:
    intent: StyleIntent
    profiles: tuple[StyleProfile, ...]
    reference_resolutions: tuple[ReferenceResolution, ...]
    evidence: tuple[StyleEvidence, ...]
    application_scopes: tuple[ScopeBinding, ...]
    selections: tuple[SelectedStyle, ...]
    problems: tuple[StyleProblem, ...]
    hard_constraints: tuple[HardStyleConstraint, ...]
    capabilities: tuple[StyleCapability, ...]
    hard_constraint_refs: tuple[str, ...]
    capability_refs: tuple[str, ...]
    modification_scope_ref: str
    defaults: tuple[StylePreference, ...]
    composition_rule_version: str = "style-composition-v1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.intent, StyleIntent)
            or self.modification_scope_ref != self.intent.modification_scope_ref
        ):
            raise ValueError("Modification scope must remain exactly bound to intent")
        for name, kind in (
            ("profiles", StyleProfile),
            ("reference_resolutions", ReferenceResolution),
            ("evidence", StyleEvidence),
            ("application_scopes", ScopeBinding),
            ("selections", SelectedStyle),
            ("problems", StyleProblem),
            ("hard_constraints", HardStyleConstraint),
            ("capabilities", StyleCapability),
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name), kind))
        for name in ("hard_constraint_refs", "capability_refs"):
            object.__setattr__(self, name, _refs(getattr(self, name)))
        object.__setattr__(self, "defaults", _preferences(self.defaults))
        _text(self.composition_rule_version)


_RANK = {
    PreferenceScope.PROJECT: 1,
    PreferenceScope.CHANNEL: 2,
    PreferenceScope.CONTENT_TYPE: 2,
    PreferenceScope.USER_DEFAULT: 3,
    PreferenceScope.TEAM: 4,
}


def compose_style(
    intent: StyleIntent,
    *,
    profiles: tuple[StyleProfile, ...] = (),
    evidence: tuple[StyleEvidence, ...] = (),
    application_scopes: tuple[ScopeBinding, ...] = (),
    hard_constraints: tuple[HardStyleConstraint, ...] = (),
    capabilities: tuple[StyleCapability, ...] = (),
    hard_constraint_refs: tuple[str, ...] = (),
    capability_refs: tuple[str, ...] = (),
    defaults: tuple[StylePreference, ...] = (),
) -> EffectiveStyleContext:
    """Resolve soft context per dimension; uncertainty blocks that dimension, not the editor."""
    profiles = _tuple(profiles, StyleProfile)
    evidence = _tuple(evidence, StyleEvidence)
    application_scopes = _tuple(application_scopes, ScopeBinding)
    hard_constraints = _tuple(hard_constraints, HardStyleConstraint)
    capabilities = _tuple(capabilities, StyleCapability)
    defaults = _preferences(defaults)
    if len({e.evidence_id for e in evidence}) != len(evidence):
        raise ValueError("Duplicate evidence ID")
    if len({p.reference for p in profiles}) != len(profiles):
        raise ValueError("Duplicate profile version")
    applicable = tuple(
        p
        for p in profiles
        if p.scope in application_scopes
        and set(p.applicability) <= set(application_scopes)
        and not set(p.exclusions) & set(application_scopes)
    )
    selections: list[SelectedStyle] = []
    problems: list[StyleProblem] = []
    R = StyleProblemReason
    resolution = intent.reference_resolution
    for dimension in sorted(intent.requested_dimensions, key=lambda d: d.value):

        def problem(reason: StyleProblemReason, subject: StyleDimension = dimension) -> None:
            problems.append(StyleProblem(subject, reason))

        if dimension in intent.unresolved_dimensions or (
            intent.unresolved_interpretation and not intent.unresolved_dimensions
        ):
            problem(R.INTERPRETATION_UNRESOLVED)
            continue
        current = next((p for p in intent.preferences if p.dimension == dimension), None)
        selected: SelectedStyle | None = None
        if intent.reference_query is not None and not intent.inherit_dimensions and current is None:
            problem(R.INTERPRETATION_UNRESOLVED)
            continue
        if dimension in intent.inherit_dimensions:
            if current is not None:
                problem(R.CONFLICT)
                continue
            if resolution is None or resolution.selected_ref is None:
                problem(R.REFERENCE_UNRESOLVED)
                continue
            # Recompute from retained declared input; a hand-built success label is not proof.
            if resolve_reference(resolution.query, resolution.catalog) != resolution:
                problem(R.REFERENCE_UNRESOLVED)
                continue
            records = tuple(
                e
                for e in evidence
                if e.reference == resolution.selected_ref and e.feature.value == dimension.value
            )
            if not records or any(
                e.knowledge != StyleKnowledge.OBSERVED or e.assertion != EvidenceAssertion.PRESENT
                for e in records
            ):
                problem(R.EVIDENCE_MISSING_OR_UNCERTAIN)
                continue
            if len({e.value for e in records}) != 1:
                problem(R.CONFLICT)
                continue
            selected = SelectedStyle(
                dimension, PreferenceOrigin.REFERENCE, None, reference_evidence=records
            )
        elif current is not None:
            selected = SelectedStyle(dimension, PreferenceOrigin.CURRENT_REQUEST, current)
        else:
            options = tuple(
                p for p in applicable if any(v.dimension == dimension for v in p.preferences)
            )
            if any(p.scope.scope == PreferenceScope.ONE_EDIT for p in options):
                # Applicability alone is not an explicit current request. Do not invent a tier.
                problem(R.INTERPRETATION_UNRESOLVED)
                continue
            if options:
                rank = min(_RANK[p.scope.scope] for p in options)
                best = tuple(p for p in options if _RANK[p.scope.scope] == rank)
                values = {v for p in best for v in p.preferences if v.dimension == dimension}
                ids = [p.reference.profile_id for p in best]
                if len(values) != 1 or len(set(ids)) != len(ids):
                    problem(R.CONFLICT)
                    continue
                selected = SelectedStyle(
                    dimension, PreferenceOrigin.PROFILE, next(iter(values)), best
                )
            else:
                default = next((p for p in defaults if p.dimension == dimension), None)
                if default is not None:
                    selected = SelectedStyle(dimension, PreferenceOrigin.ZERO_SHOT, default)
        if selected is None:
            problem(R.PREFERENCE_MISSING)
            continue
        support = tuple(c for c in capabilities if c.dimension == dimension)
        if not support or any(c.supported is not True for c in support):
            problem(R.CAPABILITY_UNSUPPORTED_OR_UNKNOWN)
            continue
        constraints = tuple(c for c in hard_constraints if c.dimension == dimension)
        if any(
            c.allowed is None or selected.preference is None or selected.preference not in c.allowed
            for c in constraints
        ):
            problem(R.HARD_CONSTRAINT)
            continue
        selections.append(selected)
    return EffectiveStyleContext(
        intent,
        profiles,
        (resolution,) if resolution is not None else (),
        evidence,
        application_scopes,
        tuple(selections),
        tuple(problems),
        hard_constraints,
        capabilities,
        hard_constraint_refs,
        capability_refs,
        intent.modification_scope_ref,
        defaults,
    )


@dataclass(frozen=True)
class PreferenceChange:
    dimension: StyleDimension
    before: StylePreference | None
    after: StylePreference | None

    def __post_init__(self) -> None:
        _enum(self.dimension, StyleDimension)
        if self.before == self.after:
            raise ValueError("Delta must describe a change")
        for value in (self.before, self.after):
            if value is not None and (
                not isinstance(value, StylePreference) or value.dimension != self.dimension
            ):
                raise ValueError("Change dimension mismatch")


@dataclass(frozen=True)
class StyleProfileDeltaProposal:
    proposal_id: str
    base: ProfileVersionRef
    requested_scope: ScopeBinding
    changes: tuple[PreferenceChange, ...]
    supporting_feedback: tuple[FeedbackEvent, ...]
    supporting_proposal_refs: tuple[str, ...]
    contrary_feedback: tuple[FeedbackEvent, ...]
    contrary_evidence_refs: tuple[str, ...]
    generalization_limitations: tuple[str, ...]
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.proposal_id)
        if not isinstance(self.base, ProfileVersionRef) or not isinstance(
            self.requested_scope, ScopeBinding
        ):
            raise TypeError("Exact base and scope required")
        changes = _tuple(self.changes, PreferenceChange)
        if not changes or len({c.dimension for c in changes}) != len(changes):
            raise ValueError("Nonempty unique changes required")
        object.__setattr__(self, "changes", changes)
        for name in ("supporting_feedback", "contrary_feedback"):
            object.__setattr__(self, name, _tuple(getattr(self, name), FeedbackEvent))
        for name in (
            "supporting_proposal_refs",
            "contrary_evidence_refs",
            "generalization_limitations",
            "provenance_refs",
        ):
            object.__setattr__(
                self,
                name,
                _refs(
                    getattr(self, name),
                    required=name in ("generalization_limitations", "provenance_refs"),
                ),
            )
        if any(
            e.proposal_id not in self.supporting_proposal_refs for e in self.supporting_feedback
        ):
            raise ValueError("Feedback must retain supporting proposal references")


@dataclass(frozen=True)
class StyleProfileApproval:
    """Supplied explicit profile approval only, never edit/apply authority."""

    approval_ref: str
    proposal: StyleProfileDeltaProposal
    owner_ref: str
    approver_ref: str
    new_version: str
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.approval_ref, self.owner_ref, self.approver_ref, self.new_version)
        if not isinstance(self.proposal, StyleProfileDeltaProposal):
            raise TypeError("Approval binds the entire immutable delta")
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs, required=True))


class ProfileUpdateStatus(str, Enum):
    CREATED = "CREATED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    STALE = "STALE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class ProfileUpdateResult:
    status: ProfileUpdateStatus
    base: StyleProfile
    proposal: StyleProfileDeltaProposal
    approval: StyleProfileApproval | None
    profile: StyleProfile | None

    def __post_init__(self) -> None:
        _enum(self.status, ProfileUpdateStatus)
        if (self.status == ProfileUpdateStatus.CREATED) != (self.profile is not None):
            raise ValueError("Only CREATED exposes a new profile")


def apply_profile_delta(
    profile: StyleProfile,
    proposal: StyleProfileDeltaProposal,
    approval: StyleProfileApproval | None,
) -> ProfileUpdateResult:
    """Create a value, not a durable write; approver authenticity is externally supplied."""
    S = ProfileUpdateStatus

    def stop(status: ProfileUpdateStatus) -> ProfileUpdateResult:
        return ProfileUpdateResult(status, profile, proposal, approval, None)

    if proposal.base != profile.reference:
        return stop(S.STALE)
    if approval is None:
        return stop(S.APPROVAL_REQUIRED)
    if (
        approval.proposal != proposal
        or approval.owner_ref != profile.owner_ref
        or proposal.requested_scope != profile.scope
        or approval.new_version == profile.reference.version
        or (profile.parent is not None and approval.new_version == profile.parent.version)
    ):
        return stop(S.CONFLICT)
    values = {v.dimension: v for v in profile.preferences}
    if any(values.get(c.dimension) != c.before for c in proposal.changes):
        return stop(S.CONFLICT)
    for change in proposal.changes:
        if change.after is None:
            values.pop(change.dimension, None)
        else:
            values[change.dimension] = change.after
    updated = replace(
        profile,
        reference=ProfileVersionRef(profile.reference.profile_id, approval.new_version),
        parent=profile.reference,
        preferences=tuple(values[d] for d in sorted(values, key=lambda d: d.value)),
        approved_delta_refs=profile.approved_delta_refs + (proposal.proposal_id,),
        approval_refs=profile.approval_refs + (approval.approval_ref,),
        provenance_refs=profile.provenance_refs
        + proposal.provenance_refs
        + approval.provenance_refs,
        limitations=profile.limitations + proposal.generalization_limitations,
    )
    return ProfileUpdateResult(S.CREATED, profile, proposal, approval, updated)
