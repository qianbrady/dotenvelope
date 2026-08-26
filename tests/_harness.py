"""Shared fixtures/helpers for the dotenvelope test-suite (stdlib only).

All temporary directories are created under ``<workspace>/.build-tmp``.
Subprocesses are always spawned with explicit ``encoding``/``errors``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = PROJECT_ROOT.name  # "dotenvelope"
BUILD_TMP = PROJECT_ROOT.parents[1] / ".build-tmp"


def fresh_dir(prefix: str = "de") -> Path:
    """Create an isolated temp dir under ``.build-tmp``."""
    BUILD_TMP.mkdir(parents=True, exist_ok=True)
    while True:
        candidate = BUILD_TMP / f"{prefix}-{uuid.uuid4().hex[:12]}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue


def write_tree(root: Path, files: dict) -> None:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def write_bytes(root: Path, rel: str, data: bytes) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def run_cli(args, cwd=None, input_text: str | None = "") -> subprocess.CompletedProcess:
    """Run ``python -m dotenvelope ...`` in a real subprocess (utf-8 stdio)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    for noisy in ("PYTHONUTF8", "PYTHONLEGACYWINDOWSSTDIO"):
        env.pop(noisy, None)
    return subprocess.run(
        [sys.executable, "-m", PACKAGE_NAME, *args],
        capture_output=True,
        input=input_text,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )