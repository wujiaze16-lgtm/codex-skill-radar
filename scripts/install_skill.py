#!/usr/bin/env python3
"""Compatibility entry point for the installer bundled with the Codex skill."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).parents[1] / "skills" / "skill-radar" / "scripts" / "install_from_github.py"
    runpy.run_path(str(target), run_name="__main__")
