# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for LiveCut (one-folder build).

Builds two executables that share one dependency bundle:

    dist/LiveCut/LiveCut.exe       windowed GUI (default entry point)
    dist/LiveCut/LiveCut-cli.exe   console CLI

FFmpeg and the Whisper model are NOT bundled: the installer/app downloads them
into ``components/`` at run time (see ``livecut/provisioning.py``).

Build with:  pyinstaller packaging/livecut.spec --noconfirm
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(SPECPATH).resolve().parent
CONFIG_FILE = ROOT / "config" / "config.json"
ICON = ROOT / "packaging" / "assets" / "livecut.ico"

ICON_PATH = str(ICON) if ICON.exists() else None

datas = [(str(CONFIG_FILE), "config"), (str(ROOT / "README.md"), ".")]
if ICON.exists():
    datas.append((str(ICON), "assets"))

# The modern web UI (HTML/CSS/JS) is bundled and loaded from _internal/web.
WEB_DIR = ROOT / "web"
if WEB_DIR.is_dir():
    for f in WEB_DIR.rglob("*"):
        if f.is_file():
            datas.append((str(f), str(f.parent.relative_to(ROOT))))

# faster-whisper loads silero_vad_v6.onnx from its own package directory at
# runtime (see faster_whisper.utils.get_assets_path). PyInstaller does not pick
# up package data files on its own, so they must be collected explicitly.
datas += collect_data_files("faster_whisper")

# pywebview ships WebView2 loader DLLs and platform backends as package data.
datas += collect_data_files("webview")

# rapidocr-onnxruntime bundles ONNX models used for screenshot OCR.
datas += collect_data_files("rapidocr_onnxruntime")

hiddenimports = [
    "run_gui",
    "run_cli",
    "huggingface_hub",
    "yt_dlp",
    "curl_cffi",
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "librosa",
    "soundfile",
    "numpy",
    "scipy",
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.mshtml",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "livecut.ocr",
    "livecut.user_settings",
]
hiddenimports += collect_submodules("ctranslate2")
hiddenimports += collect_submodules("webview")

binaries = []
for package in ("ctranslate2", "tokenizers", "soundfile"):
    binaries += collect_dynamic_libs(package)
# WebView2Loader.dll shipped by pywebview on Windows.
try:
    binaries += collect_dynamic_libs("webview")
except Exception:
    pass

excludes = ["matplotlib", "IPython", "PyQt5", "PySide2", "PySide6", "pytest"]

common = dict(
    pathex=[str(ROOT)],
    binaries=list(binaries),
    datas=list(datas),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

a_gui = Analysis([str(ROOT / "packaging" / "entry_gui.py")], **common)
a_cli = Analysis([str(ROOT / "packaging" / "entry_cli.py")], **common)

pyz_gui = PYZ(a_gui.pure)
pyz_cli = PYZ(a_cli.pure)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name="LiveCut",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_PATH,
)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="LiveCut-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=ICON_PATH,
)

coll = COLLECT(
    exe_gui,
    a_gui.binaries,
    a_gui.datas,
    exe_cli,
    a_cli.binaries,
    a_cli.datas,
    strip=False,
    upx=False,
    name="LiveCut",
)
