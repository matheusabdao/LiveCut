"""
LiveCut — Simple Tkinter GUI.

A minimal desktop interface so non-CLI users can generate clips:

    1. Paste a VOD URL (or browse to a local file)
    2. Pick an output directory for clips
    3. Optionally tweak quality / clip count / transcription
    4. Click "Run" and watch the log widget update in real time

Uses a background worker thread so the UI stays responsive while the
(potentially multi-minute) pipeline runs.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "LiveCut — Local VOD Highlight Generator"
APP_SIZE = "820x640"


QUALITY_OPTIONS = [
    ("Best (stream-copy, lossless)", "best"),
    ("720p (re-encoded)",             "720p"),
    ("480p (faster)",                 "480p"),
    ("Worst (smallest file)",         "worst"),
]


class LiveCutGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        self.minsize(700, 540)

        # --- Ensure project is importable when double-clicked from Explorer ---
        project_root = Path(__file__).resolve().parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Config defaults (loaded lazily from config/config.json)
        self._default_output = Path.cwd() / "output"
        self._default_config = Path.cwd() / "config" / "config.json"

        # Message queue: worker thread pushes strings here; UI thread drains it
        self._msg_queue: "queue.Queue[tuple[int, str]]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._stop_requested = threading.Event()

        self._build_widgets()
        self._update_run_button()
        self.after(80, self._drain_queue)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Label(
            root,
            text="🎬  LiveCut — Local Automatic Highlight Clipper",
            font=("Segoe UI", 14, "bold"),
        )
        header.pack(anchor=tk.W, **pad)
        sub = ttk.Label(
            root,
            text="Kick • Twitch • YouTube • Local files   |   100% local, no cloud API required",
            foreground="#555",
        )
        sub.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # --- Section: Input ---
        input_frame = ttk.LabelFrame(root, text="1. Input source (VOD URL or local file)", padding=10)
        input_frame.pack(fill=tk.X, **pad)

        self.var_source = tk.StringVar()
        ttk.Label(input_frame, text="Video source:").grid(row=0, column=0, sticky=tk.W)
        source_entry = ttk.Entry(input_frame, textvariable=self.var_source)
        source_entry.grid(row=0, column=1, sticky=tk.EW, padx=6, ipady=2)
        source_entry.bind("<KeyRelease>", lambda *_: self._update_run_button())

        ttk.Button(input_frame, text="Browse file…", command=self._browse_file)\
            .grid(row=0, column=2, padx=(4, 0))
        ttk.Button(input_frame, text="Paste URL", command=self._paste_clipboard)\
            .grid(row=0, column=3, padx=(4, 0))
        input_frame.columnconfigure(1, weight=1)

        hint = ttk.Label(
            input_frame,
            text="Example URLs:  https://kick.com/user/videos/UUID   •   "
                 "https://twitch.tv/videos/123   •   https://youtube.com/watch?v=ID",
            foreground="#666",
            font=("Segoe UI", 8),
        )
        hint.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))

        # --- Section: Output ---
        out_frame = ttk.LabelFrame(root, text="2. Output directory (where clips are saved)", padding=10)
        out_frame.pack(fill=tk.X, **pad)

        self.var_output = tk.StringVar(value=str(self._default_output))
        ttk.Label(out_frame, text="Save clips to:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(out_frame, textvariable=self.var_output)\
            .grid(row=0, column=1, sticky=tk.EW, padx=6, ipady=2)
        ttk.Button(out_frame, text="Browse…", command=self._browse_output)\
            .grid(row=0, column=2, padx=(4, 0))
        out_frame.columnconfigure(1, weight=1)

        open_btn = ttk.Button(out_frame, text="Open in Explorer", command=self._open_output)
        open_btn.grid(row=0, column=3, padx=(4, 0))

        # --- Section: Options ---
        opts = ttk.LabelFrame(root, text="3. Options", padding=10)
        opts.pack(fill=tk.X, **pad)

        ttk.Label(opts, text="Download quality:").grid(row=0, column=0, sticky=tk.W)
        self.var_quality = tk.StringVar(value="best")
        q_combo = ttk.Combobox(
            opts, textvariable=self.var_quality, state="readonly",
            values=[label for label, _ in QUALITY_OPTIONS], width=28,
        )
        q_combo.current(0)
        q_combo.grid(row=0, column=1, sticky=tk.W, padx=6)

        self.var_keep = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Keep downloaded VOD in temp/", variable=self.var_keep)\
            .grid(row=0, column=2, sticky=tk.W, padx=12)

        self.var_skip_tx = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, text="Skip Whisper transcription (faster, volume peaks only)",
            variable=self.var_skip_tx,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        self.var_skip_cut = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, text="Skip final FFmpeg cut (report only)",
            variable=self.var_skip_cut,
        ).grid(row=1, column=2, sticky=tk.W, pady=(8, 0), padx=12)

        # --- Section: Run button + progress ---
        action = ttk.Frame(root)
        action.pack(fill=tk.X, **pad)

        self.btn_run = ttk.Button(action, text="▶  Run pipeline", command=self._run_pressed)
        self.btn_run.pack(side=tk.LEFT)

        self.btn_stop = ttk.Button(action, text="Stop", command=self._stop_pressed, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(6, 0))

        self.progress = ttk.Progressbar(action, mode="indeterminate", length=240)
        self.progress.pack(side=tk.RIGHT, padx=6)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(action, textvariable=self.status_var, foreground="#444")\
            .pack(side=tk.RIGHT)

        # --- Section: Log widget ---
        log_frame = ttk.LabelFrame(root, text="4. Log output", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self.log_widget = tk.Text(
            log_frame, wrap=tk.WORD, height=14,
            font=("Consolas", 9), background="#fafafa",
        )
        self.log_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_widget.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_widget.configure(yscrollcommand=sb.set)
        self._append_log("Welcome to LiveCut! Paste a VOD URL (or pick a local file), "
                         "choose where clips should be saved, and click Run.\n")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a local video file",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.var_source.set(path)
            self._update_run_button()

    def _paste_clipboard(self) -> None:
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            messagebox.showinfo(APP_TITLE, "Clipboard is empty.")
            return
        if not text:
            return
        self.var_source.set(text)
        self._update_run_button()

    def _browse_output(self) -> None:
        initial = self.var_output.get() or str(Path.home())
        path = filedialog.askdirectory(
            title="Select output folder for generated clips",
            initialdir=initial if Path(initial).exists() else str(Path.home()),
        )
        if path:
            self.var_output.set(path)

    def _open_output(self) -> None:
        out = Path(self.var_output.get() or self._default_output)
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
            messagebox.showwarning(APP_TITLE, f"Could not open folder: {exc}")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _resolve_quality(self) -> str:
        label = self.var_quality.get()
        for lab, val in QUALITY_OPTIONS:
            if lab == label:
                return val
        return "best"

    def _update_run_button(self) -> None:
        ok = bool(self.var_source.get().strip())
        self.btn_run.configure(state=tk.NORMAL if ok else tk.DISABLED)

    def _run_pressed(self) -> None:
        source = self.var_source.get().strip()
        if not source:
            messagebox.showwarning(APP_TITLE, "Please enter a video source first.")
            return
        out_dir = self.var_output.get().strip() or str(self._default_output)

        # Validate URL / file early
        from livecut.vod_downloader import VodDownloader

        if not VodDownloader.is_url(source) and not Path(source).exists():
            messagebox.showerror(
                APP_TITLE,
                f"Input is not a valid URL and the local file was not found:\n{source}",
            )
            return

        Path(out_dir).mkdir(parents=True, exist_ok=True)

        quality = self._resolve_quality()
        opts = dict(
            config_path=str(self._default_config) if self._default_config.exists() else None,
            output_dir_override=out_dir,
            quality=quality,
            keep_downloaded=self.var_keep.get(),
            skip_cut=self.var_skip_cut.get(),
            skip_transcription=self.var_skip_tx.get(),
        )

        self._stop_requested.clear()
        self.btn_run.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.progress.start(10)
        self.status_var.set("Running…")
        self._append_log(f"\n{'='*72}\n"
                         f"▶ Starting pipeline\n"
                         f"   Source:  {source}\n"
                         f"   Output:  {out_dir}\n"
                         f"   Quality: {quality}    "
                         f"Skip-Whisper={opts['skip_transcription']}    "
                         f"Skip-Cut={opts['skip_cut']}\n"
                         f"{'='*72}\n")

        self._worker = threading.Thread(
            target=self._worker_target, args=(source, opts), daemon=True,
        )
        self._worker.start()

    def _stop_pressed(self) -> None:
        if self._worker and self._worker.is_alive():
            self._stop_requested.set()
            self._append_log("⏹ Stop requested. Waiting for current stage to "
                             "finish (clip download/encode may be cancelled).\n")
            self.status_var.set("Stopping…")

    def _worker_target(self, source: str, opts: dict) -> None:
        tag_progress = 1
        try:
            from livecut.pipeline import run_pipeline

            def _progress(msg: str, step: int = 0, total: int = 0) -> None:
                nonlocal tag_progress
                tag_progress = step
                self._msg_queue.put((0, msg))

            result = run_pipeline(source, on_progress=_progress, **opts)
            if result.ok:
                lines = ["\n✅ Pipeline finished successfully!\n"]
                if result.output_dir:
                    lines.append(f"   Output folder: {result.output_dir}")
                if result.report_path:
                    lines.append(f"   Ranking report: {result.report_path}")
                if result.metadata_path:
                    lines.append(f"   Metadata JSON:  {result.metadata_path}")
                if result.clips:
                    lines.append(f"   {len(result.clips)} clip(s) generated.\n")
                self._msg_queue.put((2, "\n".join(lines)))
                self._msg_queue.put((3, "open_output_folder"))
            else:
                self._msg_queue.put((1, f"\n❌ Pipeline failed:\n{result.error_message}\n"))

        except Exception as exc:
            tb = traceback.format_exc()
            self._msg_queue.put((1, f"\n❌ Unexpected exception in worker:\n{exc}\n{tb}\n"))
        finally:
            self._msg_queue.put((99, "STOP"))

    # ------------------------------------------------------------------
    # Log widget + queue drain (runs on Tk main thread)
    # ------------------------------------------------------------------
    def _append_log(self, text: str) -> None:
        tag = None
        if text.startswith("✅"):
            tag = "ok"
        elif text.startswith("❌"):
            tag = "err"
        elif text.startswith("⏹"):
            tag = "warn"
        self.log_widget.insert(tk.END, text + ("" if text.endswith("\n") else "\n"), tag)
        self.log_widget.see(tk.END)

    def _configure_log_tags(self) -> None:
        self.log_widget.tag_configure("ok", foreground="#0c7a2a")
        self.log_widget.tag_configure("err", foreground="#b22222")
        self.log_widget.tag_configure("warn", foreground="#b8860b")

    def _drain_queue(self) -> None:
        self._configure_log_tags()
        try:
            while True:
                kind, payload = self._msg_queue.get_nowait()
                if kind == 99 and payload == "STOP":
                    self.progress.stop()
                    self.btn_run.configure(state=tk.NORMAL)
                    self.btn_stop.configure(state=tk.DISABLED)
                    self.status_var.set("Idle")
                    self._update_run_button()
                    continue
                if kind == 3 and payload == "open_output_folder":
                    self._open_output()
                    continue
                self._append_log(payload)
        except queue.Empty:
            pass
        self.after(80, self._drain_queue)


def main() -> int:
    try:
        app = LiveCutGui()
        app.mainloop()
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
