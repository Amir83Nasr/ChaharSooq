"""One-shot backup worker for hosts without the API's background thread.

Uses the API's application-role database URL and local archive directory; it
never reads the PostgreSQL admin or migration credential. Staging (Neon) is
refused because the runtime has no PostgreSQL client tools or local storage.

    DEPLOYMENT_ENV=production python backend/api/scripts/backup_cli.py plan --json
    ... backup_cli.py queue-backup
    ... backup_cli.py run-once
    ... backup_cli.py prune
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_engine
from app.core.deployment import enforce_deployment_env
from app.services import BackupService
from app.services.backup_worker import BackupWorker


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-shot backup worker CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Read owner settings and the last completed archive")
    plan.add_argument("--json", action="store_true", help="Emit one JSON object")

    sub.add_parser("queue-backup", help="Queue a manual backup for the next run")
    sub.add_parser("run-once", help="Execute at most one queued backup or restore")
    sub.add_parser("prune", help="Delete archives past the 30-day retention")
    return parser


def main() -> None:
    """Dispatch one CLI command; invalid states exit non-zero without a traceback."""
    enforce_deployment_env("backup", ("development", "production"))
    args = _parser().parse_args()
    with Session(get_engine()) as session:
        service = BackupService(session)
        if args.command == "plan":
            last = service.last_completed()
            view = service.settings_view()
            view["last_completed"] = (
                {"id": last.id, "created_at": last.created_at.isoformat()} if last else None
            )
            if args.json:
                print(json.dumps(view, ensure_ascii=False))
            else:
                print(
                    f"enabled={str(view['enabled']).lower()} "
                    f"interval_minutes={view['interval_minutes']} "
                    f"tools_available={str(view['tools_available']).lower()}"
                )
        elif args.command == "queue-backup":
            record = service.queue_manual()
            print(record.id)
        elif args.command in ("run-once", "prune"):
            factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
            worker = BackupWorker(factory)
            worked = worker.tick() if args.command == "run-once" else worker.prune()
            print(worked)
        else:  # pragma: no cover — argparse enforces the choices above
            raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
