"""Download and install the runtime resources LiveCut needs.

LiveCut ships without FFmpeg and without the Whisper model to keep the installer
small. This module fetches both from their official upstream sources into the
app's components directory. It is idempotent: anything already present is skipped.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, List, Optional

from . import app_paths

ProgressFn = Callable[[str], None]

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MODEL_REPO_TEMPLATE = "Systran/faster-whisper-{name}"
DEFAULT_MODEL = "small"

_FFMPEG_EXE = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
_FFPROBE_EXE = "ffprobe.exe" if os.name == "nt" else "ffprobe"


def _noop(message: str) -> None:
    print(message, flush=True)


def ffmpeg_ready() -> bool:
    bin_dir = app_paths.ffmpeg_dir()
    return (bin_dir / _FFMPEG_EXE).exists() and (bin_dir / _FFPROBE_EXE).exists()


def model_ready(name: str = DEFAULT_MODEL) -> bool:
    model_dir = app_paths.models_dir() / f"faster-whisper-{name}"
    try:
        return model_dir.is_dir() and any(model_dir.iterdir())
    except OSError:
        return False


def missing_components(name: str = DEFAULT_MODEL) -> List[str]:
    missing = []
    if not ffmpeg_ready():
        missing.append("ffmpeg")
    if not model_ready(name):
        missing.append("model")
    return missing


def _download(url: str, dest: Path, progress: ProgressFn) -> None:
    progress(f"Baixando {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "LiveCut"})
    with urllib.request.urlopen(request, timeout=60) as response, open(dest, "wb") as handle:
        shutil.copyfileobj(response, handle)


def install_ffmpeg(progress: ProgressFn = _noop) -> None:
    if ffmpeg_ready():
        progress("FFmpeg ja esta instalado.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "ffmpeg.zip"
        _download(FFMPEG_URL, archive, progress)
        progress("Extraindo FFmpeg...")
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(tmp)

        source_bin: Optional[Path] = None
        for candidate in Path(tmp).rglob("bin"):
            if (candidate / _FFMPEG_EXE).exists():
                source_bin = candidate
                break
        if source_bin is None:
            raise RuntimeError("Nao encontrei os binarios do FFmpeg no pacote baixado.")

        destination = app_paths.ffmpeg_dir()
        destination.mkdir(parents=True, exist_ok=True)
        for item in source_bin.iterdir():
            if item.is_file():
                shutil.copy2(item, destination / item.name)

    progress("FFmpeg instalado.")


def install_model(name: str = DEFAULT_MODEL, progress: ProgressFn = _noop) -> None:
    if model_ready(name):
        progress("Modelo do Whisper ja esta instalado.")
        return

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - dependency is always present
        raise RuntimeError("huggingface_hub nao esta instalado.") from exc

    destination = app_paths.models_dir() / f"faster-whisper-{name}"
    destination.mkdir(parents=True, exist_ok=True)
    progress(f"Baixando modelo do Whisper ({name}). Isso pode demorar um pouco...")
    snapshot_download(repo_id=MODEL_REPO_TEMPLATE.format(name=name), local_dir=str(destination))
    progress("Modelo instalado.")


def ensure_components(progress: ProgressFn = _noop, model: str = DEFAULT_MODEL) -> bool:
    """Install whatever is missing. Returns True when everything is ready."""
    ok = True
    try:
        install_ffmpeg(progress)
    except Exception as exc:
        ok = False
        progress(f"Falha ao instalar o FFmpeg: {exc}")

    try:
        install_model(model, progress)
    except Exception as exc:
        ok = False
        progress(f"Falha ao instalar o modelo: {exc}")

    return ok


def _parse_model_arg(argv: List[str]) -> str:
    if "--model" in argv:
        index = argv.index("--model")
        if index + 1 < len(argv):
            return argv[index + 1]
    return DEFAULT_MODEL


def provision_main(argv: Optional[List[str]] = None) -> int:
    """Entry point for ``LiveCut.exe --provision`` (called by the installer)."""
    args = list(sys.argv[1:] if argv is None else argv)
    model = _parse_model_arg(args)

    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return 0 if ensure_components(_noop, model=model) else 1

    result = {"ok": False}
    root = tk.Tk()
    root.title("LiveCut - preparando componentes")
    root.geometry("560x320")
    root.minsize(480, 260)

    ttk.Label(
        root,
        text="Baixando FFmpeg e o modelo do Whisper.\nIsso so acontece uma vez.",
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", padx=12, pady=(12, 6))

    bar = ttk.Progressbar(root, mode="indeterminate")
    bar.pack(fill="x", padx=12)
    bar.start(12)

    log = tk.Text(root, wrap="word", height=10, font=("Consolas", 9))
    log.pack(fill="both", expand=True, padx=12, pady=10)

    def append(message: str) -> None:
        log.insert("end", message + "\n")
        log.see("end")
        root.update_idletasks()

    def worker() -> None:
        result["ok"] = ensure_components(append, model=model)
        root.after(0, root.destroy)

    import threading

    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()

    return 0 if result["ok"] else 1
