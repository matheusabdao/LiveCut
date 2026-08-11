import subprocess
import math
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from .ffmpeg_utils import get_ffmpeg_exe, get_ffprobe_exe, probe_video_info


class VideoCutter:
    def __init__(
        self,
        output_dir: str = "output",
        target_aspect_ratio: str = "16:9",
        fallback_aspect_ratio: str = "16:9",
        preset: str = "slow",
        crf: int = 18,
        audio_bitrate: str = "256k",
        video_codec: str = "libx264",
        audio_codec: str = "aac",
    ):
        self.output_dir = Path(output_dir)
        self.target_aspect_ratio = target_aspect_ratio
        self.fallback_aspect_ratio = fallback_aspect_ratio
        self.preset = preset
        self.crf = crf
        self.audio_bitrate = audio_bitrate
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.ffmpeg_exe = get_ffmpeg_exe()
        self.ffprobe_exe = get_ffprobe_exe()

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def probe_video(self, video_path: str) -> Dict[str, Any]:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        return probe_video_info(str(video_path), self.ffprobe_exe)

    def get_aspect_ratio(self, video_info: Dict[str, Any]) -> str:
        width = video_info.get("width", 0)
        height = video_info.get("height", 0)
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid video dimensions: width={width}, height={height}")
        g = math.gcd(width, height)
        if g == 0:
            g = 1
        return f"{width // g}:{height // g}"

    def _parse_aspect_ratio(self, s: str) -> Tuple[int, int]:
        if not s or ":" not in s:
            raise ValueError(f"Invalid aspect ratio format: '{s}'. Expected 'W:H' format.")
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid aspect ratio format: '{s}'. Expected 'W:H' format.")
        try:
            w = int(parts[0].strip())
            h = int(parts[1].strip())
        except ValueError as e:
            raise ValueError(f"Invalid aspect ratio values in '{s}': must be integers.") from e
        if w <= 0 or h <= 0:
            raise ValueError(f"Aspect ratio values must be positive: got {w}:{h}")
        return (w, h)

    def _build_crop_filter(
        self, src_w: int, src_h: int, target_ratio: Tuple[int, int]
    ) -> Optional[str]:
        if src_w <= 0 or src_h <= 0:
            raise ValueError(f"Invalid source dimensions: {src_w}x{src_h}")

        target_w, target_h = target_ratio
        if target_w <= 0 or target_h <= 0:
            raise ValueError(f"Invalid target ratio: {target_w}:{target_h}")

        src_ratio = src_w / src_h
        target_ratio_val = target_w / target_h

        tolerance = 0.01
        if abs(src_ratio - target_ratio_val) < tolerance:
            return None

        if src_ratio > target_ratio_val:
            new_h = src_h
            new_w = int(src_h * target_w / target_h)
            new_w = new_w - (new_w % 2)
            x_offset = (src_w - new_w) // 2
            x_offset = x_offset - (x_offset % 2)
        else:
            new_w = src_w
            new_h = int(src_w * target_h / target_w)
            new_h = new_h - (new_h % 2)
            y_offset = (src_h - new_h) // 2
            y_offset = y_offset - (y_offset % 2)
            x_offset = 0

        if src_ratio > target_ratio_val:
            return f"crop={new_w}:{new_h}:{x_offset}:0"
        else:
            return f"crop={new_w}:{new_h}:0:{y_offset}"

    def _build_fallback_crop_if_needed(
        self,
        src_w: int,
        src_h: int,
        target_rat: Tuple[int, int],
        fallback_rat: Tuple[int, int],
    ) -> Tuple[Optional[str], str]:
        target_filter = self._build_crop_filter(src_w, src_h, target_rat)

        if target_filter is not None:
            return (target_filter, f"{target_rat[0]}:{target_rat[1]}")

        fallback_filter = self._build_crop_filter(src_w, src_h, fallback_rat)
        if fallback_filter is not None:
            return (fallback_filter, f"{fallback_rat[0]}:{fallback_rat[1]}")

        return (None, f"{target_rat[0]}:{target_rat[1]}")

    def cut_clip(
        self,
        video_path: str,
        start: float,
        end: float,
        clip_name: str,
        rank: Optional[int] = None,
        video_info: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if start < 0:
            raise ValueError(f"Start time cannot be negative: {start}")
        if end <= start:
            raise ValueError(f"End time must be greater than start time: start={start}, end={end}")

        duration = end - start

        if video_info is None:
            video_info = self.probe_video(str(video_path))

        src_w = video_info.get("width", 0)
        src_h = video_info.get("height", 0)

        target_rat = self._parse_aspect_ratio(self.target_aspect_ratio)
        fallback_rat = self._parse_aspect_ratio(self.fallback_aspect_ratio)

        filter_str, aspect_ratio_used = self._build_fallback_crop_if_needed(
            src_w, src_h, target_rat, fallback_rat
        )

        if rank is not None:
            output_filename = f"{rank:02d}_{clip_name}.mp4"
        else:
            output_filename = f"{clip_name}.mp4"

        output_path = self.output_dir / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        initial_seek = max(0.0, start - 2.0)
        refine_seek = min(2.0, start)

        command = [
            self.ffmpeg_exe,
            "-y",
            "-ss", f"{initial_seek:.6f}",
            "-i", str(video_path),
            "-ss", f"{refine_seek:.6f}",
            "-t", f"{duration:.6f}",
        ]

        if filter_str is not None:
            command.extend(["-filter_complex", filter_str])

        command.extend([
            "-c:v", self.video_codec,
            "-preset", self.preset,
            "-crf", str(self.crf),
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-c:a", self.audio_codec,
            "-b:a", self.audio_bitrate,
            "-ar", "48000",
            "-movflags", "+faststart",
            str(output_path),
        ])

        try:
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to cut clip '{clip_name}' from {start:.2f}s to {end:.2f}s: {e.stderr}"
            ) from e

        clip_info = {
            "clip_name": clip_name,
            "output_path": str(output_path.resolve()),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "rank": rank,
            "aspect_ratio_used": aspect_ratio_used,
            "crop_filter_applied": filter_str is not None,
            "crop_filter": filter_str,
            "source_dimensions": {"width": src_w, "height": src_h},
        }

        return (str(output_path.resolve()), clip_info)

    def cut_clips(
        self,
        video_path: str,
        candidates_list: List[Dict[str, Any]],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not candidates_list:
            return []

        video_info = self.probe_video(str(video_path))

        results = []
        for i, candidate in enumerate(candidates_list, 1):
            start = candidate.get("start")
            end = candidate.get("end")
            clip_name = candidate.get("clip_name") or candidate.get("name") or f"clip_{i:02d}"
            rank = candidate.get("rank") or i

            if start is None or end is None:
                raise ValueError(
                    f"Candidate at index {i - 1} is missing 'start' or 'end' time fields."
                )

            output_path, clip_info = self.cut_clip(
                video_path=str(video_path),
                start=float(start),
                end=float(end),
                clip_name=clip_name,
                rank=rank,
                video_info=video_info,
            )
            results.append((output_path, clip_info))

        return results
