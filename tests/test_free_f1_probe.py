import re
from pathlib import Path

PROBE = Path("tools/free_bridge_probe/resolve_free_f1.lua")
EXPECTED = {
    "GetProductName",
    "GetVersionString",
    "GetProjectManager",
    "GetCurrentProject",
    "GetCurrentTimeline",
    "GetUniqueId",
    "GetName",
    "GetStartFrame",
    "GetEndFrame",
    "GetTrackCount",
    "GetItemListInTrack",
    "GetStart",
    "GetEnd",
    "GetDuration",
    "GetMediaPoolItem",
    "GetMediaId",
}


def source():
    return PROBE.read_text(encoding="utf-8")


def test_f1_fixed_allowlist_matches_all_literal_native_calls():
    code = source()
    declared = set(re.findall(r"^    (Get\w+) = true,", code, re.MULTILINE))
    called = set(re.findall(r":(Get\w+)\(", code))
    assert declared == called == EXPECTED
    assert "parent[method]" not in code and "object[method]" not in code
    assert "pcall(operation)" in code


def test_f1_no_mutation_io_network_dynamic_or_persistent_surface():
    code = source()
    assert code.startswith("-- TASK-023 F1")
    for token in (
        "io.",
        "os.",
        "require(",
        "load(",
        "loadstring",
        "dofile",
        "socket",
        "http",
        "UIManager",
        "while ",
        "repeat ",
        "SetCurrent",
        "SetProperty",
        "CreateProject",
        "Delete",
        "ImportMedia",
        "AppendToTimeline",
        "AddMarker",
        "SaveProject",
        "execute(",
        "eval(",
        "debug.",
    ):
        assert token not in code
    assert "FREE_F1|BOOT|START" in code
    assert "FREE_F1|END|" in code
    assert "global_resolve = resolve" in code
    assert "app:GetResolve" not in code


def test_f1_evidence_vocabulary_and_distinct_failures():
    code = source()
    for token in (
        "AVAILABLE_TYPED",
        "AVAILABLE_AMBIGUOUS",
        "UNAVAILABLE",
        "UNKNOWN",
        "VALUE",
        "NIL",
        "ERROR",
        "PARENT_NOT_OBSERVED",
        "RAW_ONLY",
        "NOT_ESTABLISHED",
        "OPAQUE",
        "NONCALLABLE",
        "SERIALIZATION_ERROR",
    ):
        assert '"' + token + '"' in code
    assert "type(value)" in code
    assert 'string.format("%.17g", value)' in code
    assert "table.sort(entries)" in code
    assert "value == nil" in code
    assert "member == nil" in code
    assert "pcall(function() return raw_value(value) end)" in code
    assert "tostring(value)" not in code


def test_f1_no_semantic_repairs_or_inferred_correspondence():
    code = source()
    for token in (
        "math.floor",
        "math.ceil",
        "FrameRange",
        "ripple",
        "APPROVED",
        "PERSISTENT_VERIFIED",
        "SafetyVerdict",
        "READY_TO_REASON",
        "or 0",
        "or false",
    ):
        assert token not in code
    assert 'for _, track_type in ipairs({"video", "audio", "subtitle"})' in code
    assert "pairs(items)" in code
    assert "local global_resolve = resolve" in code
    assert "diagnostic paths are not native identities" in code


def test_f1_never_claims_native_support_from_static_tests():
    spec = Path("tasks/TASK_023_F1_READ_CAPABILITY_MAP.md").read_text(encoding="utf-8-sig")
    assert "Static tests do not execute Lua" in spec
    assert "F2/F3" in spec and "NOT AUTHORIZED" in spec


def test_f1_p3_mixed_collection_metadata_does_not_gate_items():
    fixture = Path("tests/fixtures/free_f1_mixed_collection.lua").read_text(encoding="utf-8")
    assert '["__flags"] = 4194304' in fixture
    assert '[1] = opaque_item' in fixture
    code = source()
    collection = code.split("local function inspect_collection", 1)[1].split(
        "local function inspect_timeline", 1
    )[0]
    assert "for key, value in pairs(items) do" in collection
    assert 'type(key) ~= "number"' in collection
    assert "raw_value(key)" in collection and "raw_value(value)" in collection
    assert '"COLLECTION_METADATA"' in collection
    assert "table.sort(metadata)" in collection
    assert "table.sort(keys)" in collection
    assert "for _, key in ipairs(keys) do" in collection
    assert "inspect_item(item," in collection
    assert "if valid then" not in collection
    assert "INVALID_ENUMERATION_KEYS" not in code
    assert "__flags" not in code  # No special-case interpretation or dropping.


def test_f1_malformed_entry_is_diagnosed_individually():
    code = source()
    assert '"INVALID_ITEM_ENTRY"' in code
    assert '"INVALID_ENUMERATION_KEY"' in code
    assert 'type(item) == "table" or type(item) == "userdata"' in code
    assert 'key >= 1 and key < math.huge and key % 1 == 0' in code
    assert '"COLLECTION_METADATA_ERROR"' in code
    assert '"COLLECTION_METADATA"' in code

    assert 'if shape == "collection" and type(value) == "table" then return value end' in code
