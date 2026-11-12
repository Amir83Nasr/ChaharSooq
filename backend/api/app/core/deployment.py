"""Explicit deployment identity for environment-crossing and destructive commands.

`APP_ENV` is application behavior, not environment identity: Staging and
Production both run `APP_ENV=production`, so a script cannot tell them apart
from it (see `docs/architecture/deployment.md`). Protected database scripts
therefore read `DEPLOYMENT_ENV`, whose accepted values are `development`,
`staging`, and `production`.

The guard is fail-closed: a missing, empty, or unrecognised identity raises
`DeploymentIdentityError` and the CLI wrappers exit non-zero *before* any
database connection is opened. Unknown is never treated as Development.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable

DEPLOYMENT_ENV_VAR = "DEPLOYMENT_ENV"
DEVELOPMENT = "development"
STAGING = "staging"
PRODUCTION = "production"
KNOWN_DEPLOYMENT_ENVS = frozenset({DEVELOPMENT, STAGING, PRODUCTION})

#: Operations that may run in Development and Staging but never Production.
NON_PRODUCTION_ENVS = (DEVELOPMENT, STAGING)


class DeploymentIdentityError(RuntimeError):
    """The deployment identity is missing, invalid, or not allowed here."""


class DeploymentConfigurationError(ValueError):
    """Runtime configuration cannot determine or accept the deployment identity.

    ``ValueError`` (not ``RuntimeError``) so Pydantic reports it as a normal
    configuration-validation failure while keeping the message free of secrets.
    """


def resolve_runtime_deployment_env(app_env: str) -> str | None:
    """Return the identity runtime configuration may use, enforcing production.

    Development/Staging keep the previous lenient behavior: a missing or
    unrecognised ``DEPLOYMENT_ENV`` yields ``None`` and is never mistaken for
    Production. With ``APP_ENV=production`` an explicit, recognised identity is
    mandatory because Staging and Production share that application mode.
    """
    raw = os.environ.get(DEPLOYMENT_ENV_VAR, "").strip().lower()
    if app_env != PRODUCTION:
        return raw if raw in KNOWN_DEPLOYMENT_ENVS else None
    if not raw:
        raise DeploymentConfigurationError(
            f"{DEPLOYMENT_ENV_VAR} must be set explicitly when APP_ENV=production; "
            f"accepted values: {', '.join(sorted(KNOWN_DEPLOYMENT_ENVS))} "
            "(Staging and Production both run APP_ENV=production)"
        )
    if raw not in KNOWN_DEPLOYMENT_ENVS:
        raise DeploymentConfigurationError(
            f"{DEPLOYMENT_ENV_VAR}={raw!r} is not a known environment "
            f"({', '.join(sorted(KNOWN_DEPLOYMENT_ENVS))})"
        )
    return raw


def resolve_deployment_env_optional() -> str | None:
    """Return a known identity, or ``None`` when it is missing or unrecognised.

    This is for runtime configuration checks that must not make
    ``DEPLOYMENT_ENV`` globally mandatory. Protected commands still use
    :func:`resolve_deployment_env` and fail closed.
    """
    raw = os.environ.get(DEPLOYMENT_ENV_VAR, "").strip().lower()
    return raw if raw in KNOWN_DEPLOYMENT_ENVS else None


def is_production_deployment() -> bool:
    """True only when Production is explicitly identified."""
    return resolve_deployment_env_optional() == PRODUCTION


def resolve_deployment_env() -> str:
    """Return the explicit deployment identity, or raise when it is unusable."""
    raw = os.environ.get(DEPLOYMENT_ENV_VAR, "").strip().lower()
    if not raw:
        raise DeploymentIdentityError(
            f"{DEPLOYMENT_ENV_VAR} is not set; protected database commands require an "
            f"explicit environment identity ({', '.join(sorted(KNOWN_DEPLOYMENT_ENVS))})"
        )
    if raw not in KNOWN_DEPLOYMENT_ENVS:
        raise DeploymentIdentityError(
            f"{DEPLOYMENT_ENV_VAR}={raw!r} is not a known environment "
            f"({', '.join(sorted(KNOWN_DEPLOYMENT_ENVS))})"
        )
    return raw


def require_deployment_env(operation: str, allowed: Iterable[str]) -> str:
    """Return the identity when it is known and allowed; raise otherwise."""
    env = resolve_deployment_env()
    allowed_set = frozenset(allowed)
    if env not in allowed_set:
        raise DeploymentIdentityError(
            f"{operation} refuses to run with {DEPLOYMENT_ENV_VAR}={env}; "
            f"allowed: {', '.join(sorted(allowed_set)) or 'none'}"
        )
    return env


def enforce_deployment_env(operation: str, allowed: Iterable[str]) -> str:
    """CLI wrapper: print a readable refusal and exit 1 before touching the database."""
    try:
        return require_deployment_env(operation, allowed)
    except DeploymentIdentityError as error:
        print(f"{operation}: {error}", file=sys.stderr)
        raise SystemExit(1) from None
