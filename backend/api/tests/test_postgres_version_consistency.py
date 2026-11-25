"""PostgreSQL version pins must stay aligned across the runtime manifests.

Production's Compose file is the canonical pin. Development and CI may follow a
newer minor within the same major, but a major drift would make tests pass
against a different server than Production. The end of the temporary 18 CI leg
is recorded in ADR 028.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

PRODUCTION_COMPOSE = REPO_ROOT / "compose.production.yml"
LOCAL_COMPOSE = REPO_ROOT / "compose.local.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
API_DOCKERFILE = REPO_ROOT / "Dockerfile.api"
UPGRADE_ADR = REPO_ROOT / "docs" / "adr" / "028-postgresql-19-upgrade-readiness.md"

POSTGRES_TAG = re.compile(r"postgres:(\d{2}(?:\.\d+)*(?:-[a-z]+)?)(?![\d.])")
CLIENT_PACKAGE = re.compile(r"postgresql-client-(\d{2})")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _postgres_refs(path: Path) -> set[str]:
    return set(POSTGRES_TAG.findall(_read(path)))


def _major(tag: str) -> str:
    return tag.split(".", 1)[0]


def _production_tag() -> str:
    refs = _postgres_refs(PRODUCTION_COMPOSE)
    assert len(refs) == 1, f"expected one Production PostgreSQL pin, found {sorted(refs)}"
    return refs.pop()


def test_production_pin_is_an_exact_minor() -> None:
    assert re.fullmatch(r"\d{2}\.\d+-trixie", _production_tag())


def test_local_ci_and_client_follow_the_production_major() -> None:
    production_major = _major(_production_tag())

    assert _postgres_refs(LOCAL_COMPOSE) == {production_major}
    assert production_major in {_major(tag) for tag in _postgres_refs(CI_WORKFLOW)}

    clients = set(CLIENT_PACKAGE.findall(_read(API_DOCKERFILE)))
    assert clients == {production_major}


def test_ci_has_no_transition_major_after_the_upgrade_was_verified() -> None:
    # ADR 028 kept one non-blocking PostgreSQL 18 leg while a rollback to the
    # old major was possible. The Production 19 cutover was verified, so that
    # temporary leg is removed and every CI service now matches Production.
    production_major = _major(_production_tag())
    ci = _read(CI_WORKFLOW)
    other_majors = {_major(tag) for tag in _postgres_refs(CI_WORKFLOW)} - {production_major}

    assert other_majors == set()
    assert "matrix.transition" not in ci
    assert "ADR 028" in ci  # the removed leg is still explained there
    assert "19.1" in _read(UPGRADE_ADR)


def test_no_stale_pins_remain_in_the_runtime_manifests() -> None:
    for path in (PRODUCTION_COMPOSE, LOCAL_COMPOSE, API_DOCKERFILE):
        assert "postgres:18" not in _read(path), path
        assert "postgresql-client-18" not in _read(path), path
