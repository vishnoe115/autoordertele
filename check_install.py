from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
errors = []

for file in ROOT.rglob("*.py"):
    if any(part in {".venv", "venv"} for part in file.parts):
        continue
    try:
        ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except Exception as exc:
        errors.append(f"{file.relative_to(ROOT)}: {exc}")

if errors:
    print("FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("OK - all Python files parsed successfully")
