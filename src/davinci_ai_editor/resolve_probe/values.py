"""Lossless typed raw values; only unordered-map ordering is normalized."""

import json
from dataclasses import dataclass
from typing import TypeAlias

Scalar: TypeAlias = str | int | bool | None


@dataclass(frozen=True)
class NativeValue:
    type_name: str
    scalar: Scalar = None
    children: tuple["NativeValue", ...] = ()
    entries: tuple[tuple["NativeValue", "NativeValue"], ...] = ()

    def __post_init__(self) -> None:
        if type(self.type_name) is not str or not self.type_name:
            raise ValueError("Exact runtime type required")
        if type(self.scalar) not in (str, int, bool, type(None)):
            raise TypeError("Raw scalar must be immutable and JSON representable")
        children = tuple(self.children)
        entries = tuple(tuple(pair) for pair in self.entries)
        if any(not isinstance(v, NativeValue) for v in children):
            raise TypeError("Typed child required")
        if any(len(p) != 2 or any(not isinstance(v, NativeValue) for v in p) for p in entries):
            raise TypeError("Typed key/value pairs required")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "entries", entries)

    def record(self) -> dict[str, object]:
        return {
            "type": self.type_name,
            "scalar": self.scalar,
            "children": [v.record() for v in self.children],
            "entries": [[k.record(), v.record()] for k, v in self.entries],
        }


def freeze(value: object) -> NativeValue:
    kind = type(value)
    name = kind.__module__ + "." + kind.__qualname__
    if value is None or kind in (str, bool, int):
        assert isinstance(value, (str, bool, int)) or value is None
        return NativeValue(name, value)
    if kind is float:
        assert isinstance(value, float)
        return NativeValue(name, value.hex())
    if isinstance(value, (list, tuple)):
        return NativeValue(name, children=tuple(freeze(v) for v in value))
    if isinstance(value, dict):
        return NativeValue(name, entries=tuple((freeze(k), freeze(v)) for k, v in value.items()))
    # Native handles are not serializable identities. Preserve type, not process address/repr.
    return NativeValue(name, "<opaque-native-object>")


def semantic(value: NativeValue) -> NativeValue:
    return NativeValue(
        value.type_name,
        value.scalar,
        tuple(semantic(v) for v in value.children),
        tuple(
            sorted(
                ((semantic(k), semantic(v)) for k, v in value.entries),
                key=lambda pair: canonical(pair[0].record()),
            )
        ),
    )


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def opaque(value: NativeValue) -> bool:
    return value.scalar == "<opaque-native-object>" and value.type_name != "builtins.str"


def contains_opaque(value: NativeValue) -> bool:
    return (
        opaque(value)
        or any(contains_opaque(v) for v in value.children)
        or any(contains_opaque(k) or contains_opaque(v) for k, v in value.entries)
    )
