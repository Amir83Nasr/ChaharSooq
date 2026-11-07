"""OpenAPI contract guards.

Every operation must carry a tag, summary, description, and stable
`operationId`, and every protected operation must advertise the session
cookie. This keeps Swagger useful as routes are added.
"""

from typing import Any

from app.api.openapi import TAGS_METADATA
from app.main import create_app

_PUBLIC_OPERATIONS = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/ready"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
}


def _schema() -> dict[str, Any]:
    return create_app().openapi()


def test_every_operation_is_documented() -> None:
    schema = _schema()
    tag_names = {tag["name"] for tag in TAGS_METADATA}
    operation_ids: list[str] = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            label = f"{method.upper()} {path}"
            assert operation.get("summary"), f"{label} has no summary"
            assert operation.get("description"), f"{label} has no description"
            assert operation.get("tags"), f"{label} has no tag"
            assert set(operation["tags"]) <= tag_names, f"{label} uses an undeclared tag"
            assert operation.get("operationId"), f"{label} has no operationId"
            operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids)), "operationIds must be unique"


def test_protected_operations_advertise_the_session_cookie() -> None:
    schema = _schema()
    scheme = schema["components"]["securitySchemes"]["SessionCookie"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "cookie"
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if (method.upper(), path) in _PUBLIC_OPERATIONS:
                continue
            assert operation.get("security") == [{"SessionCookie": []}], (
                f"{method.upper()} {path} is missing the session cookie requirement"
            )


def test_error_responses_use_the_shared_envelope() -> None:
    schema = _schema()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status in ("401", "404", "409", "422", "429", "503"):
                response = operation["responses"].get(status)
                if response is None:
                    continue
                ref = response["content"]["application/json"]["schema"]["$ref"]
                assert ref == "#/components/schemas/ErrorEnvelope", (
                    f"{method.upper()} {path} {status} does not use ErrorEnvelope"
                )
