#!/usr/bin/env python3
"""Build deterministic public assets from the canonical prompt."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "一鍵定位-貼上任何AI.md"
OUTPUT = ROOT / "docs" / "prompt-full.txt"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"missing canonical prompt: {SOURCE}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    content = normalize(SOURCE.read_text(encoding="utf-8-sig"))
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"built {OUTPUT.relative_to(ROOT)} from {SOURCE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


