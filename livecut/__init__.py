"""
LiveCut - Local automatic highlight clip generator for VODs.

Pipeline: Download -> Audio Extraction -> Whisper Transcription ->
Peak Volume Analysis -> Highlight Ranking -> FFmpeg Clipping.

Supported platforms (via URL):
    - Kick.com (native extractor, bypasses Cloudflare)
    - Twitch.tv (yt-dlp fallback)
    - YouTube (yt-dlp fallback)
    - Facebook, Rumble, and more (generic yt-dlp)

Also accepts local video files directly.
"""

from .config_loader import load_config
from .ffmpeg_utils import (
    get_ffmpeg_exe,
    get_ffprobe_exe,
    probe_video_info,
    check_ffmpeg_available,
)
from .audio_extractor import AudioExtractor
from .transcriber import WhisperTranscriber
from .volume_analyzer import VolumeAnalyzer
from .clip_selector import HighlightClipSelector
from .video_cutter import VideoCutter
from .vod_downloader import VodDownloader

__all__ = [
    "load_config",
    "get_ffmpeg_exe",
    "get_ffprobe_exe",
    "probe_video_info",
    "check_ffmpeg_available",
    "AudioExtractor",
    "WhisperTranscriber",
    "VolumeAnalyzer",
    "HighlightClipSelector",
    "VideoCutter",
    "VodDownloader",
]

__version__ = "1.1.1"
