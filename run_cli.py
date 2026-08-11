"""
LiveCut — Command-line entry point.

Runs the highlight-generation pipeline from a terminal.

Usage examples
--------
# Local file
    python run_cli.py path/to/video.mp4

# Kick VOD URL (1080p stream-copy, fastest & highest quality)
    python run_cli.py https://kick.com/user/videos/UUID --quality best

# Twitch VOD URL with custom output folder
    python run_cli.py https://www.twitch.tv/videos/123456 --output-dir D:\\Clips

# YouTube (download only)
    python run_cli.py https://www.youtube.com/watch?v=ID --only-download
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="livecut",
        description=(
            "LiveCut: 100% local automatic highlight clip generator "
            "for Twitch / YouTube / Kick VODs and local video files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "video",
        help="Local video path OR VOD URL (Kick, Twitch, YouTube, Facebook, Rumble, ...)",
    )
    p.add_argument(
        "-c", "--config",
        default=None,
        help="Path to config.json (default: config/config.json relative to CWD)",
    )
    p.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Override output directory for clips/reports/metadata (overrides config)",
    )
    p.add_argument(
        "-q", "--quality",
        choices=["best", "720p", "480p", "worst"],
        default="best",
        help="VOD download quality (default 'best' = 1080p stream copy on Kick)",
    )
    p.add_argument(
        "-k", "--keep-downloaded", action="store_true",
        help="Keep downloaded VOD in temp/ after pipeline is finished",
    )
    p.add_argument(
        "--only-download", action="store_true",
        help="Stop after downloading the VOD (skip analysis/cut)",
    )
    p.add_argument(
        "--skip-cut", action="store_true",
        help="Run analysis and write the ranking report, but skip FFmpeg cutting",
    )
    p.add_argument(
        "--skip-transcription", action="store_true",
        help="Skip Whisper transcription; rank by volume peaks only (faster)",
    )
    p.add_argument(
        "--only-transcribe", action="store_true",
        help="Download audio, transcribe, save transcript, stop (skip peak detection/cut)",
    )
    p.add_argument(
        "--no-gui", action="store_true",
        help="Explicitly run CLI (this script; equivalent to omitting --gui)",
    )
    return p


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # Ensure project root is on sys.path so `import livecut` works even when
    # running from an arbitrary working directory.
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from livecut.pipeline import run_pipeline, PipelineResult

    result: PipelineResult = run_pipeline(
        args.video,
        config_path=args.config,
        output_dir_override=args.output_dir,
        quality=args.quality,
        keep_downloaded=args.keep_downloaded,
        only_download=args.only_download,
        skip_cut=args.skip_cut,
        skip_transcription=args.skip_transcription,
        only_transcribe=args.only_transcribe,
    )

    if not result.ok:
        print(f"\n❌ FAILED: {result.error_message}", file=sys.stderr)
        return 1

    print("\n🎉 Done!")
    if result.report_path:
        print(f"   Report:   {result.report_path}")
    if result.metadata_path:
        print(f"   Metadata: {result.metadata_path}")
    if result.output_dir:
        print(f"   Clips:    {result.output_dir}{os.sep}")
    print(f"   Platform: {result.platform}   Title: {result.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
