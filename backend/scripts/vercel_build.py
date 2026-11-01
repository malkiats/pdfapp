"""Vercel build step: copies the shared tool catalog into the backend function bundle."""

import shutil
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SOURCE = BACKEND.parent / "shared"
TARGET = BACKEND / "shared"

if __name__ == "__main__":
    TARGET.mkdir(exist_ok=True)
    for name in ("tool-catalog.json", "tool-catalog.schema.json"):
        shutil.copy2(SOURCE / name, TARGET / name)
    print(f"copied tool catalog to {TARGET}")
