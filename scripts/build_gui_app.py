"""Build the standalone desktop app for the graphical interface.

One script for local builds and CI, so there is a single build recipe. It
freezes the same ``lcf.gui`` launcher that the ``lcf-gui`` command uses into
a single PyInstaller one-file executable, dropped at the repository root.

One-file is a deliberate maintainer choice for a single double-clickable
artifact. The costs are real and accepted: the exe unpacks itself to a temp
directory on every launch, so startup takes noticeably longer than the
one-folder layout, and one-file builds trigger antivirus false positives
more often. The exe is far over GitHub's 100 MB file limit, so it is
gitignored and distributed as a release asset instead, uploaded by the
windows-app job in publish.yml.

Usage, from the repository root with the gui extra and pyinstaller installed:

    python scripts/build_gui_app.py

Output: ``lcf-strain-life-app.exe`` at the repository root (or the platform
equivalent). The build is unsigned. Windows SmartScreen and macOS Gatekeeper
will warn until the app is code signed.
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

# Packages measurably bloating the exe that the GUI can never reach. Most are
# optional imports that pandas, streamlit, or PIL guard with try/except, so
# excluding them just makes the guard take its normal fallback path. Sizes are
# the uncompressed payload measured from PKG-00.toc on 2026-07-17.
EXCLUDES = [
    # pulled through pandas' and the fatigue adapters' optional numba path,
    # the GUI computes nothing with numba (llvmlite.dll alone was 107 MB)
    "numba", "llvmlite",
    # streamlit's optional plotly chart backend, the GUI only uses st.pyplot
    # (14 MB)
    "plotly",
    # optional backend of PyJWT, only needed for streamlit's OIDC st.login,
    # which a local single-user app has no use for (10 MB)
    "cryptography",
    # matplotlib's Tk window backend, the GUI renders figures headlessly
    # (tcl/tk runtimes, 8 MB)
    "tkinter", "_tkinter",
    # PIL's AVIF codec, plots are PNG (8 MB)
    "PIL._avif", "PIL.AvifImagePlugin",
    # the MCP server has its own entry point and makes no sense inside the
    # GUI exe, and it drags in the mcp SDK and pywin32 (7 MB and up)
    "mcp", "win32com", "pythoncom", "pywintypes", "pythonwin",
]


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
        # the MCP server is excluded from the GUI exe, see EXCLUDES
        if m.name == "lcf.mcp_server":
            continue
        names.append(m.name)
    return names


def main() -> int:
    app_py = ROOT / "src" / "lcf" / "gui" / "app.py"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile",
        # the finished exe lands at the repository root automatically
        "--distpath", str(ROOT),
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
    for name in EXCLUDES:
        cmd += ["--exclude-module", name]
    cmd.append(str(ROOT / "scripts" / "gui_entry.py"))
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
