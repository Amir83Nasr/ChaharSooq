"""Emit backend/openapi.json — run from backend/api so `app.*` imports resolve."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app  # noqa: E402

out = Path(__file__).resolve().parent.parent.parent / "openapi.json"
out.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n")
print(f"wrote {out}")
