"""Fail (exit 1) if backend/api/openapi.json differs from the app contract.

Read-only: never writes the snapshot. Run from anywhere; mirrors
scripts/export_openapi.py. Refresh with:
  uv run --project backend/api python backend/api/scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app  # noqa: E402

root = Path(__file__).resolve().parent.parent
snapshot = root / "openapi.json"
fresh = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"
if snapshot.read_text() != fresh:
    print(
        "openapi.json is stale - refresh with:\n"
        "  uv run --project backend/api python backend/api/scripts/export_openapi.py",
        file=sys.stderr,
    )
    raise SystemExit(1)
print("openapi: fresh")
