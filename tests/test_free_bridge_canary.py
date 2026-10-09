from pathlib import Path


def test_free_canary_is_strictly_read_only_and_local_only():
    text = Path("tools/free_bridge_probe/resolve_free_canary.lua").read_text(encoding="utf-8")

    required_reads = {
        "GetResolve",
        "GetProductName",
        "GetVersionString",
        "GetProjectManager",
        "GetCurrentDatabase",
        "GetCurrentProject",
        "GetName",
        "GetUniqueId",
        "GetCurrentTimeline",
        "GetStartFrame",
        "GetEndFrame",
    }
    assert all(token in text for token in required_reads)

    forbidden = (
        "SetCurrent",
        "SetTrack",
        "AddTrack",
        "Delete",
        "ImportMedia",
        "AppendToTimeline",
        "AddMarker",
        "UpdateMarker",
        "DeleteMarker",
        "CreateTimeline",
        "CreateProject",
        "SaveProject",
        "loadstring",
        "eval(",
        "load(",
        "UIManager",
        "os.remove",
        "io.write",
        "dofile",
        "io.open",
        "io.popen",
        "os.execute",
        "socket",
        "http",
        "require(",
    )
    assert not any(token in text for token in forbidden)
    assert "pcall" in text
    assert "FREE_CANARY|" in text


def test_boot_precedes_root_acquisition_and_global_resolve_has_priority():
    text = Path("tools/free_bridge_probe/resolve_free_canary.lua").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    ).lstrip()
    assert code.startswith('print("FREE_CANARY|BOOT|START")')
    assert "if resolve ~= nil then" in code
    assert "resolve_instance = resolve" in code
    assert "app:GetResolve()" in code
    assert code.index("if resolve ~= nil then") < code.index("app:GetResolve()")
    assert "local resolve =" not in code
    for label in ("GLOBAL_RESOLVE", "APP_GETRESOLVE", "APP_GETRESOLVE_ERROR", "ROOT_ERROR"):
        assert label in code
