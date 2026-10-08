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
    assert 'FREE_CANARY|' in text
