"""One-shot PostgreSQL role provisioning for the Production stack.

Usage (normally through ``docker compose``)::

    DEPLOYMENT_ENV=production uv run --project backend/api \
      python backend/api/scripts/provision_database_roles.py

The service reads ``database_url``, ``migration_database_url``, and
``postgres_password`` from ``SECRETS_DIR`` (or the matching environment
variables), creates or updates the application and migration roles, and applies
the least-privilege grants. It is idempotent: a re-run rotates both role
passwords to the URLs' values and converges the grants.

The administrative password is used here only. Neither the API nor the
migration runner instantiates the provisioning settings, so neither can read
it. No URL or password is printed; failures exit non-zero so ``api`` never
starts after a failed provision.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import ProvisioningSettings, get_provisioning_settings
from app.core.deployment import KNOWN_DEPLOYMENT_ENVS, enforce_deployment_env
from app.core.migrations import safe_error_message
from app.core.provisioning import (
    ProvisioningError,
    provision_from_settings,
    redact_provisioning_error,
)


def main() -> None:
    enforce_deployment_env("provision-database-roles", KNOWN_DEPLOYMENT_ENVS)
    settings: ProvisioningSettings | None = None
    try:
        settings = get_provisioning_settings()
        plan = provision_from_settings(settings)
    except ProvisioningError as error:
        message = redact_provisioning_error(str(error), settings)
        print(f"provision-database-roles: provisioning failed: {message}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:  # noqa: BLE001 — turn every failure into a clean exit
        message = redact_provisioning_error(safe_error_message(error), settings)
        print(
            f"provision-database-roles: provisioning failed ({type(error).__name__}): {message}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(
        "provision-database-roles: application and migration roles are ready "
        f"(application={plan.app_role}, migration={plan.migrator_role})"
    )


if __name__ == "__main__":
    main()
