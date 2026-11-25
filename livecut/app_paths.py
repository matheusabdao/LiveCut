"""Path resolution for LiveCut.

Works both when running from source and when frozen by PyInstaller, so the rest
of the codebase never has to care where it is running from.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "LiveCut"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Repository root when running from source."""
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Directory holding bundled resources (``_MEIPASS`` when frozen)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return project_root()


def install_dir() -> Path:
    """Directory of the executable when frozen; project root otherwise."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def user_data_dir() -> Path:
    """Per-user writable data directory (config, logs, temp)."""
    override = os.environ.get("LIVECUT_HOME")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def _dir_writable(path: Path) -> bool:
    if not path.is_dir():
        return False
    probe = path / ".livecut_write_test"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def components_dir() -> Path:
    """Where FFmpeg and Whisper models live."""
    if not is_frozen():
        return project_root() / "components"
    candidate = install_dir() / "components"
    if _dir_writable(install_dir()):
        return candidate
    return user_data_dir() / "components"


def ffmpeg_dir() -> Path:
    return components_dir() / "ffmpeg" / "bin"


def models_dir() -> Path:
    return components_dir() / "models"


def logs_dir() -> Path:
    return user_data_dir() / "logs"


def default_config_path() -> Path:
    """User config when frozen; repo config when developing."""
    if is_frozen():
        return user_data_dir() / "config.json"
    return project_root() / "config" / "config.json"


def bundled_default_config() -> Path:
    return bundle_dir() / "config" / "config.json"


def default_output_dir() -> Path:
    if is_frozen():
        home = Path.home()
        if os.name == "nt":
            return home / "Documents" / APP_NAME
        return home / APP_NAME
    return project_root() / "output"


def default_temp_dir() -> Path:
    if is_frozen():
        return user_data_dir() / "temp"
    return project_root() / "temp"


def local_model_ref(name: str) -> str:
    """Return a provisioned local model directory, else the plain model name.

    ``faster-whisper`` accepts either a name (which it downloads) or a folder.
    """
    candidate = models_dir() / f"faster-whisper-{name}"
    try:
        if candidate.is_dir() and any(candidate.iterdir()):
            return str(candidate)
    except OSError:
        pass
    return name
