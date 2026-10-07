"""Fixed installed bridge connection. No script text, project lookup or activation."""

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

INSTALLED_SCRIPTING = Path(
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
)


def connect_installed() -> object | None:
    # Only the documented installed vendor module. No caller-supplied Python/module path.
    directory = INSTALLED_SCRIPTING / "Modules"
    if not (directory / "DaVinciResolveScript.py").is_file():
        raise RuntimeError("INSTALLED_BRIDGE_UNAVAILABLE")
    location = str(directory)
    if location not in sys.path:
        sys.path.append(location)
    module = importlib.import_module("DaVinciResolveScript")
    factory = cast(Callable[[str], object | None], module.scriptapp)
    return factory("Resolve")
