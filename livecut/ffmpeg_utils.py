import os
import shutil
import json
import subprocess
from pathlib import Path
from typing import Tuple, Optional


_PROJECT_ROOT = Path(__file__).parent.parent.resolve()

_FFMPEG_SEARCH_DIRS = [
    _PROJECT_ROOT,
]

_FFMPEG_DIR_PATTERNS = [
    "ffmpeg-*essentials_build/bin",
    "ffmpeg-*full_build/bin",
    "ffmpeg/bin",
    "bin",
]


def _find_ffmpeg_directory() -> Optional[Path]:
    for base_dir in _FFMPEG_SEARCH_DIRS:
        if not base_dir.exists():
            continue
        for pattern in _FFMPEG_DIR_PATTERNS:
            matches = list(base_dir.glob(pattern))
            for match in matches:
                if (match / "ffmpeg.exe").exists() and (match / "ffprobe.exe").exists():
                    return match.resolve()
    return None


_FFMPEG_DIR = _find_ffmpeg_directory()


def _get_ffmpeg_paths() -> Tuple[str, str, Optional[str]]:
    if _FFMPEG_DIR is not None:
        ffmpeg = str(_FFMPEG_DIR / "ffmpeg.exe")
        ffprobe = str(_FFMPEG_DIR / "ffprobe.exe")
        ffplay = str(_FFMPEG_DIR / "ffplay.exe")
        return ffmpeg, ffprobe, ffplay

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    ffplay = shutil.which("ffplay")

    if ffmpeg is None or ffprobe is None:
        raise RuntimeError(
            "FFmpeg not found!\n"
            "Place the FFmpeg folder in the project root, or install it and add it to the system PATH.\n"
            "Expected directory structure example:\n"
            "  Live Cut/\n"
            "    └── ffmpeg-2026-08-09-git-...-essentials_build/\n"
            "        └── bin/\n"
            "            ├── ffmpeg.exe\n"
            "            └── ffprobe.exe"
        )

    return ffmpeg, ffprobe, ffplay


def get_ffmpeg_exe() -> str:
    return _get_ffmpeg_paths()[0]


def get_ffprobe_exe() -> str:
    return _get_ffmpeg_paths()[1]


def ensure_ffmpeg_in_path() -> None:
    if _FFMPEG_DIR is not None:
        current_path = os.environ.get("PATH", "")
        ffmpeg_bin = str(_FFMPEG_DIR)
        if ffmpeg_bin not in current_path:
            os.environ["PATH"] = ffmpeg_bin + os.pathsep + current_path


def check_ffmpeg_available() -> bool:
    try:
        ffmpeg, ffprobe, _ = _get_ffmpeg_paths()
        return Path(ffmpeg).exists() and Path(ffprobe).exists()
    except RuntimeError:
        return False


def probe_video_info(video_path: str, ffprobe_exe: str) -> dict:
    command = [
        ffprobe_exe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration,codec_name",
        "-of", "json",
        video_path
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        stream = info["streams"][0]

        width = int(stream["width"])
        height = int(stream["height"])
        duration = float(stream.get("duration", 0))
        codec_name = stream.get("codec_name", "unknown")

        ratio_parts = stream["r_frame_rate"].split("/")
        if len(ratio_parts) == 2 and int(ratio_parts[1]) != 0:
            fps = float(ratio_parts[0]) / float(ratio_parts[1])
        else:
            fps = 30.0

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "codec_name": codec_name,
            "aspect_ratio": f"{width}:{height}"
        }
    except Exception as e:
        raise RuntimeError(
            f"Failed to probe video information for '{video_path}': {str(e)}"
        ) from e
