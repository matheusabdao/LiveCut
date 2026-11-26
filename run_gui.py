"""
LiveCut — modern desktop GUI (pywebview + web UI).

The heavy lifting (download, audio, Whisper, clip selection, FFmpeg cut) still
runs 100% locally in Python. This module only hosts the visual layer inside a
native desktop window (WebView2 on Windows) and bridges UI calls to the
pipeline.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import webview

from livecut import __version__
from livecut import app_paths, crash, user_settings
from livecut.user_settings import phrase_texts

APP_TITLE = "LiveCut"
WINDOW_SIZE = (1000, 680)


class LiveCutApi:
    """Bridge exposed to the web UI as ``pywebview.api``."""

    def __init__(self) -> None:
        self._window: Optional[webview.Window] = None
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    # ------------------------------------------------------------------
    # Window / lifecycle
    # ------------------------------------------------------------------
    def attach_window(self, window: webview.Window) -> None:
        self._window = window

    def _js(self, expr: str) -> None:
        """Evaluate a JS expression on the UI thread (thread-safe)."""
        if self._window is not None:
            try:
                self._window.evaluate_js(expr)
            except Exception:
                pass

    def _log(self, text: str, level: str = "") -> None:
        safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        self._js(f"window.onLog(`{safe}`, '{level}')")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def get_settings(self) -> Dict[str, Any]:
        return user_settings.load_settings()

    def save_settings(self, settings: Dict[str, Any]) -> bool:
        try:
            user_settings.save_settings(settings or {})
            return True
        except Exception:
            traceback.print_exc()
            return False

    def get_version(self) -> str:
        return __version__

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------
    def browse_file(self) -> Optional[str]:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(Path.home()),
            file_types=("Video files (*.mp4;*.mkv;*.mov;*.avi;*.webm;*.flv;*.ts;*.m4v)",),
        )
        if result:
            return result[0]
        return None

    def browse_output(self) -> Optional[str]:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            return result[0]
        return None

    def open_output(self, path: str) -> None:
        out = Path(path or app_paths.default_output_dir())
        out.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(out))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", str(out)], check=False)
            else:
                import subprocess

                subprocess.run(["xdg-open", str(out)], check=False)
        except Exception as exc:
            self._log(f"Could not open folder: {exc}", "warn")

    def paste_clipboard(self) -> str:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            return text.strip()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------
    def ocr_image(self) -> str:
        from livecut.ocr import extract_text

        if self._window is None:
            return ""
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(Path.home()),
            file_types=("Images (*.png;*.jpg;*.jpeg;*.bmp;*.webp)",),
        )
        if not result:
            return ""
        return extract_text(result[0])

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    def run_pipeline(self, source: str, output: str, settings: Dict[str, Any]) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        settings = settings or {}
        phrases = phrase_texts(settings)

        opts = dict(
            config_path=str(app_paths.default_config_path())
            if app_paths.default_config_path().exists()
            else None,
            output_dir_override=output or str(app_paths.default_output_dir()),
            quality=settings.get("quality", "best"),
            keep_downloaded=bool(settings.get("keep_downloaded", False)),
            skip_cut=bool(settings.get("skip_cut", False)),
            skip_transcription=bool(settings.get("skip_whisper", False)),
            chat_sensitivity=settings.get("sensitivity"),
            precision_speed=settings.get("precision"),
            custom_phrases=phrases,
            max_clips=settings.get("max_clips"),
        )

        self._worker = threading.Thread(
            target=self._worker_target, args=(source, opts), daemon=True
        )
        self._worker.start()

    def stop_pipeline(self) -> None:
        if self._running:
            self._stop_event.set()
            self._log("⏹ Parando… (aguardando a etapa atual terminar)", "warn")

    def _worker_target(self, source: str, opts: Dict[str, Any]) -> None:
        try:
            from livecut.pipeline import run_pipeline

            def _progress(msg: str, step: int = 0, total: int = 0) -> None:
                if self._stop_event.is_set():
                    return
                level = ""
                if msg.startswith("✅"):
                    level = "ok"
                elif msg.startswith("❌"):
                    level = "err"
                elif msg.startswith("⏹"):
                    level = "warn"
                self._log(msg, level)

            result = run_pipeline(source, on_progress=_progress, **opts)
            if result.ok:
                lines = ["✅ Pipeline finalizado com sucesso!"]
                if result.output_dir:
                    lines.append(f"   Pasta de saída: {result.output_dir}")
                if result.clips:
                    lines.append(f"   {len(result.clips)} clipe(s) gerado(s).")
                self._js(f"window.onPipelineDone(true, `{chr(10).join(lines)}`)")
            else:
                self._js(
                    f"window.onPipelineDone(false, `❌ {result.error_message or 'Erro desconhecido'}`)"
                )
        except Exception as exc:
            tb = traceback.format_exc()
            self._js(f"window.onPipelineDone(false, `❌ {exc}\\n{tb}`)")
        finally:
            self._running = False


def main() -> int:
    # Ensure project is importable when double-clicked from Explorer.
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Install crash handlers for unhandled exceptions.
    try:
        crash.install_handlers()
    except Exception:
        pass

    api = LiveCutApi()

    # Resolve the bundled web UI path (works in dev and frozen).
    web_root = app_paths.bundle_dir() / "web"
    index = web_root / "index.html"
    url = str(index) if index.exists() else "web/index.html"

    window = webview.create_window(
        APP_TITLE,
        url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=(820, 560),
        text_select=True,
    )
    api.attach_window(window)

    # Check for app updates on launch (non-blocking best-effort).
    try:
        from livecut import updater

        if updater.should_check():
            updater.mark_checked()
            threading.Thread(target=_check_update, daemon=True).start()
    except Exception:
        pass

    webview.start(api=api, debug=False)
    return 0


def _check_update() -> None:
    try:
        from livecut import updater

        info = updater.check_for_update()
        if info and info.get("has_update"):
            # best-effort: could surface via JS, but keep it simple for now.
            pass
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
