"""Capture fatal errors and build a diagnostic bundle the user can send.

Nothing is ever uploaded automatically. On a crash the user gets a local ZIP and
the choice to open a pre-filled GitHub issue.
"""

from __future__ import annotations

import platform
import sys
import threading
import traceback
import urllib.parse
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Type

from . import app_paths, logging_setup

REPO = "matheusabdao/livecut"
LOG_TAIL_LINES = 200


def _app_version() -> str:
    from . import __version__

    return __version__


def _component_status() -> str:
    try:
        from . import provisioning

        return (
            f"ffmpeg={'ok' if provisioning.ffmpeg_ready() else 'faltando'}, "
            f"modelo={'ok' if provisioning.model_ready() else 'faltando'}"
        )
    except Exception:
        return "desconhecido"


def _log_tail(lines: int = LOG_TAIL_LINES) -> str:
    try:
        content = logging_setup.log_file_path().read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return "(sem arquivo de log)"
    return "\n".join(content[-lines:])


def _environment() -> str:
    return (
        f"Versao: {_app_version()}\n"
        f"Python: {sys.version.split()[0]}\n"
        f"Sistema: {platform.platform()}\n"
        f"Executavel empacotado: {app_paths.is_frozen()}\n"
        f"Componentes: {_component_status()}\n"
    )


def build_bundle(exc_type: Type[BaseException], exc_value: BaseException,
                 exc_tb) -> Path:
    """Write ``crash_<timestamp>.zip`` and return its path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = app_paths.logs_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / f"crash_{timestamp}.zip"

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("resumo.txt", _environment())
        archive.writestr("erro.txt", tb_text)
        archive.writestr("log.txt", _log_tail())

    return bundle


def issue_url(bundle: Path, tb_text: str) -> str:
    summary = tb_text.strip().splitlines()
    head = summary[-1] if summary else "erro desconhecido"
    title = f"[crash] {head[:120]}"
    body = (
        "O app encontrou um erro. Detalhes abaixo.\n\n"
        f"**Versao:** {_app_version()}\n"
        f"**Sistema:** {platform.platform()}\n\n"
        "**Erro:**\n```\n"
        f"{tb_text[-1500:]}\n```\n\n"
        f"O pacote de diagnostico foi salvo em:\n`{bundle}`\n"
        "Anexe esse arquivo .zip se puder.\n"
    )
    query = urllib.parse.urlencode({"title": title, "body": body})
    return f"https://github.com/{REPO}/issues/new?{query}"


def open_logs_folder() -> None:
    import os
    import subprocess

    folder = app_paths.logs_dir()
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)
    except Exception:
        pass


def _show_dialog(bundle: Path, tb_text: str) -> None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        print(f"Erro inesperado. Diagnostico salvo em: {bundle}", file=sys.stderr)
        print(tb_text, file=sys.stderr)
        return

    try:
        root = tk.Tk()
    except Exception:
        print(f"Erro inesperado. Diagnostico salvo em: {bundle}", file=sys.stderr)
        return

    root.title("LiveCut - ocorreu um erro")
    root.geometry("560x260")
    root.minsize(480, 220)

    ttk.Label(
        root,
        text="O LiveCut encontrou um erro inesperado.",
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", padx=14, pady=(14, 6))

    ttk.Label(
        root,
        text=(
            "Um pacote com os detalhes foi salvo em:\n"
            f"{bundle}\n\n"
            "Voce pode reportar no GitHub (o log vai ser anexado manualmente) "
            "para ajudar a corrigir o problema."
        ),
        wraplength=520,
        justify="left",
    ).pack(anchor="w", padx=14)

    buttons = ttk.Frame(root)
    buttons.pack(fill="x", padx=14, pady=14)

    def report() -> None:
        webbrowser.open(issue_url(bundle, tb_text))
        root.destroy()

    ttk.Button(buttons, text="Reportar no GitHub", command=report).pack(side="left")
    ttk.Button(buttons, text="Abrir pasta do log", command=open_logs_folder).pack(
        side="left", padx=6
    )
    ttk.Button(buttons, text="Fechar", command=root.destroy).pack(side="right")

    root.mainloop()


def handle_exception(exc_type, exc_value, exc_tb, show_dialog: bool = True) -> None:
    """Build the bundle and offer to report. Never raises."""
    if issubclass(exc_type, KeyboardInterrupt):
        return
    try:
        bundle = build_bundle(exc_type, exc_value, exc_tb)
        logging_setup.get_logger().error(
            "Erro nao tratado", exc_info=(exc_type, exc_value, exc_tb)
        )
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        if show_dialog:
            _show_dialog(bundle, tb_text)
        else:
            print(f"Erro inesperado. Diagnostico: {bundle}", file=sys.stderr)
    except Exception:
        # Last-resort: never crash the crash handler.
        traceback.print_exception(exc_type, exc_value, exc_tb)


def install_handlers(show_dialog: bool = True) -> None:
    """Route unhandled exceptions (main thread + threads) to the reporter."""

    def main_hook(exc_type, exc_value, exc_tb):
        handle_exception(exc_type, exc_value, exc_tb, show_dialog=show_dialog)

    sys.excepthook = main_hook

    if hasattr(threading, "excepthook"):
        def thread_hook(args):
            handle_exception(args.exc_type, args.exc_value, args.exc_traceback,
                             show_dialog=show_dialog)

        threading.excepthook = thread_hook


def tk_callback_exception(exc_type, exc_value, exc_tb) -> None:
    """Assign to ``Tk.report_callback_exception`` for GUI callbacks."""
    handle_exception(exc_type, exc_value, exc_tb, show_dialog=True)


def latest_bundle() -> Optional[Path]:
    logs = app_paths.logs_dir()
    try:
        bundles = sorted(logs.glob("crash_*.zip"))
    except OSError:
        return None
    return bundles[-1] if bundles else None
