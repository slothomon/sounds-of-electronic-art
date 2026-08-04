#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    command = [sys.executable, *args]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run("scripts/validate_site.py", "--source")
    run("scripts/build.py")
    run("scripts/validate_site.py", "--public")
    print("All source, build and generated-site checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
