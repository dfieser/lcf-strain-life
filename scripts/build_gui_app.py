"""Build the standalone desktop app for the graphical interface.

One script for local builds and CI, so there is a single build recipe. It
freezes the same ``lcf.gui`` launcher that the ``lcf-gui`` command uses into
a PyInstaller one-folder app. One-folder is deliberate: one-file builds start
slowly and trigger antivirus false positives.

Usage, from the repository root with the gui extra and pyinstaller installed:

    python scripts/build_gui_app.py

Output: ``dist/lcf-strain-life-app/`` with ``lcf-strain-life-app.exe`` inside
(or the platform equivalent). The build is unsigned. Windows SmartScreen and
macOS Gatekeeper will warn until the app is code signed.
"""

from __future__ import annotations

import os
import pkgutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "lcf-strain-life-app"
SEP = ";" if os.name == "nt" else ":"


def lcf_submodules() -> list[str]:
    """Every module in the installed lcf package, found at build time.

    app.py is executed by the streamlit script runner, not imported, so its
    imports are invisible to PyInstaller's analysis. Enumerating the package
    with pkgutil keeps the build in sync with the library automatically, with
    no hand-maintained module list, and works for editable installs where
    PyInstaller's own --collect-submodules finds nothing.
    """
    import lcf

    names = ["lcf"]
    for m in pkgutil.walk_packages(lcf.__path__, prefix="lcf."):
        names.append(m.name)
    return names


def main() -> int:
    app_py = ROOT / "src" / "lcf" / "gui" / "app.py"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir",
        "--name", APP_NAME,
        # streamlit ships its web frontend as package data and reads its own
        # version from package metadata, both must be collected explicitly
        "--collect-all", "streamlit",
        "--copy-metadata", "streamlit",
        # the streamlit script runner needs app.py as a real file, placed
        # next to the bundled lcf.gui package so app_path() resolves it
        "--add-data", f"{app_py}{SEP}lcf/gui",
    ]
    for name in lcf_submodules():
        cmd += ["--hidden-import", name]
    cmd.append(str(ROOT / "scripts" / "gui_entry.py"))
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
