"""JSON Schema files for the data contracts (spec section 6), and a small validator.

The core may not depend on jsonschema (section 4.1), so this module checks
documents itself. It supports only the keywords listed in KEYWORDS and refuses
a schema that uses any other keyword, so a schema cannot silently ask for a
check that is not made. Tests compare its verdicts with the jsonschema library.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from musegauge.errors import SchemaError

SCHEMA_DIR = Path(__file__).resolve().parent
NAMES = ("clip", "manifest", "suite", "request", "response", "prefetch", "results")

KEYWORDS = {
    "type", "properties", "required", "additionalProperties", "items", "enum", "const",
    "pattern", "minLength", "minimum", "exclusiveMinimum", "maximum", "minItems", "anyOf",
    "$ref", "$defs",
}
ANNOTATIONS = {"$schema", "$id", "title", "description", "$comment"}

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool))
    or (isinstance(v, float) and v.is_integer()),
}


@cache
def load_schema(name: str) -> dict:
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    _check_keywords(schema, f"{name}.schema.json")
    return schema


def _check_keywords(node: Any, where: str) -> None:
    if isinstance(node, dict):
        unknown = set(node) - KEYWORDS - ANNOTATIONS
        if unknown:
            raise ValueError(f"{where}: unsupported schema keywords {sorted(unknown)}")
        for key, value in node.items():
            if key in ("properties", "$defs"):
                for sub_name, sub in value.items():
                    _check_keywords(sub, f"{where}/{key}/{sub_name}")
            elif key in ("items", "additionalProperties") and isinstance(value, dict):
                _check_keywords(value, f"{where}/{key}")
            elif key == "anyOf":
                for i, sub in enumerate(value):
                    _check_keywords(sub, f"{where}/anyOf/{i}")


def problems(instance: Any, name: str) -> list[str]:
    """Return a list of problems, one line each. Empty means valid."""
    schema = load_schema(name)
    out: list[str] = []
    _validate(instance, schema, schema, "$", out)
    return out


def check(instance: Any, name: str) -> None:
    """Raise SchemaError if the instance does not match the named schema."""
    found = problems(instance, name)
    if found:
        raise SchemaError(name, found)


def _validate(value: Any, schema: dict, root: dict, path: str, out: list[str]) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"unsupported $ref {ref!r}")
        _validate(value, root["$defs"][ref[len("#/$defs/"):]], root, path, out)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](value) for t in types):
            out.append(f"{path}: expected {' or '.join(types)}, got {_describe(value)}")
            return
    if "const" in schema and not _equal(value, schema["const"]):
        out.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and not any(_equal(value, e) for e in schema["enum"]):
        out.append(f"{path}: must be one of {schema['enum']!r}, got {value!r}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(f"{path}: shorter than {schema['minLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{path}: {value!r} does not match {schema['pattern']!r}")
    if _TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{path}: {value} is below {schema['minimum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            out.append(f"{path}: {value} must be above {schema['exclusiveMinimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{path}: {value} is above {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{path}: needs at least {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                _validate(item, schema["items"], root, f"{path}[{i}]", out)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                out.append(f"{path}: missing required field {key!r}")
        for key, item in value.items():
            if key in props:
                _validate(item, props[key], root, f"{path}.{key}", out)
            elif schema.get("additionalProperties") is False:
                out.append(f"{path}: unexpected field {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate(item, schema["additionalProperties"], root, f"{path}.{key}", out)
    if "anyOf" in schema:
        branches = []
        for sub in schema["anyOf"]:
            sub_out: list[str] = []
            _validate(value, sub, root, path, sub_out)
            if not sub_out:
                return
            branches.append(sub_out)
        out.append(f"{path}: matches none of the allowed forms ({'; '.join(b[0] for b in branches)})")


def _equal(a: Any, b: Any) -> bool:
    # JSON Schema equality: true is not 1, false is not 0.
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b


def _describe(value: Any) -> str:
    if value is None:
        return "null"
    return {bool: "boolean", int: "integer", float: "number", str: "string", list: "array",
            dict: "object"}.get(type(value), type(value).__name__)
