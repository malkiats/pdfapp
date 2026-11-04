"""Contract drift test (docs/api.md section 8).

Fails the build when the API that FastAPI serves drifts from shared/openapi.yaml:

1. Every contract operation with x-phase <= IMPLEMENTED_PHASE exists (method + path), and no
   /api/v1 operation exists that the contract lacks. Later-phase operations are reported as
   skipped ("not yet implemented"), never silently ignored.
2. operationId, documented status codes (minus FastAPI's auto 422 when the contract has none),
   response media types, parameters and security are equal per implemented operation.
3. Every request/response schema reachable from an implemented operation is equal after
   normalization (drops title/description/examples/default/x-*, treats nullable unions and
   `type: [X, "null"]` alike, compares type/properties/required/enum/format/pattern/limits/
   additionalProperties/items).
4. createJob multipart part names (Phase 2) - skipped until then.
5. Every example in the contract validates against its generated model (or, for schemas the
   generator collapsed into plain types, against the contract schema itself).
6. Tool equals tool-catalog.schema.json#/$defs/Tool; the catalog validates, slugs are unique,
   options_schema names exist.
Also: the generated models are up to date with the contract, and nothing under app/schemas
outside `generated/` re-declares a contract model.
"""

from __future__ import annotations

import ast
import copy
import json
import shutil
import subprocess
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Any

import pdfapp.backend.app.schemas.generated.models as generated
import pytest
import yaml
from jsonschema import Draft202012Validator
from pdfapp.backend.app.main import create_app
from pdfapp.backend.tests.conftest import (
    CATALOG_PATH,
    CATALOG_SCHEMA_PATH,
    OPENAPI_PATH,
    make_settings,
)
from pydantic import BaseModel

IMPLEMENTED_PHASE = 1
# Later-phase operations that already ship and are therefore checked in full.
IMPLEMENTED_AHEAD = frozenset({"createUpload", "runUploadedTool", "deleteUpload"})
HTTP_METHODS = ("get", "put", "post", "delete", "patch", "options", "head")
API_PREFIX = "/api/v1"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

CONTRACT: dict[str, Any] = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
CATALOG_SCHEMA: dict[str, Any] = json.loads(CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))

# Keywords compared by the normalizer.
KEEP = {
    "type",
    "properties",
    "required",
    "enum",
    "format",
    "pattern",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "additionalProperties",
    "items",
    "minProperties",
}
# Formats pydantic has no type for, so the generator emits a plain `str` without them.
UNREPRESENTABLE_FORMATS = {"uri-reference"}


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    app = create_app(make_settings(tmp_path_factory.mktemp("contract")))
    return app.openapi()


# ------------------------------------------------------------------ normalizer
def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    assert ref.startswith("#/"), ref
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    assert isinstance(node, dict)
    return node


def normalize(schema: Any, root: dict[str, Any], depth: int = 0) -> Any:
    assert depth < 50, "schema recursion too deep"
    if not isinstance(schema, dict):
        return schema
    schema = dict(schema)
    while "$ref" in schema:
        ref = schema.pop("$ref")
        schema = {**_resolve_ref(ref, root), **schema}
    if "allOf" in schema and len(schema["allOf"]) == 1:
        inner = schema.pop("allOf")[0]
        schema = {**normalize(inner, root, depth + 1), **schema}
    nullable = False
    for union in ("anyOf", "oneOf"):
        if union in schema:
            raw = schema.pop(union)
            branches = [normalize(b, root, depth + 1) for b in raw]
            keep = [i for i, b in enumerate(branches) if b != {"type": "null"}]
            nullable = len(keep) < len(raw)
            if len(keep) == 1:
                # `X | None` style union: compare X itself, flagged nullable.
                merged = normalize({**raw[keep[0]], **schema}, root, depth + 1)
                if nullable:
                    merged["nullable"] = True
                return merged
            schema["anyOf"] = sorted(json.dumps(branches[i], sort_keys=True) for i in keep)
    if isinstance(schema.get("type"), list):
        types = [t for t in schema["type"] if t != "null"]
        nullable = nullable or len(types) < len(schema["type"])
        schema["type"] = types[0] if len(types) == 1 else sorted(types)
    if "const" in schema:
        schema["enum"] = [schema.pop("const")]
    if schema.get("format") in UNREPRESENTABLE_FORMATS:
        schema.pop("format")
    if schema.get("format") == "uri" and schema.get("minLength") == 1:
        # pydantic's AnyUrl always emits minLength 1; an empty string is never a uri anyway.
        schema.pop("minLength")
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "anyOf":
            out[key] = value
        elif key not in KEEP:
            continue
        elif key == "properties":
            required = set(schema.get("required", []))
            props = {}
            for name, prop in value.items():
                norm = normalize(prop, root, depth + 1)
                if name not in required and isinstance(norm, dict):
                    norm.pop("nullable", None)  # optional: null-ability is not on the wire
                props[name] = norm
            out[key] = props
        elif key in ("items", "additionalProperties"):
            out[key] = normalize(value, root, depth + 1) if isinstance(value, dict) else value
        elif key == "enum":
            out[key] = sorted(value, key=str)
        elif key == "required":
            if value:
                out[key] = sorted(value)
        else:
            out[key] = value
    if nullable:
        out["nullable"] = True
    return out


# ------------------------------------------------------------------ operations
def contract_operations() -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in CONTRACT["paths"].items():
        for method in HTTP_METHODS:
            if method in item:
                yield path, method, item[method]


OPERATIONS = list(contract_operations())
OP_IDS = [op["operationId"] for _, _, op in OPERATIONS]


def _is_future(op: dict[str, Any]) -> bool:
    return (
        int(op.get("x-phase", 1)) > IMPLEMENTED_PHASE and op["operationId"] not in IMPLEMENTED_AHEAD
    )


def _skip_if_future(op: dict[str, Any]) -> None:
    phase = int(op.get("x-phase", 1))
    if _is_future(op):
        pytest.skip(
            f"{op['operationId']}: x-phase {phase} > IMPLEMENTED_PHASE {IMPLEMENTED_PHASE} "
            "(not yet implemented)"
        )


def _served_op(served: dict[str, Any], path: str, method: str) -> dict[str, Any]:
    item = served["paths"].get(path)
    assert item is not None, f"{path} is not served"
    assert method in item, f"{method.upper()} {path} is not served"
    return dict(item[method])


@pytest.mark.parametrize(("path", "method", "op"), OPERATIONS, ids=OP_IDS)
def test_operation_exists_with_same_id(
    served: dict[str, Any], path: str, method: str, op: dict[str, Any]
) -> None:
    if _is_future(op):
        item = served["paths"].get(path, {})
        assert method not in item, f"{op['operationId']} is served before its phase"
    _skip_if_future(op)
    assert _served_op(served, path, method)["operationId"] == op["operationId"]


def test_no_extra_api_operations(served: dict[str, Any]) -> None:
    contract = {(p, m) for p, m, _ in OPERATIONS}
    extra = [
        (p, m)
        for p, item in served["paths"].items()
        for m in item
        if m in HTTP_METHODS and p.startswith(API_PREFIX) and (p, m) not in contract
    ]
    assert extra == []


@pytest.mark.parametrize(("path", "method", "op"), OPERATIONS, ids=OP_IDS)
def test_status_codes_media_types_and_security(
    served: dict[str, Any], path: str, method: str, op: dict[str, Any]
) -> None:
    _skip_if_future(op)
    mine = _served_op(served, path, method)
    contract_codes = set(op["responses"])
    served_codes = set(mine["responses"])
    if "422" not in contract_codes:
        served_codes.discard("422")
    assert served_codes == contract_codes
    for code in contract_codes:
        want = set(contract_response(op["responses"][code]).get("content", {}))
        got = set(mine["responses"][code].get("content", {}))
        assert got == want, f"{op['operationId']} {code} media types"
    assert mine.get("security", []) == op.get("security", CONTRACT.get("security", []))


def contract_response(response: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in response:
        return _resolve_ref(response["$ref"], CONTRACT)
    return response


@pytest.mark.parametrize(("path", "method", "op"), OPERATIONS, ids=OP_IDS)
def test_parameters_match(
    served: dict[str, Any], path: str, method: str, op: dict[str, Any]
) -> None:
    _skip_if_future(op)
    mine = _served_op(served, path, method)

    def params(raw: list[dict[str, Any]], root: dict[str, Any]) -> dict[tuple[str, str], Any]:
        out = {}
        for param in raw:
            param = _resolve_ref(param["$ref"], root) if "$ref" in param else param
            schema = normalize(param.get("schema", {}), root)
            if not param.get("required", False):
                schema.pop("nullable", None)
            out[(param["in"], param["name"].lower())] = (bool(param.get("required")), schema)
        return out

    assert params(mine.get("parameters", []), served) == params(op.get("parameters", []), CONTRACT)


@pytest.mark.parametrize(("path", "method", "op"), OPERATIONS, ids=OP_IDS)
def test_reachable_schemas_match(
    served: dict[str, Any], path: str, method: str, op: dict[str, Any]
) -> None:
    _skip_if_future(op)
    mine = _served_op(served, path, method)
    for code, response in op["responses"].items():
        for media, body in contract_response(response).get("content", {}).items():
            want = normalize(body.get("schema", {}), CONTRACT)
            got = normalize(mine["responses"][code]["content"][media].get("schema", {}), served)
            assert got == want, f"{op['operationId']} {code} {media}"
    if "requestBody" in op:
        for media, body in op["requestBody"].get("content", {}).items():
            want = normalize(body["schema"], CONTRACT)
            got = normalize(mine["requestBody"]["content"][media]["schema"], served)
            assert got == want


def test_create_job_multipart_parts() -> None:
    op = CONTRACT["paths"]["/api/v1/jobs"]["post"]
    _skip_if_future(op)
    pytest.fail("implement the multipart part-name comparison when createJob ships")


# ------------------------------------------------------------------ examples
def _examples(schema: dict[str, Any]) -> list[Any]:
    found = list(schema.get("examples", []))
    if "example" in schema:
        found.append(schema["example"])
    return found


def _validate_with_model(name: str, value: Any) -> bool:
    model = getattr(generated, name, None)
    if isinstance(model, type) and issubclass(model, BaseModel):
        model.model_validate(value)
        return True
    if isinstance(model, type) and issubclass(model, Enum):
        model(value)
        return True
    return False


def _validate_with_schema(name: str, value: Any) -> None:
    doc = copy.deepcopy(CONTRACT)
    schema = {**doc["components"]["schemas"][name], "components": doc["components"]}
    Draft202012Validator(schema).validate(value)


SCHEMA_EXAMPLES = [
    (name, i, example)
    for name, schema in CONTRACT["components"]["schemas"].items()
    for i, example in enumerate(_examples(schema))
]


@pytest.mark.parametrize(
    ("name", "index", "example"), SCHEMA_EXAMPLES, ids=[f"{n}[{i}]" for n, i, _ in SCHEMA_EXAMPLES]
)
def test_schema_examples_validate(name: str, index: int, example: Any) -> None:
    if not _validate_with_model(name, example):
        _validate_with_schema(name, example)


def _response_examples() -> Iterator[tuple[str, str, Any]]:
    responses = [contract_response(r) for _, _, op in OPERATIONS for r in op["responses"].values()]
    responses += list(CONTRACT["components"]["responses"].values())
    for response in responses:
        for body in response.get("content", {}).values():
            ref = body.get("schema", {}).get("$ref", "")
            name = ref.rsplit("/", 1)[-1]
            for label, example in body.get("examples", {}).items():
                yield name, label, example["value"]


RESPONSE_EXAMPLES = list(_response_examples())


@pytest.mark.parametrize(
    ("name", "label", "value"),
    RESPONSE_EXAMPLES,
    ids=[f"{n}:{label}" for n, label, _ in RESPONSE_EXAMPLES],
)
def test_response_examples_validate(name: str, label: str, value: Any) -> None:
    assert name, f"example {label} has no schema $ref"
    if not _validate_with_model(name, value):
        _validate_with_schema(name, value)


# ------------------------------------------------------------------ catalog
def test_tool_schema_equals_catalog_schema() -> None:
    contract_tool = normalize({"$ref": "#/components/schemas/Tool"}, CONTRACT)
    catalog_tool = normalize({"$ref": "#/$defs/Tool"}, CATALOG_SCHEMA)
    assert catalog_tool == contract_tool


def test_catalog_validates_and_is_consistent() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(CATALOG_SCHEMA).validate(catalog)
    slugs = [t["slug"] for t in catalog["tools"]]
    assert len(slugs) == len(set(slugs))
    schemas = CONTRACT["components"]["schemas"]
    for tool in catalog["tools"]:
        name = tool["options_schema"]
        assert name is None or (name.startswith("Options") and name in schemas), tool["slug"]


# ------------------------------------------------------------------ generated code
def test_no_hand_mirrored_contract_models() -> None:
    contract_names = set(CONTRACT["components"]["schemas"])
    offenders = []
    for file in (BACKEND_ROOT / "app" / "schemas").rglob("*.py"):
        if "generated" in file.parts:
            continue
        tree = ast.parse(file.read_text(encoding="utf-8"))
        offenders += [
            f"{file.name}:{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name in contract_names
        ]
    assert offenders == []


@pytest.fixture
def codegen_out() -> Iterator[Path]:
    # Must live inside backend/: the ruff-format pass picks up pyproject.toml (line-length
    # 100) from the output location, exactly like `make codegen` and the CI drift step.
    out_dir = BACKEND_ROOT / "var" / "codegen-check"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield out_dir / "models.py"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_generated_models_are_current(codegen_out: Path) -> None:
    exe = shutil.which("datamodel-codegen")
    if exe is None:
        pytest.skip("datamodel-codegen not installed (dev dependency)")
    out = codegen_out
    subprocess.run(  # noqa: S603 - fixed argv, no user input
        [
            exe,
            "--input", str(OPENAPI_PATH), "--input-file-type", "openapi",
            "--output", str(out),
            "--output-model-type", "pydantic_v2.BaseModel", "--target-python-version", "3.12",
            "--use-annotated", "--field-constraints", "--use-standard-collections",
            "--use-union-operator", "--use-subclass-enum", "--use-schema-description",
            "--disable-timestamp", "--reuse-model", "--strict-nullable",
            "--collapse-root-models", "--formatters", "ruff-format",
        ],
        check=True,
        capture_output=True,
        cwd=BACKEND_ROOT,
    )  # fmt: skip
    committed = (BACKEND_ROOT / "app" / "schemas" / "generated" / "models.py").read_text()
    regenerated = out.read_text()
    # The header names the input file; only the body must match.
    strip = lambda text: text.split("\n", 2)[2]  # noqa: E731
    assert strip(regenerated) == strip(committed), "regenerate app/schemas/generated/models.py"
