"""Check GitHub Releases for a newer LiveCut version.

Read-only: one public API call, no personal data sent. Can be disabled with
``check_for_updates: false`` in the config.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional, Tuple

from . import app_paths

REPO = "matheusabdao/livecut"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
_MARKER = "last_update_check"


def parse_version(text: str) -> Optional[Tuple[int, ...]]:
    """Extract a numeric x.y.z tuple from a version string, or None."""
    if not text:
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer(latest: str, current: str) -> bool:
    """True when ``latest`` is a strictly newer x.y.z than ``current``."""
    latest_v = parse_version(latest)
    current_v = parse_version(current)
    if latest_v is None or current_v is None:
        return False
    return latest_v > current_v


def _marker_path() -> Path:
    return app_paths.user_data_dir() / _MARKER


def should_check() -> bool:
    try:
        last = float(_marker_path().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return True
    return (time.time() - last) > CHECK_INTERVAL_SECONDS


def mark_checked() -> None:
    try:
        path = _marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def fetch_latest_release(timeout: float = 5.0) -> Optional[dict]:
    request = urllib.request.Request(
        API_LATEST,
        headers={"User-Agent": "LiveCut", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def check_for_update(current_version: str, force: bool = False) -> Optional[dict]:
    """Return ``{"version", "url"}`` when a newer release exists, else None."""
    if not force and not should_check():
        return None

    release = fetch_latest_release()
    mark_checked()
    if not release:
        return None

    tag = release.get("tag_name", "") or ""
    if is_newer(tag, current_version):
        return {
            "version": tag.lstrip("vV"),
            "url": release.get("html_url") or RELEASES_PAGE,
        }
    return None


def open_release_page(url: str) -> None:
    webbrowser.open(url or RELEASES_PAGE)
