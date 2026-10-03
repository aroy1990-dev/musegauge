"""The schema files, the example files, and the built-in validator against jsonschema."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from musegauge import schemas
from musegauge.errors import SchemaError

DATA = Path(__file__).resolve().parents[1] / "data"


def examples() -> list[tuple[str, object]]:
    out = [("clip", json.loads(line)) for line in (DATA / "clips.example.jsonl").read_text().splitlines()]
    out.append(("manifest", yaml.safe_load((DATA / "manifest.example.yaml").read_text())))
    out.append(("suite", yaml.safe_load((DATA / "suite.example.yaml").read_text())))
    for name in ("request", "response", "prefetch", "results"):
        out.append((name, json.loads((DATA / f"{name}.example.json").read_text())))
    return out


def theirs(doc, name) -> bool:
    return jsonschema.Draft202012Validator(schemas.load_schema(name)).is_valid(doc)


def ours(doc, name) -> bool:
    return not schemas.problems(doc, name)


def mutations(doc):
    """Yield documents that differ from doc at one place: removed, retyped, or an extra key."""
    replacements = [None, "text", 1.5, 7, True, [], {}, -3]

    def walk(node, path):
        if isinstance(node, dict):
            yield path, node
            for key, value in node.items():
                yield from walk(value, path + [key])
        elif isinstance(node, list):
            yield path, node
            for i, value in enumerate(node):
                yield from walk(value, path + [i])
        else:
            yield path, node

    def put(root, path, value, delete=False):
        new = copy.deepcopy(root)
        target = new
        for step in path[:-1]:
            target = target[step]
        if delete:
            del target[path[-1]]
        else:
            target[path[-1]] = value
        return new

    for path, node in list(walk(doc, [])):
        if path:
            for value in replacements:
                yield put(doc, path, value)
            if isinstance(path[-1], str):
                yield put(doc, path, None, delete=True)
        if isinstance(node, dict):
            extra = copy.deepcopy(doc)
            target = extra
            for step in path:
                target = target[step]
            target["zz_extra"] = 1
            yield extra


@pytest.mark.parametrize("name", schemas.NAMES)
def test_schema_files_are_valid_draft_2020_12(name):
    jsonschema.Draft202012Validator.check_schema(schemas.load_schema(name))


@pytest.mark.parametrize("name,doc", examples(), ids=lambda x: x if isinstance(x, str) else "")
def test_examples_pass_both_validators(name, doc):
    assert schemas.problems(doc, name) == []
    assert theirs(doc, name)


@pytest.mark.parametrize("name,doc", examples(), ids=lambda x: x if isinstance(x, str) else "")
def test_validator_agrees_with_jsonschema_on_mutations(name, doc):
    count = 0
    for mutated in mutations(doc):
        count += 1
        assert ours(mutated, name) == theirs(mutated, name), json.dumps(mutated)[:400]
    assert count > 10


def test_every_example_contract_has_a_file():
    assert {name for name, _ in examples()} == set(schemas.NAMES)


def test_integer_and_boolean_semantics_match_jsonschema():
    for value in (1, 1.0, 1.5, True, False, None, "1"):
        doc = {"schema": 1, "suite_id": "x", "version": value, "description": "", "metrics": ["a.b@1"]}
        assert ours(doc, "suite") == theirs(doc, "suite"), value
    for value in (1, 1.0, True):
        doc = {"schema": value, "suite_id": "x", "version": 1, "description": "", "metrics": ["a.b@1"]}
        assert ours(doc, "suite") == theirs(doc, "suite"), value


def test_check_raises_with_one_line_per_problem():
    with pytest.raises(SchemaError) as info:
        schemas.check({"clip_id": "bad id!", "extra": 1}, "clip")
    assert len(info.value.problems) == 2  # bad pattern, missing path


def test_unsupported_keyword_is_refused():
    with pytest.raises(ValueError, match="unsupported schema keywords"):
        schemas._check_keywords({"type": "object", "oneOf": []}, "test")


def test_json_written_by_the_tool_rejects_nan():
    with pytest.raises(ValueError):
        json.dumps({"value": float("nan")}, allow_nan=False)
