"""Graphical no-code interface for lcf, served locally by Streamlit.

Installed with the ``gui`` extra (``pip install lcf-strain-life[gui]``) and
started with the ``lcf-gui`` command. The same :func:`main` also drives the
frozen desktop build made by ``scripts/build_gui_app.py``, so there is one
launcher for both. The app runs entirely on the local machine. Telemetry is
disabled explicitly at launch.
"""

from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path


def app_path() -> Path:
    """Path of the Streamlit app script, installed or frozen.

    In a PyInstaller one-folder build this package is bundled compiled, and
    the build script places ``app.py`` next to it as a data file, so the
    same relative lookup works in both worlds.
    """
    return Path(__file__).with_name("app.py")


def should_bootstrap_credentials() -> bool:
    """Whether to auto-write streamlit credentials on launch.

    Only the frozen desktop build does. It is windowed with no console to
    answer streamlit's interactive first-run email prompt, so the prompt must
    be suppressed by writing the credentials file ahead of it. A plain ``pip``
    install runs from a terminal where streamlit's normal onboarding applies,
    so we do not silently mutate that user's global ``~/.streamlit`` config.
    """
    return bool(getattr(sys, "frozen", False))


def ensure_streamlit_credentials() -> None:
    """Suppress streamlit's first-run email prompt, once and for all.

    On a machine that never ran streamlit, ``streamlit run`` stops at an
    interactive "enter your email" onboarding prompt. In the windowed desktop
    exe there is no console to answer it, and no user of this app should see
    it anyway. Streamlit skips the prompt when its credentials file exists,
    so write the file with an empty email exactly as streamlit itself does
    when the prompt is left blank. An existing file is never touched.
    """
    path = Path.home() / ".streamlit" / "credentials.toml"
    if path.exists():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[general]\nemail = ""\n', encoding="utf-8")
    except OSError:
        # a locked-down home directory only costs the pip user the one-time
        # prompt, and the frozen build runs before this ever matters
        pass


def main() -> None:
    """Launch the Streamlit app (console entry point ``lcf-gui``)."""
    # No-op when not frozen. Required on Windows in the frozen build so
    # multiprocessing child processes do not re-launch the app.
    multiprocessing.freeze_support()

    # The windowed (no-console) exe has no stdout/stderr. Streamlit and its
    # logging write to both, so give them a sink instead of None.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "The graphical interface needs the 'gui' extra:\n"
            "    pip install lcf-strain-life[gui]"
        ) from exc

    if should_bootstrap_credentials():
        ensure_streamlit_credentials()

    sys.argv = [
        "streamlit", "run", str(app_path()),
        "--global.developmentMode=false",
        # privacy: no usage statistics, ever, regardless of user config
        "--browser.gatherUsageStats=false",
        # hide streamlit's Deploy button and developer menu. This is a
        # local private app, there is nothing to deploy to their cloud.
        "--client.toolbarMode=viewer",
    ]
    sys.exit(stcli.main())
