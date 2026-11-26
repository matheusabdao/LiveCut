"""User-facing settings persistence.

Stores GUI preferences (theme, quality, sensitivity, custom phrases, ...) in
``%APPDATA%\\LiveCut\\user_settings.json`` (or ``LIVECUT_HOME``). These are
applied on top of the static ``config.json`` at pipeline runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from . import app_paths

_SETTINGS_FILENAME = "user_settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "light",
    "quality": "best",
    "sensitivity": 60,        # 0 = audio only, 100 = chat/keywords dominant
    "precision": 50,          # 0 = fastest, 100 = most precise
    "max_clips": 8,
    "keep_downloaded": False,
    "skip_whisper": False,
    "skip_cut": False,
    "phrases": [],            # list of {text, fromImage}
}


def settings_path() -> Path:
    return app_paths.user_data_dir() / _SETTINGS_FILENAME


def load_settings() -> Dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    return merged


def save_settings(settings: Dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {k: settings.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}
    path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")


def phrase_texts(settings: Dict[str, Any]) -> list[str]:
    """Return the plain text list of custom phrases from a settings dict."""
    phrases = settings.get("phrases") or []
    out = []
    for p in phrases:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict) and p.get("text"):
            out.append(str(p["text"]))
    return out
