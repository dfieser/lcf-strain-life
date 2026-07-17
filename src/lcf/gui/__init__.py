"""Graphical no-code interface for lcf, served locally by Streamlit.

Installed with the ``gui`` extra (``pip install lcf-strain-life[gui]``) and
started with the ``lcf-gui`` command. The same :func:`main` also drives the
frozen desktop build made by ``scripts/build_gui_app.py``, so there is one
launcher for both. The app runs entirely on the local machine. Telemetry is
disabled explicitly at launch.
"""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path


def app_path() -> Path:
    """Path of the Streamlit app script, installed or frozen.

    In a PyInstaller one-folder build this package is bundled compiled, and
    the build script places ``app.py`` next to it as a data file, so the
    same relative lookup works in both worlds.
    """
    return Path(__file__).with_name("app.py")


def main() -> None:
    """Launch the Streamlit app (console entry point ``lcf-gui``)."""
    # No-op when not frozen. Required on Windows in the frozen build so
    # multiprocessing child processes do not re-launch the app.
    multiprocessing.freeze_support()
    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "The graphical interface needs the 'gui' extra:\n"
            "    pip install lcf-strain-life[gui]"
        ) from exc

    sys.argv = [
        "streamlit", "run", str(app_path()),
        "--global.developmentMode=false",
        # privacy: no usage statistics, ever, regardless of user config
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())
